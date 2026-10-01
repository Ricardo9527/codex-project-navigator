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
  await run(path.join(root,'data/bin/play-codex-icon'),[appPath,path.join(root,'assets/codex'),'--idle']);
}
export async function playCodexWake(root,startedAt=Date.now(),{coldStart=false}={}){
  const config=JSON.parse(await readFile(path.join(root,'assets/codex/animation.json'),'utf8'));
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
  // The left animation's contact frame is 11 at 24 fps. In cold starts,
  // readiness may arrive later, so the reaction follows readiness instead.
  const delay=Math.max(0,startedAt+config.impactOffsetMs-Date.now())+config.readyDelayMs;
  if(delay)await sleep(delay);
  const frames=await Promise.all(Array.from({length:config.frameCount},(_,i)=>readFile(path.join(root,'assets/codex/frames',`frame-${String(i).padStart(3,'0')}.png`))));
  const client=new CDP(readyURL);
  try{
    const result=await playRuntimeIconFrames({root,appPath,frames,fps:config.fps,direct:coldStart,setPreference:async value=>{
      if(!await client.evaluate(dockPreferenceExpression(value,{early:coldStart,refresh:coldStart})))throw Error('Codex 主界面在动画过程中离开，已停止播放并恢复图标。');
    }});
    console.log('Codex runtime icon animation:',JSON.stringify(result));
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
