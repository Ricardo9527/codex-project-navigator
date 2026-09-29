"""Find concrete gaps between conversation deliveries and canonical project records."""
import hashlib
import json
from pathlib import Path
import project_records as records
from content_pages import resource_path
from conversation_assets import thread_assets
from file_versions import version_stamp


def gaps(hub, project, threads=None):
    path=records.record_path(project)
    record=json.loads(path.read_text()) if path.exists() else {}
    paths={};origins=set();candidates={};found=[]
    for card in record.get('cards',[]):
        for source in card['sources']:candidates.setdefault(source['id'],[]).append(card['id'])
        for resource in card['resources']:
            target=resource_path(project,resource,record)
            paths.setdefault(str(target),[]).append((card,resource))
            origin=resource.get('origin')
            if origin and origin.get('itemId'):origins.add((origin['threadId'],origin.get('itemId')))
            issues=[]
            if not target.exists():issues.append('missing_file')
            if resource['role']=='result' and (not origin or not origin.get('itemId') or not origin.get('turnId')) and card['sources']:issues.append('missing_origin')
            for kind in issues:
                key=kind+':'+card['id']+':'+resource['id']
                found.append({'id':key,'kind':kind,'cardId':card['id'],'resourceId':resource['id'],
                              'label':resource['label'],'path':str(target),'sources':card['sources'],
                              'evidence':version_stamp(target)})
    for thread in hub.maintenance_threads(project['id'],threads):
        for asset in thread_assets(hub,thread['id']):
            if asset['kind']=='reference':continue
            generated=Path(asset['path']).is_relative_to(Path.home()/'.codex/generated_images')
            if not generated and not records.discoverable(asset['path']):continue
            origin=asset['origin']
            if str(Path(asset['path']).resolve()) in paths or (thread['id'],origin.get('itemId')) in origins:continue
            found.append({'id':'delivery:'+asset['id'],'kind':'unregistered_delivery',
                          'threadId':thread['id'],'threadTitle':thread['title'],'assetId':asset['id'],
                          'label':Path(asset['path']).name,'path':asset['path'],'origin':origin,
                          'deliveredAt':asset['deliveredAt'],'candidateCardIds':candidates.get(thread['id'],[]),
                          'evidence':version_stamp(asset['path'])})
    decisions=record.get('deliveryReview',{})
    pending=[]
    for gap in found:
        identity={k:v for k,v in gap.items() if k not in {'label','threadTitle'}}
        if 'sources' in identity:identity['sources']=[s['id'] for s in identity['sources']]
        signature=hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        gap['signature']=signature
        if decisions.get(gap['id'],{}).get('signature')!=signature:pending.append(gap)
    return pending


def review(hub, project, args):
    items=gaps(hub,project);offset=args.get('offset',0)
    if type(offset) is not int or offset<0:raise ValueError('读取位置无效。')
    return {'items':items[offset:offset+30],'total':len(items),'nextOffset':offset+30 if offset+30<len(items) else None}


def resolve(hub, project, args):
    gap=next((g for g in gaps(hub,project) if g['id']==args['gapId']),None)
    if gap is None or gap['signature']!=args['signature']:raise ValueError('缺口已有变化，请重新读取。')
    status=args['status'];reason=args.get('reason','').strip()
    if status not in {'reference','duplicate','unavailable'} or not reason:raise ValueError('请记录具体处理结论和依据。')
    if status=='reference' and gap['kind']!='unregistered_delivery':raise ValueError('只有尚未归卡的交付线索可以判定为参考资料。')
    if status=='unavailable' and gap['kind']=='unregistered_delivery' and Path(gap['path']).exists():raise ValueError('文件存在，请确认归属并登记成果。')
    record=json.loads(records.record_path(project).read_text())
    if status=='duplicate':
        if gap['kind']!='unregistered_delivery':raise ValueError('请直接补齐已有文件的路径或来源。')
        card=next((c for c in record['cards'] if c['id']==args.get('cardId')),None)
        target=next((r for r in card['resources'] if r['id']==args.get('resourceId')),None) if card else None
        if target is None:raise ValueError('重复项必须指向已有成果。')
    record.setdefault('deliveryReview',{})[gap['id']]={**gap,'status':status,'reason':reason,
        **({'targetCardId':args['cardId'],'targetResourceId':args['resourceId']} if status=='duplicate' else {})}
    return records.save(project,record,args['expectedRevision'])
