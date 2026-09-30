import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {runSingleDraftTrial} from '../scripts/native-draft-trial.mjs';

test('trial rejects old or mismatched requests and closes before its only native attempt',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'native-trial-'));
 const folder=path.join(root,'experimental/project-navigator');await mkdir(folder,{recursive:true});
 const file=path.join(folder,'draft-trial.json'),payload={project:{id:'library'},cardId:'card',nativeProjectId:'native'};
 const trial={enabled:true,remainingUses:1,armedAt:100,projectId:'library',cardId:'card',nativeProjectId:'native'};
 try{
  await writeFile(file,JSON.stringify(trial));let calls=0;
  await assert.rejects(runSingleDraftTrial(root,payload,{createdAt:99},()=>{calls++;}),/旧请求/);
  await assert.rejects(runSingleDraftTrial(root,{...payload,cardId:'wrong'},{createdAt:101},()=>{calls++;}),/已启用的项目/);
  assert.equal(calls,0);
  await assert.rejects(runSingleDraftTrial(root,payload,{createdAt:101},async()=>{
   calls++;assert.equal(JSON.parse(await readFile(file,'utf8')).enabled,false);throw Error('native failure');
  }),/native failure/);
  await assert.rejects(runSingleDraftTrial(root,payload,{createdAt:102},()=>{calls++;}),/试验已结束/);
  assert.equal(calls,1);
 }finally{await rm(root,{recursive:true,force:true});}
});

test('explicit mode supports repeated user requests on project cards while rejecting old requests and other projects',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'native-explicit-'));
 const folder=path.join(root,'experimental/project-navigator');await mkdir(folder,{recursive:true});
 const file=path.join(folder,'draft-trial.json');
 const config={mode:'explicit',enabled:true,remainingUses:0,armedAt:100,projectId:'project',nativeProjectId:'service-project'};
 const payload={project:{id:'project'},cardId:'first-card',nativeProjectId:'service-project'};
 try{
  await writeFile(file,JSON.stringify(config));const calls=[];
  const prepare=async p=>{calls.push(p.cardId);return {draftRequested:true};};
  await assert.rejects(runSingleDraftTrial(root,payload,{createdAt:99},prepare),/旧请求/);
  await assert.rejects(runSingleDraftTrial(root,{...payload,project:{id:'another-project'}},{createdAt:101},prepare),/已启用的项目/);
  await runSingleDraftTrial(root,payload,{createdAt:101},prepare);
  await runSingleDraftTrial(root,{...payload,cardId:'second-card'},{createdAt:102},prepare);
  assert.deepEqual(calls,['first-card','second-card']);
  assert.deepEqual(JSON.parse(await readFile(file,'utf8')),config);
 }finally{await rm(root,{recursive:true,force:true});}
});

test('maintenance draft accepts only the current pending job independently of card trials',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'maintenance-draft-'));
 try{
  await mkdir(path.join(root,'data'));
  await writeFile(path.join(root,'data/maintenance.json'),JSON.stringify({project:{jobId:'job',state:'pending'}}));
  const payload={kind:'maintenance',project:{id:'project'},jobId:'job'};let calls=0;
  const prepare=async()=>{calls++;return {draftRequested:true};};
  await assert.rejects(runSingleDraftTrial(root,{...payload,jobId:'old'},{},prepare),/任务已变化/);
  assert.deepEqual(await runSingleDraftTrial(root,payload,{},prepare),{draftRequested:true});
  await writeFile(path.join(root,'data/maintenance.json'),JSON.stringify({project:{jobId:'job',state:'running'}}));
  await assert.rejects(runSingleDraftTrial(root,payload,{},prepare),/任务已变化/);
  assert.equal(calls,1);
 }finally{await rm(root,{recursive:true,force:true});}
});
