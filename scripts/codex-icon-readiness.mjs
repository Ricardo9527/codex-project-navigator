const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const changedPage=/Execution context was destroyed|Cannot find context with specified id|Inspected target navigated or closed|Target closed|Session closed|Codex 连接已断开|无法连接 Codex 主窗口/;

// A target appearing in /json/list does not mean its renderer survived startup.
// Reacquire the target after a navigation; do not retry real settings errors.
export async function waitForCodexIconPage({fetchTargets,connect,configure,timeoutMs=30000,now=Date.now,pause=sleep}){
 const deadline=now()+timeoutMs;
 let lastError;
 while(now()<deadline){
  let client,fetching=true;
  try{
   const targets=await fetchTargets();
   fetching=false;
   const target=targets.find(t=>t.type==='page'&&t.url.startsWith('app://-/index.html'));
   if(target){
    client=connect(target.webSocketDebuggerUrl);
    if(await configure(client))return;
   }
  }catch(error){
   if(!((fetching&&(error instanceof TypeError||error.name==='TimeoutError'))||changedPage.test(error.message)))throw error;
   lastError=error;
  }finally{client?.close();}
  await pause(100);
 }
 throw new Error('Codex 页面初始化未在规定时间内完成，图标动画未播放。'+(lastError?' 最后状态：'+lastError.message:''),{cause:lastError});
}
