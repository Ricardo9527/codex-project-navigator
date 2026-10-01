import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {idleOnUnloadExpression,finishLibraryIconSession} from '../scripts/codex-icon-session.mjs';
test('library session restores gray defaults only after running blue settles',async()=>{
 const order=[];
 await finishLibraryIconSession({settle:async()=>order.push('blue settled'),restoreGray:async()=>order.push('gray on disk'),installExitHook:async()=>order.push('exit hook')});
 assert.deepEqual(order,['blue settled','gray on disk','exit hook']);
});
test('exit hook requests gray refresh before unload without changing icons on registration',()=>{
 const listeners=new Map(),sent=[];
 const window={addEventListener:(name,fn)=>listeners.set(name,fn),electronBridge:{sendMessageFromView:async message=>{sent.push(message);}}};
 const context={window,console};
 assert.equal(vm.runInNewContext(idleOnUnloadExpression(),context),true);
 assert.equal(sent.length,0);
 vm.runInNewContext(idleOnUnloadExpression(),context);assert.equal(listeners.size,1);
 listeners.get('beforeunload')();
 assert.equal(sent.length,1);assert.equal(sent[0].url,'vscode://codex/set-configuration');
 assert.deepEqual(JSON.parse(sent[0].body),{key:'dock-icon-preference',value:'codex-system'});
});
