import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
execFileSync('/opt/homebrew/bin/python3',[path.join(root,'scripts/install-agent.py')],{stdio:'inherit'});
let connected=false;
try{connected=(await fetch('http://127.0.0.1:9333/json/list',{signal:AbortSignal.timeout(1500)})).ok;}
catch(e){if(!(e instanceof TypeError||e.name==='TimeoutError'))throw e;}
if(!connected){
  let running=false;
  try{execFileSync('/usr/bin/pgrep',['-f','^/Applications/ChatGPT.app/Contents/MacOS/ChatGPT'],{stdio:'ignore'});running=true;}catch(e){if(e.status!==1)throw e;}
  if(running)throw new Error('Codex 当前没有启用接入端口。请正常退出 Codex，再打开这个启动器；当前对话不会被强制关闭。');
  execFileSync('/usr/bin/open',['-a','/Applications/ChatGPT.app','--args','--remote-debugging-address=127.0.0.1','--remote-debugging-port=9333']);
}
console.log('Codex 启动后会自动出现资料入口。');
