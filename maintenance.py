"""Recoverable ownership for project maintenance launches and native tasks."""
from contextlib import contextmanager
import fcntl
import json
import time
import uuid
from pathlib import Path
import project_records as records


@contextmanager
def jobs_file(hub):
    path=hub.data_dir/'maintenance.json'
    with hub.lock,(hub.data_dir/'.maintenance.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        jobs=json.loads(path.read_text()) if path.exists() else {}
        before=json.dumps(jobs,sort_keys=True)
        yield jobs
        if json.dumps(jobs,sort_keys=True)!=before:
            temp=path.with_suffix('.tmp');temp.write_text(json.dumps(jobs,ensure_ascii=False,indent=2));temp.replace(path)


def native_state(hub, thread_id):
    with hub.codex() as db:row=db.execute('SELECT rollout_path FROM threads WHERE id=?',(thread_id,)).fetchone()
    if not row:return 'missing'
    path=Path(row['rollout_path'])
    if not path.is_file():return 'unknown'
    # Lifecycle events are read-only and contain the native turn's actual end state.
    state='unknown'
    with path.open() as stream:
        for line in stream:
            if not line.endswith('\n'):break
            event=json.loads(line);payload=event.get('payload',{})
            if event.get('type')!='event_msg':continue
            kind=payload.get('type')
            if kind=='task_started':state='running'
            elif kind in {'task_complete','task_completed'}:state='finished'
            elif kind in {'turn_aborted','task_aborted','turn_cancelled'}:state='interrupted'
    return state


def launched_thread(hub, project_id, job):
    with hub.codex() as db:
        rows=db.execute('SELECT id,cwd,project_id,rollout_path FROM threads WHERE updated_at>=? ORDER BY updated_at DESC',(job['startedAt']-1,)).fetchall()
    for row in rows:
        if hub.owner(row['cwd'],row['project_id'])!=project_id:continue
        path=Path(row['rollout_path'])
        if path.is_file() and job['jobId'] in hub.messages(path):return row['id']
    return None


def reconcile(hub, project, job):
    if not job:return None
    if job.get('state') in {'pending','cancelled'} and not job.get('threadId'):
        found=launched_thread(hub,project['id'],job)
        if found:
            job.update(threadId=found,state='running')
            job['threadIds']=sorted(set(job.get('threadIds',[]))|{found})
        elif job['state']=='pending' and time.time()-job['startedAt']>60:
            job.update(state='interrupted',reason='上次维护未成功启动，可继续整理。')
    if job.get('state')=='running' and job.get('threadId'):
        state=records.checkpoint_state(hub.data_dir,project) or {}
        if job.get('batchId') and state.get('lastScope')==job['batchId']:
            job.update(state='completed',finishedAt=int(time.time()))
        else:
            native=native_state(hub,job['threadId'])
            if native in {'finished','interrupted','missing'}:
                job.update(state='interrupted',reason='上次任务已结束，整理清单尚未完成；点击更新继续。')
    return job


def status(hub, project):
    with jobs_file(hub) as jobs:return reconcile(hub,project,jobs.get(project['id']))


def update(hub, project, action, args):
    with jobs_file(hub) as jobs:
        job=jobs.get(project['id'])
        if not job or job['jobId']!=args['jobId']:raise ValueError('维护任务已变化，请重新读取。')
        if action=='markMaintenance':
            thread=hub.thread(args['threadId'])
            if hub.owner(thread['cwd'],thread['project_id'])!=project['id']:raise ValueError('维护对话不属于项目。')
            job.update(threadId=thread['id'],state='running')
            job['threadIds']=sorted(set(job.get('threadIds',[]))|{thread['id']})
        elif action=='cancelMaintenanceLaunch':
            reconcile(hub,project,job)
            if job['state']=='pending':job.update(state='cancelled',reason='启动已取消，可重新更新。')
        else:
            state=args.get('state','completed')
            if state not in {'completed','failed'}:raise ValueError('无效的维护结束状态。')
            checkpoint=records.checkpoint_state(hub.data_dir,project) or {}
            if state=='completed' and job.get('batchId') and checkpoint.get('lastScope')!=job['batchId']:
                raise ValueError('本次整理清单尚未完成，不能标记完成。')
            job.update(state=state,finishedAt=int(time.time()))
    return {'saved':True}


def begin(hub, project):
    with jobs_file(hub) as jobs:
        previous=reconcile(hub,project,jobs.get(project['id'])) or {}
        if previous.get('state') in {'pending','running'}:
            if previous.get('threadId'):return {'existingThreadId':previous['threadId']}
            raise ValueError('项目维护正在启动，请稍候。')
        batch=hub.prepare_record_batch(project)
        if batch.get('noChanges'):return batch
        context=records.export_context(project)
        job_id=str(uuid.uuid4())
        jobs[project['id']]={'jobId':job_id,'batchId':batch['batchId'],'state':'pending','threadIds':previous.get('threadIds',[]),'startedAt':int(time.time())}
    root=Path(__file__).resolve().parent
    # The full scope remains on disk; the prompt points to it instead of embedding an unbounded JSON list.
    scope_path=hub.data_dir/'review-batches'/(batch['batchId']+'.json')
    mode='首次整理' if batch['initialReview'] else '更新项目记录'
    context.update(project=project,jobId=job_id,maintenanceContextWindows=context_windows(),prompt=f'''请为这个项目{mode}。先读 {root}/skills/project-records/SKILL.md。
本次完整待整理清单：{scope_path}。用 python3 "{root}/scripts/libraryctl.py" reviewScope --project {project['id']} --json '{{"batchId":"{batch['batchId']}"}}' 分页读取；分段只用于阅读和保存，不作为结束理由。持续完成本次未整理范围，保留人工修改，使用清单给出的对话时间登记实际已读位置。
完成后按 Skill 用本次 batchId、head 与保存后的 revision 调用 checkpoint。deliveryGaps 是成果入口缺口；补齐或记录具体处理结论后再提交检查点。首次建立基线后检查该项目独立周检是否已注册，按 Skill 自动接入。
全部完成后调用 finishMaintenance --project {project['id']} --json '{{"jobId":"{job_id}"}}'。整理线程保留，由用户手动归档。真实阻塞则保存进度，说明剩余事项并以 state=failed 结束，保留线程。维护会话不是业务卡片。''')
    return context


def context_windows():
    """Use advertised model limits only for the dedicated maintenance composer."""
    path=Path.home()/'.codex/models_cache.json'
    if not path.exists():return {}
    models=json.loads(path.read_text())['models']
    return {m['slug']:{'model_context_window':m['max_context_window'],
                       'model_auto_compact_token_limit':int(m['max_context_window']*min(.90,m.get('effective_context_window_percent',95)/100))}
            for m in models if m.get('max_context_window',0)>m.get('context_window',0)}


def scheduled(hub, project, thread_id):
    hub.register_scheduled_maintenance(project['id'],thread_id)
    with jobs_file(hub) as jobs:
        previous=reconcile(hub,project,jobs.get(project['id'])) or {}
        if previous.get('state') in {'pending','running'}:
            if previous.get('threadId')==thread_id:
                return records.read_batch(hub.data_dir,previous['batchId'])
            return {'existingThreadId':previous.get('threadId'),'alreadyRunning':True}
        batch=hub.prepare_record_batch(project)
        if batch.get('noChanges'):return batch
        jobs[project['id']]={'jobId':str(uuid.uuid4()),'batchId':batch['batchId'],'state':'running','threadId':thread_id,
                            'threadIds':sorted(set(previous.get('threadIds',[]))|{thread_id}),'startedAt':int(time.time())}
    return batch
