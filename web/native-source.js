/* Reveal a registered source item through the installed transcript navigation API. */
window.__projectNavigationRevealSource=async origin=>{
 const urls=[...document.querySelectorAll('link[rel="modulepreload"]')].map(n=>n.href);
 const primaryUrl=urls.find(u=>u.endsWith('/app-primary-83ab2f0c1a5c.js'));
 const sharedUrl=urls.find(u=>u.endsWith('/app-shared-eececb2d2eb0.js'));
 if(!primaryUrl||!sharedUrl)throw Error('对话已打开；当前 Codex 版本的来源消息定位需要适配。');
 const [primary,shared]=await Promise.all([import(primaryUrl),import(sharedUrl)]);
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
     const handler=scope.get(registry,origin.threadId);if(!handler)continue;
     await handler.revealItem({conversationId:origin.threadId,itemId:origin.itemId,turnKey:origin.turnId});
     if(primary.Lp(origin.itemId,'instant'))return {revealed:true};
     throw Error('对话已打开，但未找到这条来源消息；记录可能已变化。');
    }finally{frame.familyBindings.delete(accessor);}
   }
  }
  await new Promise(resolve=>setTimeout(resolve,150));
 }
 throw Error('来源对话没有及时加载到可定位状态，请稍后重试。');
};
