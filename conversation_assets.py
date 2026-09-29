"""Read delivered files and images from a conversation without changing its history."""
from pathlib import Path
from urllib.parse import unquote
import hashlib
import json
import re

VERSION = 4
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}


def scan(path, thread_id):
    turn = None
    prompt = ''
    assets = []
    seen = set()
    def add(file, event, payload, kind):
        file = unquote(file).strip('<>')
        if re.search(r':\d+(?::\d+)?$',file):
            file=re.sub(r':\d+(?::\d+)?$','',file);kind='reference'
        if any(x in file for x in ['/.codex/skills/','/.agents/skills/','/knowledge/']):kind='reference'
        if Path(file).is_dir():return
        if not file.startswith('/'):return
        identity = (file, turn)
        if identity in seen:
            if payload.get('kind')=='image_gen.generation':
                existing=next(a for a in assets if (a['path'],a['origin']['turnId'])==identity)
                existing['origin']['itemId']=payload['id']
            return
        seen.add(identity)
        assets.append({'id':hashlib.sha256((thread_id+'\0'+file+'\0'+str(turn)).encode()).hexdigest()[:24],
                       'path':file,'kind':kind,'deliveredAt':event.get('timestamp'),
                       'origin':{'threadId':thread_id,'turnId':turn,'itemId':payload.get('id'),
                                 'prompt':prompt},'exists':Path(file).is_file()})
    with Path(path).open() as stream:
        for line in stream:
            if not line.endswith('\n'):break
            e=json.loads(line);p=e.get('payload',{});kind=p.get('type')
            if e['type']=='event_msg' and kind=='task_started':turn=p.get('turn_id',turn)
            if e['type']=='turn_context':turn=p.get('turn_id',turn)
            if e['type']=='event_msg' and kind=='item_completed':
                item=p.get('item',{})
                if item.get('kind')=='image_gen.generation' and item.get('status')=='completed' and item.get('savedPath'):
                    turn=p.get('turn_id',turn);add(item['savedPath'],e,item,'image')
            if e['type']!='response_item':continue
            meta=p.get('internal_chat_message_metadata_passthrough') or {}
            turn=meta.get('turn_id',turn)
            if kind=='message':
                text='\n'.join(c.get('text','') for c in p.get('content',[]))
                if p.get('role')=='user':
                    if '## My request:' in text:text=text.split('## My request:',1)[1]
                    if not text.lstrip().startswith(('<','# AGENTS.md')):prompt=re.sub(r'<image\b.*?</image>|<image_annotations>.*?</image_annotations>','',text,flags=re.S).strip()[:500]
                if p.get('role')!='assistant' or p.get('phase') not in (None,'final','final_answer'):continue
                # Assistant delivery links, including encoded paths and paths containing spaces.
                for angle,plain in re.findall(r'\]\((?:<([^>\n]+)>|((?:[^()\n]|\([^()\n]*\))+))\)',text):add(angle or plain,e,p,'file')
            if kind in {'custom_tool_call_output','function_call_output'}:
                output=p.get('output',[])
                if not isinstance(output,list):continue
                for item in output:
                    text=item.get('text','')
                    # The image tool's saved-file notice ties its delivered image to a real local path.
                    if text.startswith('Generated images are saved to '):
                        for f in re.findall(r'(/[^\n]+?\.(?:png|jpg|jpeg|webp))(?= by default|, |\n|$)',text.split(' as ',1)[-1]):add(f,e,p,'image')
                    if item.get('type') in {'image','input_image'}:
                        url=item.get('image_url','')
                        if isinstance(url,str) and url.startswith('file://'):add(url[7:],e,p,'image')
    return sorted(assets,key=lambda a:a['deliveredAt'] or '',reverse=True)


def thread_assets(hub, thread_id):
    with hub.codex() as db:
        row=db.execute('SELECT rollout_path FROM threads WHERE id=?',(thread_id,)).fetchone()
    if row is None:raise ValueError('来源对话已不存在。')
    path=Path(row['rollout_path']);stat=path.stat()
    cache=Path(hub.data_dir)/'conversation-assets';cache.mkdir(exist_ok=True)
    key=hashlib.sha256(thread_id.encode()).hexdigest()
    target=cache/(key+'.json');stamp=[VERSION,stat.st_size,stat.st_mtime_ns]
    if target.exists():
        previous=json.loads(target.read_text())
        if previous['stamp']==stamp:return previous['assets']
    assets=scan(path,thread_id)
    target.write_text(json.dumps({'stamp':stamp,'assets':assets},ensure_ascii=False))
    return assets


def review(hub, project, args):
    thread=hub.thread(args['threadId'])
    if hub.owner(thread['cwd'],thread['project_id'])!=project['id']:raise ValueError('来源对话不属于当前项目。')
    assets=thread_assets(hub,args['threadId'])
    offset=args.get('offset',0)
    if type(offset) is not int or offset<0:raise ValueError('读取位置无效。')
    end=offset+30
    return {'items':assets[offset:end],'total':len(assets),'nextOffset':end if end<len(assets) else None}
