import {randomUUID} from 'node:crypto';
export function dockPreferenceExpression(value,{early=false,refresh=false}={}){
 return `(async()=>{
  if(!window.electronBridge?.sendMessageFromView)return false;
  if(!${early}&&(document.readyState!=='complete'||!document.querySelector('[data-app-shell-main-surface],nav[data-app-navigation-rail]')))return false;
  const key='dock-icon-preference',value=${JSON.stringify(value)};
  const userAgent=await window.electronBridge.getDesktopUserAgent?.();
  const build=${JSON.stringify([
   {version:'26.1021.31345',module:'app-shared-2cae01273bae.js',init:'zit',read:'Bit',write:'Yit'},
   {version:'26.1023.50603',module:'app-shared-2864d2ff2296.js',init:'sat',read:'cat',write:'_at'},
   {version:'26.1023.51421',module:'app-shared-e9f258fd3588.js',init:'sat',read:'cat',write:'_at'},
  ])}.find(build=>userAgent?.startsWith('Codex Desktop/'+build.version+' '));
  if(build){
   const settings=await import('app://-/assets/'+build.module);
   settings[build.init]();
   if(${refresh}||await settings[build.read]({key})!==value)await settings[build.write]({key},value);
   return true;
  }
  const prefix=${JSON.stringify(randomUUID())};let sequence=0;
  const call=(name,args)=>new Promise((resolve,reject)=>{
   const requestId=prefix+':'+(++sequence);
   const on=e=>{const r=e.data;if(r?.type!=='fetch-response'||r.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',on);r.responseType==='success'?resolve(JSON.parse(r.bodyJsonString)):reject(Error(r.error));};
   const timer=setTimeout(()=>{window.removeEventListener('message',on);reject(Error('Dock 图标设置超时'));},8000);
   window.addEventListener('message',on);
   window.electronBridge.sendMessageFromView({type:'fetch',requestId,url:'vscode://codex/'+name,method:'POST',body:JSON.stringify(args)}).catch(error=>{clearTimeout(timer);window.removeEventListener('message',on);reject(error)});
  });
  if(${refresh})await call('set-configuration',{key,value});
  else if((await call('get-setting',{key})).value!==value)await call('set-setting',{key,value});
  return true;
 })()`;
}
