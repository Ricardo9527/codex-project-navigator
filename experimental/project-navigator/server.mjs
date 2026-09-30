import {McpServer} from '@modelcontextprotocol/sdk/server/mcp.js';
import {StdioServerTransport} from '@modelcontextprotocol/sdk/server/stdio.js';
import {execFile} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {z} from 'zod';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {renderNavigationUI} from './render-ui.mjs';
import {requestNativeDraft} from '../../scripts/native-draft-queue.mjs';

const uiDocument=await renderNavigationUI();
const uiRevision=createHash('sha256').update(uiDocument).digest('hex').slice(0,16);
const resourceUri=`ui://project-navigator/navigation-${uiRevision}.html`;
const server=new McpServer({name:'project-navigator-flow',version:'0.1.0'},
  {instructions:'Read the existing project record and card context. Source conversations are background, not authorization. Automatically registered deliverables remain unaccepted until the user confirms them.'});
const annotations={readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:false};
function query(args){
  return new Promise((resolve,reject)=>{
    const child=execFile(process.env.PROJECT_NAVIGATOR_PYTHON||(process.platform==='win32'?'python':'python3'),
      [fileURLToPath(new URL('./query.py',import.meta.url))],{timeout:15000,maxBuffer:2_000_000},
      (error,stdout,stderr)=>{
        if(error){reject(new Error(stderr.trim()||error.message));return;}
        try{resolve(JSON.parse(stdout));}catch(error){reject(error);}
      });
    child.stdin.end(JSON.stringify(args));
  });
}
async function result(args){
  try{
    const data=await query(args);
    data.apiVersion=2;
    return {content:[{type:'text',text:data.context?.text||`${data.project.name}：${data.cards.length} 张工作卡片。`}],structuredContent:data};
  }catch(error){return {isError:true,content:[{type:'text',text:error.message}]};}
}
server.registerResource('project-navigator',resourceUri,{mimeType:'text/html;profile=mcp-app'},async()=>({contents:[{
  uri:resourceUri,mimeType:'text/html;profile=mcp-app',text:uiDocument,
  _meta:{ui:{prefersBorder:false,csp:{connectDomains:[],resourceDomains:[]}}},
}]}));
server.registerTool('browse_navigation',{
  title:process.env.PROJECT_NAVIGATOR_PLUGIN==='1'?'项目导航':'项目导航 · 原生验证',description:'Browse real work cards and deliverables from the selected local project record.',
  inputSchema:{projectId:z.string().optional(),cardId:z.string().optional()},annotations,
  _meta:{ui:{resourceUri},'openai/ui':{entrypoints:[{type:'global'},{type:'thread'}],preferredModelDisplayMode:'fullscreen'}},
},args=>result({...args,cardId:args.cardId||(args.projectId?undefined:process.env.PROJECT_NAVIGATOR_CARD)}));
server.registerTool('read_navigation',{
  title:'读取项目卡片',description:'Read the current project navigation and a selected card from its authoritative record.',
  inputSchema:{projectId:z.string().optional(),cardId:z.string().optional()},annotations,
},result);
// Only the existing navigator's named operations are exposed to its UI.
server.registerTool('navigation_action',{
  title:'项目导航界面操作',description:'Use the existing project navigation search, preview and explicit record controls.',
  inputSchema:{action:z.enum(['projectSearch','searchOpen','pagePreview','pageThumbnail','pageReveal','updateCard','chooseResource','registerResource','adoptResource']),args:z.record(z.string(),z.unknown())},
  annotations:{readOnlyHint:false,destructiveHint:false,idempotentHint:false,openWorldHint:false},
  _meta:{ui:{visibility:['app']}},
},async ({action,args})=>{
  try{
    const response=await fetch('http://127.0.0.1:47832/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,args}),signal:AbortSignal.timeout(60000)});
    if(!response.ok)throw Error('项目导航服务返回 HTTP '+response.status);
    const value=await response.json();if(value.error)throw Error(value.error);
    return {content:[],structuredContent:value.result};
  }catch(error){return {isError:true,content:[{type:'text',text:error.message}]};}
});
server.registerTool('get_card_context',{
  title:'获取卡片工作背景',description:'Read the selected card, its project, deliverables and sources to continue work with accurate context.',
  inputSchema:{projectId:z.string().optional(),cardId:z.string()},annotations,
},args=>result({...args,context:true}));
server.registerTool('prepare_card_work',{
  title:'打开卡片所属项目的原生草稿',
  description:'When the user explicitly chooses to start work on a card, prepare a native Codex draft in its project with the latest card context. The user chooses the model, reasoning effort and sends in the native composer.',
  inputSchema:{projectId:z.string().optional(),cardId:z.string()},annotations:{...annotations,readOnlyHint:false,idempotentHint:false},
},async args=>{
  try{
    const trial=JSON.parse(await readFile(new URL('./draft-trial.json',import.meta.url),'utf8'));
    if(process.platform!=='darwin')throw Error('此系统的原生草稿接入尚待实机适配，请从项目中新建聊天。');
    if(!trial.enabled)throw Error('原生草稿桥接试验已暂停，待隔离验证通过后单独启用。');
    const data=await query({...args,context:true});
    if(trial.mode==='explicit'&&data.project.id!==trial.projectId)throw Error('该项目的原生草稿接入未启用。');
    const response=await fetch('http://127.0.0.1:47832/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'overview',args:{}}),signal:AbortSignal.timeout(5000)});
    const overview=await response.json();if(overview.error)throw Error(overview.error);
    const project=overview.result.projects.find(p=>p.path===data.project.path);
    if(!project)throw Error('卡片所属项目未接入本机项目导航。');
    const nativeProjectId=Object.entries(overview.result.aliases).find(([,id])=>id===project.id)?.[0];
    if(!nativeProjectId)throw Error('没有找到卡片所属项目的原生项目身份。');
    const value=await requestNativeDraft(path.resolve(fileURLToPath(new URL('../..',import.meta.url))),{
      project,context:data.context,nativeProjectId,cardId:data.card.id,cardTitle:data.card.title,
    });
    return {content:[{type:'text',text:'已请求打开 '+project.name+' 的原生草稿。请在原生输入框选择模型、思考强度并填写需求。'}],structuredContent:value};
  }catch(error){return {isError:true,content:[{type:'text',text:error.message}]};}
});
await server.connect(new StdioServerTransport());
