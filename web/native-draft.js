/* Project routing uses the installed Codex native draft action, without submitting a turn. */
(() => {
 let scopeAccessor;
 function nativeModules(urls){
  const builds=[
   {initial:'app-initial-74096abaa6b3.js',shared:'app-shared-5d8e744d1fa1.js',draftExport:'CLt'},
   {initial:'app-initial-135a4ef2552c.js',shared:'app-shared-eececb2d2eb0.js',draftExport:'kIt'},
  ];
  for(const build of builds){
   const initialUrl=urls.find(u=>u.endsWith('/'+build.initial));
   const sharedUrl=urls.find(u=>u.endsWith('/'+build.shared));
   if(initialUrl&&sharedUrl)return {initialUrl,sharedUrl,draftExport:build.draftExport};
  }
  throw Error('当前 Codex 版本的项目草稿入口需要适配。');
 }
 function nativeDraftOptions({project,context,cardTitle}){
  const attachment={id:crypto.randomUUID(),kind:'context',untrusted:true,sourceName:cardTitle,
   server:'project-navigator-flow',composerLabel:cardTitle,composerAttachmentLayout:'pill',
   content:[{type:'text',text:context.text}]};
  return {activeProject:{projectId:project.id,projectKind:'local'},freshDraft:true,
   prefillComposerMode:'local',prefillMcpAppAttachments:[attachment],prefillPrompt:''};
 }
 function findAppScope(fiber,token){
  for(let current=fiber;current;current=current.return){
   if(current.tag!==10)continue;
   const chain=current.memoizedProps.value;
   if(!(chain instanceof Map))continue;
   const node=Map.prototype.get.call(chain,token.id);
   if(node?.token===token&&node.familyBindings instanceof Map)return {chain,node};
  }
  return null;
 }
 function editorChain(shared){
  let node=[...document.querySelectorAll('[contenteditable="true"]')].find(n=>n.checkVisibility()),key;
  while(node&&!(key=Object.keys(node).find(k=>k.startsWith('__reactFiber'))))node=node.parentElement;
  return findAppScope(node?.[key],shared.dJt);
 }
 window.__projectNavigationPrepareDraft=async ({project,context,cardId,cardTitle,nativeProjectId})=>{
  const urls=[...document.querySelectorAll('link[rel="modulepreload"]')].map(n=>n.href);
  const modules=nativeModules(urls);
  const initial=await import(modules.initialUrl);
  const shared=await import(modules.sharedUrl);
  if(typeof initial[modules.draftExport]!=='function')throw Error('当前 Codex 版本的原生草稿动作需要适配。');
  const match=editorChain(shared);
  if(!match)throw Error('当前窗口尚未找到符合原生契约的应用上下文。');
  const {chain,node:scopeNode}=match;
  scopeAccessor??=shared.n7t(shared.dJt,(_,{scope})=>scope);
  const scope=scopeAccessor.resolve(scopeNode,chain);
  const desktopProject=scope.get(shared.gTt)[project.id];
  if(!desktopProject?.rootPaths.includes(project.path))throw Error('卡片所属项目未在桌面项目目录中匹配到工作区。');
  const options=nativeDraftOptions({project:desktopProject,context,cardTitle});
  window.__codexLibrary?.close();
  initial[modules.draftExport](scope,options);
  return {draftRequested:true,projectId:project.id,nativeProjectId:desktopProject.id,appServerProjectId:nativeProjectId,projectPath:project.path,cardId};
 };
})();
