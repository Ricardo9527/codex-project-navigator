import {mkdir,writeFile,readFile,readdir,rename,unlink} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

export async function requestCodexWake(root,startedAt,{timeoutMs=40000,action='wake',coldStart=false}={}){
  const directory=path.join(root,'data/icon-requests');
  await mkdir(directory,{recursive:true});
  const id=randomUUID(),request=path.join(directory,id+'.request.json'),result=path.join(directory,id+'.result.json');
  await writeFile(request+'.tmp',JSON.stringify({startedAt,action,coldStart,expiresAt:Date.now()+timeoutMs}),{mode:0o600});
  await rename(request+'.tmp',request);
  const deadline=Date.now()+timeoutMs;
  while(Date.now()<deadline){
    let content;
    try{content=await readFile(result,'utf8');}
    catch(error){if(error.code!=='ENOENT')throw error;await sleep(50);continue;}
    await unlink(result);
    const value=JSON.parse(content);
    if(value.error)throw Error(value.error);
    return value;
  }
  // The service ignores requests whose playback window has already expired.
  throw Error('后台资料库服务未在规定时间内完成图标动画。');
}

export async function consumeCodexWakeRequests(root,play,idle){
  const directory=path.join(root,'data/icon-requests');
  let files;
  try{files=await readdir(directory);}catch(error){if(error.code==='ENOENT')return;throw error;}
  for(const name of files.filter(x=>/^[0-9a-f-]+\.request\.json$/.test(x))){
    const request=path.join(directory,name),claimed=request+'.processing';
    await rename(request,claimed);
    const result=request.replace('.request.json','.result.json');
    let value;
    try{
      const {startedAt,action='wake',coldStart=false,expiresAt}=JSON.parse(await readFile(claimed,'utf8'));
      if(!Number.isFinite(startedAt)||Date.now()-startedAt>35000||(expiresAt!==undefined&&Date.now()>expiresAt))throw Error('图标播放请求已过期。');
      if(action==='idle')await idle(root);
      else if(action==='wake')await play(root,startedAt,{coldStart});
      else throw Error('未知图标请求');
      value={ok:true};
    }catch(error){value={error:error.message};}
    await writeFile(result+'.tmp',JSON.stringify(value),{mode:0o600});
    await rename(result+'.tmp',result);
    await unlink(claimed);
  }
}
