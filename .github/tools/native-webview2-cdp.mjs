/** R8 experimental: attach Playwright to the real installed Tauri WebView2.
 * Never run against a user's application; the PowerShell caller uses a fresh CI-only install.
 */
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const require=createRequire(new URL('../../ui/editor/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const pid=Number(process.argv[2]);
const port=Number(process.argv[3]);
if(!Number.isInteger(pid)||pid<=0||!Number.isInteger(port)||port<1024||port>65535)
  throw Error('CI_PID_OR_PORT_INVALID');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const processAlive=()=>{
  try {
    execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',
      'if (!(Get-Process -Id '+pid+' -ErrorAction SilentlyContinue)) { exit 42 }'],
      {stdio:'pipe',timeout:10000});
    return true;
  }catch{return false;}
};
const closeMain=()=>{
  execFileSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',
    "$p=Get-Process -Id "+pid+" -ErrorAction Stop; if(!$p.CloseMainWindow()){throw 'CLOSE_MAIN_WINDOW_REJECTED'}"],
    {stdio:'pipe',timeout:15000});
};
let browser;
for(let i=0;i<50;i++){
  try { browser=await chromium.connectOverCDP('http://127.0.0.1:'+port,{timeout:1500}); break; }
  catch {if(!processAlive())throw Error('WINDOW_EXITED_BEFORE_CDP');await sleep(500);}
}
if(!browser)throw Error('WEBVIEW2_CDP_UNAVAILABLE');
try {
  let page;
  for(let i=0;i<40;i++){
    page=browser.contexts().flatMap(c=>c.pages()).find(p=>!p.url().startsWith('devtools://'));
    if(page)break;
    await sleep(250);
  }
  if(!page)throw Error('WEBVIEW2_PAGE_NOT_FOUND');
  await page.getByTestId('gscad-signed-svg-canvas').waitFor({state:'visible',timeout:20000});
  console.log('REAL_WEBVIEW2_CANVAS_READY');
  await page.getByRole('button',{name:'Показать сетку'}).click();
  await page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true})
    .waitFor({state:'visible',timeout:7000});
  console.log('REAL_WEBVIEW2_DIRTY_SET');
  const armConfirm=(accept)=>new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error('NATIVE_JS_CONFIRM_NOT_OBSERVED')),12000);
    page.once('dialog',async dialog=>{
      clearTimeout(timer);
      try{
        assert.equal(dialog.type(),'confirm');
        if(accept)await dialog.accept();else await dialog.dismiss();
        resolve();
      }catch(error){reject(error);}
    });
  });
  await sleep(500);
  const cancel=armConfirm(false);
  closeMain();
  await cancel;
  if(!processAlive())throw Error('DIRTY_CANCEL_DID_NOT_KEEP_WINDOW');
  await page.getByTestId('gscad-signed-svg-canvas').waitFor({state:'visible',timeout:7000});
  console.log('REAL_WEBVIEW2_DIRTY_CANCEL_PASS');
  const confirm=armConfirm(true);
  closeMain();
  await confirm;
  console.log('REAL_WEBVIEW2_DIRTY_CONFIRM_REQUEST_SENT');
  for(let i=0;i<60&&processAlive();i++)await sleep(500);
  if(processAlive())throw Error('REAL_WEBVIEW2_CONFIRMED_CLOSE_TIMEOUT');
  console.log('REAL_WEBVIEW2_DIRTY_CONFIRM_EXIT_PASS');
}finally{try{await browser.close();}catch{/* may already be closing */}}
