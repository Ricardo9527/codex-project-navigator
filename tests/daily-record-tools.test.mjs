import test from 'node:test';
import assert from 'node:assert/strict';
import {z} from 'zod';
import {registerDailyTools} from '../experimental/project-navigator/daily-tools.mjs';

test('daily forms are agent-visible, typed and forward only a small delta',async()=>{
 const tools=new Map(),calls=[];
 registerDailyTools({registerTool(name,definition,handler){tools.set(name,{definition,handler});}},async(action,args)=>{calls.push({action,args});return {saved:true,revision:'r',cardIds:['work']};});
 const prepare=tools.get('prepare_daily_record'),save=tools.get('save_daily_record');
 assert.equal(prepare.definition._meta,undefined);assert.equal(save.definition._meta,undefined);
 assert.equal(save.definition.annotations.idempotentHint,true);
 const schema=z.object(save.definition.inputSchema);
 const delta={projectId:'p',scopeId:'b50eab25-9f1e-4a41-89a2-e07ea41126eb',threadCoverage:'complete',updates:[{cardId:'work',deliveries:[{assetId:'asset'}]}]};
 assert.equal(schema.safeParse({...delta,threadCoverage:undefined}).success,false);
 assert.equal(schema.safeParse({...delta,updates:[{cardId:'work',changes:{madeUp:'field'}}]}).success,false);
 const result=await save.handler(schema.parse(delta));
 assert.deepEqual(calls,[{action:'saveDailyRecord',args:delta}]);
 assert.equal(result.structuredContent.saved,true);
 assert.equal(result.structuredContent.contentPage,undefined);
});
