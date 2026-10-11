import test from 'node:test';import assert from 'node:assert/strict';import{readFile}from'node:fs/promises';import vm from'node:vm';
test('resource source click passes current project and card identities to navigation',async()=>{
 const source=await readFile(new URL('../web/content-page.js',import.meta.url),'utf8');
 const start=source.indexOf('    async function click(event)'),end=source.indexOf('    function input(event)',start),calls=[],error={hidden:true,textContent:''};
 const click=vm.runInNewContext(source.slice(start,end)+';click',{active:true,project:{id:'project'},cardId:'card',card:()=>({resources:[{id:'resource',origin:{threadId:'thread'}}]}),onThread:async(...args)=>calls.push(args),$:()=>error});
 await click({target:{closest:()=>({dataset:{action:'content-source',id:'resource'}})}});
 assert.equal(error.textContent,'');assert.equal(calls.length,1);assert.equal(calls[0][0],'thread');assert.deepEqual(JSON.parse(JSON.stringify(calls[0][2])),{projectId:'project',cardId:'card',resourceId:'resource'});
});

test('thumbnail requests are bounded and cached across card redraws',async()=>{
 const source=await readFile(new URL('../web/content-page.js',import.meta.url),'utf8');
 const pump=source.slice(source.indexOf('    function pumpThumbnails()'),source.indexOf('    let page'));
 const render=source.slice(source.indexOf('    function renderBody()'),source.indexOf('    function refreshListing()'));
 let props;const calls=[],waiting=[],resources=Array.from({length:8},(_,i)=>({id:String(i),versionStamp:'v1',exists:true}));
 const context={project:{id:'project'},category:'category',cardId:'card',card:()=>({resources}),detail:()=>'',nativeSurface:{update:p=>{props=p;}},mountControl:true,window:{},click(){},input(){},surfaceRendered(){},request:(action,args)=>{calls.push(args);return new Promise(resolve=>waiting.push(()=>resolve({data:'image-'+args.resourceId})));}};
 vm.createContext(context);const api=vm.runInContext('let thumbnailScope="",thumbnailCache=new Map(),thumbnailQueue=[],thumbnailActive=0;'+pump+render+';({renderBody})',context);
 api.renderBody();const pending=resources.map(r=>props.loadThumbnail(r.id));assert.equal(calls.length,3);
 while(waiting.length){waiting.splice(0).forEach(r=>r());await new Promise(r=>setImmediate(r));}
 assert.deepEqual(await Promise.all(pending),resources.map(r=>'image-'+r.id));assert.equal(calls.length,8);
 api.renderBody();await Promise.all(resources.map(r=>props.loadThumbnail(r.id)));assert.equal(calls.length,8);
 resources[0].versionStamp='v2';api.renderBody();const changed=props.loadThumbnail('0');assert.equal(calls.length,9);waiting.shift()();await changed;
});
