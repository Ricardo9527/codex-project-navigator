import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';

export async function runSingleDraftTrial(root,payload,request,prepare){
 if(payload.kind==='source')return prepare(payload);
 if(payload.kind==='maintenance'){
  const jobs=JSON.parse(await readFile(path.join(root,'data/maintenance.json'),'utf8'));
  const job=jobs[payload.project.id];
  if(job?.jobId!==payload.jobId||job.state!=='pending')throw Error('项目维护任务已变化，请重新点击更新。');
  return prepare(payload);
 }
 const file=path.join(root,'experimental/project-navigator/draft-trial.json');
 const trial=JSON.parse(await readFile(file,'utf8'));
 if(!trial.enabled||(!['explicit','registered'].includes(trial.mode)&&trial.remainingUses!==1))throw Error('原生草稿接入未启用，或单次试验已结束。');
 if(request.createdAt<trial.armedAt)throw Error('这是启用试验前的旧请求，未执行。');
 if(trial.mode==='registered')return prepare(payload);
 if(payload.project.id!==trial.projectId||payload.nativeProjectId!==trial.nativeProjectId||trial.mode!=='explicit'&&payload.cardId!==trial.cardId)
  throw Error('请求不属于已启用的项目或验证卡片。');
 if(trial.mode==='explicit')return prepare(payload);
 await writeFile(file,JSON.stringify({...trial,enabled:false,remainingUses:0,attemptedAt:Date.now()},null,2)+'\n');
 return prepare(payload);
}
