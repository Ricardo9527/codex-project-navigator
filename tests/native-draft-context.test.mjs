import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

function functionSource(source,name){
 const start=source.indexOf('function '+name+'(');
 assert.notEqual(start,-1,'installed function '+name);
 const opening=source.indexOf('{',source.indexOf('){',start));
 let depth=0,quote=null;
 for(let i=opening;i<source.length;i++){
  const c=source[i];
  if(quote){if(c==='\\'){i++;continue;}if(c===quote)quote=null;continue;}
  if(c==='"'||c==="'"||c==='`'){quote=c;continue;}
  if(c==='{')depth++;
  else if(c==='}'&&--depth===0)return source.slice(start,i+1);
 }
 throw Error('Unterminated installed function '+name);
}

test('native module adapter supports registered desktop builds and rejects unmatched module pairs',async()=>{
 const source=await readFile(new URL('../web/native-draft.js',import.meta.url),'utf8');
 const select=vm.runInNewContext(functionSource(source,'nativeModules')+';nativeModules');
 for(const [initial,shared,draftExport]of [
  ['app-initial-74096abaa6b3.js','app-shared-5d8e744d1fa1.js','CLt'],
  ['app-initial-135a4ef2552c.js','app-shared-eececb2d2eb0.js','kIt'],
  ['app-initial-8a7b00193cb6.js','app-shared-44edd7bfa69c.js','kIt'],
  ['app-initial-576fc7ca620e.js','app-shared-b72e16382796.js','tIt'],
 ]){
  const urls=[initial,shared].map(n=>'app://-/assets/'+n);
  assert.equal(select(urls).draftExport,draftExport);
  assert.equal(select(urls).initialUrl,urls[0]);
 }
 assert.throws(()=>select(['app://-/assets/app-initial-135a4ef2552c.js','app://-/assets/app-shared-5d8e744d1fa1.js']),/需要适配/);
 assert.throws(()=>select(['app://-/assets/app-initial-unknown.js']),/需要适配/);
});

test('the installed desktop adapter targets the actual project draft action',async t=>{
 let archive;
 try{archive=await readFile(process.env.CODEX_DESKTOP_ASAR||'/Applications/ChatGPT.app/Contents/Resources/app.asar');}
 catch(e){if(e.code==='ENOENT'){t.skip('installed desktop bundle is unavailable');return;}throw e;}
 const headerSize=archive.readUInt32LE(4),jsonSize=archive.readUInt32LE(12);
 const assets=JSON.parse(archive.subarray(16,16+jsonSize).toString()).files.webview.files.assets.files;
 const bridge=await readFile(new URL('../web/native-draft.js',import.meta.url),'utf8');
 const select=vm.runInNewContext(functionSource(bridge,'nativeModules')+';nativeModules');
 const build=select(Object.keys(assets).map(n=>'app://-/assets/'+n));
 const entry=assets[build.initialUrl.split('/').at(-1)],offset=8+headerSize+Number(entry.offset);
 const source=archive.subarray(offset,offset+entry.size).toString();
 const exports=source.slice(source.lastIndexOf('export{'));
 const name=exports.match(new RegExp('(\\w+) as '+build.draftExport+'[,}]'))[1];
 const action=functionSource(source,name);
 const sharedEntry=assets[build.sharedUrl.split('/').at(-1)];
 const sharedOffset=8+headerSize+Number(sharedEntry.offset);
 const shared=archive.subarray(sharedOffset,sharedOffset+sharedEntry.size).toString();
 const sharedExports=shared.slice(shared.lastIndexOf('export{'));
 const local=alias=>sharedExports.match(new RegExp('([\\w$]+) as '+(build.sharedExports?.[alias]||alias)+'[,}]'))[1];
 assert.match(functionSource(shared,local('n7t')),/familyBindings\.get/);
 assert.match(functionSource(shared,local('lJt')),/forHost/);
 assert.match(shared,new RegExp(local('dJt')+'=\\w+\\(`AppScope`\\)'));
 assert.ok(shared.includes(local('gTt')+'=X('));
 assert.ok(shared.includes('LOCAL_PROJECTS'));
 assert.match(action,/activeProject:/);assert.match(action,/freshDraft:/);assert.match(action,/prepareNavigation/);
 if(build.maintenanceExport){
  const createName=exports.match(new RegExp('(\\w+) as '+build.maintenanceExport+'[,}]'))[1];
  const create=functionSource(source,createName);
  assert.match(create,/target:/);assert.match(create,/prompt:/);assert.match(create,/environment.type/);
 }
});

test('installed Scope constructor and resolver require real frame fields omitted by the former mock',async t=>{
 let archive;
 try{archive=await readFile(process.env.CODEX_DESKTOP_ASAR||'/Applications/ChatGPT.app/Contents/Resources/app.asar');}
 catch(e){if(e.code==='ENOENT'){t.skip('installed desktop bundle is unavailable');return;}throw e;}
 const headerSize=archive.readUInt32LE(4),jsonSize=archive.readUInt32LE(12);
 const header=JSON.parse(archive.subarray(16,16+jsonSize).toString());
 const entry=header.files.webview.files.assets.files['app-shared-5d8e744d1fa1.js'];
 if(!entry){t.skip('this isolated contract check targets desktop 26.928.20755');return;}
 const offset=8+headerSize+Number(entry.offset);
 const source=archive.subarray(offset,offset+entry.size).toString();
 const names=['zct','iA','yit','Lst','Rst','zst','Nk','Got','Wot','Vst','Kk','Kot','mst','vst','bst','Bst'];
 const sandbox={Map,Set,WeakMap,WeakSet,Symbol,console,
  zot:Symbol('family-key'),wk:Symbol('family-member'),Tk:Symbol('resolve-family'),
  wO:init=>({init}),pit:()=>({}),Cit:class{},
 };
 vm.createContext(sandbox);
 vm.runInContext(names.map(n=>functionSource(source,n)).join('\n'),sandbox);
 const token={id:Symbol('AppScope')};
 const node=sandbox.zct({scope:token,providedValue:{project:'target'},scopeKey:'root',queryClient:{}});
 const chain=new Map([[token.id,node]]);
 const family=sandbox.iA(token,(_,{scope})=>scope);
 const scope=family.resolve(node,chain);
 assert.equal(scope.node,node);
 assert.equal(scope.scope,token);
 assert.equal(typeof scope.get,'function');
 assert.equal(typeof scope.query.setData,'function');
 assert.throws(()=>family.resolve({token},chain),/reading 'get'/);
 assert.ok(node.familyBindings instanceof Map);
 const bridge=await readFile(new URL('../web/native-draft.js',import.meta.url),'utf8');
 vm.runInContext(functionSource(bridge,'findAppScope'),sandbox);
 const animation={get(){throw Error('animation getter must never be used for Scope lookup');}};
 const invalidChain=new Map([[token.id,{token}]]);
 const fiber={tag:10,memoizedProps:{value:animation},return:{tag:10,memoizedProps:{value:invalidChain},return:{tag:10,memoizedProps:{value:chain},return:null}}};
 const match=sandbox.findAppScope(fiber,token);
 assert.equal(match.node,node);
 assert.equal(match.chain,chain);
 assert.equal(family.resolve(match.node,match.chain).scope,token);
});

test('draft uses the desktop project identity even when the request includes its different app-server identity',async()=>{
 const source=await readFile(new URL('../web/native-draft.js',import.meta.url),'utf8');
 const sandbox={crypto:{randomUUID:()=> 'context-id'}};vm.createContext(sandbox);
 vm.runInContext(functionSource(source,'nativeDraftOptions'),sandbox);
 const params=sandbox.nativeDraftOptions({project:{id:'desktop-project',path:'/target/project'},nativeProjectId:'app-server-project',cardTitle:'工作卡片',context:{text:'当前卡片背景'}});
 assert.equal(params.activeProject.projectId,'desktop-project');
 assert.equal(params.activeProject.projectKind,'local');
 assert.equal(params.prefillMcpAppAttachments[0].content[0].text,'当前卡片背景');
 assert.equal(params.prefillMcpAppAttachments[0].untrusted,true);
 assert.equal(params.prefillPrompt,'');
 assert.equal(params.freshDraft,true);
});

test('maintenance starts one project task directly and reports cancelled creation as failure',async()=>{
 const source=await readFile(new URL('../web/native-draft.js',import.meta.url),'utf8');
 const start=vm.runInNewContext('async '+functionSource(source,'startMaintenance')+';startMaintenance');
 const calls=[],scope={};const payload={project:{id:'desktop-project',name:'Project',path:'/test/project'},prompt:'整理本项目',maintenanceContextWindows:{modelA:{model_context_window:872000,model_auto_compact_token_limit:784800}}};
 const readConfig=async cwd=>{assert.equal(cwd,'/test/project');return {model:'modelA'};};
 const result=await start(scope,async args=>{calls.push(args);return {kind:'creation',result:{status:'created',conversationId:'maintenance-thread'}};},payload,readConfig);
 assert.equal(result.started,true);assert.equal(result.threadId,'maintenance-thread');assert.equal(calls.length,1);
 assert.equal(calls[0].target.type,'project');assert.equal(calls[0].target.projectId,'desktop-project');assert.equal(calls[0].target.environment.type,'local');
 assert.equal(calls[0].prompt,payload.prompt);assert.equal(calls[0].scope,scope);assert.equal(calls[0].model,'modelA');assert.equal(calls[0].config.model_context_window,872000);
 await assert.rejects(start(scope,async()=>({kind:'creation',result:{status:'cancelled'}}),payload,readConfig),/未启动/);
});
