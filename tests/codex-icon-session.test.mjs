import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {removeIdleOnUnloadExpression,finishLibraryIconSession} from '../scripts/codex-icon-session.mjs';
test('finishing a library session keeps running resources blue and updates only the static icon',async()=>{
 const order=[];let runtimeResource='blue';
 await finishLibraryIconSession({settle:async()=>order.push('blue settled'),writeStaticIdle:async()=>{order.push('gray file icon');assert.equal(runtimeResource,'blue')},removePageExitHook:async()=>order.push('remove renderer hook')});
 assert.deepEqual(order,['blue settled','gray file icon','remove renderer hook']);assert.equal(runtimeResource,'blue');
});
test('removes the old unload hook so a renderer reload cannot turn the running icon gray',()=>{
 const handler=()=>assert.fail('old hook must not run');const listeners=new Map([['beforeunload',handler]]);
 const window={__projectLibraryIdleOnUnload:handler,removeEventListener:(name,fn)=>{assert.equal(fn,handler);listeners.delete(name)}};
 assert.equal(vm.runInNewContext(removeIdleOnUnloadExpression(),{window}),true);
 assert.equal(listeners.size,0);assert.equal(window.__projectLibraryIdleOnUnload,undefined);
 assert.equal(vm.runInNewContext(removeIdleOnUnloadExpression(),{window}),true);
});
