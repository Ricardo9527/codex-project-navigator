import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import {renderNavigationUI} from '../experimental/project-navigator/render-ui.mjs';

test('native navigation reads live cards, preserves records and exports their actual context',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'project-navigator-'));
 const recordPath=path.join(root,'.project-library/record.json');
 await mkdir(path.dirname(recordPath));await writeFile(path.join(root,'result.txt'),'实际成果');
 const record={version:1,projectId:'fixture-project',about:'项目用途',categories:[{id:'work',title:'工作'}],cards:[{
  id:'task',title:'工作成果',summary:'继续这项工作',categoryIds:['work'],kind:'工作',icon:'book',caption:'',
  resources:[{id:'result',label:'成果文件',path:'result.txt',format:'文本',role:'result'}],
  sources:[{id:'source-thread',title:'来源工作对话',label:'来源工作对话'}],
  sections:[{title:'当前情况',paragraphs:['文件已生成，等待用户确认。']}],requirements:[],records:[],related:[],
 }],reviewedThreads:{}};
 await writeFile(recordPath,JSON.stringify(record));
 const client=new Client({name:'native-navigation-test',version:'1.0.0'});
 try{
  await client.connect(new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../experimental/project-navigator/server.mjs',import.meta.url))],env:{...process.env,PROJECT_NAVIGATOR_ROOT:root,PROJECT_NAVIGATOR_CARD:'task'},stderr:'pipe'}));
  const {tools}=await client.listTools();
  assert.equal(tools.find(t=>t.name==='prepare_card_work').annotations.readOnlyHint,false);
  const paused=await client.callTool({name:'prepare_card_work',arguments:{cardId:'task'}});
  assert.equal(paused.isError,true);
  assert.match(paused.content[0].text,/已暂停|未启用|未接入|尚待实机/);
  assert.deepEqual(tools.find(t=>t.name==='browse_navigation')._meta['openai/ui'].entrypoints,[{type:'global'},{type:'thread'}]);
  const expectedRevision=createHash('sha256').update(await renderNavigationUI()).digest('hex').slice(0,16);
  assert.equal(tools.find(t=>t.name==='browse_navigation')._meta.ui.resourceUri,`ui://project-navigator/navigation-${expectedRevision}.html`);
  const ui=await client.readResource({uri:tools.find(t=>t.name==='browse_navigation')._meta.ui.resourceUri});
  assert.equal(ui.contents[0].text,await renderNavigationUI());
  assert.match(ui.contents[0].text,/window.createContentPage/);
  for(const match of ui.contents[0].text.matchAll(/<script(?: type="module")?>([\s\S]*?)<\/script>/g))new vm.Script('(async()=>{'+match[1]+'})()');
  const denied=await client.callTool({name:'navigation_action',arguments:{action:'saveRecord',args:{}}});
  assert.equal(denied.isError,true);
  const before=await readFile(recordPath,'utf8');
  const opened=await client.callTool({name:'browse_navigation',arguments:{}});
  assert.equal(opened.structuredContent.card.id,'task');
  assert.equal(opened.structuredContent.contentPage.cards[0].resources[0].label,'成果文件');
  assert.equal(opened.structuredContent.card.resources[0].effectiveAdoption,'review');
  const context=await client.callTool({name:'get_card_context',arguments:{cardId:'task'}});
  assert.match(context.structuredContent.context.text,/source-thread/);
  assert.ok(context.structuredContent.context.text.includes(recordPath));
  assert.equal(await readFile(recordPath,'utf8'),before);
  record.cards[0].summary='成果已修订';await writeFile(recordPath,JSON.stringify(record));
  const fresh=await client.callTool({name:'read_navigation',arguments:{cardId:'task'}});
  assert.equal(fresh.structuredContent.card.summary,'成果已修订');
  assert.notEqual(fresh.structuredContent.revision,opened.structuredContent.revision);
  const missing=await client.callTool({name:'get_card_context',arguments:{cardId:'missing'}});
  assert.equal(missing.isError,true);
 }finally{await client.close();await rm(root,{recursive:true,force:true});}
});

test('project entry resets to homepage while refresh preserves card state',async()=>{
 const html=await renderNavigationUI();
 assert.doesNotMatch(html.split('<script>')[0],/<select id="projects"/);
 const script=html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
 let listener,state={cardId:'old',query:'old'},restores=0;
 const elements=new Map();const $=id=>{if(!elements.has(id))elements.set(id,{dataset:{}});return elements.get(id);};
 const data={project:{id:'project',name:'项目'},contentPage:{categories:[],cards:[]}};
 const parent={postMessage(m){if(m.id===undefined)return;const result=m.method==='ui/initialize'?{hostContext:{'openai/deepLink':{url:'/projects/project?entry=first'}}}:{structuredContent:data};queueMicrotask(()=>listener({source:parent,data:{jsonrpc:'2.0',id:m.id,result}}));}};
 const window={mountNavigationSDKControl(){},addEventListener(name,fn){if(name==='message')listener=fn;},libraryIcon(){},markdownit:()=>({disable(){return this;}}),createContentPage:()=>({update(){},restore(s){state=s;restores++;},destroy(){}})};
 await vm.runInNewContext('(async()=>{'+script+'})()',{window,parent,document:{querySelector:$},URL,setTimeout,clearTimeout});
 assert.equal(state.cardId,null);state={cardId:'detail',query:'搜索'};
 await $('#refresh').onclick();assert.equal(state.cardId,'detail');
 listener({source:parent,data:{jsonrpc:'2.0',method:'ui/notifications/host-context-changed',params:{'openai/deepLink':{url:'/projects/project?entry=second'}}}});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(restores,2);assert.equal(state.cardId,null);assert.equal(state.query,'');assert.equal(state.scrollTop,0);
});
