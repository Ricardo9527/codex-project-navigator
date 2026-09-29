"""Read agent-authored project pages from local data; source files stay read-only."""
import base64
import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from project_records import record_path, revision
from file_versions import fingerprint, version_stamp


def resource_path(project, resource, record=None):
    source = resource.get('source', 'project')
    if source == 'external':
        record=record if record is not None else json.loads(record_path(project).read_text())
        entry=record.get('externalFiles',{}).get(resource['path'])
        if not entry:raise ValueError('外部文件尚未登记。')
        path=Path(entry['path'])
        if not path.is_absolute() or path.resolve()!=path:raise ValueError('外部文件位置已变化，请重新登记。')
        return path
    if source not in {'project', 'skill'}:
        raise ValueError('未知的资料来源。')
    root = (Path.home() / '.codex/skills' if source == 'skill' else Path(project['path'])).resolve()
    if source=='skill':
        relative=Path(resource['path'])
        if relative.is_absolute() or '..' in relative.parts or relative.name!='SKILL.md':
            raise ValueError('全局技能入口应指向已安装技能的 SKILL.md。')
        path=(root/relative).resolve()
        if path.name!='SKILL.md':raise ValueError('技能入口指向的文件不是 SKILL.md。')
        return path
    path = (root / resource['path']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('资料文件已超出所属项目目录。')
    return path


def resource_label(resource, target):
    label=resource.get('label',target.stem)
    if label.lower() in {'readme','manifest','skill','.','docs','md','json','txt'}:
        if target.suffix.lower() in {'.md','.txt'} and target.is_file():
            with target.open(encoding='utf-8',errors='replace') as f:
                for _ in range(30):
                    line=f.readline().strip()
                    if line.startswith('# '):return line[2:].strip()
        names={'readme':'说明','manifest':'来源文件清单','skill':'技能说明'}
        label=names.get(label.lower(),target.stem)
        if target.parent.name not in {'docs','sources'}:label=target.parent.name+' · '+label
    return label.replace('_',' ')


def read_page(data_dir, project):
    path = record_path(project)
    if not path.exists():
        return None
    page = json.loads(path.read_text())
    if page['version'] != 1 or page['projectId'] != project['id']:
        raise ValueError('项目内容页版本或归属不匹配；导入或移动项目后，请点击更新重新关联。')
    for card in page['cards']:
        for resource in card['resources']:
            target=resource_path(project,resource,page)
            resource['exists'] = target.exists()
            resource['sortTime']=resource.get('deliveredAt') or (datetime.fromtimestamp(target.stat().st_mtime,timezone.utc).isoformat() if target.exists() else '')
            resource['timeBasis']='delivery' if resource.get('deliveredAt') else 'file'
            resource['displayLabel']=resource_label(resource,target)
            resource['previewSupported']=target.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.gif','.md','.txt','.srt','.tsv','.csv','.fcpxml','.json','.docx','.xlsx','.pdf'}
            resource['versionStamp']=version_stamp(target)
            if resource.get('adoption')=='accepted':
                current=fingerprint(target)
                resource['versionUnverified']=not resource.get('acceptedFingerprint')
                resource['versionChanged']=bool(resource.get('acceptedFingerprint')) and current!=resource['acceptedFingerprint']
                resource['effectiveAdoption']='review' if resource['versionChanged'] or resource['versionUnverified'] else 'accepted'
            else:resource['effectiveAdoption']=resource.get('adoption','review')
        card['resources'].sort(key=lambda r:r['sortTime'],reverse=True)
    if page.get('reviewState'):page['reviewState']={k:v for k,v in page['reviewState'].items() if k not in {'working','resources'}}
    page.update(revision=revision(path),recordPath=str(path))
    return page


def read_resource(data_dir, project, args):
    page = read_page(data_dir, project)
    if page is None:
        raise ValueError('这个项目尚未整理内容页。')
    card = next((c for c in page['cards'] if c['id'] == args['cardId']), None)
    resource = next((r for r in card['resources'] if r['id'] == args['resourceId']), None) if card else None
    if resource is None:
        raise ValueError('找不到这项资料，请刷新内容页。')
    path = resource_path(project, resource)
    if not path.exists():
        raise ValueError('源文件已移动或删除，原始记录仍保留。')
    return path


def preview_resource(path):
    if not path.is_file():
        return {'type': 'unavailable', 'message': '这是一个文件包，可在 Finder 中打开。'}
    if path.stat().st_size > 15 * 1024 * 1024:
        return {'type': 'unavailable', 'message': '文件较大，可在 Finder 中查看。'}
    if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
        return {'type': 'image', 'data': 'data:' + mimetypes.guess_type(path)[0] + ';base64,' + base64.b64encode(path.read_bytes()).decode()}
    if path.suffix.lower() in {'.docx','.xlsx','.pdf'}:
        from project_search import document_text
        text=document_text(path)
        return {'type':'text','text':text[:100_000],'truncated':len(text)>100_000,'markdown':False}
    if path.suffix.lower() in {'.md', '.txt', '.srt', '.tsv', '.csv', '.fcpxml', '.json'}:
        with path.open() as stream:
            text = stream.read(100_001)
        return {'type': 'text', 'text': text[:100_000], 'truncated': len(text) > 100_000, 'markdown': path.suffix.lower() == '.md'}
    return {'type': 'unavailable', 'message': '此文件可在 Finder 中定位，再用对应应用打开。'}


def resource_action(data_dir, project, action, args):
    path = read_resource(data_dir, project, args)
    if action == 'pagePreview':
        viewed=version_stamp(path)
        result=preview_resource(path)
        if viewed!=version_stamp(path):raise ValueError('读取期间文件发生变化，请点击“刷新预览”重试。')
        return {**result,'versionStamp':viewed}
    if action == 'pageReveal':
        subprocess.run(['open', '-R', str(path)], check=True)
        return {'opened': True}
    if action == 'pageThumbnail':
        if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
            raise ValueError('这项资料不是图片。')
        key = hashlib.sha256(f'{path}:{path.stat().st_mtime_ns}'.encode()).hexdigest()
        destination = Path(data_dir) / 'thumbnails' / f'page-{key}.png'
        if not destination.exists():
            destination.parent.mkdir(exist_ok=True)
            subprocess.run(['/usr/bin/sips', '-Z', '900', '-s', 'format', 'png', str(path), '--out', str(destination)], check=True, capture_output=True, timeout=20)
        return {'data': 'data:image/png;base64,' + base64.b64encode(destination.read_bytes()).decode()}
    raise ValueError('不支持的资料操作。')
