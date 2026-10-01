import {existsSync} from 'node:fs';
import {consumeCodexWakeRequests} from './codex-icon-queue.mjs';
import {readFile,writeFile,mkdir,rename} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {CDP} from './cdp.mjs';
import {createTaskboardSupervisor} from '../vendor/dashi-taskboard/taskboard-supervisor.mjs';
import {consumeNativeDrafts} from './native-draft-queue.mjs';
import {runSingleDraftTrial} from './native-draft-trial.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const endpoint='http://127.0.0.1:9333',service='http://127.0.0.1:47832';
const python=process.env.PROJECT_HUB_PYTHON||(process.platform==='win32'?'python':'python3');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const [hub,content,launcher,controls,hubCSS,contentCSS,native]=await Promise.all(['hub.js','content-page.js','native-composer.js','native-controls.js','hub.css','content-page.css','native.js'].map(f=>readFile(path.join(root,'web',f),'utf8')));
const ui=launcher+'\n'+controls+'\n'+content+'\n'+hub,css=hubCSS+'\n'+contentCSS;
const markdown=await readFile(path.join(root,'node_modules/markdown-it/dist/markdown-it.min.js'),'utf8');
let iconExitWatcher;
let stopped=false,supervisor,clients=new Map(),lastState='',lastHandoffCheck=0;
function log(state){if(state!==lastState){console.log(new Date().toISOString(),state);lastState=state;}}
async function reachable(){try{const r=await fetch(service+'/health',{signal:AbortSignal.timeout(1500)});const d=await r.json();return d.service==='codex-library';}catch(e){if(e instanceof TypeError||e.name==='TimeoutError')return false;throw e;}}
async function waitUntilReachable(timeout){const end=Date.now()+timeout;while(Date.now()<end){if(await reachable())return;await sleep(200);}throw new Error('资料库服务启动超时');}
function newSupervisor(){return createTaskboardSupervisor({detached:false,isReachable:reachable,waitUntilReachable,
  start(){const child=spawn(python,[path.join(root,'server.py'),'--parent-pid',String(process.pid)],{cwd:root,stdio:['ignore','inherit','inherit']});return child;},
  onProcessError:e=>console.error('Service error:',e),onUnexpectedExit:(code,signal)=>console.error('Service exited:',code,signal)});}
async function connect(target){
  const client=new CDP(target.webSocketDebuggerUrl);
  try{
    if(!await client.evaluate("Boolean(document.querySelector('nav[data-app-navigation-rail]'))")){client.close();return;}
    const contexts=new Set();
    client.handlers.add(message=>{
      if(message.method==='Runtime.executionContextCreated'&&message.params.context.origin==='app://-'&&message.params.context.auxData?.isDefault)contexts.add(message.params.context.id);
      if(message.method==='Runtime.executionContextDestroyed')contexts.delete(message.params.executionContextId);
      if(message.method==='Runtime.executionContextsCleared')contexts.clear();
      if(message.method==='Runtime.bindingCalled'&&message.params.name==='__codexLibraryRPC'&&contexts.has(message.params.executionContextId))void respond(client,message);
    });
    await client.send('Runtime.enable');
    await client.send('Runtime.addBinding',{name:'__codexLibraryRPC'});
    await mount(client);clients.set(target.id,client);
  }catch(e){client.close();throw e;}
}
async function respond(client,message){
  let id,result;
  try{const payload=JSON.parse(message.params.payload);id=payload.id;
    await supervisor.ensure();
    const r=await fetch(service+'/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:payload.action,args:payload.args}),signal:AbortSignal.timeout(payload.action==='chooseResource'?300000:25000)});
    result=await r.json();
  }catch(e){result={error:e.message};}
  try{await client.send('Runtime.evaluate',{expression:`window.__codexLibraryResolve?.(${JSON.stringify(id)},${JSON.stringify(result)})`,contextId:message.params.executionContextId});}
  catch(e){console.error('Response delivery:',e.message);}
}
async function mount(client){
  const bridge=`(()=>{let seq=0;const pending=new Map();window.__codexLibraryResolve=(id,r)=>{const p=pending.get(id);if(!p)return;clearTimeout(p.timer);pending.delete(id);r.error?p.reject(new Error(r.error)):p.resolve(r.result);};window.__codexLibraryConfig={css:${JSON.stringify(css)},contentCSS:${JSON.stringify(contentCSS)},request:(action,args)=>new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('资料库暂未响应，连接恢复后可重试。'));},action==='chooseResource'?300000:30000);pending.set(id,{resolve,reject,timer});window.__codexLibraryRPC(JSON.stringify({id,action,args}));})};})();`;
  await client.evaluate(markdown+'\n'+ui+'\n'+bridge+'\n'+native);
}
async function stop(){if(stopped)return;stopped=true;iconExitWatcher?.kill();for(const c of clients.values()){try{await c.evaluate('window.__codexLibrary?.dispose()');}catch(e){console.error(e.message);}c.close();}await supervisor?.stop();process.exit(0);}
process.on('SIGINT',stop);process.on('SIGTERM',stop);
await mkdir(path.join(root,'data'),{recursive:true});
const iconEnabled=process.platform==='darwin'&&existsSync(path.join(root,'assets/codex/animation.json'));
const iconActions=iconEnabled?await import('./codex-icon-animation.mjs'):null;
let iconBusy=false,iconState='unknown',pendingIdle=false;
if(iconActions){
 iconExitWatcher=iconActions.watchCodexExit(root,()=>{pendingIdle=true;});
 const timer=setInterval(async()=>{
  if(stopped||iconBusy)return;
  iconBusy=true;
  try{
   if(pendingIdle){pendingIdle=false;if(!await iconActions.codexProcessRunning()){await iconActions.applyCodexIdleIcon(root);iconState='idle';}}
   await consumeCodexWakeRequests(root,iconActions.playCodexWake,iconActions.applyCodexIdleIcon);
  }
  catch(error){console.error('图标播放队列：',error);}
  finally{iconBusy=false;}
 },50);timer.unref();
}
while(!stopped){
  try{
    let targets;
    try{targets=await(await fetch(endpoint+'/json/list',{signal:AbortSignal.timeout(1500)})).json();}
    catch(e){if(!(e instanceof TypeError||e.name==='TimeoutError'))throw e;targets=[];}
    const nativeTargets=targets.filter(t=>t.type==='page'&&t.url.startsWith('app://-/index.html'));
    if(!nativeTargets.length){
      if(iconActions&&iconState!=='idle')pendingIdle=true;
      for(const c of clients.values())c.close();clients.clear();
      if(supervisor){await supervisor.stop();supervisor=null;}
      log('等待 Codex 接入窗口；资料服务已停止。');
    }else{
      iconState='running';
      supervisor??=newSupervisor();await supervisor.ensure();
      for(const [id,c] of clients){if(!nativeTargets.some(t=>t.id===id)||c.socket.readyState!==WebSocket.OPEN){c.close();clients.delete(id);}}
      for(const target of nativeTargets){
        const client=clients.get(target.id);
        if(!client)await connect(target);
        else if(!await client.evaluate('Boolean(window.__codexLibrary?.ping())'))await mount(client);
      }
      log('Codex 项目资料库已接入。');
      if(Date.now()-lastHandoffCheck>15000){
        const response=await fetch(service+'/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'reconcileCardHandoffs',args:{}})});
        const value=await response.json();if(value.error)throw Error(value.error);lastHandoffCheck=Date.now();
      }
      await consumeNativeDrafts(root,(payload,request)=>runSingleDraftTrial(root,payload,request,async value=>{
        if(clients.size!==1)throw Error('本次试验要求仅有一个 Codex 主窗口。');
        const client=[...clients.values()][0];
        if(value.kind==='source'){
          await client.evaluate(await readFile(path.join(root,'web/native-source.js'),'utf8'));
          return client.evaluate(`window.__projectNavigationRevealSource(${JSON.stringify(value.origin)})`);
        }
        await client.evaluate(await readFile(path.join(root,'web/native-draft.js'),'utf8'));
        return client.evaluate(`window.__projectNavigationPrepareDraft(${JSON.stringify(value)})`);
      }));
    }
    await writeFile(path.join(root,'data/runtime.json.tmp'),JSON.stringify({pid:process.pid,connected:clients.size>0,checkedAt:Date.now(),state:lastState}),{mode:0o600});
    await rename(path.join(root,'data/runtime.json.tmp'),path.join(root,'data/runtime.json'));
  }catch(e){log('正在恢复连接：'+e.message);}
  await sleep(3000);
}
