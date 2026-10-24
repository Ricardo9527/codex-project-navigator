import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
test('source reveal adapter matches installed transcript registry and focus exports',async t=>{
 let archive;try{archive=await readFile(process.env.CODEX_DESKTOP_ASAR||'/Applications/ChatGPT.app/Contents/Resources/app.asar');}catch(e){if(e.code==='ENOENT'){t.skip('no installed desktop bundle');return;}throw e;}
 const size=archive.readUInt32LE(4),jsonSize=archive.readUInt32LE(12),assets=JSON.parse(archive.subarray(16,16+jsonSize).toString()).files.webview.files.assets.files;
 const {default:vm}=await import('node:vm');
 const bridge=await readFile(new URL('../web/native-source.js',import.meta.url),'utf8');
 const select=vm.runInNewContext(bridge.slice(0,bridge.indexOf('/* Reveal'))+';nativeSourceModules');
 const build=select(Object.keys(assets).map(n=>'app://-/assets/'+n));
 const entry=assets[build.primaryUrl.split('/').at(-1)];
 const src=archive.subarray(8+size+Number(entry.offset),8+size+Number(entry.offset)+entry.size).toString(),exports=src.slice(src.lastIndexOf('export{'));
 const alias=name=>build.exports?.primary[name]||name;
 const registry=exports.match(new RegExp('([\\w$]+) as '+alias('Ip')+'[,}]'))[1],focus=exports.match(new RegExp('([\\w$]+) as '+alias('Lp')+'[,}]'))[1];
 assert.match(src.slice(src.indexOf('function '+registry+'('),src.indexOf('function '+registry+'(')+180),/\.set\(/);
 assert.match(src.slice(src.indexOf('function '+focus+'('),src.indexOf('function '+focus+'(')+240),/scrollIntoView/);
 const sharedEntry=assets[build.sharedUrl.split('/').at(-1)];
 const shared=archive.subarray(8+size+Number(sharedEntry.offset),8+size+Number(sharedEntry.offset)+sharedEntry.size).toString();
 const sharedExports=shared.slice(shared.lastIndexOf('export{'));
 const initialEntry=build.initialUrl?assets[build.initialUrl.split('/').at(-1)]:null;
 const initial=initialEntry?archive.subarray(8+size+Number(initialEntry.offset),8+size+Number(initialEntry.offset)+initialEntry.size).toString():'';
 const moduleSource=key=>build.exports?.initial?.[key]?initial:shared;
 const name=key=>moduleSource(key).slice(moduleSource(key).lastIndexOf('export{')).match(new RegExp('([\\w$]+) as '+(build.exports?.initial?.[key]||build.exports?.shared[key]||key).replace(/[$]/g,'\\$')+'[,}]'))[1];
 assert.match(moduleSource('t$'),new RegExp(name('t$')+'=\\w+\\(`RouteScope`'));
 const resolver=name('n7t'),rpc=name('lJt');
 assert.match(shared.slice(shared.indexOf('function '+resolver+'('),shared.indexOf('function '+resolver+'(')+800),/familyBindings.get/);
 assert.match(moduleSource('lJt').slice(moduleSource('lJt').indexOf('function '+rpc+'('),moduleSource('lJt').indexOf('function '+rpc+'(')+1300),/forHost/);
 assert.ok(moduleSource('lJt').includes('hydrateConversationSearchMatch('));

});

test('source reveal hydrates only the recorded turn before locating its target item',async()=>{
 const {default:vm}=await import('node:vm');
 const source=await readFile(new URL('../web/native-source.js',import.meta.url),'utf8');
 const hydrate=vm.runInNewContext(source.slice(0,source.indexOf('/* Reveal'))+';hydrateNavigationSource');
 const calls=[],origin={threadId:'thread',turnId:'older-turn',itemId:'assistant-source'};
 const client={async sendRequest(method,args){calls.push({method,args});if(method==='thread/items/list')return {data:[{item:{type:'userMessage',content:[{type:'text',text:'the original request'}]}}]};return args.cursor?{data:[{turnId:'older-turn',itemId:'user-source',turnCursor:'exact-anchor'}],nextCursor:null}:{data:[{turnId:'different-turn',turnCursor:'wrong-anchor'}],nextCursor:'next'};},async hydrateConversationSearchMatch(args){calls.push({method:'hydrate',args});}};
 await hydrate(client,origin);
 assert.equal(calls.at(-1).args.turnCursor,'exact-anchor');
 assert.equal(calls.at(-1).args.itemId,'assistant-source');
 assert.equal(calls[0].args.turnId,'older-turn');
 assert.equal(calls.filter(c=>c.method==='hydrate').length,1);
});

test('text source focus uses the exact turn and search item key, not tool-block IDs',async()=>{
 const {default:vm}=await import('node:vm');const source=await readFile(new URL('../web/native-source.js',import.meta.url),'utf8');
 let scrolled=0,focused=0;
 const node={getAttribute:()=> 'turn:message',checkVisibility:()=>true,scrollIntoView(){scrolled++},focus(){focused++}};
 const focus=vm.runInNewContext(source.slice(0,source.indexOf('/* Reveal'))+';focusNavigationSourceMessage',{document:{querySelectorAll:()=>[node]}});
 assert.equal(focus({turnId:'other',itemId:'message'}),false);
 assert.equal(focus({turnId:'turn',itemId:'message'}),true);assert.equal(scrolled,1);assert.equal(focused,1);
});


test('legacy null item IDs locate the recorded turn using its real search message ID',async()=>{
 const {default:vm}=await import('node:vm');
 const source=await readFile(new URL('../web/native-source.js',import.meta.url),'utf8');
 const hydrate=vm.runInNewContext(source.slice(0,source.indexOf('/* Reveal'))+';hydrateNavigationSource');
 let loaded;const origin={threadId:'thread',turnId:'older-turn',itemId:null};
 const client={async sendRequest(method){return method==='thread/items/list'?{data:[{item:{type:'userMessage',content:[{type:'text',text:'original request'}]}}]}:{data:[{turnId:'other',itemId:'wrong',turnCursor:'wrong'},{turnId:'older-turn',itemId:'real-user-message',turnCursor:'exact-anchor'}]};},async hydrateConversationSearchMatch(args){loaded=args;}};
 const target=await hydrate(client,origin);
 assert.equal(target.itemId,'real-user-message');assert.equal(loaded.turnId,'older-turn');assert.equal(loaded.turnCursor,'exact-anchor');assert.equal(loaded.itemId,'real-user-message');assert.equal(origin.itemId,null);
});


test('non-addressable image generation anchors to its preceding request, not the latest message',async()=>{
 const {default:vm}=await import('node:vm');
 const source=await readFile(new URL('../web/native-source.js',import.meta.url),'utf8');
 const hydrate=vm.runInNewContext(source.slice(0,source.indexOf('/* Reveal'))+';hydrateNavigationSource');
 const client={async sendRequest(method){return method==='thread/items/list'?{data:[{item:{id:'first',type:'userMessage',content:[{type:'text',text:'earlier request'}]}},{item:{id:'request',type:'userMessage',content:[{type:'text',text:'source request'}]}},{item:{id:'image',type:'imageGeneration'}},{item:{id:'latest',type:'userMessage',content:[{type:'text',text:'latest request'}]}}]}:{data:[{turnId:'turn',itemId:'request',turnCursor:'cursor'}]};},async hydrateConversationSearchMatch(){}};
 const target=await hydrate(client,{threadId:'thread',turnId:'turn',itemId:'image'});
 assert.equal(target.sourceType,'imageGeneration');assert.equal(target.turnAnchor,'request');assert.equal(target.itemId,'image');
});

test('source adapter loads the relocated transcript module without requiring it to be preloaded',async()=>{
 const {default:vm}=await import('node:vm');
 const source=await readFile(new URL('../web/native-source.js',import.meta.url),'utf8');
 const select=vm.runInNewContext(source.slice(0,source.indexOf('/* Reveal'))+';nativeSourceModules');
 const urls=['app-primary-7d7313419f84.js','app-shared-2cae01273bae.js','app-initial-feb30b196d11.js'].map(name=>'app://-/assets/'+name);
 assert.equal(select(urls).primaryUrl,'app://-/assets/followup-analytics-4a9d22031a4e.js');
 assert.throws(()=>select(urls.slice(0,2)),/需要适配/);
});
