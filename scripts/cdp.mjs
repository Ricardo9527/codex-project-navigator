export class CDP {
  constructor(url) {
    this.socket = new WebSocket(url); this.seq = 0; this.pending = new Map(); this.handlers = new Set();
    this.ready = new Promise((resolve,reject)=>{this.socket.onopen=resolve;this.socket.onerror=()=>reject(new Error('无法连接 Codex 主窗口'));});
    this.socket.onmessage=event=>{
      const message=JSON.parse(event.data);
      if(message.id){const p=this.pending.get(message.id);if(!p)return;clearTimeout(p.timer);this.pending.delete(message.id);message.error?p.reject(new Error(message.error.message)):p.resolve(message.result);}
      else for(const handler of this.handlers) handler(message);
    };
    this.socket.onclose=()=>{for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(new Error('Codex 连接已断开'));}this.pending.clear();};
  }
  async send(method,params={}) {
    await this.ready;
    if(this.socket.readyState!==WebSocket.OPEN)throw new Error('Codex 连接已断开');
    const id=++this.seq;
    return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error(method+' 超时'));},15000);this.pending.set(id,{resolve,reject,timer});this.socket.send(JSON.stringify({id,method,params}));});
  }
  async evaluate(expression) {
    const result=await this.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
    if(result.exceptionDetails)throw new Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);
    return result.result.value;
  }
  close(){this.socket.close();}
}
