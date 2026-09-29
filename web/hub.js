(() => {
  const paths={navigation:'M4 5h5v5H4z M15 14h5v5h-5z M6.5 10v6.5H15 M14 5h6 M17 2v6',book:'M4 4h6a3 3 0 0 1 3 3v14a3 3 0 0 0-3-3H4z M13 7a3 3 0 0 1 3-3h4v14h-4a3 3 0 0 0-3 3',search:'m21 21-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',close:'m6 6 12 12 M18 6 6 18',back:'m12 5-7 7 7 7 M5 12h15',refresh:'M20 7v5h-5 M4 17v-5h5 M5.5 7a7 7 0 0 1 12-2L20 8 M4 16l2.5 3a7 7 0 0 0 12-2',file:'M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h6',image:'M3 3h18v18H3z m0 14 6-6 4 4 3-3 5 5 M16 7h.01',chat:'M21 11a9 9 0 0 1-9 9H3l1.5-4A9 9 0 1 1 21 11',folder:'M3 5h6l2 2h10v13H3z',info:'M12 11v6 M12 7h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0'};
  const icon=name=>`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.file}"/></svg>`;
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  window.libraryIcon=icon;
  window.mountLibrary=(root,options)=>{
    let restored=false,disposed=false,sequence=0,projectId=options.projectId,poll,maintenance,launchContext,projectPicker,toolbar,projects=[];
    const markdown=window.markdownit({html:false,linkify:false}).disable(['image','link']);
    root.innerHTML=`<section class="library" aria-label="项目导航"><div class="topbar">${icon('navigation')}<span class="label">项目导航</span><span class="spacer"></span>${options.mountControl?'<div id="native-project-picker"></div>':'<select id="projects" aria-label="选择项目"></select>'}<button data-action="maintain" title="检查并更新项目记录">${icon('refresh')}更新</button>${options.onClose?`<button class="icon" data-action="close" aria-label="返回对话">${icon('back')}</button>`:''}</div><div class="error" role="alert" hidden></div><div class="workspace"><aside class="topics"></aside><main class="main organized"><div class="heading" hidden></div><div class="filters" hidden></div><div class="results"><div class="empty">正在读取项目记录…</div></div></main></div><footer class="statusbar"><span id="record-status"></span></footer></section>`;
    const $=s=>root.querySelector(s),request=options.request;
    const error=e=>{if(!disposed){$('.error').hidden=false;$('.error').textContent=e.message;}};
    const onThread=async (id,origin)=>{await request('openThread',{threadId:id});options.onClose?.();if(origin)try{await window.libraryRevealSource(origin);}catch(e){const notice=document.createElement('div');notice.setAttribute('role','alert');notice.style.cssText='position:fixed;right:24px;top:60px;z-index:99999;padding:14px 18px;background:var(--color-background-elevated,#24272b);color:var(--color-text-primary,#eee);border:1px solid #666;border-radius:10px;max-width:380px';notice.textContent=e.message;const close=document.createElement('button');close.textContent='关闭';close.style.marginLeft='12px';close.onclick=()=>notice.remove();notice.append(close);document.body.append(notice);}};
    if(options.mountControl){const dock=document.createElement('div');$('.topbar').querySelectorAll('button').forEach(n=>n.remove());$('.topbar').append(dock);toolbar=options.mountControl({dock,kind:'toolbar',props:{onAction:action=>handleClick({target:{closest:()=>({dataset:{action}})}}),canClose:Boolean(options.onClose)},onError:error});}
    const content=window.createContentPage({root,request,icon,escape,markdown,onThread,mountComposer:options.mountComposer,mountControl:options.mountControl,onUpdated:()=>load()});
    async function load(){const n=++sequence;try{
      const data=await request('record',{projectId});if(disposed||n!==sequence)return;
      projectId=data.project.id;options.onProject?.(data.project);$('.error').hidden=true;
      const page=data.contentPage||{version:1,projectId:data.project.id,about:'整理已有成果和讨论，建立这个项目的内容目录。',categories:[],cards:[],coverage:'尚未整理',coverageDetail:'',uninitialized:true};
      page.uninitialized=!data.checkpoint&&!page.cards.length;
      content.update({...data,contentPage:page});
      if(!restored&&options.initialState){content.restore(options.initialState);restored=true;}
      if(projectPicker)projectPicker.update({selected:projectId});else if($('#projects'))$('#projects').value=projectId;setUpdate({disabled:false});
      $('#record-status').textContent=data.checkpoint?(data.checkpoint.commit?`已整理到 ${data.checkpoint.commit.slice(0,8)}`:'初始记录已整理'):'等待首次整理';
      const updating=['pending','running'].includes(data.maintenance?.state);
      setUpdate({label:updating?'更新中':'更新'});
      if(updating)$('#record-status').textContent='正在检查项目记录';
      else if(['interrupted','failed','cancelled'].includes(data.maintenance?.state))$('#record-status').textContent='上次整理未完成，点击更新继续';
    }catch(e){error(e);}}
    async function start(){try{const overview=await request('overview');if(disposed)return;
      projectId=overview.aliases[projectId]||projectId||(options.chooseProject?undefined:overview.projects[0]?.id);
      if(!overview.projects.some(p=>p.id===projectId))projectId=overview.projects.find(p=>p.name===options.projectName)?.id;
      projects=overview.projects;
      if(options.mountControl){projectPicker=options.mountControl({dock:$('#native-project-picker'),kind:'project',props:{projects,selected:projectId,onSelect:selectProject},onError:error});}
      else{$('#projects').innerHTML='<option value="" disabled>选择项目</option>'+projects.map(p=>`<option value="${escape(p.id)}">${escape(p.name)}</option>`).join('');$('#projects').value=projectId;}
      if(projectId)await load();else{
        setUpdate({disabled:true});
        $('.topics').innerHTML='<div class="content-nav"><div class="section-label">项目</div></div>';
        $('.results').innerHTML=`<div class="content-document"><header class="content-heading"><h1>项目导航</h1><p>选择一个项目，查看成果和记录。</p></header><div class="navigation-projects">${overview.projects.map(p=>`<button data-action="choose-project" data-project="${escape(p.id)}">${icon('folder')}<span>${escape(p.name)}</span></button>`).join('')}</div></div>`;
      }
    }catch(e){error(e);}}
    function cancelLaunch(){if(launchContext&&!maintenance?.submitted)request('cancelMaintenanceLaunch',launchContext).catch(e=>console.error('维护取消登记失败',e));launchContext=null;maintenance?.destroy();maintenance=null;}
    function selectProject(id){cancelLaunch();projectId=id;restored=true;load();}
    root.addEventListener('change',e=>{if(e.target.id==='projects')selectProject(e.target.value);});
    function setUpdate(props){if(toolbar)toolbar.update(props);else{const b=$('.topbar [data-action="maintain"]');if('disabled' in props)b.disabled=props.disabled;if(props.label)b.innerHTML=icon('refresh')+props.label;}}
    async function handleClick(e){const b=e.target.closest('[data-action]');if(!b)return;
      if(b.dataset.action==='close')options.onClose?.();
      if(b.dataset.action==='choose-project'){projectId=b.dataset.project;restored=true;load();}
      if(b.dataset.action==='maintain'){
        if(maintenance)return;setUpdate({disabled:true});
        try{
          if(!options.mountComposer)throw new Error('请在 Codex 项目导航中启动维护。');
          const selectedProject=projectId;
          const context=await request('maintenanceContext',{projectId:selectedProject});
          if(context.jobId&&(disposed||projectId!==selectedProject)){await request('cancelMaintenanceLaunch',{projectId:selectedProject,jobId:context.jobId});return;}
          if(disposed)return;
          if(context.noChanges){$('#record-status').textContent='没有新增变化';return;}
          if(context.existingThreadId){await onThread(context.existingThreadId);return;}
          launchContext={projectId:selectedProject,jobId:context.jobId};
          content.deactivate();$('.heading').hidden=true;$('.filters').hidden=true;
          $('.results').innerHTML='<div class="empty"><h2>正在启动项目维护</h2><p>检查新增内容，更新项目记录。</p></div>';
          const dock=document.createElement('div');dock.className='content-compose-dock';$('.main').append(dock);
          maintenance=options.mountComposer({dock,project:context.project,context,defaultPrompt:context.prompt,autoSubmit:true,onCreated:async id=>{await request('markMaintenance',{projectId:selectedProject,jobId:context.jobId,threadId:id});launchContext=null;if(!disposed&&projectId===selectedProject)await onThread(id);},onError:async e=>{await request('finishMaintenance',{projectId:selectedProject,jobId:context.jobId,state:'failed'});launchContext=null;maintenance?.destroy();maintenance=null;dock.remove();if(!disposed){await load();error(e);}}});
        }catch(e){error(e);}finally{setUpdate({disabled:false});}
      }
    }
    root.addEventListener('click',handleClick);
    root.addEventListener('keydown',e=>{if(e.key==='Escape'&&!e.composedPath().some(n=>n.classList?.contains('library-native-composer'))){e.stopPropagation();options.onClose?.();}});
    poll=setInterval(()=>{if(!disposed&&!maintenance)load();},15000);start();
    return {snapshot:()=>content.snapshot(),destroy(){disposed=true;sequence++;clearInterval(poll);cancelLaunch();projectPicker?.destroy();toolbar?.destroy();content.destroy();root.replaceChildren();}};
  };
})();
