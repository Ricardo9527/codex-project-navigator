"""Require a visible result before an active chat can enter daily maintenance."""
import json
from pathlib import Path
import re
from urllib.parse import unquote


class DeliveryNotPublished(ValueError):
    pass


def _reverse_lines(path):
    # Only walk back to the latest turn boundary. Large tool outputs are not parsed.
    with path.open('rb') as stream:
        end=stream.seek(0,2);tail=[];skip_last=True
        while end:
            start=max(0,end-65536);stream.seek(start)
            parts=stream.read(end-start).split(b'\n');end=start
            if len(parts)==1:
                tail.append(parts[0]);continue
            last=parts.pop()
            if skip_last:skip_last=False  # Ignore the empty or partially written last line.
            else:yield b''.join([last,*reversed(tail)])
            tail=[parts.pop(0)]
            yield from reversed(parts)
        if not skip_last:yield b''.join(reversed(tail))


def _published(text):
    if not text.lstrip().startswith('**可用成果**\n'):return False
    if any(m.strip() for m in re.findall(r'^```[^\n]*\n(.*?)\n```[ \t]*$',text,re.M|re.S)):return True
    for angle,plain in re.findall(r'\]\((?:<([^>\n]+)>|([^()\n]+))\)',text):
        path=Path(unquote(angle or plain))
        if path.is_absolute() and path.is_file():return True
    return False


def _check(path):
    # Compacted sessions are closed history; current work uses the live JSONL.
    if path.suffix=='.zst' or not path.is_file() and Path(str(path)+'.zst').is_file():return
    published=False
    for line in _reverse_lines(path):
        if not any(token in line for token in (b'"task_started"',b'"task_complete"',b'"task_completed"',b'"turn_aborted"',b'"task_aborted"',b'"turn_cancelled"',b'"commentary"',b'"final_answer"',b'"final"')):continue
        event=json.loads(line);payload=event.get('payload',{});kind=payload.get('type')
        if event['type']=='event_msg':
            if kind in {'task_complete','task_completed','turn_aborted','task_aborted','turn_cancelled'}:return
            if kind=='task_started':
                if published:return
                raise DeliveryNotPublished('DELIVER_FIRST：先在本轮聊天中以“**可用成果**”单独成行，附可打开的本地成品链接或完整可复制的代码块，再准备或保存维护。只有进度说明时不要重试，也不要改用旧接口绕过。')
        if event['type']=='response_item' and kind=='message' and payload.get('role')=='assistant':
            if payload.get('phase') in {'final','final_answer'}:published=True
            if payload.get('phase')=='commentary':
                text='\n'.join(c.get('text','') for c in payload.get('content',[]))
                if _published(text):published=True


def require_delivery(hub, thread_id, caller_id=None):
    with hub.codex() as db:
        for identity in dict.fromkeys([caller_id or thread_id,thread_id]):
            row=db.execute('SELECT rollout_path FROM threads WHERE id=?',(identity,)).fetchone()
            if row is None:raise ValueError('维护对话已不存在。')
            _check(Path(row['rollout_path']))
