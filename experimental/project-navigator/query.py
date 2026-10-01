"""Read the authoritative project record for the native MCP navigation trial."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from content_pages import read_page
from project_records import export_context
from library import Library


def query(args, root, catalog=None):
    root = Path(root).resolve()
    if catalog is None:
        hub = Library()
        hub.refresh_projects()
        catalog = {'projects': hub.projects(), 'aliases': hub.aliases}
    projects = list(catalog['projects'])
    default = next((p for p in projects if Path(p['path']).resolve() == root), None)
    if default is None:
        record_path = root / '.project-library/record.json'
        if record_path.exists():
            raw = json.loads(record_path.read_text())
            default = {'id': raw['projectId'], 'name': root.name, 'path': str(root)}
            projects.append(default)
        elif projects:
            default = projects[0]
        else:
            raise ValueError('请先在 Codex 中添加一个本地项目，再打开项目导航。')
    selected_project = args.get('projectId') or default['id']
    selected_project = catalog.get('aliases', {}).get(selected_project, selected_project)
    project = next((p for p in projects if p['id'] == selected_project), None)
    if project is None:
        raise ValueError('找不到这个项目，请刷新项目列表。')
    page = read_page(None, project)
    selected = args.get('cardId')
    if selected:
        card = next((c for c in (page or {}).get('cards', []) if c['id'] == selected), None)
        if card is None:
            raise ValueError('找不到这张卡片，请刷新项目记录。')
    else:
        card = None
    result = {
        'project': project, 'recordPath': str(Path(project['path']) / '.project-library/record.json'),
        'revision': (page or {}).get('revision', ''), 'about': (page or {}).get('about', ''),
        'uninitialized': page is None,
        'projects': [{'id': p['id'], 'name': p['name'], 'path': p['path'], 'hasRecord': (Path(p['path']) / '.project-library/record.json').exists()} for p in projects],
        'categories': (page or {}).get('categories', []),
        'cards': [{'id': c['id'], 'title': c['title'], 'summary': c['summary'], 'categoryIds': c['categoryIds']} for c in (page or {}).get('cards', [])],
        'card': card, 'contentPage': page,
    }
    trial = json.loads((ROOT / 'experimental/project-navigator/draft-trial.json').read_text())
    result['draftTrialEnabled'] = trial['enabled'] and trial.get('remainingUses') == 1
    result['draftTrialCardId'] = trial.get('cardId')
    result['draftTrialId'] = str(trial.get('armedAt', 0))
    result['draftPreparationEnabled'] = trial['enabled'] and sys.platform == 'darwin' and (trial.get('mode') == 'registered' or trial.get('mode') == 'explicit' and trial['projectId'] == project['id'])
    runtime_path = ROOT / 'data/runtime.json'
    result['draftBridgeConnected'] = json.loads(runtime_path.read_text())['connected'] if runtime_path.exists() else False
    if args.get('context'):
        if card is None:
            raise ValueError('请先选择一张卡片。')
        context = export_context(project, selected)
        result['context'] = {**context, 'text': Path(context['path']).read_text()}
    return result


if __name__ == '__main__':
    print(json.dumps(query(json.load(sys.stdin), os.environ.get('PROJECT_NAVIGATOR_ROOT', ROOT)), ensure_ascii=False))
