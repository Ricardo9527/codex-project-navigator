"""Controlled recovery test, restricted to this library's own processes."""
import argparse
import json
import os
from pathlib import Path
import signal
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def health():
    with urllib.request.urlopen('http://127.0.0.1:47832/health',timeout=2) as response:
        result=json.load(response)
    assert result['service']=='codex-library'
    return result

parser=argparse.ArgumentParser()
parser.add_argument('--manager',action='store_true')
args=parser.parse_args()
before=health()
runtime=json.loads((ROOT/'data/runtime.json').read_text())
target=runtime['pid'] if args.manager else before['pid']
os.kill(target,signal.SIGKILL if args.manager else signal.SIGTERM)
started=time.monotonic()
while time.monotonic()-started<35:
    time.sleep(.5)
    try:
        after=health()
        current=json.loads((ROOT/'data/runtime.json').read_text())
        if after['pid']!=before['pid'] and current['connected'] and (not args.manager or current['pid']!=runtime['pid']):
            print(json.dumps(dict(test='manager' if args.manager else 'service',recovered=True,
                seconds=round(time.monotonic()-started,1),oldService=before['pid'],newService=after['pid'],
                oldManager=runtime['pid'],newManager=current['pid'])))
            break
    except (OSError,ValueError):
        continue
else:
    raise RuntimeError('资料库在 35 秒内没有完成恢复。')
