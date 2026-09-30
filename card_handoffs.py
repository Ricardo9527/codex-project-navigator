"""Reconcile explicitly prepared card handoffs against read-only Codex rollouts."""
import json
import time
import uuid
from pathlib import Path


def _path(hub):
    return hub.data_dir/'card-handoffs.json'


def _read(hub):
    path=_path(hub)
    return json.loads(path.read_text()) if path.exists() else {}


def _save(hub,items):
    path=_path(hub);temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(items,ensure_ascii=False,indent=2));temp.replace(path)


def prepare(hub,project,card_id):
    from content_pages import read_page
    page=read_page(hub.data_dir,project)
    if not page or not any(c['id']==card_id for c in page['cards']):
        raise ValueError('卡片已不在项目记录中，请返回目录核对。')
    with hub.lock,hub.codex() as db:
        existing=[row['id'] for row in db.execute('SELECT id,cwd,project_id FROM threads') if hub.owner(row['cwd'],row['project_id'])==project['id']]
        token='project-navigation-handoff:'+str(uuid.uuid4())
        items=_read(hub);items[token]={'projectId':project['id'],'cardId':card_id,'createdAt':int(time.time()),'existingThreadIds':existing}
        _save(hub,items)
    return {'token':token}


def cancel(hub,token):
    with hub.lock:
        items=_read(hub);items.pop(token,None);_save(hub,items)
    return {'cancelled':True}


def reconcile(hub):
    linked=[]
    with hub.lock:
        items=_read(hub)
        for token,item in list(items.items()):
            with hub.codex() as db:
                rows=db.execute('SELECT id,cwd,project_id,rollout_path FROM threads WHERE updated_at>=?',(item['createdAt']-1,)).fetchall()
            for row in rows:
                if row['id'] in item['existingThreadIds'] or hub.owner(row['cwd'],row['project_id'])!=item['projectId']:continue
                path=Path(row['rollout_path'])
                if not path.is_file():continue
                found=False;context_calls=set()
                with path.open() as stream:
                    for line in stream:
                        if not line.endswith('\n'):break
                        event=json.loads(line)
                        if event.get('type')!='response_item':continue
                        payload=event.get('payload',{})
                        if payload.get('type')=='function_call' and payload.get('name')=='untrusted_input':context_calls.add(payload.get('call_id'))
                        is_context=payload.get('type')=='function_call_output' and payload.get('call_id') in context_calls
                        is_user=payload.get('type')=='message' and payload.get('role')=='user'
                        if (is_context or is_user) and token in json.dumps(payload,ensure_ascii=False):found=True;break
                if not found:continue
                hub.dispatch('linkCardThread',{'projectId':item['projectId'],'cardId':item['cardId'],'threadId':row['id']})
                linked.append({'projectId':item['projectId'],'cardId':item['cardId'],'threadId':row['id']})
                del items[token];_save(hub,items);break
    return {'linked':linked}
