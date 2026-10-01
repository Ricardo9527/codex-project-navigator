import test from 'node:test';
import assert from 'node:assert/strict';
import {waitForCodexIconPage} from '../scripts/codex-icon-readiness.mjs';

test('cold start reacquires a replaced renderer after context destruction',async()=>{
 let clock=0,reads=0,attempts=0;const closed=[],configured=[];
 await waitForCodexIconPage({now:()=>clock,pause:async ms=>{clock+=ms;},fetchTargets:async()=>{
  reads++;return reads===1?[]:[{type:'page',url:'app://-/index.html',webSocketDebuggerUrl:'target-'+reads}];
 },connect:url=>({url,close(){closed.push(url)}}),configure:async client=>{
  configured.push(client.url);attempts++;
  if(attempts===1)return false;
  if(attempts===2)throw Error('Execution context was destroyed.');
  return true;
 }});
 assert.deepEqual(configured,['target-2','target-3','target-4']);
 assert.deepEqual(closed,configured);
});
test('real settings errors fail promptly and preserve the error',async()=>{
 let closed=false;
 await assert.rejects(waitForCodexIconPage({fetchTargets:async()=>[{type:'page',url:'app://-/index.html',webSocketDebuggerUrl:'target'}],connect:()=>({close(){closed=true}}),configure:async()=>{throw new TypeError('Setting permission denied')},pause:async()=>assert.fail('must not retry')}),/Setting permission denied/);
 assert.equal(closed,true);
});
test('startup deadline is bounded and retains the last lifecycle error',async()=>{
 let clock=0;
 await assert.rejects(waitForCodexIconPage({timeoutMs:200,now:()=>clock,pause:async ms=>{clock+=ms},fetchTargets:async()=>[{type:'page',url:'app://-/index.html',webSocketDebuggerUrl:'target'}],connect:()=>({close(){}}),configure:async()=>{throw Error('Execution context was destroyed.')}}),/最后状态：Execution context was destroyed/);
 assert.equal(clock,200);
});
