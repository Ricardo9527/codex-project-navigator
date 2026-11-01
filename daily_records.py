"""Small, scoped daily maintenance forms over the existing project record."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import uuid
import conversation_assets
import project_records as records
from content_pages import resource_path
from file_versions import cached_fingerprint, fingerprint, version_stamp
from project_resources import attach_delivery


def _scope_path(hub, identity):
    return hub.data_dir/'daily-records'/(str(uuid.UUID(identity))+'.json')


def _card_view(card):
    return {k:card[k] for k in ['id','title','summary','categoryIds','sections']}



def _filter_assets(hub, project, record, thread_id, requested, assets, since):
    cards=[c for c in record['cards'] if c['id'] in requested] if requested else [c for c in record['cards'] if any(t['id']==thread_id for t in c['sources'])]
    known={}
    for card in cards:
        for resource in card['resources']:
            for delivery in resource.get('deliveries',[]):
                if delivery.get('assetId'):
                    known.setdefault(delivery['assetId'],[]).append((card,resource,delivery.get('fingerprint')))
    pending=[];repairs=[];skipped=0
    for asset in assets:
        path=Path(asset['path']).resolve();candidates=known.get(asset['id'],[])
        digest=cached_fingerprint(hub,path) if path.is_file() else None
        matched=None
        for card,resource,saved_digest in candidates:
            target=resource_path(project,resource,record)
            if saved_digest and (digest is None or digest==saved_digest) and target.is_file() and cached_fingerprint(hub,target)==saved_digest:
                matched=(card,resource);break
        if matched:
            skipped+=1;continue
        if candidates:
            pending.append({**asset,'reason':'content_changed_or_missing'});continue
        recent=datetime.fromisoformat(asset['deliveredAt'].replace('Z','+00:00')).timestamp()>since
        for card in cards:
            for resource in card['resources']:
                target=resource_path(project,resource,record)
                if not target.is_file():continue
                if target==path:
                    saved={d['fingerprint'] for d in resource.get('deliveries',[]) if d.get('fingerprint')}
                    if resource.get('acceptedFingerprint'):saved.add(resource['acceptedFingerprint'])
                    previous=record.get('reviewState',{}).get('resources',{}).get(card['id']+'/'+resource['id'])
                    stat=target.stat()
                    if (saved and digest not in saved) or (not saved and previous is not None and previous!=[stat.st_size,stat.st_mtime_ns]):
                        matched=None;break
                    if saved or previous==[stat.st_size,stat.st_mtime_ns]:matched=(card,resource)
                    break
                if recent and digest and target.stat().st_size==path.stat().st_size and cached_fingerprint(hub,target)==digest:
                    matched=(card,resource);break
            if matched:break
        if matched:
            card,resource=matched
            # Add the verified path/message relation in the same eventual save; no AI work.
            if all(asset['origin'].get(k) for k in ['threadId','turnId','itemId']):
                repairs.append({'cardId':card['id'],'resourceId':resource['id'],'asset':asset})
                skipped+=1
            elif recent:pending.append({**asset,'reason':'source_incomplete'})
        elif recent or any(resource_path(project,r,record)==path for c in cards for r in c['resources']):
            pending.append({**asset,'reason':'new_or_changed'})
    return pending,repairs,skipped

def prepare(hub, project, args):
    if args.get('scopeId'):
        scope=json.loads(_scope_path(hub,args['scopeId']).read_text())
        if scope['projectId']!=project['id']:raise ValueError('维护表单不属于当前项目。')
    else:
        records.ensure(project)
        path=records.record_path(project);record=json.loads(path.read_text())
        thread=hub.thread(args['threadId'])
        if hub.owner(thread['cwd'],thread['project_id'])!=project['id']:raise ValueError('对话不属于当前项目。')
        requested=set(args.get('cardIds',[]))
        if args.get('cardId'):requested.add(args['cardId'])
        selected_cards=[_card_view(c) for c in record['cards'] if c['id'] in requested]
        if requested-{c['id'] for c in selected_cards}:raise ValueError('找不到请求的卡片。')
        selected=next((c for c in record['cards'] if c['id']==args.get('cardId')),None)
        if args.get('cardId') and selected is None:raise ValueError('找不到卡片。')
        since=record.get('reviewedThreads',{}).get(thread['id'],0);until=thread['updated_at']
        assets=[]
        for asset in conversation_assets.thread_assets(hub,thread['id']):
            when=asset.get('deliveredAt')
            if asset['kind']=='reference' or not when:continue
            timestamp=datetime.fromisoformat(when.replace('Z','+00:00')).timestamp()
            if timestamp < until+1:assets.append({**asset,'preparedStamp':version_stamp(asset['path'])})
        if args.get('includeRegistered'):
            assets=[a for a in assets if datetime.fromisoformat(a['deliveredAt'].replace('Z','+00:00')).timestamp()>since]
            repairs=[];skipped=0
        else:assets,repairs,skipped=_filter_assets(hub,project,record,thread['id'],requested,assets,since)
        scope={'scopeId':str(uuid.uuid4()),'projectId':project['id'],'threadId':thread['id'],
               'threadTitle':thread['title'],'reviewedUntil':since,'updated_at':until,
               'categories':record['categories'],'card':_card_view(selected) if selected else None,'selectedCards':selected_cards,
               'cards':[{'id':c['id'],'title':c['title'],'categoryIds':c['categoryIds']} for c in record['cards']],
               'assets':assets,'matchedDeliveries':repairs,'skippedRegistered':skipped,'sourceLinksToAdd':len(repairs)}
        folder=hub.data_dir/'daily-records';folder.mkdir(exist_ok=True)
        _scope_path(hub,scope['scopeId']).write_text(json.dumps(scope,ensure_ascii=False))
    offset=args.get('offset',0)
    if type(offset) is not int or not 0<=offset<=len(scope['assets']):raise ValueError('成果读取位置无效。')
    result={k:v for k,v in scope.items() if k not in {'assets','matchedDeliveries'}}
    result['assets']=[{'assetId':a['id'],'name':Path(a['path']).name,'deliveredAt':a['deliveredAt'],
                      'path':a['path'],'reason':a.get('reason','requested'),'turnId':a['origin'].get('turnId'),'exists':Path(a['path']).is_file()} for a in scope['assets'][offset:offset+30]]
    result.update(assetCount=len(scope['assets']),nextOffset=offset+30 if offset+30<len(scope['assets']) else None)
    return result


def _add_category(record, category):
    current=next((c for c in record['categories'] if c['id']==category['id']),None)
    if current:
        if current['title']!=category['title'] or current.get('parentId')!=category.get('parentId'):
            raise ValueError('分类已存在且定义不同：'+category['id'])
    else:record['categories'].append({**category,'description':category.get('description','')})


def _match_file(hub, project, record, card, path):
    """Only same-card files of the same size are candidates; hashes are persistent."""
    size=path.stat().st_size
    candidates=[]
    for resource in card['resources']:
        target=resource_path(project,resource,record)
        if target==path:return resource
        if target.is_file() and target.stat().st_size==size:candidates.append((resource,target))
    if candidates:
        digest=cached_fingerprint(hub,path)
        for resource,target in candidates:
            if cached_fingerprint(hub,target)==digest:return resource
    return None


def _attach(hub, project, record, card, asset, label):
    source=Path(asset['path']).resolve()
    if not source.is_file():raise ValueError('本次成果文件不存在：'+str(source))
    existing=_match_file(hub,project,record,card,source)
    original=deepcopy(asset)
    if existing is None:
        # Preserve explicitly selected generated results in a stable project directory.
        if source.is_relative_to((Path.home()/'.codex/generated_images').resolve()):
            target=Path(project['path'])/'assets/deliveries'/card['id']/(asset['id']+'-'+cached_fingerprint(hub,source)[7:19]+source.suffix)
            target=target.resolve()
            if not target.is_relative_to(Path(project['path']).resolve()):raise ValueError('成果目录越出项目。')
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and fingerprint(target)!=cached_fingerprint(hub,source):
                raise ValueError('成果副本已有不同内容：'+str(target))
            if not target.exists():shutil.copy2(source,target)
            asset={**asset,'id':asset['id']+'-'+cached_fingerprint(hub,source)[7:19],'path':str(target)}
        existing=attach_delivery(project,record,card,asset,label)
    else:
        existing.setdefault('deliveries',[])
        old_origin=existing.get('origin')
        if old_origin and old_origin!=original['origin'] and not any(d['origin']==old_origin for d in existing['deliveries']):
            existing['deliveries'].append({'origin':old_origin,'deliveredAt':existing.get('deliveredAt')})
        if original['deliveredAt']>=existing.get('deliveredAt',''):
            existing.update(origin=original['origin'],deliveredAt=original['deliveredAt'])
    delivery={'assetId':original['id'],'path':original['path'],'origin':original['origin'],
              'deliveredAt':original['deliveredAt'],'fingerprint':cached_fingerprint(hub,source)}
    entries=existing.setdefault('deliveries',[])
    if not any(d.get('assetId')==delivery['assetId'] and d.get('fingerprint')==delivery['fingerprint'] for d in entries):entries.append(delivery)
    return existing['id']


def submit(hub, project, args):
    scope=json.loads(_scope_path(hub,args['scopeId']).read_text())
    if scope['projectId']!=project['id']:raise ValueError('维护表单不属于当前项目。')
    coverage_mode=args.get('threadCoverage')
    if coverage_mode not in {'complete','unchanged'}:raise ValueError('请明确本次聊天覆盖为 complete 或 unchanged。')
    updates=args.get('updates')
    if not isinstance(updates,list):raise ValueError('updates 必须是数组；无卡片变化可填 []。')
    digest=hashlib.sha256(json.dumps({k:v for k,v in args.items() if k!='projectId'},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    thread=hub.thread(scope['threadId'])
    if hub.owner(thread['cwd'],thread['project_id'])!=project['id']:raise ValueError('对话不属于当前项目。')
    assets={a['id']:a for a in scope['assets']}
    path=records.record_path(project)
    with records.locked(project):
        record=json.loads(path.read_text())
        prior=record.get('dailyReceipts',{}).get(scope['scopeId'])
        if prior:
            if prior['digest']!=digest:raise ValueError('此表单已提交；修改内容请重新准备表单。')
            return {'saved':True,'replayed':True,'cardIds':prior['cardIds'],'revision':records.revision(path)}
        current=record.get('reviewedThreads',{}).get(scope['threadId'],0)
        if coverage_mode=='complete' and current!=scope['reviewedUntil']:
            raise ValueError('聊天处理位置已变化，请重新准备表单；本次未保存。')
        for category in args.get('categories',[]):_add_category(record,category)
        changed=[];resource_ids=[]
        for index,update in enumerate(updates):
            card_id=update.get('cardId')
            card=next((c for c in record['cards'] if c['id']==card_id),None) if card_id else None
            changes=update.get('changes',{})
            if card_id and card is None:raise ValueError('找不到卡片：'+card_id)
            if not card_id:
                if not all(changes.get(k) for k in ['title','summary','categoryId']):
                    raise ValueError('新卡片必须填写 title、summary、categoryId。')
                card={'id':'daily-'+scope['scopeId'][:12]+'-'+str(index),'title':changes['title'],'summary':changes['summary'],
                      'categoryIds':[changes['categoryId']],'kind':'工作','icon':'file','caption':'',
                      'resources':[],'sources':[],'sections':[],'records':[],'requirements':[],'related':[]}
                record['cards'].append(card)
            else:
                base=next((c for c in scope['selectedCards'] if c['id']==card_id),None)
                if changes and (not base or base['id']!=card_id):
                    raise ValueError('修改现有卡片前，请在准备表单时指定该 cardId。')
                for key,value in changes.items():
                    field='categoryIds' if key=='categoryId' else 'sections' if key=='notes' else key
                    if key not in {'title','summary','categoryId','notes'}:raise ValueError('不支持的卡片修改字段：'+key)
                    desired=[value] if key=='categoryId' else value
                    if key=='notes':
                        desired=[s for s in card['sections'] if s['title']!='当前情况']+[{'title':'当前情况','paragraphs':value}]
                    if field in card.get('manualFields',[]) and card[field]!=desired:raise ValueError('请保留用户修改的字段：'+field)
                    if card[field]!=base[field] and card[field]!=desired:raise ValueError('卡片字段已变化：'+field+'；本次未保存。')
                    card[field]=desired
            if not card_id and 'notes' in changes:card['sections']=[{'title':'当前情况','paragraphs':changes['notes']}]
            if not any(s['id']==thread['id'] for s in card['sources']):
                card['sources'].append({'id':thread['id'],'title':thread['title'],'label':'相关工作对话'})
            for delivery in update.get('deliveries',[]):
                asset=assets.get(delivery['assetId'])
                if asset is None:raise ValueError('交付不在本次固定范围内：'+delivery['assetId'])
                origin=asset['origin']
                if version_stamp(asset['path'])!=asset['preparedStamp']:raise ValueError('交付文件在准备表单后已变化，请重新准备。')
                if not all(origin.get(k) for k in ['threadId','turnId','itemId']):
                    raise ValueError('本次交付缺少消息定位，请使用 files 登记并明确来源缺失原因。')
                resource_ids.append(_attach(hub,project,record,card,asset,delivery.get('label')))
            for item in update.get('files',[]):
                source=Path(item['path']).expanduser().resolve()
                if not item.get('sourceReason','').strip():raise ValueError('导入文件需填写来源说明 sourceReason。')
                if not source.is_file():raise ValueError('导入文件不存在：'+str(source))
                if not source.is_relative_to(Path(project['path']).resolve()) and item.get('external') is not True:
                    raise ValueError('导入外部文件需明确 external=true。')
                # Imported files have a declared source, not a fabricated chat message.
                asset={'id':hashlib.sha256(str(source).encode()).hexdigest()[:24],'path':str(source),
                       'deliveredAt':datetime.fromtimestamp(source.stat().st_mtime).astimezone().isoformat(),
                       'origin':{'threadId':thread['id'],'sourceType':'import','reason':item['sourceReason']}}
                rid=_attach(hub,project,record,card,asset,item.get('label'))
                resource=next(r for r in card['resources'] if r['id']==rid)
                resource['sourceDeclaration']={'type':'import','reason':item['sourceReason']}
                resource_ids.append(rid)
            changed.append(card['id'])
        for match in scope.get('matchedDeliveries',[]):
            card=next((c for c in record['cards'] if c['id']==match['cardId']),None)
            resource=next((r for r in card['resources'] if r['id']==match['resourceId']),None) if card else None
            asset=match['asset']
            if resource is None or version_stamp(asset['path'])!=asset['preparedStamp']:
                raise ValueError('自动关联的成果已变化，请重新准备表单。')
            if _match_file(hub,project,record,card,Path(asset['path']).resolve()) is not resource:
                raise ValueError('自动关联的文件内容已变化，请重新准备表单。')
            _attach(hub,project,record,card,asset,None)
            if not all(resource.get('origin',{}).get(k) for k in ['threadId','turnId','itemId']):
                resource.update(origin=asset['origin'],deliveredAt=asset['deliveredAt'])
            if card['id'] not in changed:changed.append(card['id'])
        coverage={'cardIds':list(dict.fromkeys(changed)),'commits':args.get('commits',[])}
        if coverage_mode=='complete':
            coverage['thread']={'id':thread['id'],'reviewedUntil':scope['reviewedUntil'],'updated_at':scope['updated_at']}
        receipts=record.setdefault('dailyReceipts',{})
        receipts[scope['scopeId']]={'digest':digest,'cardIds':changed}
        while len(receipts)>32:receipts.pop(next(iter(receipts)))
        saved=records.save(project,record,records.revision(path),allow_external=True,coverage=coverage,_lock_held=True)
    return {'saved':True,'replayed':False,'revision':saved['revision'],'cardIds':changed,
            'resourceIds':resource_ids,'threadCoveredUntil':scope['updated_at'] if coverage_mode=='complete' else current}
