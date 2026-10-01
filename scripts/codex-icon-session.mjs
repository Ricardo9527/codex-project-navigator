import {randomUUID} from 'node:crypto';

// The default image is gray on disk. Refresh it before this renderer unloads,
// while the main-process icon handler is still reachable.
export function idleOnUnloadExpression(){
 return `(()=>{
  if(!window.electronBridge?.sendMessageFromView)return false;
  if(window.__projectLibraryIdleOnUnload)return true;
  const handler=()=>{
   window.electronBridge.sendMessageFromView({type:'fetch',requestId:${JSON.stringify(randomUUID())},url:'vscode://codex/set-configuration',method:'POST',body:JSON.stringify({key:'dock-icon-preference',value:'codex-system'})}).catch(error=>console.error('退出前恢复灰色图标失败：',error));
  };
  window.addEventListener('beforeunload',handler);
  window.__projectLibraryIdleOnUnload=handler;
  return true;
 })()`;
}

// The current-session blue image must be established before restoring the
// persistent gray resources, and no refresh may follow that restoration.
export async function finishLibraryIconSession({settle,restoreGray,installExitHook}){
 await settle();
 await restoreGray();
 await installExitHook();
}
