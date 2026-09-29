window.mountLibrary(document.querySelector('#app'), {request: async(action,args={})=>{
  const response=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,args})});
  const data=await response.json();if(data.error)throw new Error(data.error);return data.result;
}});
