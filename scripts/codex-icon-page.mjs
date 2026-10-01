import {randomUUID} from 'node:crypto';
export function dockPreferenceExpression(value,{early=false,refresh=false}={}){
 return `(async()=>{
  if(!window.electronBridge?.sendMessageFromView)return false;
  if(!${early}&&(document.readyState!=='complete'||!document.querySelector('[data-app-shell-main-surface],nav[data-app-navigation-rail]')))return false;
  const prefix=${JSON.stringify(randomUUID())};let sequence=0;
  const call=(name,args)=>new Promise((resolve,reject)=>{
   const requestId=prefix+':'+(++sequence);
   const on=e=>{const r=e.data;if(r?.type!=='fetch-response'||r.requestId!==requestId)return;clearTimeout(timer);window.removeEventListener('message',on);r.responseType==='success'?resolve(JSON.parse(r.bodyJsonString)):reject(Error(r.error));};
   const timer=setTimeout(()=>{window.removeEventListener('message',on);reject(Error('Dock 图标设置超时'));},8000);
   window.addEventListener('message',on);
   window.electronBridge.sendMessageFromView({type:'fetch',requestId,url:'vscode://codex/'+name,method:'POST',body:JSON.stringify(args)}).catch(error=>{clearTimeout(timer);window.removeEventListener('message',on);reject(error)});
  });
  const key='dock-icon-preference',value=${JSON.stringify(value)};
  if(${refresh})await call('set-configuration',{key,value});
  else if((await call('get-setting',{key})).value!==value)await call('set-setting',{key,value});
  return true;
 })()`;
}
