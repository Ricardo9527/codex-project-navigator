(() => {
  window.createContentPage = ({root, request, icon, escape: esc, markdown, onThread, mountComposer, mountControl, startWork, onUpdated}) => {
    const $ = selector => root.querySelector(selector)||nativeSurface?.element?.querySelector(selector);
    const $$ = selector => [...root.querySelectorAll(selector),...(nativeSurface?.element?.querySelectorAll(selector)||[])];
    let page, project, signature, category = null, cardId = null, returnCategory = null, query = '';
    let active = false, disposed = false, preview = null, sequence = 0, listScroll = 0, imageObserver;
    let searchResult=null,searchSequence=0,searchTimer,searchPoll;
    let expanded = new Set(), gallery = [], galleryIndex = 0, nativeComposer, nativeDirectory, nativeSurface, nativeDialog, dialogDock, pendingScroll, pendingFocus, composerSequence = 0;
    const card = () => page.cards.find(c => c.id === cardId);
    const paragraphs = lines => lines.map(line => `<p>${esc(line)}</p>`).join('');
    const button = (action, label, id = '', extra = '') => `<button type="button" data-action="content-${action}" data-id="${esc(id)}" ${extra}>${esc(label)}</button>`;
    const children = id => page.categories.filter(c => (c.parentId || null) === id);
    function descendants(id) {return [id, ...children(id).flatMap(c => descendants(c.id))];}
    function ancestors(id) {const c = page.categories.find(c => c.id === id); return c ? [...(c.parentId ? ancestors(c.parentId) : []), c] : [];}
    const cardsIn = id => page.cards.filter(c => c.categoryIds.some(cid => descendants(id).includes(cid)));
    const titleFor = id => id ? page.categories.find(c => c.id === id).title : '项目首页';

    function update(data) {
      active = true; $('.main').classList.add('organized'); $('.heading').hidden = true; $('.filters').hidden = true;
      const next = JSON.stringify(data.contentPage), changed = project?.id !== data.project.id;
      if (!changed && signature === next) return;
      if (changed) {category = null; cardId = null; query = ''; expanded = new Set(); listScroll = 0;}
      const previousCard=page?.cards.find(c=>c.id===cardId);
      const preserveComposer=!changed&&Boolean(nativeComposer)&&Boolean(cardId);
      project = data.project; page = data.contentPage; signature = next;
      if(preserveComposer&&!page.cards.some(c=>c.id===cardId)&&previousCard)page={...page,cards:[...page.cards,{...previousCard,stale:true}]};
      if (category && !page.categories.some(c => c.id === category)) category = null;
      if (returnCategory && !page.categories.some(c => c.id === returnCategory)) returnCategory = null;
      if (cardId && !page.cards.some(c => c.id === cardId)) {cardId = null; category = returnCategory; listScroll = 0;}
      if (changed) page.categories.filter(c => c.parentId).forEach(c => expanded.add(c.parentId));
      render(preserveComposer);if(changed)pendingFocus='heading';
    }
    function snapshot() {
      if(!project)return null;
      return {projectId:project.id,category,cardId,returnCategory,query,expanded:[...expanded],listScroll,scrollTop:$('.results').scrollTop};
    }
    function restore(state) {
      if(!state||state.projectId!==project.id)return;
      const hasCategory=id=>page.categories.some(c=>c.id===id);
      category=hasCategory(state.category)?state.category:null;
      returnCategory=hasCategory(state.returnCategory)?state.returnCategory:null;
      cardId=page.cards.some(c=>c.id===state.cardId)?state.cardId:null;
      query=state.query;expanded=new Set(state.expanded.filter(hasCategory));listScroll=state.listScroll;
      pendingScroll=state.scrollTop;render();if(!mountControl)requestAnimationFrame(()=>{if(active&&!disposed)$('.results').scrollTop=state.scrollTop;});
      if(query&&!cardId)searchRemote(false);
    }
    function deactivate() {
      active = false; nativeSurface?.destroy();nativeSurface=null;nativeDialog?.destroy();nativeDialog=null;dialogDock?.remove();signature = null; sequence++; composerSequence++; nativeComposer?.destroy();nativeComposer=null; imageObserver?.disconnect(); closeGallery(false);
      $('.content-compose-dock')?.remove(); $('.main').classList.remove('organized'); $('.heading').hidden = false; $('.filters').hidden = false;
    }
    function navBranch(parent = null, depth = 0) {
      return children(parent).map(c => {
        const nested = children(c.id).length > 0, open = expanded.has(c.id);
        return `<div class="directory-branch"><div class="directory-row" style="--depth:${depth}">
          ${nested ? button('expand', open ? '⌄' : '›', c.id, `class="directory-toggle" aria-label="${open?'收起':'展开'}${esc(c.title)}" aria-expanded="${open}" aria-controls="directory-${esc(c.id)}"`) : '<span class="directory-spacer"></span>'}
          ${button('category', c.title, c.id, `class="directory-label" aria-current="${category===c.id?'page':'false'}"`)}<span class="nav-count">${cardsIn(c.id).length}</span></div>
          ${nested ? `<div id="directory-${esc(c.id)}" ${open?'':'hidden'}>${navBranch(c.id,depth+1)}</div>` : ''}</div>`;
      }).join('');
    }
    function nav() {
      $('.topics').setAttribute('aria-label','内容目录');
      if(mountControl){
        const props={categories:page.categories,category,expanded:[...expanded],counts:Object.fromEntries(page.categories.map(c=>[c.id,cardsIn(c.id).length])),coverage:page.coverage,
          onSelect:id=>{if(active){query='';navigate(id,null);}},
          onToggle:id=>{if(active){expanded.has(id)?expanded.delete(id):expanded.add(id);nav();}}};
        if(nativeDirectory)nativeDirectory.update(props);
        else{const dock=document.createElement('div');$('.topics').replaceChildren(dock);nativeDirectory=mountControl({dock,kind:'directory',props,onError:e=>{$('.error').hidden=false;$('.error').textContent=e.message;}});}
        return;
      }
      $('.topics').innerHTML = `<div class="content-nav">${button('category','项目首页','',`aria-current="${category===null?'page':'false'}" class="home-link"`)}
        <div class="section-label">内容目录</div><nav aria-label="项目内容分类">${navBranch()}</nav>
        <div class="content-nav-bottom"><p>${esc(page.coverage)}</p></div></div>`;
    }
    function selectedCards() {
      const q = query.trim().toLocaleLowerCase();
      return page.cards.filter(c => (!category || c.categoryIds.some(id => descendants(category).includes(id))) && (!q || searchResult?.cardIds.includes(c.id)||JSON.stringify([c.title,c.summary,c.sections,c.requirements,c.records,c.attention,c.sources,c.resources.map(r=>[r.label,r.note,r.path])]).toLocaleLowerCase().includes(q)));
    }
    function searchHTML(){
      if(!query.trim()||!searchResult)return '';
      return `<section class="search-sources"><h2>文件与对话中的结果</h2>${searchResult.indexing?`<p role="status">${searchResult.progress.total?`正在查找 ${searchResult.progress.done} / ${searchResult.progress.total}…`:'正在更新搜索结果…'}</p>`:''}${searchResult.hits.map((hit,i)=>`<button class="search-hit" data-action="content-search-open" data-id="${i}"><strong>${esc(hit.title)}</strong><span>${hit.kind==='thread'?'对话':esc(hit.path)}</span><p>${esc(hit.snippet||'')}</p></button>`).join('')}${searchResult.hits.length<searchResult.total?button('search-more',`继续显示（共 ${searchResult.total} 条）`):''}${searchResult.errors.length?`<details><summary>${searchResult.errors.length} 项正文暂未读取</summary>${searchResult.errors.map(e=>`<p>${esc(e.title)}：${esc(e.error)}</p>`).join('')}</details>`:''}</section>`;
    }
    async function searchRemote(refresh,more=false){
      const n=++searchSequence,selectedProject=project.id,text=query;
      try{
        const result=await request('projectSearch',{projectId:selectedProject,query:text,refresh,offset:more?searchResult.hits.length:0});
        if(disposed||!active||project.id!==selectedProject||query!==text||n!==searchSequence)return;
        if(more)result.hits=[...searchResult.hits,...result.hits];searchResult=result;
        refreshListing();
        clearTimeout(searchPoll);if(result.indexing)searchPoll=setTimeout(()=>searchRemote(false),750);
      }catch(e){if(n===searchSequence){$('.error').hidden=false;$('.error').textContent=e.message;}}
    }
    async function openSearchResult(index){
      const hit=searchResult.hits[index];
      if(hit.kind==='thread'){await onThread(hit.identity);return;}
      const value=await request('searchOpen',{projectId:project.id,kind:hit.kind,identity:hit.identity});
      if(mountControl){nativeModal(hit.title,previewHTML(value)+button('search-reveal','文件位置',index));return;}
      $('.search-preview')?.remove();const dialog=document.createElement('dialog');dialog.className='record-edit search-preview';dialog.setAttribute('aria-label',hit.title);
      const body=value.type==='image'?`<img src="${esc(value.data)}" alt="${esc(hit.title)}">`:value.type==='text'?(value.markdown?markdown.render(value.text):`<pre>${esc(value.text)}</pre>`):`<p>${esc(value.message)}</p>`;
      dialog.innerHTML=`<h2>${esc(hit.title)}</h2><div class="content-preview-body">${body}</div><footer>${button('search-reveal','文件位置',index)}${button('search-close','关闭')}</footer>`;$('.library').append(dialog);dialog.showModal();
    }
    function cardHTML(c) {
      return `<button class="content-card" data-action="content-card" data-id="${esc(c.id)}"><span class="card-heading"><span class="card-symbol">${icon(c.icon)}</span><span class="card-type">${esc(c.kind)}</span><span class="card-arrow" aria-hidden="true">↗</span></span><span class="card-title">${esc(c.title)}</span><span class="card-summary">${esc(c.summary)}</span><span class="card-bottom"><span>${esc(c.caption)}</span>${c.status?`<span class="card-status">${c.attention?'<span class="status-dot" aria-hidden="true"></span>':''}${esc(c.status)}</span>`:''}</span></button>`;
    }
    function groups() {
      const cards = selectedCards();
      if (!cards.length&&!query&&page.uninitialized)return '<div class="content-empty"><p>可以先搜索已有文件和对话，也可以开始整理。</p><button class="outline" data-action="maintain">整理这个项目</button></div>';
      if(!cards.length&&query&&(!searchResult||searchResult.indexing))return '<p role="status">正在搜索文件和对话…</p>';
      if(!cards.length&&query&&searchResult?.total)return '';
      if (!cards.length) return `<div class="content-empty"><h2>没有找到相关内容</h2><p>换个关键词试试。</p>${button('clear','清除搜索')}</div>`;
      if (category || query.trim()) return `<div class="content-grid">${cards.map(cardHTML).join('')}</div>`;
      return children(null).map(c => {const group = cards.filter(item=>descendants(c.id).includes(item.categoryIds[0]));return group.length?`<section class="content-group"><div class="content-group-heading"><h2>${esc(c.title)}</h2><span>${group.length}</span></div><div class="content-grid">${group.map(cardHTML).join('')}</div></section>`:'';}).join('');
    }
    function deliveryIssues(card=null){
      const issues=Object.values(page.deliveryReview||{}).filter(g=>g.status==='unavailable'&&(!card||g.cardId===card));
      if(!issues.length)return '';
      return disclosure('暂未找回的内容',issues.map(g=>`<p><strong>${esc(g.label)}</strong>：${esc(g.reason)}</p>${g.origin||g.sources?.length?button('gap-source','查看来源',g.id):''}`).join(''));
    }
    function list() {
      const current = page.categories.find(c=>c.id===category);
      return `<div class="content-document"><header class="content-heading">${category?`<div class="content-eyebrow">${esc([project.name,...ancestors(category).slice(0,-1).map(c=>c.title)].join(' / '))}</div>`:''}
        <h1 tabindex="-1">${esc(current?.title||project.name)}</h1><p class="content-intro">${esc(current?.description||page.about)}</p>
        ${!category&&page.history?`<details class="project-history"><summary>项目历史</summary><p>${esc(page.history)} ${button('card','查看记录',page.historyCardId)}</p></details>`:''}</header>
        <div class="content-toolbar"><label class="search content-search">${icon('search')}<input id="content-search" type="search" autocomplete="off" value="${esc(query)}" placeholder="搜索内容" aria-label="搜索内容"></label><span class="content-total" aria-live="polite">${selectedCards().length} 项${query&&searchResult?' · '+searchResult.total+' 条来源':''}</span></div>
        <div id="content-card-list">${groups()}${searchHTML()}</div>${!category?deliveryIssues():''}${!category?`<p class="content-coverage">${esc(page.coverageDetail)}</p>`:''}</div>`;
    }
    const resourceName = r => r.displayLabel || r.label;
    function resourceMeta(r) {
      const time=r.deliveredAt||r.sortTime;
      return [r.format,time?`${time.slice(0,10)}${r.timeBasis==='file'?' · 文件更新':''}`:''].filter(Boolean).join(' · ');
    }
    function fileButton(r) {
      return `${button(r.format==='图片'?'image':'preview','预览',r.id,`class="resource-preview-button" ${r.exists?'':'disabled'} aria-label="预览${esc(resourceName(r))}"`)}
        ${button('source','↗',r.id,`class="file-location" ${r.origin?'':'disabled'} aria-label="跳到来源消息：${esc(resourceName(r))}" title="${r.origin?'跳到来源消息':'来源消息尚未定位'}"`)}
        <button type="button" class="file-location icon" data-action="content-reveal" data-id="${esc(r.id)}" ${r.exists?'':'disabled'} aria-label="在文件夹中显示${esc(resourceName(r))}" title="在文件夹中显示">${icon('folder')}</button>`;
    }
    function adoptionButton(r) {
      if(r.role!=='result')return '';
      const selected=r.effectiveAdoption==='accepted';
      return `${selected?'<span class="adoption-label">✓ 已选用</span>':r.versionChanged?'<span>文件已更新</span>':''}${button(selected?'unadopt':'adopt',selected?'取消选用':'确认选用',r.id,`${r.exists||selected?'':'disabled'}`)}`;
    }
    function filesHTML(resources) {
      return `<div class="resource-list">${resources.map(r=>`<div class="content-resource ${r.effectiveAdoption==='accepted'?'is-adopted':''}"><span class="resource-symbol">${icon(r.source==='skill'?'book':'file')}</span><div class="resource-label"><strong>${esc(resourceName(r))}</strong><span>${esc(resourceMeta(r))}</span>${!r.exists?'<span>文件暂不可用，可查来源消息</span>':''}</div><div class="resource-actions">${fileButton(r)}${adoptionButton(r)}</div></div>`).join('')}</div>`;
    }
    function photo(r) {
      return `<figure class="content-photo ${r.effectiveAdoption==='accepted'?'is-adopted':''}"><button data-action="content-image" data-id="${esc(r.id)}" aria-label="放大${esc(resourceName(r))}" ${r.exists?'':'disabled'}><img data-content-image="${esc(r.id)}" alt="${esc(resourceName(r))}" loading="lazy"><span class="image-error" hidden></span></button><figcaption><div class="photo-caption"><strong>${esc(resourceName(r))}</strong><span>${esc(resourceMeta(r))}</span></div><div class="photo-actions">${fileButton(r)}${adoptionButton(r)}</div></figcaption></figure>`;
    }
    function imagesHTML(images) {
      return `<div class="content-gallery ${images.length===1?'single-image':''}">${images.map(photo).join('')}</div>`;
    }
    function disclosure(title,body) {return `<details class="content-disclosure"><summary>${esc(title)}</summary><div class="disclosure-body">${body}</div></details>`;}
    function detail() {
      const c=card(), results=c.resources.filter(r=>r.role==='result'), pictures=results.filter(r=>r.format==='图片'), files=results.filter(r=>r.format!=='图片'), process=c.resources.filter(r=>r.role==='process'||r.role==='preview'&&!c.resources.some(parent=>parent.previewId===r.id));
      const notes=c.sections.filter(s=>!s.title.includes('版本')), versions=c.sections.filter(s=>s.title.includes('版本'));
      return `<article class="content-document content-detail"><div class="content-breadcrumb">${button('back','← '+titleFor(returnCategory))}${returnCategory?'':`<span>${esc(ancestors(category||c.categoryIds[0]).map(c=>c.title).join(' / '))}</span>`}</div>
        <header class="content-heading"><div class="content-title-row"><h1 tabindex="-1">${esc(c.title)}</h1>${button('add-file','添加文件')}${button('edit','编辑')}</div><p class="content-intro">${esc(c.summary)}</p>${c.links?.length?`<div class="content-link-list">${c.links.filter(link=>link.url.startsWith('https://')).map(link=>`<a href="${esc(link.url)}" target="_blank" rel="noopener noreferrer">${esc(link.label)} ↗</a>`).join('')}</div>`:''}${c.stale?'<p role="status">这项内容已调整，输入草稿已保留。请先保存草稿，再选择对应的新卡片。</p>':''}${c.status?`<div class="detail-meta">${esc(c.status)}</div>`:''}</header>
        <div class="content-detail-columns"><div class="content-primary">${results.length?`<section class="detail-section"><h2>${esc(c.resourceHeading||'文件')}</h2>${pictures.length?imagesHTML(pictures):''}${files.length?filesHTML(files):''}</section>`:''}
        <div id="content-preview-slot"></div>
        ${c.attention?`<section class="content-attention"><h2>${icon('info')}需要注意</h2>${paragraphs(c.attention)}</section>`:''}
        ${c.quickStart?`<p class="content-quick-start">${esc(c.quickStart)}</p>`:''}
        <div class="detail-folders">${deliveryIssues(c.id)}
          ${notes.length||c.requirements.length?disclosure('说明与要求',`${c.requirements.length?`<ul>${c.requirements.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`:''}${notes.map(s=>`<h3>${esc(s.title)}</h3>${paragraphs(s.paragraphs)}`).join('')}`):''}
          ${c.records.length||versions.length?disclosure('修改记录',`${versions.map(s=>paragraphs(s.paragraphs)).join('')}<ol class="content-timeline">${c.records.map(r=>`<li><span class="timeline-date">${esc(r.date)}</span><p>${esc(r.text)}</p></li>`).join('')}</ol>`):''}
          ${process.length?disclosure(`其他文件 · ${process.length}`,filesHTML(process)):''}
        </div>
        </div><aside class="content-context" aria-label="相关信息">
          ${c.related.length?`<section><h2>相关内容</h2>${c.related.map(id=>button('related',page.cards.find(c=>c.id===id).title,id,'class="context-link"')).join('')}</section>`:''}
          ${c.sources.length?`<section><h2>相关对话</h2>${c.sources.map(s=>`<button class="context-link" data-action="content-thread" data-id="${esc(s.id)}">${icon('chat')}<span>${esc(s.title)}</span></button>`).join('')}</section>`:''}
        </aside></div>
      </article>`;
    }
    function composer() {
      const turn=++composerSequence;nativeComposer?.destroy();nativeComposer=null;$('.content-compose-dock')?.remove();if(!cardId)return;
      if(startWork&&mountControl){
        const dock=document.createElement('div');dock.className='content-compose-dock';$('.main').append(dock);
        const selected=cardId,selectedProject=project.id;nativeComposer=mountControl({dock,kind:'work',props:{enabled:startWork.enabled(),note:startWork.note(),onStart:()=>startWork.open(selectedProject,selected)},onError:e=>{$('.error').hidden=false;$('.error').textContent=e.message;}});return;
      }
      if(startWork){
        const dock=document.createElement('div');dock.className='content-compose-dock';
        const button=document.createElement('button');button.className='outline';button.textContent='在此项目开始工作';button.disabled=!startWork.enabled();
        const feedback=document.createElement('p');feedback.className='composer-feedback';feedback.setAttribute('role','status');feedback.textContent=startWork.note();
        const selected=cardId,selectedProject=project.id;
        button.onclick=async()=>{button.disabled=true;try{await startWork.open(selectedProject,selected);feedback.textContent='已请求打开项目原生草稿，请填写需求后发送。';}catch(error){feedback.textContent=error.message;}finally{button.disabled=!startWork.enabled();}};
        dock.append(button,feedback);$('.main').append(dock);return;
      }
      const selected=cardId,selectedProject=project.id,dock=document.createElement('div');dock.className='content-compose-dock';
      dock.innerHTML=`<div class="native-composer-align"><div class="composer-card-label">已关联：${esc(card().title)}</div><div class="native-composer-slot"></div><p class="composer-feedback" role="status">正在读取输入框…</p></div>`;$('.main').append(dock);
      if(!mountComposer){dock.querySelector('.composer-feedback').textContent='在 Codex 中打开项目资料，即可从卡片开始工作。';return;}
      request('cardContext',{projectId:selectedProject,cardId:selected}).then(context=>{
        if(disposed||!active||turn!==composerSequence)return;
        dock.querySelector('.composer-feedback').textContent='';
        nativeComposer=mountComposer({dock:dock.querySelector('.native-composer-slot'),project,context:{...context,key:selected},
          beforeSubmit:()=>request('cardContext',{projectId:selectedProject,cardId:selected}),
          onError:error=>{if(dock.isConnected)dock.querySelector('.composer-feedback').textContent=error.message;},
          onCreated:async id=>{try{await request('linkCardThread',{projectId:selectedProject,cardId:selected,threadId:id});await onThread(id);}catch(error){if(dock.isConnected)dock.querySelector('.composer-feedback').textContent=error.message;}}
        });
      }).catch(error=>{if(dock.isConnected)dock.querySelector('.composer-feedback').textContent=error.message;});
    }
    function edit() {
      const c=card(),editingRevision=page.revision;
      if(mountControl){nativeModal('编辑卡片','',{fields:{title:c.title,summary:c.summary},onSave:async changes=>{await request('updateCard',{projectId:project.id,cardId:c.id,expectedRevision:editingRevision,changes});await onUpdated();}});return;}
      const dialog=document.createElement('dialog');dialog.className='record-edit';
      dialog.innerHTML=`<form><h2>编辑卡片</h2><label>名称<input name="title" required maxlength="150" value="${esc(c.title)}"></label><label>这件事是做什么的？<textarea name="summary" required maxlength="500">${esc(c.summary)}</textarea></label><p role="alert"></p><footer>${button('edit-close','取消')}<button type="submit">保存</button></footer></form>`;
      $('.library').append(dialog);dialog.setAttribute('aria-label','编辑卡片');dialog.showModal();dialog.querySelector('input').focus();
      dialog.querySelector('form').addEventListener('submit',async event=>{event.preventDefault();const submit=dialog.querySelector('[type="submit"]');submit.disabled=true;try{await request('updateCard',{projectId:project.id,cardId,expectedRevision:editingRevision,changes:{title:dialog.querySelector('input').value,summary:dialog.querySelector('textarea').value}});dialog.close();dialog.remove();await onUpdated();}catch(error){dialog.querySelector('[role="alert"]').textContent=error.message;submit.disabled=false;}});
    }
    function observeImages() {
      imageObserver?.disconnect();
      imageObserver=new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting)continue;const img=entry.target;imageObserver.unobserve(img);request('pageThumbnail',{projectId:project.id,cardId,resourceId:img.dataset.contentImage}).then(r=>{if(img.isConnected)img.src=r.data;}).catch(e=>{if(!img.isConnected)return;img.hidden=true;const message=img.nextElementSibling;message.hidden=false;message.textContent=e.message;});}},{root:$('.results'),rootMargin:'150px'});
      $$('[data-content-image]').forEach(img=>imageObserver.observe(img));
    }
    function surfaceRendered(){
      if(disposed||!active)return;
      observeImages();
      if(pendingScroll!==undefined){$('.results').scrollTop=pendingScroll;pendingScroll=undefined;}
      if(pendingFocus){const target=pendingFocus==='heading'?$('.content-heading h1'):$$('[data-action="content-card"]').find(n=>n.dataset.id===pendingFocus);target?.focus({preventScroll:true});pendingFocus=undefined;}
    }
    function renderBody(){
      const html=cardId?detail():list();
      if(!mountControl){$('.results').innerHTML=html;surfaceRendered();return;}
      const props={html,routeKey:[project.id,category||'',cardId||''].join('/'),css:window.__codexLibraryConfig?.contentCSS,onClick:click,onInput:input,onRendered:surfaceRendered};
      if(nativeSurface)nativeSurface.update(props);
      else{const dock=document.createElement('div');$('.results').replaceChildren(dock);nativeSurface=mountControl({dock,kind:'surface',props,onError:e=>{$('.error').hidden=false;$('.error').textContent=e.message;}});}
    }
    function refreshListing(){
      if(mountControl)renderBody();
      else{$('#content-card-list').innerHTML=groups()+searchHTML();$('.content-total').textContent=`${selectedCards().length} 项`;}
    }
    function render(preserveComposer=false) {
      closeGallery(false);nav();sequence++;preview=null;
      $('.results').className='results content-scroll';renderBody();if(!preserveComposer)composer();
    }
    function nativeModal(title,html,extra={}){
      nativeDialog?.destroy();dialogDock?.remove();dialogDock=document.createElement('div');$('.library').append(dialogDock);
      nativeDialog=mountControl({dock:dialogDock,kind:'dialog',props:{title,html,...extra,onClose:()=>{nativeDialog?.update({open:false});preview=null;},onAction:(action,id)=>click({target:{closest:()=>({dataset:{action,id}})}})},onError:e=>{$('.error').hidden=false;$('.error').textContent=e.message;}});
      return nativeDialog;
    }
    function previewHTML(result){
      return result.type==='image'?`<img src="${esc(result.data)}" alt="文件预览">`:result.type==='text'?(result.markdown?markdown.render(result.text):`<pre>${esc(result.text)}</pre>`):`<p>${esc(result.message)}</p>`;
    }
    function navigate(nextCategory,nextCard,focusId) {
      category=nextCategory;cardId=nextCard;ancestors(category).forEach(c=>{if(c.parentId)expanded.add(c.parentId);});
      pendingFocus=focusId||'heading';pendingScroll=0;render();$('.results').scrollTop=0;
      const target=focusId?[...$$('[data-action="content-card"]')].find(n=>n.dataset.id===focusId):$('.content-heading h1');target?.focus({preventScroll:true});
    }
    function back(){const previous=cardId;navigate(returnCategory,null,previous);pendingScroll=listScroll;$('.results').scrollTop=listScroll;}
    function closePreview(){nativeDialog?.update({open:false});const id=preview;preview=null;sequence++;$('#content-preview-slot').replaceChildren();[...$$('[data-action="content-preview"]')].find(n=>n.dataset.id===id)?.focus();}
    async function showPreview(id) {
      const c=card(),r=c.resources.find(r=>r.id===id),turn=++sequence;preview=id;
      if(mountControl){
        const modal=nativeModal(resourceName(r),'<p role="status">正在读取…</p>');
        try{const result=await request('pagePreview',{projectId:project.id,cardId:c.id,resourceId:r.previewId||r.id});if(disposed||modal!==nativeDialog)return;r.versionStamp=result.versionStamp;modal.update({html:previewHTML(result)+(result.truncated?'<p>这里只显示部分内容，完整内容请打开源文件。</p>':'')+`<footer>${button('preview','刷新预览',id)}${fileButton(r)}</footer>`});}
        catch(e){if(modal===nativeDialog)modal.update({html:`<p role="alert">${esc(e.message)}</p>${button('preview','重试',id)}`});}
        return;
      }
      const slot=$('#content-preview-slot');slot.innerHTML=`<section class="content-preview"><header><h2>${esc(r.label)}</h2>${button('preview-close','×','',`aria-label="关闭预览"`)}</header><div class="content-preview-body" aria-live="polite">正在读取…</div><footer>${button('preview','刷新预览',id)}<button class="icon" data-action="content-reveal" data-id="${esc(id)}" aria-label="在文件夹中显示" title="在文件夹中显示">${icon('folder')}</button></footer></section>`;
      slot.querySelector('button').focus({preventScroll:true});slot.scrollIntoView({block:'nearest'});
      try{const result=await request('pagePreview',{projectId:project.id,cardId:c.id,resourceId:r.previewId||r.id});if(disposed||!active||sequence!==turn)return;
        r.versionStamp=result.versionStamp;$('.error').hidden=true;
        $('.content-preview-body').innerHTML=result.type==='image'?`<img src="${esc(result.data)}" alt="${esc(r.label)}">`:result.type==='text'?(result.markdown?`<div class="content-markdown">${markdown.render(result.text)}</div>`:`<pre>${esc(result.text)}</pre>`):`<p>${esc(result.message)}</p>`;
        if(result.truncated)$('.content-preview-body').insertAdjacentHTML('beforeend','<p>这里只显示部分内容，完整内容请打开源文件。</p>');
      }catch(e){if(!disposed&&active&&sequence===turn)$('.content-preview-body').innerHTML=`<p role="alert">${esc(e.message)}</p>${button('preview','重试',id)}`;}
    }
    function closeGallery(focus=true){nativeDialog?.update({open:false});const dialog=$('.image-viewer');if(!dialog)return;const id=dialog.dataset.resourceId;dialog.close();dialog.remove();if(focus)[...$$('[data-action="content-image"]')].find(n=>n.dataset.id===id)?.focus();}
    async function showImage(id) {
      gallery=card().resources.filter(r=>r.format==='图片'&&r.exists);galleryIndex=gallery.findIndex(r=>r.id===id);if(galleryIndex<0)return;
      closeGallery(false);if(mountControl){nativeModal('图片预览','<p role="status">正在读取图片…</p>',{onKeyDown:e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){const next=galleryIndex+(e.key==='ArrowRight'?1:-1);if(next>=0&&next<gallery.length){e.preventDefault();imageAt(next);}}}});await imageAt(galleryIndex);return;}const dialog=document.createElement('dialog');dialog.className='image-viewer';dialog.dataset.resourceId=id;dialog.setAttribute('aria-label','图片预览');$('.library').append(dialog);dialog.showModal();await imageAt(galleryIndex);
    }
    async function imageAt(index) {
      galleryIndex=index;const r=gallery[index],turn=++sequence;
      if(mountControl){const modal=nativeDialog;modal.update({title:resourceName(r),html:'<p role="status">正在读取图片…</p>'});try{const result=await request('pagePreview',{projectId:project.id,cardId,resourceId:r.id});if(disposed||modal!==nativeDialog||sequence!==turn)return;r.versionStamp=result.versionStamp;modal.update({html:previewHTML(result)+`<footer>${button('image-previous','上一张','',index===0?'disabled':'')} ${index+1} / ${gallery.length} ${button('image-next','下一张','',index===gallery.length-1?'disabled':'')}${button('image-refresh','刷新预览',r.id)}${fileButton(r)}</footer>`});}catch(e){if(modal===nativeDialog)modal.update({html:`<p role="alert">${esc(e.message)}</p>`});}return;}
      const dialog=$('.image-viewer');dialog.dataset.resourceId=r.id;
      dialog.innerHTML=`<header><span>${esc(r.label)}${r.versionLabel?' · '+esc(r.versionLabel):''}</span>${button('image-close','×','',`aria-label="关闭图片"`)}</header><div class="image-stage" aria-live="polite">正在读取图片…</div><footer>${button('image-previous','←','',`aria-label="上一张" ${index===0?'disabled':''}`)}<span>${index+1} / ${gallery.length}</span>${button('image-next','→','',`aria-label="下一张" ${index===gallery.length-1?'disabled':''}`)}${button('image-refresh','刷新预览',r.id)}<button class="icon" data-action="content-reveal" data-id="${esc(r.id)}" aria-label="在文件夹中显示" title="在文件夹中显示">${icon('folder')}</button></footer>`;
      dialog.querySelector('[data-action="content-image-close"]').focus();
      try{const result=await request('pagePreview',{projectId:project.id,cardId,resourceId:r.id});if(disposed||sequence!==turn||!dialog.isConnected)return;r.versionStamp=result.versionStamp;$('.error').hidden=true;dialog.querySelector('.image-stage').innerHTML=result.type==='image'?`<img src="${esc(result.data)}" alt="${esc(r.label)}">`:`<p>${esc(result.message)}</p>`;}catch(e){if(dialog.isConnected&&sequence===turn)dialog.querySelector('.image-stage').textContent=e.message;}
    }
    async function click(event) {
      const b=event.target.closest('[data-action^="content-"]');if(!b||!active)return;const action=b.dataset.action.slice(8),id=b.dataset.id;
      try{
        if(action==='category'){query='';navigate(id||null,null);}
        else if(action==='expand'){expanded.has(id)?expanded.delete(id):expanded.add(id);nav();[...root.querySelectorAll('[data-action="content-expand"]')].find(n=>n.dataset.id===id)?.focus();}
        else if(action==='card'){returnCategory=category;listScroll=$('.results').scrollTop;navigate(category,id);}
        else if(action==='related'){const c=page.cards.find(c=>c.id===id);returnCategory=c.categoryIds[0];query='';listScroll=0;navigate(returnCategory,id);}
        else if(action==='back')back();
        else if(action==='clear'){query='';searchResult=null;searchSequence++;clearTimeout(searchPoll);render();$('#content-search').focus();}
        else if(action==='edit')edit();
        else if(action==='add-file'){
          const chosen=await request('chooseResource',{projectId:project.id});if(chosen.cancelled)return;
          await request('registerResource',{projectId:project.id,cardId,path:chosen.path,external:true,expectedRevision:page.revision});await onUpdated();
        }
        else if(action==='adopt'||action==='unadopt'){await request('adoptResource',{projectId:project.id,cardId,resourceId:id,adoption:action==='unadopt'?'review':'accepted',expectedRevision:page.revision,expectedStamp:card().resources.find(r=>r.id===id).versionStamp});await onUpdated();}
        else if(action==='source'){const origin=card().resources.find(r=>r.id===id).origin;await onThread(origin.threadId,origin);}
        else if(action==='search-more')await searchRemote(false,true);
        else if(action==='search-open')await openSearchResult(Number(id));
        else if(action==='search-close'){$('.search-preview')?.close();$('.search-preview')?.remove();}
        else if(action==='search-reveal'){const hit=searchResult.hits[Number(id)];await request('searchOpen',{projectId:project.id,kind:hit.kind,identity:hit.identity,reveal:true});}
        else if(action==='edit-close'){$('.record-edit').close();$('.record-edit').remove();}
        else if(action==='gap-source'){const gap=page.deliveryReview[id];await onThread(gap.origin?.threadId||gap.sources[0].id,gap.origin);}
        else if(action==='thread')await onThread(id);
        else if(action==='preview')await showPreview(id);
        else if(action==='refresh-preview'){await onUpdated();await showPreview(id);}
        else if(action==='image-refresh')await imageAt(galleryIndex);
        else if(action==='preview-close')closePreview();
        else if(action==='reveal')await request('pageReveal',{projectId:project.id,cardId,resourceId:id});
        else if(action==='image')await showImage(id);
        else if(action==='image-close'){sequence++;closeGallery();}
        else if(action==='image-next'||action==='image-previous')await imageAt(galleryIndex+(action==='image-next'?1:-1));

      }catch(e){$('.error').hidden=false;$('.error').textContent=e.message;if(action==='adopt')$('.error').insertAdjacentHTML('beforeend',button('refresh-preview','刷新预览',id));}
    }
    function input(event) {
      if(!active)return;
      if(event.target.id==='content-search'){query=event.target.value;searchResult=null;searchSequence++;clearTimeout(searchTimer);clearTimeout(searchPoll);refreshListing();if(query.trim())searchTimer=setTimeout(()=>searchRemote(true),250);}

    }
    function keydown(event) {
      if(!active)return;
      if(event.composedPath().some(n=>n.classList?.contains('library-native-composer')))return;
      if($('.record-edit')&&event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();$('.record-edit').close();$('.record-edit').remove();return;}
      if($('.image-viewer')&&['ArrowLeft','ArrowRight','Escape'].includes(event.key)){event.preventDefault();event.stopImmediatePropagation();if(event.key==='Escape'){sequence++;closeGallery();}else{const next=galleryIndex+(event.key==='ArrowRight'?1:-1);if(next>=0&&next<gallery.length)imageAt(next);}return;}
      if(event.key==='Escape'&&(preview||cardId)){event.preventDefault();event.stopImmediatePropagation();if(preview)closePreview();else back();}
    }
    root.addEventListener('click',click);root.addEventListener('input',input);root.addEventListener('keydown',keydown,true);
    return {update,deactivate,snapshot,restore,destroy(){disposed=true;nativeDirectory?.destroy();nativeSurface?.destroy();nativeDialog?.destroy();dialogDock?.remove();clearTimeout(searchTimer);clearTimeout(searchPoll);searchSequence++;sequence++;composerSequence++;nativeComposer?.destroy();imageObserver?.disconnect();closeGallery(false);$('.content-compose-dock')?.remove();root.removeEventListener('click',click);root.removeEventListener('input',input);root.removeEventListener('keydown',keydown,true);}};
  };
})();
