import React, {useLayoutEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {flushSync} from 'react-dom';
import {Button} from '@openai/apps-sdk-ui/components/Button';
import {Input} from '@openai/apps-sdk-ui/components/Input';
import {Tooltip} from '@openai/apps-sdk-ui/components/Tooltip';
import {Animate, AnimateLayout} from '@openai/apps-sdk-ui/components/Transition';

const el=React.createElement;
const actionButton=(props,children)=>el(Button,{color:'secondary',variant:'ghost',pill:false,size:'md',...props},children);
function Disclosure({title,children}){
 const [open,setOpen]=useState(false);
 return <div className="content-disclosure">
  <Button color="secondary" variant="ghost" pill={false} block className="sdk-disclosure-trigger" aria-expanded={open} onClick={()=>setOpen(!open)}><span aria-hidden="true">{open?'⌄':'›'}</span>{title}</Button>
  <AnimateLayout as="div" hideOverflow preventInitialTransition>{open?<div key="body">{children}</div>:null}</AnimateLayout>
 </div>;
}
function htmlNodes(html,handlers){
 const template=document.createElement('template');template.innerHTML=html;
 function convert(node,index){
  if(node.nodeType===3)return node.textContent;if(node.nodeType!==1)return null;
  const tag=node.tagName.toLowerCase(),attrs={key:tag+':'+(node.getAttribute('data-action')||'')+':'+(node.getAttribute('data-id')||node.getAttribute('data-content-image')||index)};
  for(const a of node.attributes){
   let name=a.name==='class'?'className':a.name==='for'?'htmlFor':a.name==='tabindex'?'tabIndex':a.name;
   if(name==='style'){attrs.style=Object.fromEntries([...node.style].map(k=>[k.startsWith('--')?k:k.replace(/-([a-z])/g,(_,c)=>c.toUpperCase()),node.style.getPropertyValue(k)]));continue;}
   if(!name.startsWith('data-')&&!name.startsWith('aria-'))name=name.replace(/-([a-z])/g,(_,c)=>c.toUpperCase());
   attrs[name]=['disabled','hidden','required','open'].includes(name)?true:a.value;
  }
  if(tag==='details')return <Disclosure key={attrs.key} title={node.querySelector('summary')?.textContent}>{[...node.children].filter(n=>n.tagName!=='SUMMARY').map(convert)}</Disclosure>;
  if(tag==='label'&&node.classList.contains('content-search')){
   const input=node.querySelector('input');return <Input key="search" id="content-search" type="search" value={input.value} placeholder="搜索内容" aria-label="搜索内容" onChange={handlers.onInput} className="sdk-search"/>;
  }
  const children=[...node.childNodes].map(convert);
  if(tag==='button'){
   const tooltip=attrs.title;delete attrs.title;
   const component=actionButton({...attrs,onClick:handlers.onClick},node.classList.contains('content-card')?<span className="sdk-card-body">{children}</span>:children);
   return tooltip?<Tooltip key={attrs.key} content={tooltip}>{component}</Tooltip>:component;
  }
  if(tag==='input'||tag==='textarea')attrs.onChange=handlers.onInput;
  return el(tag,attrs,...(['img','input','br','hr'].includes(tag)?[]:children));
 }
 return [...template.content.childNodes].map(convert);
}
function Directory({categories,category,expanded,counts,coverage,onSelect,onToggle}){
 const hasTree=categories.some(c=>c.parentId);
 const branch=(parent=null,depth=0)=>categories.filter(c=>(c.parentId||null)===parent).map(c=>{
  const nested=categories.some(n=>n.parentId===c.id),open=expanded.includes(c.id);
  return <div key={c.id}><div className="sdk-directory-row" style={{paddingInlineStart:depth*14}}>
   {nested?<Button color="secondary" variant="ghost" pill={false} size="xs" uniform aria-label={(open?'收起':'展开')+c.title} aria-expanded={open} onClick={()=>onToggle(c.id)}>{open?'⌄':'›'}</Button>:hasTree?<span className="sdk-directory-spacer"/>:null}
   <Button color="secondary" variant="ghost" pill={false} selected={category===c.id} className="sdk-directory-label" aria-current={category===c.id?'page':undefined} onClick={()=>onSelect(c.id)}><span>{c.title}</span><span className="nav-count">{counts[c.id]}</span></Button>
  </div>{nested?<AnimateLayout as="div" hideOverflow preventInitialTransition>{open?<div key={c.id+'-children'}>{branch(c.id,depth+1)}</div>:null}</AnimateLayout>:null}</div>;
 });
 return <nav className="content-nav sdk-directory" aria-label="项目内容分类"><Button color="secondary" variant="ghost" pill={false} selected={category===null} aria-current={category===null?'page':undefined} onClick={()=>onSelect(null)}>项目首页</Button><div className="section-label">内容目录</div><div>{branch()}</div><div className="content-nav-bottom"><p>{coverage}</p></div></nav>;
}
function Surface({html,routeKey,onClick,onInput,onRendered}){
 const activeRoute=useRef(routeKey);activeRoute.current=routeKey;
 useLayoutEffect(()=>{onRendered?.();},[html,routeKey]);
 const click=e=>{e.stopPropagation();if(e.currentTarget.closest('[data-sdk-route]')?.dataset.sdkRoute===activeRoute.current)onClick(e);};
 return <Animate as="div" className="sdk-surface" preventInitialTransition initial={{opacity:0}} enter={{opacity:1,duration:160}} exit={{opacity:0,duration:100}}><div key={routeKey} data-sdk-route={routeKey}>{htmlNodes(html,{onClick:click,onInput})}</div></Animate>;
}
function Dialog({title,html,fields,onSave,onAction,onClose,onKeyDown,open=true}){
 const ref=useRef(),[values,setValues]=useState(fields||{}),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useLayoutEffect(()=>{if(open&&!ref.current.open)ref.current.showModal();else if(!open&&ref.current.open)ref.current.close();},[open]);
 const submit=async e=>{e.preventDefault();setBusy(true);try{await onSave(values);onClose();}catch(e){setError(e.message);}finally{setBusy(false);}};
 return <dialog ref={ref} className="record-edit sdk-dialog" aria-label={title} onCancel={e=>{e.preventDefault();onClose();}} onKeyDown={onKeyDown}>
  <header><h2>{title}</h2><Button color="secondary" variant="ghost" pill={false} aria-label="关闭" onClick={onClose}>×</Button></header>
  {fields?<form onSubmit={submit}>{Object.entries(values).map(([name,value])=><label key={name}>{name==='title'?'名称':'这件事是做什么的？'}{name==='summary'?<textarea required maxLength={500} value={value} onChange={e=>setValues({...values,[name]:e.target.value})}/>:<Input required maxLength={150} value={value} onChange={e=>setValues({...values,[name]:e.target.value})}/>}</label>)}<p role="alert">{error}</p><footer><Button color="secondary" variant="ghost" onClick={onClose}>取消</Button><Button type="submit" color="primary" loading={busy}>保存</Button></footer></form>:<div>{htmlNodes(html,{onClick:e=>{e.stopPropagation();onAction?.(e.currentTarget.dataset.action,e.currentTarget.dataset.id);}})}</div>}
 </dialog>;
}
function Work({enabled,note,onStart}){
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(note);
 return <><Button color="primary" variant="solid" pill={false} disabled={!enabled} loading={busy} onClick={async()=>{setBusy(true);try{await onStart();setMessage('已请求打开项目原生草稿，请填写需求后发送。');}catch(e){setMessage(e.message);}finally{setBusy(false);}}}>在此项目开始工作</Button><p className="composer-feedback" role="status">{message}</p></>;
}
function Maintain({onClick,disabled,label='更新'}){
 const [busy,setBusy]=useState(false);
 return <Tooltip content="检查并更新项目记录"><Button id="maintain" color="secondary" variant="ghost" pill={false} disabled={disabled} loading={busy} onClick={async()=>{setBusy(true);try{await onClick();}finally{setBusy(false);}}}>{label}</Button></Tooltip>;
}
function Refresh({onClick}){return <Button id="refresh" color="secondary" variant="ghost" pill={false} onClick={onClick}>刷新记录</Button>;}
window.mountNavigationSDKControl=({dock,kind,props,onError})=>{
 dock.classList.add('sdk-control-'+kind);
 const root=createRoot(dock,{onUncaughtError:onError,onCaughtError:onError});let current=props;
 const Component={directory:Directory,surface:Surface,dialog:Dialog,work:Work,refresh:Refresh,maintain:Maintain}[kind];
 const draw=()=>root.render(el(Component,current));flushSync(draw);
 return {element:dock,update(next){current={...current,...next};draw();},destroy(){root.unmount();}};
};
