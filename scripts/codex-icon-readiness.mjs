const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const changedPage=/Execution context was destroyed|Cannot find context with specified id|Inspected target navigated or closed|Target closed|Session closed|Codex 连接已断开|无法连接 Codex 主窗口/;

// Cold starts may expose both a disposable preload page and the main window.
export async function waitForCodexIconPage({fetchTargets,connect,configure,timeoutMs=30000,now=Date.now,pause=sleep}){
 const deadline=now()+timeoutMs;
 let lastError;
 while(now()<deadline){
  let targets;
  try{targets=await fetchTargets();}
  catch(error){
   if(!(error instanceof TypeError||error.name==='TimeoutError'))throw error;
   lastError=error;await pause(100);continue;
  }
  for(const target of targets.filter(t=>t.type==='page'&&t.url.startsWith('app://-/index.html'))){
   let client;
   try{
    client=connect(target.webSocketDebuggerUrl);
    if(await configure(client))return;
   }catch(error){
    if(!changedPage.test(error.message))throw error;
    lastError=error;
   }finally{client?.close();}
  }
  await pause(100);
 }
 throw new Error('Codex 页面初始化未在规定时间内完成，图标动画未播放。'+(lastError?' 最后状态：'+lastError.message:''),{cause:lastError});
}
