import {z} from 'zod';
import {callLibrary} from './api-client.mjs';

export function registerDailyTools(server, api=callLibrary){
 const invoke=action=>async args=>{
  try{const result=await api(action,args);return {content:[{type:'text',text:JSON.stringify(result)}],structuredContent:result};}
  catch(error){return {isError:true,content:[{type:'text',text:error.message}]};}
 };
 server.registerTool('prepare_daily_record',{
  title:'准备日常维护表单',
  description:'Read only a category/card index, a selected card and this chat’s incremental deliveries. Reuse scopeId and nextOffset to page assets without rereading the chat. Does not mark the chat covered or perform a project audit.',
  inputSchema:{projectId:z.string(),threadId:z.string().optional(),cardId:z.string().optional(),cardIds:z.array(z.string()).optional(),scopeId:z.string().uuid().optional(),offset:z.number().int().nonnegative().optional()},
  annotations:{readOnlyHint:false,destructiveHint:false,idempotentHint:false,openWorldHint:false},
 },invoke('prepareDailyRecord'));
 server.registerTool('save_daily_record',{
  title:'一次保存日常维护',
  description:'Submit a small delta once: card changes, selected deliveries/imports and explicitly confirmed chat coverage. scopeId fixes the chat boundary; complete means ALL meaningful content in that range was handled, unchanged saves work without advancing chat coverage. Files, source messages and delivery times are filled by the program. Same payload retries safely; unrelated old gaps do not block this update.',
  inputSchema:{projectId:z.string(),scopeId:z.string().uuid(),threadCoverage:z.enum(['complete','unchanged']),
   updates:z.array(z.object({cardId:z.string().optional(),changes:z.object({title:z.string().min(1).optional(),summary:z.string().min(1).optional(),categoryId:z.string().min(1).optional(),notes:z.array(z.string()).optional()}).strict().optional(),
    deliveries:z.array(z.object({assetId:z.string(),label:z.string().optional()}).strict()).optional(),
    files:z.array(z.object({path:z.string(),sourceReason:z.string().min(1),external:z.boolean().optional(),label:z.string().optional()}).strict()).optional()}).strict()),
   categories:z.array(z.object({id:z.string(),title:z.string(),parentId:z.string().optional()}).strict()).optional(),commits:z.array(z.string().regex(/^[0-9a-f]{40}$/)).optional()},
  annotations:{readOnlyHint:false,destructiveHint:false,idempotentHint:true,openWorldHint:false},
 },invoke('saveDailyRecord'));
}
