export function operationTimeout(action){return action==='chooseResource'?300000:60000;}
export async function callLibrary(action,args,fetcher=fetch){
 const response=await fetcher('http://127.0.0.1:47832/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,args}),signal:AbortSignal.timeout(operationTimeout(action))});
 const value=await response.json();
 if(value.error)throw Error(value.error);
 if(!response.ok)throw Error('项目导航服务返回 HTTP '+response.status);
 return value.result;
}
