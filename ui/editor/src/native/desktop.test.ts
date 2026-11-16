import test from 'node:test';
import assert from 'node:assert/strict';
import {
 nativeDesktopAvailable,nativeOpenProject,nativeSaveProject,
 nativeSaveAsProject,nativeCloseProject
} from './desktop.ts';

test('R4 JS invokes only allowlisted opaque native document handles, never file paths/shell',async()=>{
 assert.equal(nativeDesktopAvailable(),false);
 const fake={format:'gscad-project',format_version:2,project:{id:'p'},workspace:{}};
 const known={handle:'opaque-session-uuid',generation:8,project_sha256:'a'.repeat(64),filename:'safe.gscad.json'};
 const calls=[];
 Object.defineProperty(globalThis,'window',{configurable:true,value:{
  __TAURI__:{core:{invoke:async(command,args)=>{
   calls.push({command,args});
   return {...known,document:fake};
  }}}
 }});
 try{
  assert.equal(nativeDesktopAvailable(),true);
  await nativeOpenProject();
  await nativeSaveProject(known,fake);
  await nativeSaveAsProject(fake,known);
  await nativeCloseProject(known.handle);
  assert.deepEqual(calls.map(c=>c.command),[
   'native_open_project','native_save_project','native_save_as_project','native_close_project'
  ]);
  assert.deepEqual(calls[1].args,{
   handle:known.handle,expectedGeneration:8,expectedProjectSha256:'a'.repeat(64),
   document:fake
  });
  assert.deepEqual(calls[2].args,{
   document:fake,previousHandle:known.handle,
   expectedGeneration:8,expectedProjectSha256:'a'.repeat(64)
  });
  assert.deepEqual(calls[3].args,{handle:known.handle});
  for(const item of calls){
   assert.equal(JSON.stringify(item.args??{}).includes('path'),false);
   assert.equal(JSON.stringify(item.args??{}).includes('commandLine'),false);
  }
 }finally{
  delete globalThis.window;
 }
});
