import {mkdir,writeFile,readFile,readdir,rename,rm,stat} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import path from 'node:path';

const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function requestNativeDraft(root,payload,{timeoutMs=20000}={}){
 const folder=path.join(root,'data/native-drafts');await mkdir(folder,{recursive:true,mode:0o700});
 const id=randomUUID(),pending=path.join(folder,id+'.pending.json'),result=path.join(folder,id+'.result.json');
 const temporary=path.join(folder,id+'.tmp'),expiresAt=Date.now()+timeoutMs;
 await writeFile(temporary,JSON.stringify({expiresAt,payload}),{mode:0o600});await rename(temporary,pending);
 try{
  while(Date.now()<expiresAt){
   let value;try{value=JSON.parse(await readFile(result,'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
   if(value){if(value.error)throw Error(value.error);return value.result;}
   await sleep(100);
  }
  throw Error('原生草稿接入未响应，请确认项目导航监管服务已加载新桥接。');
 }finally{await rm(pending,{force:true});await rm(result,{force:true});}
}

export async function consumeNativeDrafts(root,prepare){
 const folder=path.join(root,'data/native-drafts');let names;
 try{names=await readdir(folder);}catch(e){if(e.code==='ENOENT')return;throw e;}
 for(const name of names.filter(n=>n.endsWith('.pending.json'))){
  const pending=path.join(folder,name),processing=pending.replace('.pending.json','.processing.json');
  try{await rename(pending,processing);}catch(e){if(e.code==='ENOENT')continue;throw e;}
  let response;
  try{
   const request=JSON.parse(await readFile(processing,'utf8'));
   if(request.expiresAt<=Date.now())throw Error('草稿请求已过期，请重新点击卡片。');
   response={result:await prepare(request.payload,{createdAt:(await stat(processing)).mtimeMs})};
  }catch(e){response={error:e.message};}
  const result=processing.replace('.processing.json','.result.json'),temporary=result+'.tmp';
  await writeFile(temporary,JSON.stringify(response),{mode:0o600});await rename(temporary,result);await rm(processing);
 }
}
