import {spawnSync,execFileSync} from 'node:child_process';
import {mkdir,readFile,writeFile,copyFile,cp} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import os from 'node:os';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const dryRun=process.argv.includes('--dry-run'),configureOnly=process.argv.includes('--configure-only');
function command(candidates,args){for(const candidate of candidates.filter(Boolean)){const r=spawnSync(candidate,args,{encoding:'utf8'});if(r.status===0)return {command:candidate,output:r.stdout.trim()};}throw Error('找不到可运行的 '+candidates.filter(Boolean).join(' / '));}
const python=command([process.env.PROJECT_NAVIGATOR_PYTHON,process.platform==='win32'?'python':'python3'],['-c','import sys; assert sys.version_info >= (3,10), "需要 Python 3.10+"; print(sys.executable)']).output;
if(Number(process.versions.node.split('.')[0])<22)throw Error('需要 Node.js 22 或更新版本。');
const app=process.platform==='darwin'?[process.env.CODEX_APP,'/Applications/ChatGPT.app','/Applications/Codex.app',path.join(os.homedir(),'Applications/ChatGPT.app')].filter(Boolean).find(existsSync):null;
if(process.platform==='darwin'&&!app)throw Error('未找到 Codex 桌面应用；请用 CODEX_APP 指定 .app 路径。');
const bundled=app&&path.join(app,'Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex');
const cli=command([process.env.CODEX_CLI,bundled,'codex'],['--version']).command;
const marketplace=path.join(root,'data/install-marketplace');
const runtime={root,node:process.execPath,python,cli,app,platform:process.platform};
if(dryRun){console.log(JSON.stringify({...runtime,marketplace,actions:['generate-local-marketplace','register-plugin',...(app?['build-launcher','install-launch-agent']:[])]},null,2));process.exit(0);}
await mkdir(path.join(marketplace,'.agents/plugins'),{recursive:true});
const plugin=path.join(marketplace,'plugins/project-navigator');await mkdir(path.join(plugin,'.codex-plugin'),{recursive:true});await mkdir(path.join(plugin,'scripts'),{recursive:true});
await copyFile(path.join(root,'.agents/plugins/marketplace.json'),path.join(marketplace,'.agents/plugins/marketplace.json'));
const manifest=JSON.parse(await readFile(path.join(root,'plugins/project-navigator/.codex-plugin/plugin.json'),'utf8'));
manifest.skills='./skills';
await writeFile(path.join(plugin,'.codex-plugin/plugin.json'),JSON.stringify(manifest,null,2)+'\n');
await copyFile(path.join(root,'plugins/project-navigator/scripts/start-mcp.mjs'),path.join(plugin,'scripts/start-mcp.mjs'));
await cp(path.join(root,'skills/project-records'),path.join(plugin,'skills/project-records'),{recursive:true});
await writeFile(path.join(plugin,'scripts/libraryctl.py'), 'import runpy\nrunpy.run_path('+JSON.stringify(path.join(root,'scripts/libraryctl.py'))+', run_name="__main__")\n');
await writeFile(path.join(plugin,'.mcp.json'),JSON.stringify({mcpServers:{'project-navigator-local':{command:process.execPath,args:[path.join(plugin,'scripts/start-mcp.mjs')],env:{PROJECT_NAVIGATOR_SERVICE_ROOT:root,PROJECT_NAVIGATOR_ROOT:root,PROJECT_NAVIGATOR_PYTHON:python}}}},null,2)+'\n');
await writeFile(path.join(root,'data/install.json'),JSON.stringify(runtime,null,2)+'\n');
if(configureOnly){console.log('本机配置已生成：'+marketplace);process.exit(0);}
execFileSync(cli,['plugin','marketplace','add',marketplace,'--json'],{stdio:'inherit'});
execFileSync(cli,['plugin','add','project-navigator@project-navigation-local','--json'],{stdio:'inherit'});
if(app){
 execFileSync(python,[path.join(root,'scripts/build-launcher.py')],{stdio:'inherit'});
 execFileSync(python,[path.join(root,'scripts/install-agent.py')],{stdio:'inherit'});
 console.log('安装完成。正常退出 Codex 后，打开仓库中的“Codex 资料库.app”。');
}else console.log('插件已注册。运行 npm start 启动本地服务；桌面接入按 docs/cross-platform.md 验证。');
