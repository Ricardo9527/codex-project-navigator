import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {open} from 'node:fs/promises';
import vm from 'node:vm';
import {dockPreferenceExpression} from '../scripts/codex-icon-page.mjs';

const builds=[
 ['26.1103.41825','348410.46c6a64506.js','182735.d1916dd704.js'],
 ['26.1103.60933','348410.fcfef000d0.js','182735.7f13786b92.js'],
 ['26.1106.51428','348410.1a97dde15f.js','739301.37a39f26d6.js'],
];

test('Supported Rspack package exposes the native draft, maintenance, transcript and Dock contracts',async t=>{
 const archive=await open(process.env.CODEX_DESKTOP_ASAR||'/Applications/ChatGPT.app/Contents/Resources/app.asar').catch(error=>{
  if(error.code!=='ENOENT')throw error;
 });
 if(!archive)return t.skip('desktop package unavailable');
 try{
  const header=Buffer.alloc(16);
  await archive.read(header,0,16,0);
  const base=8+header.readUInt32LE(4);
  const json=Buffer.alloc(header.readUInt32LE(12));
  await archive.read(json,0,json.length,16);
  const webview=JSON.parse(json).files.webview.files,assets=webview.assets.files;
  const build=builds.find(([,runtime])=>assets[runtime]);
  if(!build)return t.skip('package is not a supported Rspack build');
  const [version,runtime,coreChunk]=build;
  const latest=version==='26.1106.51428';
  async function read(entry){
   const buffer=Buffer.alloc(entry.size);
   await archive.read(buffer,0,buffer.length,base+Number(entry.offset));
   assert.equal(createHash('sha256').update(buffer).digest('hex'),entry.integrity.hash);
   return buffer.toString();
  }
  async function factories(name){
   const source=await read(assets.async.files[name]);
   return vm.runInNewContext(source.replaceAll('export const ','const ')+'\n;__webpack_modules__');
  }
  assert.ok((await read(webview['index.html'])).includes(`src="/assets/${runtime}"`));
  const loader=await read(assets[runtime]);
  assert.match(loader,/var v=p;[\s\S]*export\{v as __webpack_require__\}/);
  assert.match(loader,/p\.m=u/);
  assert.match(loader,latest?/783456:"56be3fdcab"/:/783456:"a3b05bbbc0"/);
  assert.match(loader,latest?/475196:"19cfbf2397"/:/497066:"82fad48b12"/);
  const core=await factories(coreChunk);
  const shared=await factories(latest?'514766.2d2f1ddc86.js':'189497.7105543924.js');
  const host=await factories(latest?'394447.49fa964b1a.js':'906498.9a5baab08f.js');
  const maintenance=await factories(latest?'475196.19cfbf2397.js':'497066.82fad48b12.js');
  const transcript=await factories(latest?'129203.347da7d178.js':'870386.51be716d6d.js');
  assert.match(String(core.Q8aV),/activeProject:[\s\S]*freshDraft:[\s\S]*startNewConversation:[\w$]+/);
  assert.match(String(shared.OWtl),/"AppScope"/);
  assert.match(String(shared.Nmf8),/resolve:[\s\S]*familyBindings\.get/);
  assert.match(String(core.Dgwo),/V:function[\s\S]*\.forHost\(/);
  assert.match(String(core.Oj9r),/GD:\(\)=>y[\s\S]*"RouteScope"/);
  assert.match(String(core.tl5a),/qX:\(\)=>\w+\.qX/);
  assert.match(String(shared.nlNF),/backKey:\w+\.pathname[\s\S]*x2:E/);
  assert.match(String(maintenance.eYlV),/kind:"creation"[\s\S]*Nw:async function[\s\S]*Unknown local project/);
  assert.match(String(maintenance.f4th),/\.Ts\)\(\w+\.Q2Y\.LOCAL_PROJECTS\)[\s\S]*\.b9\)\(\w+\)/);
  assert.match(String(host.GaA7),/appServices:/);
  assert.match(String(shared.RxZZ),/LA:\(\)=>b[\s\S]*cz:\(\)=>L[\s\S]*settings\.read\(e.key\)[\s\S]*settings\.write\(e.key,t\)/);
  // Use the actual registration factory to confirm that the setter exposes the same
  // atom the transcript uses, and the capture never writes to a real scope.
  const token={},atom={},exports={};
  const require=id=>id==='Oj9r'?{GD:token}:{bD:scope=>{assert.equal(scope,token);return atom;}};
  require.d=(target,bindings,values)=>Object.assign(target,values);
  transcript.JhHS({},exports,require);
  let captured;
  exports.ch({set:(value,key,handler)=>{assert.equal(key,'probe');assert.equal(handler,null);captured=value;}},'probe',null);
  assert.equal(captured,atom);
  assert.equal(typeof exports.mL,'function');
  assert.equal(typeof exports.Zg,'function');
 }finally{await archive.close();}
});

for(const [version,runtime] of builds)test(`${version} Dock waits for native settings and preserves forced refresh`,async()=>{
 const calls=[],settings={};
 const load=id=>({
  GaA7:{appServices:settings},
  RxZZ:{LA:async({key})=>{calls.push(['read',key]);return 'codex-system';},
        cz:async({key},value)=>calls.push(['write',key,value])},
 })[id];
 load.m={GaA7:true,RxZZ:true};
 const run=refresh=>vm.runInNewContext(
  dockPreferenceExpression('codex-system',{early:true,refresh}).replace(
   "import('app://-/assets/'+runtimeModule)",'loadFixture(runtimeModule)'),
  {loadFixture:async name=>{assert.equal(name,runtime);return {__webpack_require__:load};},window:{electronBridge:{sendMessageFromView(){throw Error('legacy route');},
   getDesktopUserAgent:()=> `Codex Desktop/${version} (Mac OS; arm64)`}},
   document:{readyState:'complete',querySelector:()=>({})}},
 );
 assert.equal(await run(true),false);
 assert.deepEqual(calls,[]);
 settings.settings={};
 assert.equal(await run(false),true);
 assert.equal(await run(true),true);
 assert.deepEqual(calls,[['read','dock-icon-preference'],['write','dock-icon-preference','codex-system']]);
});
