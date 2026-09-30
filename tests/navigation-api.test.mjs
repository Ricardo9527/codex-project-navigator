import test from 'node:test';
import assert from 'node:assert/strict';
import {callLibrary,operationTimeout} from '../experimental/project-navigator/api-client.mjs';
test('API preserves business errors and gives the file chooser its interactive timeout',async()=>{
 assert.equal(operationTimeout('chooseResource'),300000);
 assert.equal(operationTimeout('pagePreview'),60000);
 await assert.rejects(callLibrary('pagePreview',{},async()=>({ok:false,status:400,json:async()=>({error:'资料入口已被移除'})})),/资料入口已被移除/);
 assert.deepEqual(await callLibrary('chooseResource',{},async()=>({ok:true,json:async()=>({result:{cancelled:true}})})),{cancelled:true});
});
