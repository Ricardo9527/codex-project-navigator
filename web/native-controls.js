/* Native desktop controls, using the installed build's exported menu and sidebar components. */
(() => {
  window.mountLibraryNativeControl=({host,dock,kind,props,onError})=>{
    let root,slot,container,disposed=false,current=props,draw;
    const ready=(async()=>{
      const urls=[...document.querySelectorAll('link[rel="modulepreload"]')].map(n=>n.href);
      const module=name=>{const url=urls.find(u=>new RegExp('/app-'+name+'-[^/]+\\.js$').test(u));if(!url)throw Error('当前 Codex 版本的原生导航控件需要适配。');return import(url);};
      const [shared,initial]=await Promise.all([module('shared'),module('initial')]);if(disposed)return;
      const React=shared.t0t(),ReactDOM=shared.P1t(),el=React.createElement;
      const Button=shared.HQt,Menu=shared.Gb,MenuItem=shared.qb.Item,SidebarItem=initial.nkt,SidebarSection=initial.ikt;
      let node=[...document.querySelectorAll('[contenteditable="true"]')].find(n=>!n.closest('.library-native-composer')),key;
      while(node&&!(key=Object.keys(node).find(k=>k.startsWith('__reactFiber'))))node=node.parentElement;
      if(!node)throw Error('请先打开一个对话，再打开项目导航。');
      const providers=[];for(let fiber=node[key];fiber;fiber=fiber.return)if(fiber.tag===10)providers.push({type:fiber.type,value:fiber.memoizedProps.value});
      slot=document.createElement('slot');slot.name='project-navigation-control-'+crypto.randomUUID();dock.append(slot);
      container=document.createElement('div');container.slot=slot.name;container.dataset.nativeNavigationControl=kind;container.style.cssText='min-width:0;width:100%;color:var(--color-text-primary)';host.append(container);
      const chevron=open=>el('svg',{viewBox:'0 0 16 16',width:16,height:16,'aria-hidden':true,style:{transform:open?'rotate(90deg)':undefined}},el('path',{d:'m6 4 4 4-4 4',fill:'none',stroke:'currentColor',strokeWidth:1.5,strokeLinecap:'round',strokeLinejoin:'round'}));
      function ProjectPicker({projects,selected,onSelect}){
        const [query,setQuery]=React.useState('');
        const label=projects.find(p=>p.id===selected)?.name||'选择项目';
        const trigger=el(Button,{color:'secondary',variant:'ghost',size:'sm',id:'project-navigation-project-trigger','aria-label':'选择项目','data-navigation-project':selected||'',style:{maxWidth:250}},el('span',{className:'truncate'},label),el('span',{style:{transform:'rotate(90deg)',display:'flex'}},chevron(false)));
        const shown=projects.filter(p=>p.name.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
        return el(Menu,{triggerButton:trigger,align:'end',contentWidth:'workspace',contentMaxHeight:'tall',contentClassName:'project-navigation-project-menu',contentAriaLabelledBy:'project-navigation-project-trigger',size:'select',onOpenChange:open=>{if(!open)setQuery('');}},
          el(shared.qb.SearchInput,{'aria-label':'搜索项目',placeholder:'搜索项目',value:query,onChange:e=>setQuery(e.target.value)}),
          shown.length?shown.map(p=>el(MenuItem,{key:p.id,role:'menuitemradio','aria-checked':p.id===selected,RightIcon:p.id===selected?shared.Wx:undefined,onSelect:()=>onSelect(p.id)},p.name)):el(shared.qb.Message,{compact:true},'没有匹配的项目'));
      }
      function Toolbar({onAction,canClose,disabled=false,label='更新'}){
        const glyph=d=>el('svg',{viewBox:'0 0 24 24',width:18,height:18,fill:'none',stroke:'currentColor',strokeWidth:1.5,'aria-hidden':true},el('path',{d}));
        return el('div',{className:'flex items-center gap-2'},
          el(shared.sS,{tooltipContent:'检查并更新项目记录'},el(Button,{color:'secondary',variant:'ghost',size:'sm',disabled,'data-action':'maintain',onClick:()=>onAction('maintain')},glyph('M20 7v5h-5 M4 17v-5h5 M5.5 7a7 7 0 0 1 12-2L20 8 M4 16l2.5 3a7 7 0 0 0 12-2'),label)),
          canClose?el(shared.sS,{tooltipContent:'返回对话'},el(Button,{color:'secondary',variant:'ghost',size:'sm',uniform:true,'aria-label':'返回对话',onClick:()=>onAction('close')},glyph('m12 5-7 7 7 7 M5 12h15'))):null);
      }
      function Directory({categories,category,expanded,counts,coverage,onSelect,onToggle}){
        const hasTree=categories.some(c=>c.parentId);
        const branch=(parent=null,depth=0)=>categories.filter(c=>(c.parentId||null)===parent).map(c=>{
          const nested=categories.some(n=>n.parentId===c.id),open=expanded.includes(c.id);
          const row=el('div',{'data-directory-row':c.id,style:{display:'grid',gridTemplateColumns:hasTree?'20px minmax(0,1fr)':'minmax(0,1fr)',alignItems:'center',minWidth:0,paddingInlineStart:depth*14}},
            nested?el(Button,{color:'secondary',variant:'ghost',size:'xs',uniform:true,'aria-label':(open?'收起':'展开')+c.title,'aria-expanded':open,onClick:()=>onToggle(c.id)},chevron(open)):(hasTree?el('span'):null),
            el(shared.sS,{tooltipContent:c.title},el(SidebarItem,{label:c.title,isActive:category===c.id,onClick:()=>onSelect(c.id),trailing:el('span',{'data-directory-count':c.id,className:'text-xs text-tertiary',style:{minWidth:'2ch',flexShrink:0,textAlign:'right'}},counts[c.id])})));
          return el('div',{key:c.id},row,nested?el(SidebarSection,{collapsed:!open},branch(c.id,depth+1)):null);
        });
        return el('nav',{'aria-label':'项目内容分类',style:{padding:'8px 0'}},
          el(SidebarItem,{label:'项目首页',isActive:category===null,onClick:()=>onSelect(null)}),
          el('div',{className:'text-sm text-tertiary',style:{padding:'20px 8px 8px'}},'内容目录'),branch(),
          el('p',{className:'text-xs text-tertiary',style:{padding:'24px 8px 8px'}},coverage));
      }
      function Disclosure({title,children}){
        const [open,setOpen]=React.useState(false);
        return el(SidebarSection,{collapsed:!open,title:el(Button,{color:'secondary',variant:'ghost',block:true,className:'native-disclosure-trigger','aria-expanded':open,onClick:()=>setOpen(!open),style:{justifyContent:'flex-start'}},chevron(open),title)},children);
      }
      function htmlNodes(html,handlers){
        const template=document.createElement('template');template.innerHTML=html;
        const convert=(node,index)=>{
          if(node.nodeType===3)return node.textContent;if(node.nodeType!==1)return null;
          const tag=node.tagName.toLowerCase(),attrs={key:tag+':'+(node.getAttribute('data-action')||'')+':'+(node.getAttribute('data-id')||node.getAttribute('data-content-image')||index)};
          for(const a of node.attributes){let name=a.name==='class'?'className':a.name==='for'?'htmlFor':a.name==='tabindex'?'tabIndex':a.name;if(name==='style')continue;if(!name.startsWith('data-')&&!name.startsWith('aria-'))name=name.replace(/-([a-z])/g,(_,c)=>c.toUpperCase());attrs[name]=['disabled','hidden','required','open'].includes(name)?true:a.value;}
          const children=[...node.childNodes].map(convert);
          if(tag==='details')return el(Disclosure,{key:attrs.key,title:node.querySelector('summary')?.textContent},...children.slice(1));
          if(tag==='summary')return null;
          if(tag==='label'&&node.classList.contains('content-search')){
            const input=node.querySelector('input');return el(shared.qb.SearchInput,{key:'search',id:'content-search',value:input.value,placeholder:'搜索内容','aria-label':'搜索内容',variant:'inset',onChange:handlers.onInput,style:{margin:0,width:'100%'}});
          }
          if(tag==='button'){
            const tooltip=attrs.title;delete attrs.title;
            const component=el(Button,{...attrs,color:'secondary',variant:'ghost',size:node.classList.contains('icon')?'xs':'sm',uniform:node.classList.contains('icon'),onClick:handlers.onClick},...(node.classList.contains('content-card')?[el('span',{className:'native-card-body'},...children)]:children));
            return tooltip?el(shared.sS,{key:attrs.key,tooltipContent:tooltip},component):component;
          }
          if(tag==='svg')attrs.style={width:18,height:18,fill:'none',stroke:'currentColor',strokeWidth:1.5,flexShrink:0};
          if(tag==='img')attrs.style={maxWidth:'100%',maxHeight:'65vh',objectFit:'contain'};
          if(tag==='pre')attrs.style={whiteSpace:'pre-wrap',overflowWrap:'anywhere'};
          if(tag==='input'||tag==='textarea')attrs.onChange=handlers.onInput;
          return el(tag,attrs,...(['img','input','br','hr'].includes(tag)?[]:children));
        };
        return [...template.content.childNodes].map(convert);
      }
      function Surface({html,routeKey,css,onClick,onInput,onRendered}){
        const reduced=shared.tS();
        React.useLayoutEffect(()=>{onRendered?.();},[html]);
        const handlers={onClick:event=>{event.stopPropagation();if(event.currentTarget.closest('[data-native-route]')?.dataset.nativeRoute===routeKey)onClick(event);},onInput};
        return el(React.Fragment,null,
          el('style',null,`@scope ([data-native-navigation-control="surface"]) { :scope { --fg:var(--color-token-foreground,#e6edf3);--muted:var(--color-token-text-secondary,#91989f);--line:var(--color-token-border-default,rgba(230,237,243,.084));--hover:var(--color-token-interactive-bg-secondary-hover,rgba(230,237,243,.078));font-size:var(--text-base,14px);line-height:1.6; } ${css} .content-grid > .content-card { height:auto;align-items:stretch;white-space:normal; } .content-card > span {display:block;width:100%;height:auto;flex:1 0 auto;} .native-card-body {display:flex;flex-direction:column;align-items:stretch;text-align:left;width:100%;} .content-intro,.detail-section p,.content-detail h2 {font-size:var(--text-base,14px);} .card-summary,.resource-label>span,.detail-meta {font-size:var(--text-sm,13px);} .card-title,.resource-label strong {font-size:var(--text-base,14px);} .content-card {border-radius:var(--radius-xl,12px);} .context-link {white-space:normal;height:auto;} .context-link > span {width:100%;justify-content:flex-start;align-items:flex-start;} .context-link > span > span {min-width:0;} .content-photo > button > span {display:block;width:100%;} .native-disclosure-trigger > span {width:100%;justify-content:flex-start;} }`),
          el(shared.xKt,{initial:false,mode:'wait'},el(shared.gKt.div,{key:routeKey,'data-native-route':routeKey,initial:{opacity:0},animate:{opacity:1},exit:{opacity:0},transition:reduced?{duration:0}:shared.Tx,onAnimationComplete:onRendered},...htmlNodes(html,handlers))));
      }
      function Dialog({title,html,fields,onSave,onAction,onClose,onKeyDown,open=true}){
        const [values,setValues]=React.useState(fields||{}),[busy,setBusy]=React.useState(false),[error,setError]=React.useState('');
        const submit=async event=>{event.preventDefault();setBusy(true);setError('');try{await onSave(values);onClose();}catch(e){setError(e.message);}finally{setBusy(false);}};
        return el(shared.M_,{open,onOpenChange:value=>{if(!value)onClose();},contentProps:{'aria-label':title,'aria-describedby':undefined,onKeyDown,style:{width:fields?'min(520px,90vw)':'min(960px,90vw)',maxWidth:'90vw'}},contentClassName:'project-navigation-native-dialog',contentOverflow:'auto',dialogCloseLabel:'关闭',contentPosition:'centered'},
          el('div',{style:{padding:24,maxWidth:'min(900px,90vw)',maxHeight:'85vh',overflow:'auto'}},
            el(shared.SQt,{className:'text-lg font-semibold',style:{marginBottom:20}},title),
            fields?el('form',{onSubmit:submit},...Object.entries(fields).map(([name,value])=>el('label',{key:name,className:'flex flex-col gap-2 mb-4 text-sm'},name==='title'?'名称':'这件事是做什么的？',name==='summary'?el('textarea',{className:'rounded-lg border border-default bg-transparent p-3 text-default',rows:4,value:values[name],onChange:e=>setValues({...values,[name]:e.target.value}),required:true,maxLength:500}):el(shared.Yb,{className:'rounded-lg border border-default bg-transparent',value:values[name],onChange:e=>setValues({...values,[name]:e.target.value}),required:true,maxLength:150}))),error?el('p',{role:'alert',className:'text-danger'},error):null,el('div',{className:'flex justify-end gap-2'},el(Button,{color:'secondary',variant:'ghost',onClick:onClose},'取消'),el(Button,{type:'submit',color:'primary',loading:busy},'保存'))):
            el('div',{style:{lineHeight:1.7},onClick:e=>{const b=e.target.closest('[data-action]');if(b){e.stopPropagation();onAction?.(b.dataset.action,b.dataset.id);}}},...htmlNodes(html,{onClick:e=>{e.stopPropagation();onAction?.(e.currentTarget.dataset.action,e.currentTarget.dataset.id);}}))));
      }
      const Component={project:ProjectPicker,directory:Directory,surface:Surface,dialog:Dialog,toolbar:Toolbar}[kind];
      root=ReactDOM.createRoot(container,{onUncaughtError:onError,onCaughtError:onError});
      draw=()=>{let tree=el(Component,current);for(const p of providers)tree=el(p.type,{value:p.value},tree);root.render(tree);};draw();
    })().catch(error=>{if(!disposed)onError(error);});
    return {ready,get element(){return container;},update(next){current={...current,...next};if(!disposed)draw?.();},destroy(){disposed=true;root?.unmount();container?.remove();slot?.remove();}};
  };
})();
