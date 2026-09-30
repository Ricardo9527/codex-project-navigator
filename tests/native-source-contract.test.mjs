import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
test('source reveal adapter matches installed transcript registry and focus exports',async t=>{
 let archive;try{archive=await readFile('/Applications/ChatGPT.app/Contents/Resources/app.asar');}catch(e){if(e.code==='ENOENT'){t.skip('no installed desktop bundle');return;}throw e;}
 const size=archive.readUInt32LE(4),jsonSize=archive.readUInt32LE(12),assets=JSON.parse(archive.subarray(16,16+jsonSize).toString()).files.webview.files.assets.files;
 const entry=assets['app-primary-83ab2f0c1a5c.js'];if(!entry){t.skip('different desktop build');return;}
 const src=archive.subarray(8+size+Number(entry.offset),8+size+Number(entry.offset)+entry.size).toString(),exports=src.slice(src.lastIndexOf('export{'));
 const registry=exports.match(/([\w$]+) as Ip[,}]/)[1],focus=exports.match(/([\w$]+) as Lp[,}]/)[1];
 assert.match(src.slice(src.indexOf('function '+registry+'('),src.indexOf('function '+registry+'(')+180),/\.set\(/);
 assert.match(src.slice(src.indexOf('function '+focus+'('),src.indexOf('function '+focus+'(')+240),/scrollIntoView/);
});
