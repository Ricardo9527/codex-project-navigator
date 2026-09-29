"""Prepare a native per-project automation; the Agent executes the app tool."""
import json
from pathlib import Path
import tomllib
import project_records as records


def catalog():
    root=Path.home()/'.codex/automations'
    return [tomllib.loads(path.read_text()) for path in root.glob('*/automation.toml')]


def matching(project):
    return [a for a in catalog() if a.get('kind')=='cron' and (a.get('target',{}).get('project_id')==project['id'] or project['path'] in a.get('cwds',[])) and 'project-records/SKILL.md' in a.get('prompt','')]


def plan(hub, project):
    found=matching(project)
    if found:return {'needsCreate':False,'automations':[{'id':a['id'],'status':a['status']} for a in found]}
    if not records.checkpoint_state(hub.data_dir,project):return {'needsCreate':False,'reason':'首次整理完成后接入周检。'}
    busy={a.get('rrule') for a in catalog() if a.get('status')=='ACTIVE'}
    rule=next(f'FREQ=WEEKLY;BYDAY={day};BYHOUR={hour};BYMINUTE={minute}' for day in ['SU','MO','TU','WE','TH','FR','SA'] for hour in [20,21,22] for minute in [0,20,40] if f'FREQ=WEEKLY;BYDAY={day};BYHOUR={hour};BYMINUTE={minute}' not in busy)
    config=tomllib.loads((Path.home()/'.codex/config.toml').read_text())
    root=Path(__file__).resolve().parent
    prompt=f'只维护绑定项目 {project["name"]}（{project["id"]}）。读取 {root}/skills/project-records/SKILL.md，执行 python3 "{root}/scripts/libraryctl.py" prepareBatch --project {project["id"]} --maintenance-thread current。没有变化或已有维护任务时结束；否则用 reviewScope 分段读取完整清单并持续处理，保存后结果立即可查。不要按数量、用时或历史日期排除未完成内容。全部完成后调用 checkpoint，真实阻塞明确报告并保留进度；不自动 push，不整理其他项目。维护线程保留，由用户手动归档。'
    return {'needsCreate':True,'project':project,'tool':'automation_update','arguments':{'mode':'create','kind':'cron','name':project['name']+' · 每周记录检查','projectId':project['id'],'executionEnvironment':'local','destination':'local','model':config.get('model','gpt-6-astra'),'reasoningEffort':config.get('model_reasoning_effort','high'),'status':'ACTIVE','rrule':rule,'prompt':prompt}}


def link(project,args):
    found=next((a for a in matching(project) if a['id']==args['automationId']),None)
    if not found:raise ValueError('未找到绑定该项目的记录周检任务。')
    record=json.loads(records.record_path(project).read_text())
    record['maintenanceAutomation']={'id':found['id'],'status':found['status']}
    result=records.save(project,record,args['expectedRevision'])
    with records.locked(project):
        if records.revision(records.record_path(project))!=result['revision']:raise ValueError('记录已变化，请重新读取后登记周检。')
        result['commit']=records.commit_record(project,'docs: register project record maintenance')
    return result
