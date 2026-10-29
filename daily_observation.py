"""Local timing evidence for daily forms; no prompts, file contents or background work."""
import json
import logging
import time


def _table(db):
    db.execute('CREATE TABLE IF NOT EXISTS daily_observation(id INTEGER PRIMARY KEY,project_id TEXT,scope_id TEXT,action TEXT,started_at REAL,duration_ms REAL,success INTEGER,details TEXT)')


def _write(hub, project, action, started, elapsed, args, result, error):
    updates=args.get('updates',[])
    notes=[line for update in updates for line in update.get('changes',{}).get('notes',[])]
    details={'threadId':args.get('threadId') or result.get('threadId'),
             'inputBytes':len(json.dumps(args,ensure_ascii=False).encode()),
             'outputBytes':len(json.dumps(result,ensure_ascii=False).encode()) if result else 0,
             'updates':len(updates),'noteLines':len(notes),'noteChars':sum(map(len,notes)),
             'deliveries':sum(len(u.get('deliveries',[])) for u in updates),
             'imports':sum(len(u.get('files',[])) for u in updates),
             'replayed':result.get('replayed',False),'errorType':type(error).__name__ if error else None}
    with hub.local() as db:
        _table(db)
        db.execute('INSERT INTO daily_observation(project_id,scope_id,action,started_at,duration_ms,success,details) VALUES (?,?,?,?,?,?,?)',
                   (project['id'],args.get('scopeId') or result.get('scopeId'),action,started,elapsed,int(error is None),json.dumps(details)))


def observe(hub, project, action, args, operation):
    started=time.time();timer=time.perf_counter();result={};failure=None
    try:
        result=operation(hub,project,args)
        return result
    except Exception as error:
        failure=error
        raise
    finally:
        elapsed=round((time.perf_counter()-timer)*1000,3)
        try:_write(hub,project,action,started,elapsed,args,result,failure)
        except Exception:
            logging.exception('日常维护计时记录失败；业务保存结果不变。')
            if failure is None:result['observationWarning']='业务操作已完成，但本次计时记录失败，请查看服务日志。'
        if failure is None:result['measurement']={'backendMs':elapsed,'scopeId':args.get('scopeId') or result.get('scopeId')}


def report(hub, project, args):
    limit=args.get('limit',20)
    if type(limit) is not int or not 1<=limit<=100:raise ValueError('计时记录 limit 需为 1～100。')
    with hub.local() as db:
        _table(db)
        where='project_id=?';values=[project['id']]
        if args.get('scopeId'):where+=' AND scope_id=?';values.append(args['scopeId'])
        rows=db.execute('SELECT * FROM daily_observation WHERE '+where+' ORDER BY id DESC LIMIT ?',(*values,limit)).fetchall()
    return {'events':[{**{k:row[k] for k in ['scope_id','action','started_at','duration_ms','success']},**json.loads(row['details'])} for row in rows],
            'timingBasis':'backendMs 是表单后端执行时间，不包括 Agent 思考、调用前准备或额外文件操作；全轮活动按会话时间线核对。'}
