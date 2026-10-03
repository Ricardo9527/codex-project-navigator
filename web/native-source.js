async function hydrateNavigationSource(client,origin){
 const page=await client.sendRequest('thread/items/list',{threadId:origin.threadId,turnId:origin.turnId,limit:100,sortDirection:'asc'});
 const user=page.data.find(entry=>entry.item.type==='userMessage')?.item;
 const text=user?.content.filter(part=>part.type==='text').map(part=>part.text).join('\n').trim();
 if(!text)throw Error('找不到来源轮次的可检索消息，无法加载该段历史。');
 for(const searchTerm of new Set([text.slice(0,80),text.slice(-80)])){
  let cursor;
  do{
   const matches=await client.sendRequest('thread/searchOccurrences',{threadId:origin.threadId,searchTerm,limit:100,...cursor?{cursor}:{}});
   const match=matches.data.find(item=>item.turnId===origin.turnId);
   if(match){const target={...origin,itemId:origin.itemId||match.itemId};await client.hydrateConversationSearchMatch({conversationId:target.threadId,turnId:target.turnId,itemId:target.itemId,turnCursor:match.turnCursor});return target;}
   cursor=matches.nextCursor;
  }while(cursor);
 }
 throw Error('来源消息仍在记录中，但无法取得该轮历史的定位游标。');
}
function focusNavigationSourceMessage(origin){
 const key=origin.turnId+':'+origin.itemId;
 const target=[...document.querySelectorAll('[data-content-search-unit-key]')].find(node=>node.getAttribute('data-content-search-unit-key')===key&&node.checkVisibility());
 if(!target)return false;
 target.scrollIntoView({block:'center',behavior:'instant'});target.tabIndex=-1;target.focus({preventScroll:true});return true;
}
function nativeSourceModules(urls){
 for(const [primary,shared,exports] of [
  ['app-primary-83ab2f0c1a5c.js','app-shared-eececb2d2eb0.js'],
  ['app-primary-705e2d4f1e56.js','app-shared-44edd7bfa69c.js'],
  ['app-primary-5fc751535eb1.js','app-shared-b72e16382796.js',{primary:{Ip:'Np',Lp:'Pp',Rp:'Fp'},shared:{'t$':'D$',n7t:'z7t',lJt:'UJt',Oj:'Vj',XNt:'APt'}}],
 ]){
  const primaryUrl=urls.find(u=>u.endsWith('/'+primary)),sharedUrl=urls.find(u=>u.endsWith('/'+shared));
  if(primaryUrl&&sharedUrl)return {primaryUrl,sharedUrl,exports};
 }
 throw Error('对话已打开；当前 Codex 版本的来源消息定位需要适配。');
}
/* Reveal a registered source item through the installed transcript navigation API. */
window.__projectNavigationRevealSource=async origin=>{
 const urls=[...document.querySelectorAll('link[rel="modulepreload"]')].map(n=>n.href);
 const {primaryUrl,sharedUrl,exports}=nativeSourceModules(urls);
 const [rawPrimary,rawShared]=await Promise.all([import(primaryUrl),import(sharedUrl)]);
 const primary=exports?Object.fromEntries(Object.entries(exports.primary).map(([name,alias])=>[name,rawPrimary[alias]])):rawPrimary;
 const shared=exports?Object.fromEntries(Object.entries(exports.shared).map(([name,alias])=>[name,rawShared[alias]])):rawShared;
 let registry;primary.Ip({set:atom=>{registry=atom;}},'navigation-source-probe',null);
 const token=shared['t$'],deadline=Date.now()+12000;
 while(Date.now()<deadline){
  for(const editor of document.querySelectorAll('[contenteditable="true"]')){
   if(!editor.checkVisibility())continue;
   let node=editor,key;while(node&&!(key=Object.keys(node).find(k=>k.startsWith('__reactFiber'))))node=node.parentElement;
   for(let fiber=node?.[key];fiber;fiber=fiber.return){
    const chain=fiber.memoizedProps?.value;if(fiber.tag!==10||!(chain instanceof Map))continue;
    const frame=chain.get(token.id);if(frame?.token!==token)continue;
    const accessor=shared.n7t(token,(_,{scope})=>scope);
    try{
     const scope=accessor.resolve(frame,chain);
     if(scope.value.conversationId!==origin.threadId)continue;
     if(!scope.get(registry,origin.threadId))continue;
     if(origin.itemId&&(focusNavigationSourceMessage(origin)||primary.Lp(origin.itemId,'instant')))return {revealed:true,scope:'message'};
     const client=shared.lJt(scope,scope.get(shared.Oj,origin.threadId));
     const target=await hydrateNavigationSource(client,origin);
     await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
     if(scope.get(shared.XNt).pathname!=='/local/'+origin.threadId)throw Error('当前页面已切换，已停止来源定位。');
     const handler=scope.get(registry,origin.threadId);
     await handler.revealItem({conversationId:origin.threadId,itemId:target.itemId,turnKey:target.turnId});
     if(focusNavigationSourceMessage(target)||await primary.Rp(target.itemId,'instant'))return {revealed:true,scope:origin.itemId?'message':'turn'};
     throw Error('目标历史已加载，但该消息未形成可定位的页面内容。');
    }finally{frame.familyBindings.delete(accessor);}
   }
  }
  await new Promise(resolve=>setTimeout(resolve,150));
 }
 throw Error('来源对话没有及时加载到可定位状态，请稍后重试。');
};
