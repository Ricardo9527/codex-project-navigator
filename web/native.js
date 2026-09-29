/* Main-content mounting adapted from dashi-taskboard's findPageHost approach.
   The catalog uses a ShadowRoot and CDP binding, retaining Codex's content CSP. */
(() => {
  const VERSION='2.4.0';
  const memory=(window.__projectNavigationMemory||={last:null});
  const restoredProject=window.__codexLibrary?.projectId;
  window.__projectHubDetach?.();
  window.__codexLibrary?.dispose();
  let page,view,observerTimer,disposed=false,host,previousFocus,originalPosition,activeProject,headerLabel,restorePanels=false,restoreFull=false,opening=0;
  const hidden=new Map(),buttons=new Set();
  const config=window.__codexLibraryConfig;
  const style=document.createElement('style');style.id='codex-library-style';
  // The removed MCP entry can remain in the desktop menu cache until its next refresh.
  style.textContent=`
    button[id*='"project-library-preview"'] { display:none!important; }
    [data-library-entry] { border:0; padding:5px!important; width:28px; height:28px; min-width:28px; display:flex; align-items:center; justify-content:center; border-radius:6px; color:var(--color-token-text-secondary); background:transparent; cursor:pointer; flex-shrink:0; }
    [data-library-entry] svg { width:16px; height:16px; stroke:currentColor; fill:none; stroke-width:1.5; stroke-linecap:round; stroke-linejoin:round; }
    [data-app-action-sidebar-project-row] [data-library-entry] { opacity:0; pointer-events:none; }
    [data-app-action-sidebar-project-row]:hover [data-library-entry], [data-app-action-sidebar-project-row]:focus-within [data-library-entry] { opacity:1; pointer-events:auto; }
    [data-library-entry]:hover { background:var(--color-token-interactive-bg-secondary-hover); color:var(--color-token-foreground); }
    [data-library-entry]:focus-visible { opacity:1; outline:2px solid var(--color-token-text-link-foreground); outline-offset:1px; }
    nav[data-app-navigation-rail] [data-library-entry] { width:36px; height:36px; margin:0; }
    #codex-library-page { position:absolute; inset:0; z-index:20; overflow:hidden; border-radius:inherit; background:var(--color-token-main-surface-primary); }
  `;
  document.head.append(style);
  function pageHost(){
    return [...document.querySelectorAll('[data-app-shell-main-surface]')].find(n=>n.checkVisibility()&&n.getBoundingClientRect().width>0&&!n.closest('[data-app-shell-active-page="false"]'));
  }
  function hide(node){
    if(!node||hidden.has(node))return;
    hidden.set(node,{visibility:node.style.visibility,inert:node.inert});node.style.visibility='hidden';node.inert=true;
  }
  function isolate(){
    for(const child of host.children)if(child!==page)hide(child);
    const titlebar=document.querySelector('[data-testid="app-shell-header-context-menu-surface"]');
    for(const child of titlebar?.children||[])if(child!==headerLabel)hide(child);
    for(const button of document.querySelectorAll('button[data-app-shell-workspace-layout-toggle]')){
      const group=button.parentElement.closest('[data-app-shell-focus-area="main"]');
      if(group&&!host.contains(group))hide(group);
    }
  }
  function close(restoreTools=true){
    opening++;const reopen=restoreTools&&restorePanels&&host===pageHost(),full=restoreFull;restorePanels=false;restoreFull=false;
    const state=view?.snapshot();if(state)memory.last=state;
    view?.destroy();view=null;page?.remove();page=null;activeProject=undefined;headerLabel?.remove();headerLabel=null;
    for(const [node,old] of hidden){node.style.visibility=old.visibility;node.inert=old.inert;}hidden.clear();
    if(host){host.style.position=originalPosition;host.removeAttribute('data-project-navigation-open');}host=null;
    previousFocus?.focus();
    if(reopen){const area=full?'right-panel':'main';const toggle=[...document.querySelectorAll(`button[data-app-shell-workspace-layout-toggle="${area}"]`)].find(n=>n.checkVisibility());if(toggle?.getAttribute('aria-label')===(full?'进入完整视图':'显示标签页'))toggle.click();}
  }
  async function show(projectId,projectName){
    const reopen=restorePanels,full=restoreFull;close(false);restorePanels=reopen;restoreFull=full;const request=opening;
    const resume=!projectId||projectId==='all';const initialState=resume?memory.last:null;
    projectId=initialState?.projectId||(resume?undefined:projectId);host=pageHost();
    if(!host)throw new Error('当前页面未找到主内容区，请打开一个项目对话后再试。');
    previousFocus=document.activeElement;originalPosition=host.style.position;
    const fullToggle=[...document.querySelectorAll('button[data-app-shell-workspace-layout-toggle="right-panel"]')].find(n=>n.checkVisibility());
    if(fullToggle?.getAttribute('aria-label')==='退出完整视图'){restoreFull=true;restorePanels=true;fullToggle.click();await new Promise(requestAnimationFrame);if(request!==opening)return;}
    const panelToggle=[...document.querySelectorAll('button[data-app-shell-workspace-layout-toggle="main"]')].find(n=>n.checkVisibility());
    if(panelToggle?.getAttribute('aria-label')==='隐藏标签页'){restorePanels=true;panelToggle.click();}
    activeProject=projectId||'all';
    if(getComputedStyle(host).position==='static')host.style.position='relative';
    host.setAttribute('data-project-navigation-open','true');
    page=document.createElement('section');page.id='codex-library-page';page.setAttribute('aria-label','项目导航');
    const shadow=page.attachShadow({mode:'open'}),css=document.createElement('style'),root=document.createElement('div');
    css.textContent=config.css;root.style.height='100%';shadow.append(css,root);host.append(page);
    const titlebar=document.querySelector('[data-testid="app-shell-header-context-menu-surface"]');
    if(titlebar){
      headerLabel=document.createElement('span');Object.assign(headerLabel.style,{position:'absolute',left:'12px',top:'0',bottom:'0',display:'flex',alignItems:'center',fontSize:'14px',pointerEvents:'none'});headerLabel.textContent='项目导航';headerLabel.dataset.projectNavigationTitle='true';titlebar.append(headerLabel);
    }
    isolate();
    view=window.mountLibrary(root,{request:config.request,initialState,chooseProject:!projectId,mountComposer:settings=>window.mountLibraryNativeComposer({host:page,...settings}),mountControl:settings=>window.mountLibraryNativeControl({host:page,...settings}),projectId:projectId==='all'?undefined:projectId,projectName,onClose:close,onProject:project=>{activeProject=project.id;if(headerLabel)headerLabel.textContent=project.name+' · 项目导航';}});
    root.querySelector('input')?.focus();
  }
  function add(parent,id){
    const b=document.createElement('button');b.type='button';b.dataset.libraryEntry=id||'all';
    b.title=id?'打开项目导航主页':'项目导航 · 回到上次位置';b.setAttribute('aria-label',b.title);b.innerHTML=window.libraryIcon('navigation');
    b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();show(id,parent.getAttribute('data-app-action-sidebar-project-label'));});
    parent.append(b);buttons.add(b);return b;
  }
  function sync(){
    if(disposed)return;observer.disconnect();
    for(const b of buttons)if(!b.isConnected)buttons.delete(b);
    for(const row of document.querySelectorAll('[data-app-action-sidebar-project-row]')){
      const identity=row.matches('[data-app-action-sidebar-project-id]')?row:row.querySelector('[data-app-action-sidebar-project-id]');
      const id=identity?.getAttribute('data-app-action-sidebar-project-id');
      const b=row.querySelector('[data-library-entry]');
      if(b&&b.dataset.libraryEntry!==id){b.remove();buttons.delete(b);}
      if(id&&!row.querySelector('[data-library-entry]'))add(row,id);
    }
    const rail=document.querySelector('nav[data-app-navigation-rail]');
    const destinations=rail&&[...rail.children].find(n=>n.querySelector('[data-sidebar-destination="builtin:home"]'));
    if(destinations){
      const more=destinations.querySelector(':scope > button[data-slot="popover-trigger"]');
      const entry=rail.querySelector('[data-library-entry]')||add(destinations);
      if(entry.parentElement!==destinations||(more&&entry.nextSibling!==more))destinations.insertBefore(entry,more);
    }
    if(page&&(!page.isConnected||host!==pageHost()))close();
    else if(page)isolate();
    observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['data-app-action-sidebar-project-id','data-app-shell-workspace-layout','data-app-shell-right-panel-full-width','data-app-shell-active-page']});
  }
  function navigation(e){
    if(!page||e.target.closest('[data-library-entry]')||e.composedPath().includes(page))return;
    const button=e.target.closest('button');
    const label=(button?.getAttribute('aria-label')||button?.textContent||'').trim();
    const newChat=button&&(button.matches('[data-app-action-sidebar-project-row] button[aria-label]:not([aria-haspopup])')||/^(新聊天|新建对话|新对话|New chat|New thread)$/i.test(label));
    // Release the overlay before the native button handles navigation.
    if(newChat||e.target.closest('[data-app-action-sidebar-thread-id],nav[data-app-navigation-rail] button,aside a,[role="tab"],[data-app-shell-workspace-layout-toggle]'))close();
  }
  const observer=new MutationObserver(()=>{clearTimeout(observerTimer);observerTimer=setTimeout(sync,100);});
  function toolShortcut(e){
    if(!page)return;
    const key=e.key.toLowerCase();
    if(e.metaKey&&key==='w'){e.preventDefault();e.stopImmediatePropagation();close();return;}
    const nativeTool=(e.metaKey&&key==='p')||(e.ctrlKey&&key==='`')||(e.metaKey&&e.altKey&&key==='s')||(e.ctrlKey&&e.shiftKey&&['g','b','f'].includes(key));
    if(nativeTool)close();
  }
  document.addEventListener('click',navigation,true);document.addEventListener('keydown',toolShortcut,true);sync();
  window.__codexLibrary={version:VERSION,show,close,get projectId(){return activeProject;},ping:()=>true,dispose(){disposed=true;observer.disconnect();clearTimeout(observerTimer);document.removeEventListener('click',navigation,true);document.removeEventListener('keydown',toolShortcut,true);close();buttons.forEach(b=>b.remove());style.remove();delete window.__codexLibrary;}};
  if(restoredProject)show();
})();
