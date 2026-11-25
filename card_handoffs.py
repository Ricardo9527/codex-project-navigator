"""Link a sent native card draft using only the first turn of that conversation."""
import json
from session_files import open_session, session_path


def _card_from_attachment(output):
    if not isinstance(output, list):
        return None
    for part in output:
        if not isinstance(part, dict) or part.get('type') != 'input_text':
            continue
        try:
            attachment = json.loads(part['text'])
            if not isinstance(attachment, dict) or (
                attachment.get('kind'), attachment.get('source'), attachment.get('server')
            ) != ('model_context', 'mcp_app', 'project-navigator-flow'):
                continue
            # Both previously opened drafts and new drafts carry this exported snapshot.
            _, marker, body = attachment['text'].partition('# 项目记录引用\n')
            if marker:
                snapshot, _ = json.JSONDecoder().raw_decode(body.split('```json\n', 1)[1])
                return snapshot['project']['id'], snapshot['card']['id']
        except (ValueError, IndexError, KeyError, TypeError, AttributeError):
            continue


def link_sent(hub, thread_id):
    with hub.codex() as db:
        row = db.execute('SELECT cwd,project_id,rollout_path FROM threads WHERE id=?', (thread_id,)).fetchone()
    if row is None or not row['rollout_path']:
        return {'retry': True}
    owner = hub.owner(row['cwd'], row['project_id'])
    if not owner:
        return {'linked': False}
    path = session_path(row['rollout_path'])
    if not path.is_file():
        return {'retry': True}
    calls = set()
    card = None
    with open_session(path) as stream:
        for line in stream:
            if not line.endswith('\n'):
                break
            event = json.loads(line)
            item = event.get('payload', {})
            if event.get('type') == 'event_msg' and item.get('type') == 'task_started':
                if not card or card[0] != owner:
                    return {'linked': False}
                hub.dispatch('linkCardThread', {'projectId': owner, 'cardId': card[1], 'threadId': thread_id})
                return {'linked': True}
            if event.get('type') != 'response_item':
                continue
            if item.get('type') == 'message' and item.get('role') == 'assistant':
                return {'linked': False}  # Older sessions without a native first-turn boundary.
            if item.get('type') == 'function_call' and item.get('name') == 'untrusted_input':
                calls.add(item['call_id'])
            elif item.get('type') == 'function_call_output' and item.get('call_id') in calls:
                card = _card_from_attachment(item.get('output')) or card
    return {'retry': True}
