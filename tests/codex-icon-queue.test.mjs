import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm,readdir} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {requestCodexWake,consumeCodexWakeRequests} from '../scripts/codex-icon-queue.mjs';

test('wake request runs in consumer and reports completion to requester',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'icon-queue-'));
 try{
  const startedAt=Date.now();let received;
  const pending=requestCodexWake(root,startedAt,{timeoutMs:2000});
  for(let i=0;i<100;i++){
   let names=[];try{names=await readdir(path.join(root,'data/icon-requests'));}catch(e){if(e.code!=='ENOENT')throw e;}
   if(names.some(n=>n.endsWith('.request.json')))break;
   await new Promise(r=>setTimeout(r,5));
  }
  await consumeCodexWakeRequests(root,async(r,t)=>{received={r,t};});
  assert.deepEqual(await pending,{ok:true});assert.deepEqual(received,{r:root,t:startedAt});
 }finally{await rm(root,{recursive:true,force:true});}
});
test('consumer preserves icon failure and rejects expired playback without playing it',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'icon-queue-'));const dir=path.join(root,'data/icon-requests');
 try{
  await mkdir(dir,{recursive:true});
  await writeFile(path.join(dir,'abc.request.json'),JSON.stringify({startedAt:Date.now()}));
  await consumeCodexWakeRequests(root,async()=>{throw Error('macOS denied icon update');});
  assert.equal(JSON.parse(await readFile(path.join(dir,'abc.result.json'),'utf8')).error,'macOS denied icon update');
  await writeFile(path.join(dir,'def.request.json'),JSON.stringify({startedAt:Date.now()-40000}));
  let played=false;await consumeCodexWakeRequests(root,async()=>{played=true;});
  assert.equal(played,false);assert.match(JSON.parse(await readFile(path.join(dir,'def.result.json'),'utf8')).error,/过期/);
 }finally{await rm(root,{recursive:true,force:true});}
});
