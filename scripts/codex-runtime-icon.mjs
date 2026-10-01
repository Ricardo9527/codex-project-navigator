import {readFile,writeFile,mkdir,unlink} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
const slots={
 'codex-system':['icon-codex-dark-color.png','icon-codex-light.png'],
 'space-system':['icon-space-dark.png','icon-space-light.png'],
};
const names=Object.values(slots).flat();
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const fingerprint=buffer=>createHash('sha256').update(buffer).digest('hex');

export async function playRuntimeIconFrames({root,appPath,frames,fps,setPreference,now=()=>performance.now(),pause=sleep}){
 const resources=path.join(appPath,'Contents/Resources');
 const journal=path.join(root,'data/codex-icon-resource-backup.json');
 const build=fingerprint(await readFile(path.join(appPath,'Contents/Info.plist')));
 let previous;
 try{previous=JSON.parse(await readFile(journal,'utf8'));}catch(error){if(error.code!=='ENOENT')throw error;}
 if(previous){
  if(previous.build===build)for(const name of names)await writeFile(path.join(resources,name),Buffer.from(previous.images[name],'base64'));
  await unlink(journal);
 }
 const originals=Object.fromEntries(await Promise.all(names.map(async name=>[name,await readFile(path.join(resources,name))])));
 await mkdir(path.dirname(journal),{recursive:true});
 await writeFile(journal,JSON.stringify({build,images:Object.fromEntries(names.map(name=>[name,originals[name].toString('base64')]))}),{mode:0o600});
 let active='codex-system',updates=0,operationError,restoreError;
 const start=now();
 try{
  for(let index=0;index<frames.length;){
   const next=active==='codex-system'?'space-system':'codex-system';
   for(const name of slots[next])await writeFile(path.join(resources,name),frames[index]);
   await setPreference(next);active=next;updates++;
   const elapsed=now()-start;
   index=Math.max(index+1,Math.floor(elapsed*fps/1000));
   const delay=index*1000/fps-elapsed;if(delay>0)await pause(delay);
  }
 }catch(error){operationError=error;}
 // Restore every resource even if a preceding restore fails. Keep the journal
 // until all original bytes are back; the next run can recover interrupted work.
 for(const name of names){try{await writeFile(path.join(resources,name),originals[name]);}catch(error){restoreError??=error;}}
 try{
  // The last frame may already use codex-system; force a refresh using a
  // temporary official-image space slot so there is no alternate-logo flash.
  if(active==='codex-system'){
   for(let i=0;i<2;i++)await writeFile(path.join(resources,slots['space-system'][i]),originals[slots['codex-system'][i]]);
   try{await setPreference('space-system');}finally{for(const name of slots['space-system'])await writeFile(path.join(resources,name),originals[name]);}
  }
  await setPreference('codex-system');
 }catch(error){restoreError??=error;}
 if(!restoreError)await unlink(journal);
 if(operationError&&restoreError)throw new AggregateError([operationError,restoreError],'图标播放与恢复均失败');
 if(restoreError)throw restoreError;
 if(operationError)throw operationError;
 return {updates,frameCount:frames.length,durationMs:now()-start};
}
