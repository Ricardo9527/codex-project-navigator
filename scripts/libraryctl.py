"""Local API access for project handoffs and agent-authored result records."""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

parser=argparse.ArgumentParser(description='读写本地资料索引；不修改 Codex 对话数据库。')
parser.add_argument('action',choices=['status','overview','record','ensureRecord','saveRecord','updateCard','changes','checkpoint','prepareBatch','maintenanceScan','finishMaintenance','reviewScope','reviewThread','reviewAssets','reviewDeliveryGaps','resolveDeliveryGap','registerDelivery','registerResource','adoptResource','automationPlan','linkAutomation'])
parser.add_argument('--project',help='项目 ID、项目名称或绝对目录；省略时使用当前目录')
parser.add_argument('--offline',action='store_true',help='直接使用本地记录服务模块')
parser.add_argument('--json',help='JSON 参数；也可传 - 从 stdin 读取',default='{}')
parser.add_argument('--maintenance-thread',help='仅独立维护任务使用；current 表示当前 Codex 会话')
args=parser.parse_args()
payload=json.load(sys.stdin) if args.json=='-' else json.loads(args.json)
if args.maintenance_thread:
    if args.action!='prepareBatch':parser.error('--maintenance-thread 只用于 prepareBatch')
    thread_id=os.environ.get('CODEX_THREAD_ID') if args.maintenance_thread=='current' else args.maintenance_thread
    if not thread_id:parser.error('当前维护会话 ID 不可用')
    payload['maintenanceThreadId']=thread_id
def call(action,payload):
    if args.offline:
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
        from library import Library
        hub=Library();hub.refresh_projects()
        return hub.dispatch(action,payload)
    request=urllib.request.Request('http://127.0.0.1:47832/api',data=json.dumps(dict(action=action,args=payload)).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=60) as response:
        result=json.load(response)
    if 'error' in result:raise ValueError(result['error'])
    return result['result']
if args.action not in {'status','overview','maintenanceScan'} and 'projectId' not in payload:
    projects=call('overview',{})['projects']
    selection=args.project or str(Path.cwd())
    matches=[p for p in projects if selection in [p['id'],p['name'],p['path']]]
    if len(matches)!=1:raise ValueError('请使用 --project 指定唯一的项目 ID 或目录。')
    payload['projectId']=matches[0]['id']
print(json.dumps(call(args.action,payload),ensure_ascii=False,indent=2))
