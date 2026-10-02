// A renderer reload is not an application exit. Remove the old page-level hook;
// only the native process-exit watcher is allowed to restore idle resources.
export function removeIdleOnUnloadExpression(){
 return `(()=>{
  if(window.__projectLibraryIdleOnUnload){
   window.removeEventListener('beforeunload',window.__projectLibraryIdleOnUnload);
   delete window.__projectLibraryIdleOnUnload;
  }
  return true;
 })()`;
}

// Keep the running resource images blue for the entire activated process.
// Only the independent file icon is gray while this process is running.
export async function finishLibraryIconSession({settle,writeStaticIdle,removePageExitHook}){
 await settle();
 await writeStaticIdle();
 await removePageExitHook();
}
