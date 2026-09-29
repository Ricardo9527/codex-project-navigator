"""Explicit result registration and version-bound adoption."""
import hashlib
import json
from pathlib import Path
import project_records as records
from content_pages import resource_path
from file_versions import fingerprint, version_stamp


def register(project, args):
    path=Path(args['path']).expanduser().resolve()
    if not path.is_file():raise ValueError('请选择一个实际文件。')
    record=json.loads(records.record_path(project).read_text())
    card=next((c for c in record['cards'] if c['id']==args['cardId']),None)
    if not card:raise ValueError('找不到卡片。')
    root=Path(project['path']).resolve()
    if path.is_relative_to(root):source='project';pointer=str(path.relative_to(root))
    else:
        if args.get('external') is not True:raise ValueError('请明确确认登记这个项目外文件。')
        source='external';pointer=hashlib.sha256(str(path).encode()).hexdigest()[:24]
        record.setdefault('externalFiles',{})[pointer]={'path':str(path),'label':path.name}
    existing=next((r for r in card['resources'] if r.get('source','project')==source and r['path']==pointer),None)
    if not existing:
        suffix=path.suffix.lower()
        format='图片' if suffix in {'.png','.jpg','.jpeg','.webp','.gif'} else suffix.lstrip('.').upper() or '文件'
        card['resources'].append({'id':hashlib.sha256((source+':'+pointer).encode()).hexdigest()[:24],
                                 'label':args.get('label') or path.stem,'path':pointer,'source':source,
                                 'format':format,'role':'result','note':''})
    return records.save(project,record,args['expectedRevision'],'user',allow_external=True)


def adopt(project, args):
    record=json.loads(records.record_path(project).read_text())
    card=next((c for c in record['cards'] if c['id']==args['cardId']),None)
    resource=next((r for r in card['resources'] if r['id']==args['resourceId']),None) if card else None
    if resource is None:raise ValueError('找不到成果。')
    if resource['role']!='result':raise ValueError('辅助文件无需确认选用。')
    if args.get('adoption')=='review':
        resource['adoption']='review'
        return records.save(project,record,args['expectedRevision'],'user',allow_adoption=True)
    target=resource_path(project,resource,record)
    if 'expectedStamp' in args and args['expectedStamp']!=version_stamp(target):raise ValueError('文件版本已变化，请点击“刷新预览”，查看后再确认采用。')
    current=fingerprint(target)
    if not current:raise ValueError('文件不存在，不能确认采用。')
    old=resource.get('acceptedFingerprint')
    if old and old!=current:
        versions=resource.setdefault('adoptionHistory',[])
        if old not in [v['fingerprint'] for v in versions]:versions.append({'fingerprint':old,'adoption':'accepted'})
    resource.update(adoption='accepted',acceptedFingerprint=current)
    return records.save(project,record,args['expectedRevision'],'user',allow_adoption=True)


def register_delivery(hub, project, args):
    from conversation_assets import review
    # Verify ownership independently of any path supplied by the caller.
    review(hub,project,{'threadId':args['threadId']})
    from conversation_assets import thread_assets
    asset=next((a for a in thread_assets(hub,args['threadId']) if a['id']==args['assetId']),None)
    if asset is None:raise ValueError('找不到这项对话交付。')
    record=json.loads(records.record_path(project).read_text())
    card=next(c for c in record['cards'] if c['id']==args['cardId'])
    if not any(s['id']==args['threadId'] for s in card['sources']):raise ValueError('请先确认成果与卡片的来源关系。')
    attach_delivery(project,record,card,asset,args.get('label'))
    return records.save(project,record,args['expectedRevision'],allow_external=True)


def attach_delivery(project, record, card, asset, label=None):
    path=Path(asset['path']).resolve();root=Path(project['path']).resolve()
    if path.is_relative_to(root):source='project';pointer=str(path.relative_to(root))
    else:
        source='external';pointer=hashlib.sha256(str(path).encode()).hexdigest()[:24]
        record.setdefault('externalFiles',{})[pointer]={'path':str(path),'label':path.name}
    existing=next((r for r in card['resources'] if r.get('source','project')==source and r['path']==pointer),None)
    if existing is None:
        suffix=path.suffix.lower()
        existing={'id':asset['id'],'label':label or path.stem,'path':pointer,'source':source,
                  'format':'图片' if suffix in {'.png','.jpg','.jpeg','.webp','.gif'} else suffix.lstrip('.').upper(),
                  'role':'result','note':''}
        card['resources'].append(existing)
    # The latest delivery link wins; adoption is independent and preserved.
    if asset.get('deliveredAt','') >= existing.get('deliveredAt',''):
        existing.update(deliveredAt=asset['deliveredAt'],origin=asset['origin'])
    return existing
