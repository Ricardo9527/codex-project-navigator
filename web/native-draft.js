/* Project routing uses the installed Codex native draft action, without submitting a turn. */
(() => {
 let scopeAccessor;
 function nativeModules(urls){
  const builds=[
   {initial:'app-initial-74096abaa6b3.js',shared:'app-shared-5d8e744d1fa1.js',draftExport:'CLt'},
   {initial:'app-initial-135a4ef2552c.js',shared:'app-shared-eececb2d2eb0.js',draftExport:'kIt',maintenanceExport:'oC'},
   {initial:'app-initial-8a7b00193cb6.js',shared:'app-shared-44edd7bfa69c.js',draftExport:'kIt',maintenanceExport:'oC'},
   {initial:'app-initial-576fc7ca620e.js',shared:'app-shared-b72e16382796.js',draftExport:'tIt',maintenanceExport:'Px',sharedExports:{dJt:'GJt',n7t:'z7t',gTt:'WTt',lJt:'UJt'}},
   {initial:'app-initial-f9b16fbf8fc7.js',shared:'app-shared-9d148924be0b.js',draftExport:'nIt',maintenanceExport:'Px',sharedExports:{dJt:'GJt',n7t:'B7t',gTt:'WTt',lJt:'UJt'}},
  ];
  for(const build of builds){
   const initialUrl=urls.find(u=>u.endsWith('/'+build.initial));
   const sharedUrl=urls.find(u=>u.endsWith('/'+build.shared));
   if(initialUrl&&sharedUrl)return {initialUrl,sharedUrl,draftExport:build.draftExport,maintenanceExport:build.maintenanceExport,sharedExports:build.sharedExports};
  }
  throw Error('当前 Codex 版本的项目草稿入口需要适配。');
 }
 function resolveDesktopProject(project,projects){
  const id=project.desktopId||project.id,desktop=projects[id];
  if(!desktop?.rootPaths.includes(project.path))throw Error('卡片所属项目未在桌面项目目录中匹配到工作区：'+id+' · '+project.path);
  return desktop;
 }
 function nativeDraftOptions({project,context,cardTitle,prompt=''}){
  const attachment={id:crypto.randomUUID(),kind:'context',untrusted:true,sourceName:cardTitle,
   server:'project-navigator-flow',composerLabel:cardTitle,composerAttachmentLayout:'pill',
   content:[{type:'text',text:context.text}]};
  return {activeProject:{projectId:project.id,projectKind:'local'},freshDraft:true,
   prefillComposerMode:'local',prefillMcpAppAttachments:[attachment],prefillPrompt:prompt};
 }
 async function startMaintenance(scope,create,{project,prompt,maintenanceContextWindows},readConfig){
  const settings=await readConfig(project.path),model=settings.model;
  const config=maintenanceContextWindows?.[model];
  const result=await create({scope,prompt,model,config,target:{type:'project',projectId:project.id,environment:{type:'local'}},title:'更新 '+project.name+' 项目记录',threadSource:'user',turnTrigger:'app_tool_create_thread'});
  if(result.kind!=='creation'||result.result.status!=='created')throw Error('整理任务未启动：'+(result.result?.status||result.kind));
  return {started:true,threadId:result.result.conversationId,projectId:project.id};
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
 window.__projectNavigationPrepareDraft=async ({project,context,cardId,cardTitle,nativeProjectId,prompt,kind,maintenanceContextWindows})=>{
  const urls=[...document.querySelectorAll('link[rel="modulepreload"]')].map(n=>n.href);
  const modules=nativeModules(urls);
  const initial=await import(modules.initialUrl);
  const rawShared=await import(modules.sharedUrl);
  const shared=modules.sharedExports?Object.fromEntries(Object.entries(modules.sharedExports).map(([name,alias])=>[name,rawShared[alias]])):rawShared;
  if(typeof initial[modules.draftExport]!=='function')throw Error('当前 Codex 版本的原生草稿动作需要适配。');
  const match=editorChain(shared);
  if(!match)throw Error('当前窗口尚未找到符合原生契约的应用上下文。');
  const {chain,node:scopeNode}=match;
  scopeAccessor??=shared.n7t(shared.dJt,(_,{scope})=>scope);
  const scope=scopeAccessor.resolve(scopeNode,chain);
  const desktopProject=resolveDesktopProject(project,scope.get(shared.gTt));
  if(kind==='maintenance'){
   const create=initial[modules.maintenanceExport];
   if(typeof create!=='function')throw Error('当前 Codex 版本的整理任务自动启动入口需要适配。');
   return startMaintenance(scope,create,{project:{...desktopProject,path:project.path},prompt,maintenanceContextWindows},async cwd=>{const rpc=shared.lJt(scope,'local');const {config}=await rpc.sendRequest('config/read',{cwd,includeLayers:false});if(config.model)return config;const models=await rpc.sendRequest('model/list',{});const model=models.data.find(m=>m.isDefault)?.model;if(!model)throw Error('未能确认整理使用的模型，任务未启动。');return {...config,model};});
  }
  const options=nativeDraftOptions({project:desktopProject,context,cardTitle,prompt});
  window.__codexLibrary?.close();
  initial[modules.draftExport](scope,options);
  return {draftRequested:true,projectId:project.id,nativeProjectId:desktopProject.id,appServerProjectId:nativeProjectId,projectPath:project.path,cardId};
 };
})();
