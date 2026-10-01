import {waitForCodexIconPage} from './codex-icon-readiness.mjs';
import {randomUUID} from 'node:crypto';
import {execFile} from 'node:child_process';
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
  await run(path.join(root,'data/bin/play-codex-icon'),[appPath,path.join(root,'assets/codex'),'--idle']);
}
export async function playCodexWake(root,startedAt=Date.now()){
  const config=JSON.parse(await readFile(path.join(root,'assets/codex/animation.json'),'utf8'));
  await waitForCodexIconPage({
    fetchTargets:async()=>{
      const response=await fetch('http://127.0.0.1:9333/json/list',{signal:AbortSignal.timeout(1000)});
      if(!response.ok)throw Error(`Codex 调试接口返回 ${response.status}`);
      return response.json();
    },
    connect:url=>new CDP(url),
    configure:async client=>{
      return await client.evaluate(`(async()=>{
      if(document.readyState!=='complete'||!window.electronBridge?.sendMessageFromView||!document.querySelector('[data-app-shell-main-surface],nav[data-app-navigation-rail]'))return false;
      const requestPrefix=${JSON.stringify(randomUUID())};
      let requestSequence=0;
      const call=(name,args)=>new Promise((resolve,reject)=>{
        const requestId=requestPrefix+':'+(++requestSequence);
        const on=e=>{const r=e.data;if(r?.type!=='fetch-response'||r.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',on);r.responseType==='success'?resolve(JSON.parse(r.bodyJsonString)):reject(Error(r.error));};
        const timer=setTimeout(()=>{window.removeEventListener('message',on);reject(Error('Dock 图标设置超时'));},8000);
        window.addEventListener('message',on);
        window.electronBridge.sendMessageFromView({type:'fetch',requestId,url:'vscode://codex/'+name,method:'POST',body:JSON.stringify(args)}).catch(e=>{clearTimeout(timer);window.removeEventListener('message',on);reject(e)});
      });
      const key='dock-icon-preference';
      if((await call('get-setting',{key})).value!=='app-default')await call('set-setting',{key,value:'app-default'});
      return true;
    })()`);
    }
  });
  // The left animation's contact frame is 11 at 24 fps. In cold starts,
  // readiness may arrive later, so the reaction follows readiness instead.
  const delay=Math.max(0,startedAt+config.impactOffsetMs-Date.now());
  if(delay)await sleep(delay);
  const {stdout}=await run(path.join(root,'data/bin/play-codex-icon'),[appPath,path.join(root,'assets/codex')],{timeout:12000});
  console.log(stdout.trim());
}
