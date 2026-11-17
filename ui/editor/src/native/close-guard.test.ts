import test from 'node:test';
import assert from 'node:assert/strict';
import {installNativeCloseGuard} from './close-guard.ts';

test('normal browser has no native close listener',async()=>{
  assert.equal(await installNativeCloseGuard(()=>true,()=>false),null);
});

test('native user-close is blocked only when dirty and the user rejects data loss',async()=>{
  let onClose:(event:{preventDefault():void})=>void=()=>{};
  let disposed=false,prompts=0,dirty=false,accept=false;
  Object.defineProperty(globalThis,'window',{configurable:true,value:{
    __TAURI__:{
      core:{invoke:async()=>null},
      window:{getCurrentWindow:()=>({onCloseRequested:async(listener:typeof onClose)=>{
        onClose=listener;return ()=>{disposed=true;};
      }})}
    }
  }});
  try {
    const unlisten=await installNativeCloseGuard(()=>dirty,()=>{prompts++;return accept;});
    assert.ok(unlisten);
    const emit=()=>{let prevented=false;onClose({preventDefault(){prevented=true;}});return prevented;};
    assert.equal(emit(),false);
    assert.equal(prompts,0);
    dirty=true;
    assert.equal(emit(),true);
    assert.equal(prompts,1);
    accept=true;
    assert.equal(emit(),false);
    assert.equal(prompts,2);
    unlisten();
    assert.equal(disposed,true);
  }finally{
    Reflect.deleteProperty(globalThis,'window');
  }
});

test('native host missing window-close hook reports unavailable instead of pretending protection',async()=>{
  Object.defineProperty(globalThis,'window',{configurable:true,value:{
    __TAURI__:{core:{invoke:async()=>null}}
  }});
  try {
    await assert.rejects(
      installNativeCloseGuard(()=>true,()=>false),/NATIVE_CLOSE_LISTENER_UNAVAILABLE/
    );
  }finally{Reflect.deleteProperty(globalThis,'window');}
});


test('save-in-progress remains guarded even if the document is clean',async()=>{
  let listener:(event:{preventDefault():void})=>void=()=>{};
  let active=true, prompts=0, prevented=0;
  Object.defineProperty(globalThis,'window',{configurable:true,value:{
    __TAURI__:{
      core:{invoke:async()=>null},
      window:{getCurrentWindow:()=>({onCloseRequested:async(fn:typeof listener)=>{
        listener=fn;return ()=>{active=false;};
      }})}
    }
  }});
  try {
    const off=await installNativeCloseGuard(()=>false,()=>{prompts++;return false;},()=>true);
    listener({preventDefault(){prevented++;}});
    assert.equal(prompts,1);
    assert.equal(prevented,1);
    off?.();
    assert.equal(active,false);
  }finally{Reflect.deleteProperty(globalThis,'window');}
});


test('Tauri main-window ACL explicitly permits the Tauri JS close guard to destroy clean windows',async()=>{
  const {readFileSync}=await import('node:fs');
  const acl=JSON.parse(readFileSync(new URL('../../../desktop/src-tauri/capabilities/default.json',import.meta.url),'utf8'));
  // Tauri 2.12.5 Window.onCloseRequested calls this.destroy() when the handler
  // returns without preventDefault; core:window:default does NOT allow destroy.
  assert.deepEqual(acl.windows,['main']);
  assert.ok(acl.permissions.includes('core:window:allow-destroy'),
    'onCloseRequested silently leaves the main window alive without allow-destroy');
  assert.ok(!acl.permissions.some((p:string)=>p.startsWith('shell:')||p.startsWith('fs:')));
});
