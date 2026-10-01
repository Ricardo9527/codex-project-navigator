import {readFile,writeFile,mkdir,rename} from 'node:fs/promises';
import path from 'node:path';
const file=root=>path.join(root,'data/codex-icon-active-session.json');
export async function isLibraryIconSession(root,browserId){
 let state;
 try{state=JSON.parse(await readFile(file(root),'utf8'));}catch(error){if(error.code==='ENOENT')return false;throw error;}
 return state.browserId===browserId;
}
export async function markLibraryIconSession(root,browserId){
 const destination=file(root);await mkdir(path.dirname(destination),{recursive:true});
 await writeFile(destination+'.tmp',JSON.stringify({browserId}),{mode:0o600});
 await rename(destination+'.tmp',destination);
}
