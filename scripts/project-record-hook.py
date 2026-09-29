"""Provide a project-record entry point when a conversation starts."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from library import Library
import project_records as records


def handle(event, hub):
    if event['hook_event_name'] != 'SessionStart':
        return {}
    hub.refresh_projects()
    project_id = hub.owner(event['cwd'])
    if not project_id:
        try:
            thread = hub.thread(event['session_id'])
            project_id = hub.owner(event['cwd'], thread['project_id'])
        except ValueError:
            return {}
    if not project_id:
        return {}
    path = records.record_path(hub.project(project_id))
    text = f'项目记录入口：{path}。已有记录时先读相关部分；尚无记录时，在首轮实质工作中建立。重要成果、决定或待续事项按 {ROOT}/skills/project-records/SKILL.md 维护。'
    return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': text}}


if __name__ == '__main__':
    try:
        event = json.load(sys.stdin)
        print(json.dumps(handle(event, Library()) if event['hook_event_name']=='SessionStart' else {}, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'systemMessage': '项目入口读取失败：'+str(error)}, ensure_ascii=False))
        raise SystemExit(1)
