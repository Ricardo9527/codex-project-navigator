"""On-demand, project-scoped search of cards, files and human-facing chat text."""
import json
from pathlib import Path
import shutil
from platform_io import reveal
import subprocess
import threading
import zipfile
import xml.etree.ElementTree as ET
import time
from content_pages import resource_path, preview_resource
import project_records as records

TEXT={'.md','.txt','.srt','.csv','.tsv','.json','.xml','.fcpxml','.yaml','.yml','.py','.js','.mjs','.ts','.tsx','.jsx','.html','.css','.glsl','.toml'}
SKIP={'.DS_Store','.git','.project-library','.codex','.agents','node_modules','.venv','secrets','__pycache__'}


def files(project):
    root=Path(project['path'])
    if not records.git(project,'rev-parse','--show-toplevel',check=False).returncode:
        names=records.project_files(project)
    else:
        rg=shutil.which('rg') or '/Applications/ChatGPT.app/Contents/Resources/codex-cli/codex-path/rg'
        result=subprocess.run([rg,'--files','--hidden','--no-require-git','-0',*sum((['-g','!'+n+'/**'] for n in SKIP),[])],cwd=root,capture_output=True)
        if result.returncode not in (0,1):raise ValueError(result.stderr.decode())
        names=result.stdout.decode().split('\0')
    return [root/n for n in names if n and not any(part in SKIP for part in Path(n).parts) and not Path(n).name.startswith('.env') and Path(n).suffix not in {'.key','.pem'} and not (root/n).is_symlink()]


def document_text(path):
    suffix=path.suffix.lower()
    if suffix in TEXT:return path.read_text(encoding='utf-8',errors='replace')
    if suffix in {'.docx','.xlsx'}:
        with zipfile.ZipFile(path) as archive:
            names=[n for n in archive.namelist() if n.endswith('.xml') and (n.startswith('word/') if suffix=='.docx' else n=='xl/sharedStrings.xml' or n.startswith('xl/worksheets/'))]
            return '\n'.join(' '.join(e.text for e in ET.fromstring(archive.read(name)).iter() if e.text and e.tag.rsplit('}',1)[-1] in {'t','v'}) for name in names)
    if suffix=='.pdf':
        script='ObjC.import("PDFKit"); function run(argv) { const doc=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0])); if(!doc) throw Error("无法读取 PDF"); return ObjC.unwrap(doc.string)||""; }'
        result=subprocess.run(['osascript','-l','JavaScript','-e',script,str(path)],capture_output=True,text=True)
        if result.returncode:raise ValueError(result.stderr.strip())
        if not result.stdout.strip():raise ValueError('PDF 没有可提取的文字，当前仅按文件名查找。')
        return result.stdout
    return ''


def initialize(hub):
    if not hasattr(hub,'search_jobs'):hub.search_jobs={}
    with hub.local() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS content_search (
            project_id TEXT, kind TEXT, identity TEXT, title TEXT, path TEXT,
            body TEXT, searchable TEXT, stamp TEXT, card_ids TEXT,
            PRIMARY KEY(project_id,kind,identity))''')


def refresh(hub, project):
    pid=project['id'];job=hub.search_jobs[pid]
    try:
        record_path=records.record_path(project)
        record=json.loads(record_path.read_text()) if record_path.exists() else {'cards':[]}
        linked_files={};linked_threads={}
        for card in record['cards']:
            for r in card['resources']:
                path=resource_path(project,r,record)
                linked_files.setdefault(str(path),[]).append((card['id'],r['label']))
            for t in card['sources']:linked_threads.setdefault(t['id'],[]).append(card['id'])
        paths={str(p.resolve()):p for p in files(project) if p.is_file()}
        for name in linked_files:paths[name]=Path(name)
        entries=[]
        for name,path in paths.items():
            title=' · '.join(dict.fromkeys(label for _,label in linked_files.get(name,[]))) or path.name
            entries.append(('file',name,title,path,[c for c,_ in linked_files.get(name,[])]))
        with hub.codex() as db:
            rows=db.execute("SELECT id,COALESCE(NULLIF(name,''),title) AS title,cwd,project_id,rollout_path FROM threads WHERE agent_role IS NULL AND agent_path IS NULL AND COALESCE(thread_source,'') NOT IN ('subagent','guardian_review')").fetchall()
        business_ids={t['id'] for t in hub.maintenance_threads(pid,rows)}
        for row in rows:
            if row['id'] in business_ids:
                entries.append(('thread',row['id'],row['title'],Path(row['rollout_path']),linked_threads.get(row['id'],[])))
        job.update(total=len(entries),done=0,errors=[])
        live=set()
        for kind,key,title,path,cards in entries:
            live.add((kind,key))
            with hub.local() as db:
                old=db.execute('SELECT stamp,body FROM content_search WHERE project_id=? AND kind=? AND identity=?',(pid,kind,key)).fetchone()
            try:
                stat=path.stat();stamp=json.dumps([stat.st_size,stat.st_mtime_ns])
                if old and old['stamp']==stamp:body=old['body']
                elif kind=='thread':
                    with hub.local() as db:cached=db.execute('SELECT size,mtime_ns,body FROM indexed_threads WHERE id=?',(key,)).fetchone()
                    body=cached['body'] if cached and [cached['size'],cached['mtime_ns']]==[stat.st_size,stat.st_mtime_ns] else hub.messages(path)
                elif path.is_file():body=document_text(path)
                else:body=''
            except (OSError,ValueError,zipfile.BadZipFile,ET.ParseError) as e:
                job['errors'].append({'title':title,'error':str(e)});body='';stamp=None
            with hub.local() as db:
                db.execute('INSERT OR REPLACE INTO content_search VALUES (?,?,?,?,?,?,?,?,?)',
                           (pid,kind,key,title,str(path),body,(title+'\n'+(key if kind=='file' else '')+'\n'+body).casefold(),stamp,json.dumps(cards)))
            job['done']+=1
        with hub.local() as db:
            for row in db.execute('SELECT kind,identity FROM content_search WHERE project_id=?',(pid,)).fetchall():
                if (row['kind'],row['identity']) not in live:db.execute('DELETE FROM content_search WHERE project_id=? AND kind=? AND identity=?',(pid,*row))
    except Exception as e:
        job['errors'].append({'title':project['name'],'error':str(e)})
    finally:job.update(running=False,finishedAt=time.time())


def search(hub, project, args):
    initialize(hub);pid=project['id'];query=args.get('query','').strip().casefold()
    if not query:return {'hits':[],'cardIds':[],'total':0,'indexing':False,'errors':[]}
    with hub.lock:
        job=hub.search_jobs.get(pid)
        if not job or args.get('refresh',True) and not job['running']:
            hub.search_jobs[pid]={'running':True,'done':0,'total':0,'errors':[]}
            threading.Thread(target=refresh,args=(hub,project),daemon=True).start()
    job=hub.search_jobs[pid]
    offset=int(args.get('offset',0))
    if offset<0:raise ValueError('无效的搜索位置。')
    with hub.local() as db:
        total=db.execute('SELECT count(*) FROM content_search WHERE project_id=? AND instr(searchable,?)>0',(pid,query)).fetchone()[0]
        rows=db.execute("SELECT kind,identity,title,path,substr(body,max(1,instr(lower(body),?)-60),180) AS snippet,card_ids FROM content_search WHERE project_id=? AND instr(searchable,?)>0 ORDER BY CASE WHEN card_ids!='[]' THEN 0 WHEN kind='thread' THEN 1 ELSE 2 END,kind,title LIMIT 50 OFFSET ?", (query,pid,query,offset)).fetchall()
        card_ids=set()
        for row in db.execute('SELECT card_ids FROM content_search WHERE project_id=? AND instr(searchable,?)>0',(pid,query)):card_ids.update(json.loads(row[0]))
    return {'hits':[dict(row,cardIds=json.loads(row['card_ids'])) for row in rows], 'cardIds':sorted(card_ids),
            'total':total,'offset':offset,'indexing':job['running'],'progress':{'done':job['done'],'total':job['total']},'errors':job['errors']}


def open_result(hub, project, args):
    initialize(hub)
    with hub.local() as db:row=db.execute('SELECT * FROM content_search WHERE project_id=? AND kind=? AND identity=?',(project['id'],args['kind'],args['identity'])).fetchone()
    if not row:raise ValueError('搜索结果已失效，请重新搜索。')
    if row['kind']=='thread':return hub.open_thread({'threadId':row['identity']})
    path=Path(row['path'])
    record_path=records.record_path(project)
    record=json.loads(record_path.read_text()) if record_path.exists() else {'cards':[]}
    registered={resource_path(project,r,record) for c in record['cards'] for r in c['resources']}
    if path not in registered and path not in {p.resolve() for p in files(project)}:
        raise ValueError('文件不再属于可搜索的项目范围。')
    if not path.exists():raise ValueError('源文件已移动或删除，记录仍保留。')
    if args.get('reveal'):
        reveal(path);return {'opened':True}
    return preview_resource(path)
