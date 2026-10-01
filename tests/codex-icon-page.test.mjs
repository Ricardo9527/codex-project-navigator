import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {dockPreferenceExpression} from '../scripts/codex-icon-page.mjs';
import vm from 'node:vm';

test('icon settings bridge works without page crypto and assigns distinct request IDs',async()=>{
 const expression=dockPreferenceExpression('codex-system');
 const listeners=new Set(),requests=[];
 const window={addEventListener:(type,fn)=>listeners.add(fn),removeEventListener:(type,fn)=>listeners.delete(fn),electronBridge:{sendMessageFromView:async request=>{
  requests.push(request);
  queueMicrotask(()=>{for(const fn of [...listeners])fn({data:{type:'fetch-response',requestId:request.requestId,responseType:'success',bodyJsonString:JSON.stringify(request.url.endsWith('get-setting')?{value:'app-default'}:{success:true})}});});
 }}};
 assert.equal(await vm.runInNewContext(expression,{window,document:{readyState:'complete',querySelector:()=>({})},setTimeout,clearTimeout}),true);
 assert.equal(requests.length,2);
 assert.notEqual(requests[0].requestId,requests[1].requestId);
 assert.equal(JSON.parse(requests[1].body).value,'codex-system');
 assert.equal(listeners.size,0);
});
