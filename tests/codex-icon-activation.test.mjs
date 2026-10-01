import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {isLibraryIconSession,markLibraryIconSession} from '../scripts/codex-icon-activation.mjs';
test('repeat clicks and service reloads preserve library activation, while a new Codex process does not inherit it',async()=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'codex-icon-session-'));
 try{
  assert.equal(await isLibraryIconSession(root,'browser-A'),false);
  await markLibraryIconSession(root,'browser-A');
  assert.equal(await isLibraryIconSession(root,'browser-A'),true);
  assert.equal(await isLibraryIconSession(root,'browser-B'),false);
  await markLibraryIconSession(root,'browser-B');
  assert.equal(await isLibraryIconSession(root,'browser-A'),false);
  assert.equal(await isLibraryIconSession(root,'browser-B'),true);
 }finally{await rm(root,{recursive:true,force:true});}
});
