import {execFileSync,spawn} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const runtime=JSON.parse(await readFile(path.join(root,'data/install.json'),'utf8'));
if(process.platform!=='darwin'){
 const script=process.argv.includes('--desktop')?'scripts/manager.mjs':'server.py';
 const command=script.endsWith('.mjs')?process.execPath:runtime.python;
 const child=spawn(command,[path.join(root,script)],{stdio:'inherit',env:{...process.env,PROJECT_HUB_PYTHON:runtime.python}});
 child.on('error',e=>{console.error(e.message);process.exitCode=1;});child.on('exit',code=>{process.exitCode=code??1;});
}else{
 execFileSync(runtime.python,[path.join(root,'scripts/install-agent.py')],{stdio:'inherit'});
 let connected=false;
 try{connected=(await fetch('http://127.0.0.1:9333/json/list',{signal:AbortSignal.timeout(1500)})).ok;}catch(e){if(!(e instanceof TypeError||e.name==='TimeoutError'))throw e;}
 if(!connected){
  const name=path.basename(runtime.app,'.app'),executable=path.join(runtime.app,'Contents/MacOS',name);
  let running=false;try{execFileSync('/usr/bin/pgrep',['-f','^'+executable.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')],{stdio:'ignore'});running=true;}catch(e){if(e.status!==1)throw e;}
  if(running)throw Error('请先正常退出 Codex，再打开资料库启动器以启用接入端口。');
  execFileSync('/usr/bin/open',['-a',runtime.app,'--args','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9333']);
 }
 console.log('Codex 启动后会自动接入项目导航。');
}
