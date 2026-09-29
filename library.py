"""Incremental, local-only catalog of saved project results and user conversations."""
import json
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import subprocess
import base64
from datetime import datetime
from urllib.parse import unquote

from catalog import Hub, KINDS, STATES
from content_pages import read_page, resource_action
import project_records as records
import project_search
import project_resources
import conversation_assets
import delivery_audit
import maintenance
import automation_setup

SKIP = {'.git', '.codex', '.agents', '.venv', 'venv', 'node_modules', '__pycache__',
        'dist', 'build', 'target', 'vendor', 'third_party', '.cache', 'cache', 'logs',
        'data', '.data', 'secrets', 'models', 'checkpoints', 'weights'}
RESULT_DIRS = {'docs', 'doc', 'output', 'outputs', 'assets', 'references', 'prompts',
               'design', 'scripts', 'storyboards', 'documents', 'scenes', 'characters', 'shots', '素材', '文档', '剧本',
               '分镜', '场景设计', '角色设计', '提示词', '成果'}
TEXT = {'.md', '.txt'}
IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
MEDIA = {'.mp4', '.mov', '.mp3', '.wav', '.pdf', '.docx', '.pptx', '.glb', '.blend'}
TOPICS = {
    '3D 控制': ('摄像机', '相机', 'wasd', '运镜', '镜头控制', 'camera', '3d 控制', '3d功能', '3d 功能'),
    '场景与空间': ('场景', 'blockout', '建模', '展厅', '空间布局', 'environment', 'glb'),
    '角色与道具': ('角色', '人设', '道具', '物品栏', '拍立得'),
    '剧本与叙事': ('剧本', '小说', '故事', '大纲', '台词'),
    '分镜与视频': ('分镜', '预告片', '视频', 'seedance', '镜头'),
    '提示词': ('提示词', 'prompt'),
    '交互与界面': ('交互', '界面', ' ui', 'ui ', '按钮', '面板', '控制台'),
    '修复与验证': ('修复', 'bug', '故障', '诊断', '测试', '校验'),
    '项目记录': ('readme', 'handoff', '交接', '进度', '调研', '设计说明'),
    '天文台': ('天文台', 'observatory'),
    '博物馆': ('博物馆', 'museum'),
}


def topics(text):
    value = text.casefold()
    return [name for name, words in TOPICS.items() if any(word in value for word in words)]


def kind_for(path):
    value = str(path).casefold()
    if path.suffix.lower() in IMAGES:
        return 'image'
    if '提示词' in value or 'prompt' in value:
        return 'prompt'
    if '分镜' in value or 'storyboard' in value:
        return 'storyboard'
    if any(w in value for w in ['剧本', '小说', 'screenplay']):
        return 'script'
    if any(w in value for w in ['camera', '摄像机', '控制', '功能', 'handoff']):
        return 'feature'
    return 'document'


class Library(Hub):
    def __init__(self, codex_db=None, data_dir=None):
        super().__init__(codex_db, data_dir)
        self.scan_lock = threading.Lock()
        self.progress = {'running': False, 'stage': '', 'lastCompleted': None, 'errors': []}
        with self.local() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS indexed_threads (
                id TEXT PRIMARY KEY, project_id TEXT, title TEXT, preview TEXT, body TEXT,
                updated_at INTEGER, archived INTEGER, git_branch TEXT, rollout_path TEXT,
                size INTEGER DEFAULT 0, mtime_ns INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS artifact_sources (
                artifact_id INTEGER NOT NULL, thread_id TEXT NOT NULL,
                PRIMARY KEY(artifact_id,thread_id));
            CREATE TABLE IF NOT EXISTS indexed_files (
                path TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, body TEXT);
            CREATE TABLE IF NOT EXISTS manual_tags (entity TEXT, id TEXT, PRIMARY KEY(entity,id));
            CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS thread_links (thread_id TEXT, path TEXT, PRIMARY KEY(thread_id,path));
            CREATE TABLE IF NOT EXISTS accepted_files (artifact_id INTEGER PRIMARY KEY, size INTEGER, mtime_ns INTEGER);
            CREATE INDEX IF NOT EXISTS thread_links_path ON thread_links(path);
            CREATE INDEX IF NOT EXISTS indexed_threads_project ON indexed_threads(project_id);
            ''')
            version = db.execute("SELECT value FROM index_meta WHERE key='parserVersion'").fetchone()
            if not version or version[0] != '3':
                db.execute('UPDATE indexed_threads SET size=-1')
                db.execute("INSERT OR REPLACE INTO index_meta VALUES ('parserVersion','3')")
            previous = db.execute("SELECT value FROM index_meta WHERE key='lastCompleted'").fetchone()
            if previous:
                self.progress['lastCompleted'] = int(previous[0])

    def refresh_projects(self):
        with self.codex() as db:
            rows = db.execute('SELECT p.id,p.name,r.path FROM projects p JOIN project_roots r ON p.id=r.project_id WHERE r.position=0 ORDER BY p.position').fetchall()
        by_path = {os.path.realpath(p['path']): p for p in self.registry}
        aliases = {}
        registry = []
        for r in rows:
            root = os.path.realpath(r['path'])
            p = {**by_path.get(root, {'id': r['id']}), 'name': r['name'], 'path': root}
            registry.append(p)
            aliases[r['id']] = p['id']
        self.registry = registry
        self.aliases = aliases
        self.roots = sorted([(p['path'], p['id']) for p in registry], key=lambda p: len(p[0]), reverse=True)

    def tags(self, db, project_id, names):
        ids = []
        for name in dict.fromkeys(names):
            db.execute('INSERT OR IGNORE INTO categories(project_id,name) VALUES (?,?)', (project_id, name))
            ids.append(db.execute('SELECT id FROM categories WHERE project_id=? AND name=?', (project_id, name)).fetchone()[0])
        return ids

    def auto_tags(self, db, entity, identity, project_id, names):
        if db.execute('SELECT 1 FROM manual_tags WHERE entity=? AND id=?', (entity, str(identity))).fetchone():
            return
        table, column = ('thread_categories', 'thread_id') if entity == 'thread' else ('artifact_categories', 'artifact_id')
        db.execute(f'DELETE FROM {table} WHERE {column}=?', (identity,))
        db.executemany(f'INSERT OR IGNORE INTO {table} VALUES (?,?)', [(identity, c) for c in self.tags(db, project_id, names)])

    def messages(self, path, *, since=0, until=None, labelled=False):
        """Read human-facing messages, excluding instructions, tools and reasoning."""
        pieces = []
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                # A running Codex may be in the middle of writing its last JSONL line.
                if not line.endswith('\n'):
                    break
                event = json.loads(line)
                p = event.get('payload', {})
                if event.get('type') != 'response_item' or p.get('type') != 'message' or p.get('role') not in {'user', 'assistant'}:
                    continue
                if p.get('role') == 'assistant' and p.get('phase') not in (None, 'final', 'final_answer'):
                    continue
                value = '\n'.join(c.get('text', '') for c in p.get('content', []) if c.get('type') in {'input_text', 'output_text', 'text'})
                if value.startswith(('# AGENTS.md instructions', '<environment_context>', '<permissions instructions>')):
                    continue
                if event.get('timestamp'):
                    timestamp=datetime.fromisoformat(event['timestamp'].replace('Z','+00:00')).timestamp()
                    if timestamp < since or (until is not None and timestamp >= until+1):continue
                if labelled:value=f'[{p["role"]}]\n{value}'
                pieces.append(value)
        return '\n\n'.join(pieces)

    def review_thread(self, project, args):
        if args.get('batchId'):
            batch=records.read_batch(self.data_dir,args['batchId'])
            if batch['projectId']!=project['id']:raise ValueError('清单不属于当前项目。')
            item=next((t for t in batch['pendingThreads'] if t['id']==args['threadId']),None)
            if item is None:raise ValueError('对话不在本次待整理清单内。')
        else:
            item=self.thread(args['threadId'])
            if self.owner(item['cwd'],item['project_id'])!=project['id']:raise ValueError('对话不属于当前项目。')
            record=json.loads(records.record_path(project).read_text())
            item={**item,'reviewedUntil':record.get('reviewedThreads',{}).get(item['id'],0)}
            if args.get('until') is not None:
                if type(args['until']) is not int or not item['reviewedUntil']<=args['until']<=item['updated_at']:
                    raise ValueError('聊天整理边界无效。')
                item['updated_at']=args['until']
        with self.codex() as db:
            thread=db.execute('SELECT rollout_path FROM threads WHERE id=?',(item['id'],)).fetchone()
        if thread is None:raise ValueError('该对话已不存在。')
        text=self.messages(Path(thread['rollout_path']),since=item['reviewedUntil'],until=item['updated_at'],labelled=True)
        offset=args.get('offset',0)
        if type(offset) is not int or not 0<=offset<=len(text):raise ValueError('正文读取位置无效。')
        end=min(offset+12000,len(text))
        result={'threadId':item['id'],'title':item['title'],'reviewedUntil':item['reviewedUntil'],
                'updated_at':item['updated_at'],'text':text[offset:end],'offset':offset,
                'nextOffset':end if end<len(text) else None,'totalChars':len(text)}
        if args.get('batchId'):
            assets=conversation_assets.thread_assets(self,item['id'])
            result.update(assets=assets[:30] if offset==0 else [],assetCount=len(assets),assetsNextOffset=30 if len(assets)>30 else None)
        return result

    def scan_threads(self, errors):
        with self.codex() as source:
            rows = source.execute('''SELECT id,COALESCE(NULLIF(name,''),title) AS title,preview,cwd,project_id,
                updated_at,archived,git_branch,rollout_path FROM threads WHERE agent_role IS NULL
                AND agent_path IS NULL AND COALESCE(thread_source,'') NOT IN ('subagent','guardian_review')''').fetchall()
        live = set()
        for t in rows:
            owner = self.owner(t['cwd'], t['project_id'])
            if not owner:
                continue
            live.add(t['id'])
            with self.local() as db:
                old = db.execute('SELECT * FROM indexed_threads WHERE id=?', (t['id'],)).fetchone()
            path = Path(t['rollout_path'])
            body = old['body'] if old else ''
            size = mtime = 0
            try:
                if path.is_file():
                    stat = path.stat(); size, mtime = stat.st_size, stat.st_mtime_ns
                    if not old or (old['size'], old['mtime_ns']) != (size, mtime):
                        body = self.messages(path)
                else:
                    errors.append(f"对话正文暂不可读：{t['title'][:60]}")
            except (OSError, ValueError) as error:
                errors.append(f"读取对话 {t['title'][:60]}：{error}")
                # Retry on the next scan rather than recording a successful fingerprint.
                size = mtime = 0
            with self.local() as db:
                changed = not old or (old['size'], old['mtime_ns'], old['title'], old['project_id']) != (size, mtime, t['title'], owner)
                if not changed and old['updated_at'] == t['updated_at'] and old['archived'] == t['archived']:
                    continue
                db.execute('INSERT OR REPLACE INTO indexed_threads VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           (t['id'], owner, t['title'], t['preview'], body, t['updated_at'], t['archived'], t['git_branch'], str(path), size, mtime))
                self.auto_tags(db, 'thread', t['id'], owner, topics(t['title'] + ' ' + t['preview']))
                db.execute('DELETE FROM thread_links WHERE thread_id=?', (t['id'],))
                references = re.findall(r'\]\(<?(/[^\n>]+?)>?\)|`(/[^`\n]+)`', body)
                for pair in references:
                    target = unquote(next(value for value in pair if value))
                    target = re.sub(r':\d+(?::\d+)?$', '', target)
                    db.execute('INSERT OR IGNORE INTO thread_links VALUES (?,?)', (t['id'], str(Path(target).resolve())))
        with self.local() as db:
            for row in db.execute('SELECT id FROM indexed_threads').fetchall():
                if row[0] not in live:
                    db.execute('DELETE FROM indexed_threads WHERE id=?', (row[0],))

    def result_files(self, project, errors):
        root = Path(project['path'])
        if not root.is_dir():
            errors.append(f"项目目录暂不可读：{project['name']}")
            return
        def onerror(error):
            errors.append(str(error))
        for directory, dirs, files in os.walk(root, onerror=onerror, followlinks=False):
            here = Path(directory)
            rel = here.relative_to(root)
            dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('.')
                       and not (here/d).is_symlink() and self.owner(str(here/d)) == project['id']]
            # Source trees and dependencies do not belong in a results browser.
            if len(rel.parts) >= 8:
                dirs[:] = []
            for name in files:
                path = here/name
                if name.startswith('.') or path.is_symlink():
                    continue
                suffix = path.suffix.lower()
                if suffix not in TEXT | IMAGES | MEDIA:
                    continue
                if suffix in TEXT and (not rel.parts or any(p.casefold() in RESULT_DIRS for p in rel.parts) or any('\u4e00' <= c <= '\u9fff' for c in str(rel))):
                    yield path
                elif suffix in IMAGES | MEDIA and (not rel.parts or any(p.casefold() in RESULT_DIRS for p in rel.parts) or any('\u4e00' <= c <= '\u9fff' for c in str(rel))):
                    yield path

    def scan_files(self, errors):
        for project in self.registry:
            self.progress['stage'] = '整理 ' + project['name']
            for path in self.result_files(project, errors):
                try:
                    stat = path.stat()
                    with self.local() as db:
                        indexed = db.execute('SELECT size,mtime_ns FROM indexed_files WHERE path=?', (str(path),)).fetchone()
                        changed = not indexed or tuple(indexed) != (stat.st_size, stat.st_mtime_ns)
                        body = ''
                        if changed:
                            body = ''
                            if path.suffix.lower() in TEXT:
                                with path.open(encoding='utf-8', errors='replace') as f:
                                    body = f.read(200_000)
                            db.execute('INSERT OR REPLACE INTO indexed_files VALUES (?,?,?,?)', (str(path), stat.st_size, stat.st_mtime_ns, body))
                        relative = str(path.relative_to(project['path']))
                        title = path.stem.replace('_', ' ')
                        heading = re.search(r'^#\s+(.+)$', body, re.M)
                        if heading:
                            title = heading[1].strip()
                        db.execute('''INSERT OR IGNORE INTO artifacts(project_id,title,path,kind,status,note,updated_at)
                            VALUES (?,?,?,?,?,?,?)''', (project['id'], title[:200], str(path), kind_for(path), 'review', '', int(stat.st_mtime)))
                        artifact = db.execute('SELECT id FROM artifacts WHERE project_id=? AND path=?', (project['id'], str(path))).fetchone()[0]
                        accepted = db.execute('SELECT size,mtime_ns FROM accepted_files WHERE artifact_id=?', (artifact,)).fetchone()
                        if accepted and tuple(accepted) != (stat.st_size, stat.st_mtime_ns):
                            db.execute("UPDATE artifacts SET status='review' WHERE id=? AND status='accepted'", (artifact,))
                        if changed:
                            self.auto_tags(db, 'artifact', artifact, project['id'], topics(relative+' '+title))
                        # Exact absolute links establish evidence; filename similarity does not.
                        db.execute('''INSERT OR IGNORE INTO artifact_sources SELECT ?,l.thread_id FROM thread_links l
                            JOIN indexed_threads t ON t.id=l.thread_id WHERE l.path=? AND t.project_id=?''', (artifact, str(path), project['id']))
                except (OSError, sqlite3.Error) as error:
                    errors.append(f'{path.name}: {error}')

    def scan(self):
        if not self.scan_lock.acquire(blocking=False):
            return self.status({})
        self.progress.update(running=True, stage='读取项目与对话', errors=[])
        errors = []
        try:
            self.refresh_projects()
            self.scan_threads(errors)
            self.scan_files(errors)
            completed = int(time.time())
            with self.local() as db:
                db.execute("INSERT OR REPLACE INTO index_meta VALUES ('lastCompleted',?)", (str(completed),))
            self.progress['lastCompleted'] = completed
        except Exception as error:
            errors.append(str(error))
            import traceback
            traceback.print_exc()
        finally:
            self.progress.update(running=False, stage='', errors=errors)
            self.scan_lock.release()
        return self.status({})

    def status(self, args):
        with self.local() as db:
            counts = {key: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                      for key, table in [('threads', 'indexed_threads'), ('artifacts', 'artifacts')]}
        return {**self.progress, **counts}

    def overview(self, args):
        self.refresh_projects()
        result = super().overview(args)
        result.update(status=self.status({}), searchScope='已保存的对话正文、成果名称与文档内容')
        return result

    def detail(self, args):
        project_id = self.aliases.get(args['projectId'], args['projectId'])
        project = self.project(project_id)
        query = args.get('query', '').strip().casefold()
        category = args.get('categoryId')
        kind = args.get('kind')
        status = args.get('status')
        with self.local() as db:
            categories = [dict(r) for r in db.execute('SELECT * FROM categories WHERE project_id=? ORDER BY name', (project_id,))]
            artifacts = []
            for r in db.execute('''SELECT a.*,COALESCE(f.body,'') AS body FROM artifacts a
                LEFT JOIN indexed_files f ON a.path=f.path WHERE a.project_id=?
                ORDER BY CASE a.status WHEN 'accepted' THEN 0 WHEN 'superseded' THEN 2 ELSE 1 END,a.updated_at DESC''', (project_id,)):
                a = dict(r); body = a.pop('body')
                heading = re.search(r'^#\s+(.+)$', body, re.M)
                if heading and a['title'] == Path(a['path']).stem.replace('_', ' '):
                    a['title'] = heading[1].strip()[:200]
                a['categoryIds'] = self.category_ids(db, 'artifact_categories', 'artifact_id', a['id'])
                if category is not None and category not in a['categoryIds'] or kind and a['kind'] != kind or status and a['status'] != status:
                    continue
                if query and query not in (a['title']+' '+a['note']+' '+a['path']+' '+body).casefold():
                    continue
                a['exists'] = Path(a['path']).is_file()
                a['relativePath'] = os.path.relpath(a['path'], project['path'])
                a['sources'] = [dict(r) for r in db.execute('''SELECT t.id,t.title FROM indexed_threads t WHERE t.id IN
                    (SELECT thread_id FROM artifact_sources WHERE artifact_id=?) OR t.id=?''', (a['id'], a['source_thread_id']))]
                artifacts.append(a)
            threads = []
            for r in db.execute('SELECT * FROM indexed_threads WHERE project_id=? ORDER BY updated_at DESC', (project_id,)):
                t = dict(r)
                if t['archived'] and not args.get('includeArchived'):
                    continue
                ids = self.category_ids(db, 'thread_categories', 'thread_id', t['id'])
                if category is not None and category not in ids:
                    continue
                body = t.pop('body')
                text = t['title']+' '+t['preview']+' '+body
                if query and query not in text.casefold():
                    continue
                pos = body.casefold().find(query) if query else -1
                t['excerpt'] = body[max(0,pos-70):pos+180] if pos>=0 else t['preview'][:220]
                t['categoryIds'] = ids
                t['title'] = t['title'][:200]
                t.pop('rollout_path'); threads.append(t)
        offset = max(0, int(args.get('offset', 0)))
        return {'project': project, 'categories': categories, 'artifacts': artifacts[offset:offset+80],
                'threads': threads[offset:offset+80], 'totalArtifacts': len(artifacts), 'totalThreads': len(threads),
                'statuses': STATES, 'kinds': KINDS, 'offset': offset, 'status': self.status({}),
                'contentPage': read_page(self.data_dir, project)}

    def update_artifact(self, args):
        if args.get('status') not in STATES:
            raise ValueError('无效的成果状态。')
        with self.local() as db:
            row = db.execute('SELECT * FROM artifacts WHERE id=?', (args['id'],)).fetchone()
            if row is None:
                raise ValueError('成果不存在。')
            db.execute('UPDATE artifacts SET status=?,note=? WHERE id=?', (args['status'], args.get('note', row['note']), args['id']))
            if args['status'] == 'accepted':
                stat = self.artifact_file(args).stat()
                db.execute('INSERT OR REPLACE INTO accepted_files VALUES (?,?,?)', (args['id'], stat.st_size, stat.st_mtime_ns))
            if 'categoryIds' in args:
                self.validate_categories(db, row['project_id'], args['categoryIds'])
                db.execute('DELETE FROM artifact_categories WHERE artifact_id=?', (args['id'],))
                db.executemany('INSERT INTO artifact_categories VALUES (?,?)', [(args['id'], c) for c in set(args['categoryIds'])])
                db.execute('INSERT OR IGNORE INTO manual_tags VALUES (?,?)', ('artifact', str(args['id'])))
        return {'saved': True}

    def tag_thread(self, args):
        result = super().tag_thread(args)
        with self.local() as db:
            db.execute('INSERT OR IGNORE INTO manual_tags VALUES (?,?)', ('thread', args['threadId']))
        return result

    def save_artifact(self, args):
        result = super().save_artifact(args)
        self.update_artifact({'id': result['id'], 'status': args['status'], 'categoryIds': args['categoryIds']})
        return result

    def register_scheduled_maintenance(self, project_id, thread_id):
        thread=self.thread(thread_id)
        if self.owner(thread['cwd'],thread['project_id'])!=project_id:
            raise ValueError('维护对话不属于当前项目。')
        folder=self.data_dir/'scheduled-maintenance'/hashlib.sha256(project_id.encode()).hexdigest()
        folder.mkdir(parents=True,exist_ok=True)
        (folder/hashlib.sha256(thread_id.encode()).hexdigest()).touch()

    def maintenance_threads(self, project_id, threads=None):
        path=self.data_dir/'maintenance.json'
        jobs=json.loads(path.read_text()) if path.exists() else {}
        excluded=set(jobs.get(project_id,{}).get('threadIds',[]))
        folder=self.data_dir/'scheduled-maintenance'/hashlib.sha256(project_id.encode()).hexdigest()
        scheduled={p.name for p in folder.iterdir()} if folder.exists() else set()
        return [t for t in (self.all_threads() if threads is None else threads)
                if self.owner(t['cwd'],t['project_id'])==project_id and t['id'] not in excluded and hashlib.sha256(t['id'].encode()).hexdigest() not in scheduled]

    def prepare_record_batch(self,project):
        records.ensure(project)
        threads=self.maintenance_threads(project['id'])
        return records.prepare_batch(self.data_dir,project,threads,delivery_audit.gaps(self,project,threads))

    def maintenance_scan(self):
        self.refresh_projects()
        threads=self.all_threads()
        candidates=[];historical=[];errors=[]
        for project in self.projects():
            if not records.record_path(project).exists():continue
            try:
                state=records.checkpoint_state(self.data_dir,project)
                if not state:
                    historical.append({'project':project,'reason':'需要首次整理'})
                    continue
                delta=records.changes(self.data_dir,project,self.maintenance_threads(project['id'],threads))
                delta['deliveryGaps']=delivery_audit.gaps(self,project,threads)
                if records.has_changes(delta):
                    candidates.append((state['updatedAt'],project,delta))
            except (ValueError,OSError) as error:
                errors.append({'project':project,'error':str(error)})
        candidates.sort(key=lambda row:(row[0],row[1]['id']))
        selected=[{'project':project,'counts':{'commits':len(delta['commits'].splitlines()),'threads':len(delta['pendingThreads']),
                  'files':len(delta['workingTree']),'resources':len(delta['changedResources'])}} for _,project,delta in candidates]
        return {'projects':selected,'initialReviewNeeded':historical,'errors':errors}

    def dispatch(self, action, args):
        if action=='maintenanceScan':return self.maintenance_scan()
        if action in {'markMaintenance','finishMaintenance','cancelMaintenanceLaunch'}:
            project_id=self.aliases.get(args['projectId'],args['projectId'])
            return maintenance.update(self,self.project(project_id),action,args)
        if action in {'record','ensureRecord','saveRecord','updateCard','changes','prepareBatch','checkpoint','cardContext','maintenanceContext','reviewScope','reviewThread','reviewAssets','registerDelivery','reviewDeliveryGaps','resolveDeliveryGap','projectSearch','searchOpen','registerResource','adoptResource','chooseResource','automationPlan','linkAutomation'}:
            project_id=self.aliases.get(args['projectId'],args['projectId'])
            project=self.project(project_id)
            if action=='record':
                state=records.checkpoint_state(self.data_dir,project)
                checkpoint={k:v for k,v in state.items() if k not in {'working','resources'}} if state else None
                return {'project':project,'contentPage':read_page(self.data_dir,project),'checkpoint':checkpoint,'maintenance':maintenance.status(self,project)}
            if action=='reviewScope':return records.scope_page(self.data_dir,project,args)
            if action=='reviewThread':return self.review_thread(project,args)
            if action=='reviewAssets':return conversation_assets.review(self,project,args)
            if action=='reviewDeliveryGaps':return delivery_audit.review(self,project,args)
            if action=='resolveDeliveryGap':return delivery_audit.resolve(self,project,args)
            if action=='registerDelivery':return project_resources.register_delivery(self,project,args)
            if action=='projectSearch':return project_search.search(self,project,args)
            if action=='searchOpen':return project_search.open_result(self,project,args)
            if action=='registerResource':return project_resources.register(project,args)
            if action=='adoptResource':return project_resources.adopt(project,args)
            if action=='automationPlan':return automation_setup.plan(self,project)
            if action=='linkAutomation':return automation_setup.link(project,args)
            if action=='chooseResource':
                result=subprocess.run(['osascript','-e','POSIX path of (choose file with prompt "选择要登记到项目卡片的成果文件")'],capture_output=True,text=True)
                if result.returncode:
                    if '(-128)' in result.stderr:return {'cancelled':True}
                    raise ValueError(result.stderr.strip())
                return {'path':result.stdout.strip()}
            if action=='ensureRecord':
                return records.ensure(project)
            if action=='saveRecord':
                path=records.record_path(project)
                old=json.loads(path.read_text()).get('reviewedThreads',{}) if path.exists() else {}
                known={t['id']:t['updated_at'] for t in self.all_threads()}
                for key,value in args['record'].get('reviewedThreads',{}).items():
                    if value!=old.get(key) and (type(value) is not int or key not in known or value>known[key]):
                        raise ValueError('已查看位置必须来自实际对话，不能使用未来或猜测的时间。')
                coverage=args.get('coverage')
                if coverage and (covered_thread:=coverage.get('thread')):
                    thread=self.thread(covered_thread['id'])
                    if self.owner(thread['cwd'],thread['project_id'])!=project_id:raise ValueError('对话不属于当前项目。')
                    if type(covered_thread['updated_at']) is not int or covered_thread['updated_at']>thread['updated_at']:
                        raise ValueError('聊天整理位置不能超过实际对话。')
                return records.save(project,args['record'],args.get('expectedRevision'),args.get('author','agent'),coverage=coverage)
            if action=='updateCard':
                page=read_page(self.data_dir,project)
                card=next(c for c in page['cards'] if c['id']==args['cardId'])
                if set(args['changes'])-{'title','summary'}:
                    raise ValueError('页面编辑仅支持名称和说明。')
                changed={key:value for key,value in args['changes'].items() if card.get(key)!=value}
                if changed:
                    card.update(changed);card['manualFields']=sorted(set(card.get('manualFields',[]))|set(changed))
                return records.save(project,page,args['expectedRevision'],'user')
            if action=='changes':
                return records.changes(self.data_dir,project,self.maintenance_threads(project_id))
            if action=='prepareBatch':
                batch=maintenance.scheduled(self,project,args['maintenanceThreadId']) if args.get('maintenanceThreadId') else self.prepare_record_batch(project)
                return records.scope_summary(self.data_dir,batch)
            if action=='checkpoint':
                if args.get('batchId'):
                    batch=records.read_batch(self.data_dir,args['batchId'])
                    pending={g['id'] for g in delivery_audit.gaps(self,project)}
                    if any(g['id'] in pending for g in batch.get('deliveryGaps',[])):raise ValueError('本批成果缺口尚未处理，请补齐入口或记录具体无法找回的原因。')
                return records.checkpoint(self.data_dir,project,args['expectedRevision'],args.get('message','docs: update project records'),args['expectedHead'],
                    batch_id=args.get('batchId'),complete=args.get('complete',False),initial_review_complete=args.get('initialReviewComplete',False))
            if action=='cardContext':
                result=records.export_context(project,args['cardId']);result.update(project=project)
                return result
            return maintenance.begin(self,project)
        if action == 'linkCardThread':
            project_id = self.aliases.get(args['projectId'], args['projectId'])
            project = self.project(project_id)
            thread = self.thread(args['threadId'])
            if self.owner(thread['cwd'], thread['project_id']) != project_id:
                raise ValueError('这个对话不属于当前项目。')
            page = read_page(self.data_dir, project)
            if page is None or not any(c['id'] == args['cardId'] for c in page['cards']):
                raise ValueError('找不到这张卡片。')
            with self.codex() as db:
                title = db.execute("SELECT COALESCE(NULLIF(name,''),title) FROM threads WHERE id=?", (thread['id'],)).fetchone()[0]
            items=next(c['sources'] for c in page['cards'] if c['id']==args['cardId'])
            if not any(t['id']==thread['id'] for t in items):
                items.append({'id':thread['id'],'title':title,'label':'从卡片发起'})
                records.save(project,page,page['revision'])
            return {'saved': True}
        if action in {'pagePreview', 'pageReveal', 'pageThumbnail'}:
            project_id = self.aliases.get(args['projectId'], args['projectId'])
            return resource_action(self.data_dir, self.project(project_id), action, args)
        if action == 'thumbnail':
            path = self.artifact_file(args)
            if path.suffix.lower() not in IMAGES:
                raise ValueError('该文件不是可预览的图片。')
            cache = self.data_dir/'thumbnails'
            cache.mkdir(exist_ok=True)
            destination = cache/f"{args['id']}-{path.stat().st_mtime_ns}.png"
            if not destination.exists():
                subprocess.run(['/usr/bin/sips', '-Z', '320', '-s', 'format', 'png', str(path), '--out', str(destination)], check=True, capture_output=True, timeout=20)
            return {'data': 'data:image/png;base64,'+base64.b64encode(destination.read_bytes()).decode()}
        if action == 'status':
            return self.status(args)
        if action == 'rescan':
            threading.Thread(target=self.scan, daemon=True).start()
            return {'started': True}
        if action == 'updateArtifact':
            return self.update_artifact(args)
        return super().dispatch(action, args)
