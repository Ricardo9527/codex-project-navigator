"""Prepare a native per-project automation; the Agent executes the app tool."""
import json
from pathlib import Path
import tomllib
import project_records as records
import maintenance


def catalog():
    root=Path.home()/'.codex/automations'
    return [tomllib.loads(path.read_text()) for path in root.glob('*/automation.toml')]


def matching(project, hub):
    found=[]
    for task in catalog():
        if 'project-records/SKILL.md' not in task.get('prompt',''):continue
        if task.get('kind')=='heartbeat':
            try:thread=hub.thread(task['target_thread_id'])
            except ValueError:continue
            if hub.owner(thread['cwd'],thread['project_id'])==project['id']:found.append(task)
        elif task.get('kind')=='cron':
            target=task.get('target',{}).get('project_id')
            if (hub.aliases.get(target,target)==project['id'] if target else project['path'] in task.get('cwds',[])):
                found.append(task)
    return found


def plan(hub, project):
    found=matching(project,hub)
    if not records.checkpoint_state(hub.data_dir,project):return {'needsCreate':False,'reason':'首次整理完成后接入周检。'}
    thread_id=maintenance.management_thread(hub,project,maintenance.status(hub,project))
    if not thread_id:return {'needsCreate':False,'reason':'先在项目固定管理对话中开始维护，再绑定每周唤醒。'}
    if found and all(a.get('kind')=='heartbeat' and a.get('target_thread_id')==thread_id for a in found):
        return {'needsCreate':False,'automations':[{'id':a['id'],'status':a['status']} for a in found]}
    busy={a.get('rrule') for a in catalog() if a.get('status')=='ACTIVE'}
    rule=found[0]['rrule'] if found else next(f'FREQ=WEEKLY;BYDAY={day};BYHOUR={hour};BYMINUTE={minute}' for day in ['SU','MO','TU','WE','TH','FR','SA'] for hour in [20,21,22] for minute in [0,20,40] if f'FREQ=WEEKLY;BYDAY={day};BYHOUR={hour};BYMINUTE={minute}' not in busy)
    root=Path(__file__).resolve().parent
    prompt=f'用户明确要求精简维护、减少耗时：只补实际缺口，已处理内容不重读，卡片用短句分行；详细过程看原对话，必要核对完成后立即收尾。只维护绑定项目 {project["name"]}（{project["id"]}）。读取 {root}/skills/project-records/SKILL.md，执行 python3 "{root}/scripts/libraryctl.py" prepareBatch --project {project["id"]} --maintenance-thread current。没有变化或已有维护任务时结束；否则用 reviewScope 分段读取完整清单并持续处理，保存后结果立即可查。不要按数量、用时或历史日期排除未完成内容。全部完成后调用 checkpoint，真实阻塞明确报告并保留进度；不自动 push，不整理其他项目。维护线程保留，由用户手动归档。'
    arguments={'mode':'update' if found else 'create','kind':'heartbeat','name':found[0]['name'] if found else project['name']+' · 每周记录检查','targetThreadId':thread_id,'destination':'thread','status':found[0]['status'] if found else 'ACTIVE','rrule':rule,'prompt':prompt}
    if found:
        arguments['id']=found[0]['id']
        if 'notification_policy' in found[0]:arguments['notificationPolicy']=found[0]['notification_policy']
    return {'needsCreate':not found,'needsUpdate':bool(found),'project':project,'tool':'automation_update','arguments':arguments}


def link(hub,project,args):
    found=next((a for a in matching(project,hub) if a['id']==args['automationId']),None)
    if not found:raise ValueError('未找到绑定该项目的记录周检任务。')
    record=json.loads(records.record_path(project).read_text())
    if found.get('kind')!='heartbeat' or found.get('target_thread_id')!=record.get('maintenanceThreadId'):
        raise ValueError('周检必须绑定当前项目的固定管理对话。')
    record['maintenanceAutomation']={'id':found['id'],'status':found['status']}
    result=records.save(project,record,args['expectedRevision'])
    with records.locked(project):
        if records.revision(records.record_path(project))!=result['revision']:raise ValueError('记录已变化，请重新读取后登记周检。')
        result['commit']=records.commit_record(project,'docs: register project record maintenance')
    return result
