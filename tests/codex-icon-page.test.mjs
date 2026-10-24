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

test('early cold-start refresh needs only the preload bridge and no rendered page or settings round trip',async()=>{
 const expression=dockPreferenceExpression('codex-system',{early:true,refresh:true});
 const listeners=new Set(),requests=[];
 const window={addEventListener:(t,f)=>listeners.add(f),removeEventListener:(t,f)=>listeners.delete(f),electronBridge:{sendMessageFromView:async req=>{
  requests.push(req);queueMicrotask(()=>{for(const fn of [...listeners])fn({data:{type:'fetch-response',requestId:req.requestId,responseType:'success',bodyJsonString:'{"success":true}'}})});
 }}};
 assert.equal(await vm.runInNewContext(expression,{window,setTimeout,clearTimeout}),true);
 assert.equal(requests.length,1);assert.equal(requests[0].url,'vscode://codex/set-configuration');assert.equal(listeners.size,0);
});

test('31345 refresh uses the settings service even when the preference is already selected',async()=>{
 const calls=[];
 const expression=dockPreferenceExpression('codex-system',{early:true,refresh:true}).replace('await import(', 'await loadSettingsModule(');
 const window={electronBridge:{sendMessageFromView(){throw Error('legacy settings route must not be called')},getDesktopUserAgent:()=> 'Codex Desktop/26.1021.31345 (Mac OS; arm64)'}};
 const loadSettingsModule=async url=>{calls.push(url);return {zit(){calls.push('initialize')},async Bit(){throw Error('refresh does not require a settings read')},async Yit(setting,value){calls.push({setting,value})}}};
 assert.equal(await vm.runInNewContext(expression,{window,loadSettingsModule}),true);
 assert.equal(calls[0],'app://-/assets/app-shared-2cae01273bae.js');
 assert.equal(calls[1],'initialize');
 assert.equal(calls[2].setting.key,'dock-icon-preference');
 assert.equal(calls[2].value,'codex-system');
});
