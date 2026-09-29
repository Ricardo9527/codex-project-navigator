/* Reuse the current desktop build's composer. No replacement editor or send pipeline. */
(() => {
  window.mountLibraryNativeComposer = ({host,dock,project,context,defaultPrompt,onCreated,onError,beforeSubmit,autoSubmit=false}) => {
    let root,container,slot,disposed=false,submit,submitted=false,selectedModel;
    const ready=(async()=>{
      const urls=[...document.querySelectorAll('link[rel="modulepreload"]')].map(n=>n.href);
      const find=name=>{const url=urls.find(u=>new RegExp('/app-'+name+'-[^/]+\\.js$').test(u));if(!url)throw new Error('当前 Codex 版本的原生输入框需要重新适配。');return url;};
      const [shared,initial,primary]=await Promise.all([import(find('shared')),import(find('initial')),import(find('primary'))]);
      if(disposed)return;
      const React=shared.t0t(),ReactDOM=shared.P1t();
      let node=[...document.querySelectorAll('[contenteditable="true"]')].find(n=>!n.closest('.library-native-composer')),key;
      while(node&&!(key=Object.keys(node).find(k=>k.startsWith('__reactFiber'))))node=node.parentElement;
      if(!node)throw new Error('请先打开一个项目对话，再打开项目资料。');
      let fiber=node[key];
      while(fiber&&!(fiber.tag===10&&(fiber.type.displayName||fiber.type._context?.displayName)==='ComposerScope'))fiber=fiber.return;
      if(!fiber)throw new Error('未找到原生输入框上下文。');
      const providers=[];
      for(fiber=fiber.return;fiber;fiber=fiber.return)if(fiber.tag===10)providers.push({type:fiber.type,value:fiber.memoizedProps.value});
      slot=document.createElement('slot');slot.name='library-native-'+crypto.randomUUID();dock.append(slot);
      container=document.createElement('div');container.slot=slot.name;container.className='library-native-composer';container.style.cssText='width:100%;min-width:0;max-width:48rem;margin:0 auto';host.append(container);
      const value=initial.rOt({kind:'file',libraryFileId:`project-record:${project.id}:${context.key||'project'}`,file:{path:context.path,fsPath:context.path,label:context.label+' · 项目记录'}});
      const props={className:'mx-auto w-full max-w-full',selectedProject:{type:'local',projectId:project.id},onProjectChange:()=>{},defaultCwd:project.path,
        composerLayoutMode:'multiline',composerModeAvailability:primary.PD,hideRunLocationDropdownOverride:true,
        placeholderText:'你想做什么？',defaultPrompt,
        prepareLocalSubmit:async payload=>{
          if(payload.localProjectId!==project.id)throw new Error('输入框项目与卡片不一致，请重新打开卡片。');
          await beforeSubmit?.();
          const model=payload.collaborationMode?.settings?.model||selectedModel;
          if(context.maintenanceContextWindows&&!model)throw new Error('模型尚未加载，请稍后再启动整理。');
          const overrides=context.maintenanceContextWindows?.[model];
          return overrides?{...payload,firstTurnConfigOverrides:{...payload.firstTurnConfigOverrides,...overrides}}:payload;
        },
        registerSubmitHandler:handler=>{submit=handler;},
        onLocalConversationCreated:id=>{submitted=true;Promise.resolve(onCreated(id)).catch(onError);},
        onLocalSubmitError:error=>onError(error),
      };
      function Composer(surfaceProps){
        const {modelSettings}=initial.Fyt();
        selectedModel=modelSettings.model;
        return React.createElement(primary.Lt,{...props,...surfaceProps});
      }
      root=ReactDOM.createRoot(container,{onUncaughtError:onError,onCaughtError:onError});
      let tree=React.createElement(shared.mUt,{scope:shared.bH,value:shared.xH({pathname:'/',routeTemplate:'/'})},React.createElement(shared.mUt,{scope:initial.tOt,value},React.createElement(primary.qs,{placement:{kind:'home'}},React.createElement(Composer))));
      for(const provider of providers)tree=React.createElement(provider.type,{value:provider.value},tree);
      root.render(tree);
      if(autoSubmit){
        for(let i=0;i<100&&!disposed;i++){
          const button=container.querySelector('button[aria-label="发送"]');
          if(button&&!button.disabled){button.click();return;}
          await new Promise(resolve=>setTimeout(resolve,100));
        }
        if(!disposed)throw new Error('原生输入框尚未准备好。维护需求已保留，可在下方检查后发送。');
      }
    })().catch(error=>{if(!disposed)onError(error);});
    return {ready,get submitted(){return submitted;},destroy(){disposed=true;root?.unmount();container?.remove();slot?.remove();}};
  };
})();

// Use Codex's own virtualized transcript navigation, including older unloaded turns.
window.libraryRevealSource = async origin => {
  const url=[...document.querySelectorAll('link[rel="modulepreload"]')].map(n=>n.href).find(u=>/\/app-primary-[^/]+\.js$/.test(u));
  const primary=await import(url);
  let registry;
  primary.Ui({set:atom=>{registry=atom;}},'library-navigation-probe',null);
  const deadline=Date.now()+10000;
  while(Date.now()<deadline){
    const turn=[...document.querySelectorAll('[data-turn-key]')].find(n=>n.getAttribute('data-turn-key').endsWith('turn:'+origin.turnId));
    const exact=turn&&([...turn.querySelectorAll('img')].find(n=>n.src.includes('/'+origin.itemId+'.'))||[...turn.querySelectorAll('[data-content-search-unit-key]')].find(n=>n.getAttribute('data-content-search-unit-key').endsWith(':'+origin.itemId)));
    if(exact){exact.scrollIntoView({block:'center',behavior:'instant'});exact.tabIndex=-1;exact.focus({preventScroll:true});return;}
    let node=[...document.querySelectorAll('[contenteditable="true"]')].find(n=>!n.closest('.library-native-composer')),key;
    while(node&&!(key=Object.keys(node).find(k=>k.startsWith('__reactFiber'))))node=node.parentElement;
    for(let fiber=node?.[key];fiber;fiber=fiber.return){
      if(fiber.tag!==10||(fiber.type.displayName||fiber.type._context?.displayName)!=='ThreadScope')continue;
      const handler=fiber.memoizedProps.value.get(registry,origin.threadId);
      if(handler){
        await handler.revealItem({conversationId:origin.threadId,itemId:origin.itemId,turnKey:origin.turnId});
        if(primary.Wi(origin.itemId,'instant'))return;
        throw new Error('已打开来源对话，但未能定位到这条成果消息。');
      }
    }
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw new Error('来源对话未能及时加载，请重试。');
};
