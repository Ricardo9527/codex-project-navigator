import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {playRuntimeIconFrames} from '../scripts/codex-runtime-icon.mjs';
const names=['icon-codex-dark-color.png','icon-codex-light.png','icon-space-dark.png','icon-space-light.png'];
async function fixture(){
 const root=await mkdtemp(path.join(os.tmpdir(),'codex-icon-resources-')),appPath=path.join(root,'App.app'),resources=path.join(appPath,'Contents/Resources');
 await mkdir(resources,{recursive:true});await writeFile(path.join(appPath,'Contents/Info.plist'),'build-one');
 for(const name of names)await writeFile(path.join(resources,name),'original:'+name);
 return {root,appPath,resources};
}
async function restored(f){for(const name of names)assert.equal(await readFile(path.join(f.resources,name),'utf8'),'original:'+name);await assert.rejects(readFile(path.join(f.root,'data/codex-icon-resource-backup.json')),{code:'ENOENT'});}
test('custom frames use alternating runtime slots and restore original resources without alternate-logo flash',async()=>{
 const f=await fixture();let clock=0;const calls=[];
 try{
  await playRuntimeIconFrames({...f,frames:[Buffer.from('A'),Buffer.from('B')],fps:24,now:()=>clock,pause:async ms=>{clock+=ms},setPreference:async slot=>{
   const name=slot==='space-system'?'icon-space-dark.png':'icon-codex-dark-color.png';calls.push([slot,await readFile(path.join(f.resources,name),'utf8')]);
  }});
  assert.deepEqual(calls,[['space-system','A'],['codex-system','B'],['space-system','original:icon-codex-dark-color.png'],['codex-system','original:icon-codex-dark-color.png']]);
  await restored(f);
 }finally{await rm(f.root,{recursive:true,force:true});}
});
test('a playback failure restores all original images and preserves the failure',async()=>{
 const f=await fixture();let count=0;
 try{
  await assert.rejects(playRuntimeIconFrames({...f,frames:[Buffer.from('A')],fps:24,setPreference:async()=>{if(++count===1)throw Error('renderer replaced');}}),/renderer replaced/);
  await restored(f);
 }finally{await rm(f.root,{recursive:true,force:true});}
});
