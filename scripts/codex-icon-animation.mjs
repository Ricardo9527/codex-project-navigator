import {isLibraryIconSession,markLibraryIconSession} from './codex-icon-activation.mjs';
import {idleOnUnloadExpression,finishLibraryIconSession} from './codex-icon-session.mjs';
import {createInterface} from 'node:readline';
import {waitForCodexIconPage} from './codex-icon-readiness.mjs';
import {dockPreferenceExpression} from './codex-icon-page.mjs';
import {playRuntimeIconFrames,prepareIdleRuntimeResources} from './codex-runtime-icon.mjs';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {CDP} from './cdp.mjs';
const run=promisify(execFile);
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const installed=JSON.parse(await readFile(new URL('../data/install.json',import.meta.url),'utf8'));
const appPath=installed.app;

export async function codexProcessRunning(){
  try {await run('/usr/bin/pgrep',['-f','^'+path.join(appPath,'Contents/MacOS',path.basename(appPath,'.app')).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')]);return true;}
  catch(error){if(error.code===1)return false;throw error;}
}
export async function applyCodexIdleIcon(root){
  await prepareIdleRuntimeResources({root,appPath,idle:await readFile(path.join(root,'assets/codex/idle.png'))});
  await applyStaticIdleIcon(root);
}
async function applyStaticIdleIcon(root){
  const {stdout}=await run(path.join(root,'data/bin/play-codex-icon'),[appPath,path.join(root,'assets/codex'),'--idle']);
  console.log(new Date().toISOString(),stdout.trim());
}
export async function waitForNativeIconSync(){
 const prefix=path.join(appPath,'Contents/Resources/native/launch-services-helper').replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const deadline=Date.now()+5000;let quietSince;
 while(Date.now()<deadline){
  let busy;
  try{await run('/usr/bin/pgrep',['-f','^'+prefix+' set-app-icon']);busy=true;}
  catch(error){if(error.code!==1)throw error;busy=false;}
  if(busy)quietSince=undefined;
  else{quietSince??=Date.now();if(Date.now()-quietSince>=150)return;}
  await sleep(50);
 }
 throw Error('Codex 内置图标同步未结束，灰色默认资源暂未写回。');
}
export async function playCodexWake(root,startedAt=Date.now(),{coldStart=false}={}){
  const browserIdentity=async()=>{
    const response=await fetch('http://127.0.0.1:9333/json/version',{signal:AbortSignal.timeout(1000)});
    if(!response.ok)throw Error(`Codex 会话查询失败：${response.status}`);
    return (await response.json()).webSocketDebuggerUrl;
  };
  if(!coldStart&&await isLibraryIconSession(root,await browserIdentity())){
    console.log('Codex already activated through library; running icon unchanged.');return;
  }
  const config=JSON.parse(await readFile(path.join(root,'assets/codex/animation.json'),'utf8'));
  const requestedAt=Date.now();
  let readyURL;
  await waitForCodexIconPage({
    fetchTargets:async()=>{
      const response=await fetch('http://127.0.0.1:9333/json/list',{signal:AbortSignal.timeout(1000)});
      if(!response.ok)throw Error(`Codex 调试接口返回 ${response.status}`);
      return response.json();
    },
    connect:url=>{readyURL=url;return new CDP(url);},
    configure:client=>client.evaluate(dockPreferenceExpression('codex-system',{early:coldStart,refresh:coldStart}))
  });
  const browserId=await browserIdentity();
  console.log('Codex icon ready:',JSON.stringify({coldStart,waitMs:Date.now()-requestedAt,sinceClickMs:Date.now()-startedAt}));
  // The left animation's contact frame is 11 at 24 fps. In cold starts,
  // readiness may arrive later, so the reaction follows readiness instead.
  const delay=Math.max(0,startedAt+config.impactOffsetMs-Date.now())+config.readyDelayMs;
  if(delay)await sleep(delay);
  const frames=await Promise.all(Array.from({length:config.frameCount},(_,i)=>readFile(path.join(root,'assets/codex',coldStart?(config.coldFramesDirectory||'frames'):'frames',`frame-${String(i).padStart(3,'0')}.png`))));
  const client=new CDP(readyURL);
  try{
    const result=await playRuntimeIconFrames({root,appPath,frames,fps:config.fps,direct:true,setPreference:async value=>{
      if(!await client.evaluate(dockPreferenceExpression(value,{early:coldStart,refresh:true})))throw Error('Codex 主界面在动画过程中离开，已停止播放并恢复图标。');
    }});
    console.log('Codex runtime icon animation:',JSON.stringify(result));
    await finishLibraryIconSession({
      settle:waitForNativeIconSync,
      restoreGray:()=>applyCodexIdleIcon(root),
      installExitHook:async()=>{if(!await client.evaluate(idleOnUnloadExpression()))throw Error('退出图标监听未安装');}
    });
    await markLibraryIconSession(root,browserId);
  }finally{client.close();}

}

export function watchCodexExit(root,onExit){
 const child=spawn(path.join(root,'data/bin/play-codex-icon'),[appPath,path.join(root,'assets/codex'),'--watch'],{stdio:['ignore','pipe','inherit']});
 const lines=createInterface({input:child.stdout});
 lines.on('line',line=>{if(line==='idle')onExit();});
 child.on('error',error=>console.error('Codex 退出监听失败：',error));
 child.on('exit',(code,signal)=>{lines.close();if(code!==0&&signal!=='SIGTERM')console.error('Codex 退出监听结束：',code,signal);});
 return child;
}
