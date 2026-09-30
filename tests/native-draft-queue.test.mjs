import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readdir,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {requestNativeDraft,consumeNativeDrafts} from '../scripts/native-draft-queue.mjs';

const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
test('native draft requests preserve the target project and propagate preparation errors',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'native-draft-'));
 const payload={project:{id:'library-id',path:'/target/project'},nativeProjectId:'native-id',cardId:'card',context:{text:'卡片背景'}};
 try{
  for(const fail of [false,true]){
   let claimed=false;
   const requested=requestNativeDraft(root,payload,{timeoutMs:2000});
   const checked=fail?assert.rejects(requested,/原生上下文缺失/):requested;
   for(let i=0;i<50&&!claimed;i++){
    await consumeNativeDrafts(root,async actual=>{
     claimed=true;assert.deepEqual(actual,payload);
     if(fail)throw Error('原生上下文缺失');
     return {draftRequested:true,projectPath:actual.project.path,nativeProjectId:actual.nativeProjectId};
    });
    if(!claimed)await sleep(10);
   }
   assert.equal(claimed,true);
   const result=await checked;
   if(!fail)assert.equal(result.nativeProjectId,'native-id');
   assert.deepEqual(await readdir(path.join(root,'data/native-drafts')),[]);
  }
 }finally{await rm(root,{recursive:true,force:true});}
});

test('a timed-out draft request cannot open a composer when the manager later resumes',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'native-draft-'));
 try{
  await assert.rejects(requestNativeDraft(root,{cardId:'card'},{timeoutMs:20}),/未响应/);
  let invoked=false;await consumeNativeDrafts(root,async()=>{invoked=true;});
  assert.equal(invoked,false);
 }finally{await rm(root,{recursive:true,force:true});}
});
