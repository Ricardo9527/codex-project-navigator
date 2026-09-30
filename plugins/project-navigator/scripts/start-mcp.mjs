import {readFile} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

let root=process.env.PROJECT_NAVIGATOR_SERVICE_ROOT;
if(!root){
 const state=JSON.parse(await readFile(path.join(os.homedir(),'.codex/.codex-global-state.json'),'utf8'));
 const roots=new Set([...Object.values(state['local-projects']||{}).flatMap(p=>p.rootPaths),...state['electron-saved-workspace-roots']||[]]);
 const matches=[];
 for(const candidate of roots){
  let manifest;
  try{manifest=JSON.parse(await readFile(path.join(candidate,'package.json'),'utf8'));}
  catch(e){if(e.code==='ENOENT')continue;throw e;}
  if(['codex-project-library','codex-project-navigator'].includes(manifest.name))matches.push(candidate);
 }
 if(matches.length!==1)throw Error('请通过 PROJECT_NAVIGATOR_SERVICE_ROOT 指定唯一的 Codex 资料库源码目录。');
 root=matches[0];
}
process.env.PROJECT_NAVIGATOR_PLUGIN='1';
delete process.env.PROJECT_NAVIGATOR_CARD;
await import(pathToFileURL(path.join(root,'experimental/project-navigator/server.mjs')).href);
