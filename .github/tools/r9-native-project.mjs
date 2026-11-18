/** R9: real Windows NSIS + WebView2 + native IFileDialog + Python sidecar acceptance.
 * No fake Tauri commands, no browser file input, no user paths.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn,spawnSync,execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import path from 'node:path';

const require=createRequire(new URL('../../ui/editor/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const [phase,pidText,portText,projectPath,copyPath,svgPath,pngPath]=process.argv.slice(2);
const pid=Number(pidText), port=Number(portText);
const root=process.env.RUNNER_TEMP;
if(process.env.GITHUB_ACTIONS!=='true'||!root||!pid||!port||!['create','reopen'].includes(phase))
  throw Error('R9_CI_ARGS_INVALID');
for(const p of [projectPath,copyPath,svgPath,pngPath]){
  if(!path.resolve(p).toLowerCase().startsWith(path.resolve(root).toLowerCase()+path.sep))
    throw Error('R9_PATH_OUTSIDE_RUNNER_TEMP');
}
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function awaitNativePublish(filepath,label){
  // pywinauto acknowledges the OS dialog, *not* Rust/Python completion.
  // New destination names are isolated inside RUNNER_TEMP and are never reused.
  for(let i=0;i<120;i++){
    if(fs.existsSync(filepath)){
      const st=fs.statSync(filepath);
      if(st.isFile()&&st.size>50){
        console.log('R9_NATIVE_DISK_PUBLISH_ACK='+label+' bytes='+st.size);
        return;
      }
    }
    await sleep(250);
  }
  let ui='UNAVAILABLE';
  try { ui=(await page.evaluate(()=>document.body.innerText)).slice(-1500); }catch{}
  console.log('R9_NATIVE_PUBLISH_TIMEOUT_UI='+ui);
  throw Error('R9_NATIVE_PUBLISH_TIMEOUT_'+label);
}
const digest=filepath=>execFileSync('python',['-c',
  'import json,sys;from ui.editor.src.model.contract import validate,digest;d=json.load(open(sys.argv[1],encoding="utf-8"));validate(d);print(digest(d))',
  filepath],{encoding:'utf8',timeout:30000}).trim();
const status=file=>{
  const value=fs.statSync(file);
  assert(value.size>50&&value.size<850000,'native file size gate');
  return JSON.parse(fs.readFileSync(file,'utf8'));
};
const same=()=>assert.deepStrictEqual(status(copyPath),status(projectPath));
async function runDialog(mode,filepath,trigger){
  const child=spawn('python',['.github/tools/r9-native-dialog.py','--pid',String(pid),
    '--mode',mode,'--path',filepath],{cwd:process.cwd(),stdio:['ignore','pipe','pipe']});
  let output='';
  child.stdout.on('data',data=>{output+=data.toString();});
  child.stderr.on('data',data=>{output+=data.toString();});
  let exited=false;
  const done=new Promise((resolve,reject)=>{
    child.on('error',reject);
    child.on('close',code=>{exited=true;code===0?resolve():reject(Error('R9_DIALOG_FAILED_'+code+' '+output));});
  });
  const timer=setTimeout(()=>{if(!exited)child.kill();},35000);
  try {
    await trigger();
    await done;
    console.log(output.trim());
  }finally{
    clearTimeout(timer);
    if(!exited)child.kill();
  }
}
function assertModel(doc){
  assert.equal(doc.format,'gscad-project');
  assert.equal(doc.format_version,2);
  assert.equal(doc.project.provenance.status,'synthetic');
  assert.equal(doc.project.components.length,3);
  assert.deepStrictEqual(doc.project.components.map(x=>x.refdes).sort(),['C9','R1','R2']);
  assert.equal(doc.project.components.find(x=>x.refdes==='C9').value,'220н');
  assert.deepStrictEqual(doc.project.sheets[0].frame.size_um,[420000,297000]);
  assert.equal(doc.project.nets.length,1);
  assert.equal(doc.project.nets[0].members.length,2);
  assert.equal(doc.project.sheets[0].wires.length,1);
  assert.equal(doc.project.sheets[0].junctions.length,0);
  assert(doc.project.sheets[0].instances.every(i=>i.origin_um.every(Number.isInteger)));
}
let browser=null,page=null;
for(let i=0;i<45;i++){
  try{browser=await chromium.connectOverCDP('http://127.0.0.1:'+port,{timeout:1500});break;}
  catch{await sleep(500);}
}
if(!browser)throw Error('R9_REAL_WEBVIEW2_CDP_UNAVAILABLE');
try{
  for(let i=0;i<60;i++){
    page=browser.contexts().flatMap(x=>x.pages()).find(x=>!x.url().startsWith('devtools://'));
    if(page)break;
    await sleep(250);
  }
  if(!page)throw Error('R9_NATIVE_PAGE_NOT_FOUND');
  await page.getByTestId('gscad-signed-svg-canvas').waitFor({state:'visible',timeout:20000});
  console.log('R9_REAL_WEBVIEW2_CANVAS_PASS phase='+phase);
  if(phase==='create'){
    for(const file of [projectPath,copyPath,svgPath,pngPath])
      assert(!fs.existsSync(file),'R9_TEMP_FILE_PREEXISTS');
    await page.getByRole('button',{name:'Файл'}).click();
    await page.getByTestId('new-project').click();
    await page.getByText(/R3 AUTHORING/).first().waitFor({state:'visible'});
    const canvas=page.getByTestId('gscad-signed-svg-canvas');
    const narrow=await page.evaluate(()=>window.innerWidth<960);
    console.log('R9_NATIVE_VIEWPORT_NARROW='+narrow);
    // Native Tauri starts at 900px. On that width the UGO library and
    // inspector are intentionally collapsed; exercise the real toggle UI.
    const place=async(symbol,x,y,refdes)=>{
      if(narrow)await page.getByRole('button',{name:'Показать библиотеку УГО'}).click();
      await page.getByTestId('catalog-item-symbol/'+symbol).click();
      if(narrow)await page.getByRole('button',{name:'Показать библиотеку УГО'}).click();
      const box=await canvas.boundingBox();assert(box);
      await page.mouse.click(box.x+box.width*x,box.y+box.height*y);
      await page.getByTestId('symbol-'+refdes).waitFor({state:'visible',timeout:5000});
    };
    await place('resistor.fixed',.25,.40,'R1');
    await place('capacitor.fixed',.65,.40,'C1');
    if(narrow)await page.getByRole('button',{name:'Показать инспектор'}).click();
    await page.getByLabel('Позиционное обозначение').fill('C9');
    await page.getByLabel('Позиционное обозначение').press('Enter');
    await page.getByTestId('symbol-C9').waitFor({state:'visible',timeout:5000});
    await page.getByTestId('inspector-nominal').fill('220н');
    await page.getByTestId('inspector-nominal').press('Enter');
    if(narrow)await page.getByRole('button',{name:'Показать инспектор'}).click();
    await place('resistor.fixed',.83,.70,'R2');
    const r1=await page.getByTestId('symbol-R1').getAttribute('data-component-id');
    const c9=await page.getByTestId('symbol-C9').getAttribute('data-component-id');
    assert(r1&&c9);
    await page.getByRole('button',{name:'Провод W'}).click();
    await page.getByTestId('signed-pin-'+r1+'-2').click();
    await page.getByTestId('signed-pin-'+c9+'-1').click();
    assert.equal(await page.locator('[data-net-id]').count(),1,'real physical wire');
    console.log('R9_REAL_CAD_PLACEMENT_WIRE_PASS');
    // Read-only argument capture: delegate to the original real Tauri invoke.
    // If Rust reports ENGINE_TERMINATED, replay the *same* document through the
    // genuine installed sidecar without the window/dialog to distinguish causes.
    const observed=await page.evaluate(()=>{
      const core=window.__TAURI__?.core,original=core?.invoke;
      if(typeof original!=='function')return false;
      core.invoke=(command,args)=>{
        if(command==='native_save_as_project')window.__r9NativeDocument=args?.document;
        return original.call(core,command,args);
      };
      return true;
    });
    assert(observed,'R9_NATIVE_INVOKE_OBSERVATION_UNAVAILABLE');
    await runDialog('save',projectPath,()=>page.getByTestId('save-project').click());
    try {
      await page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true})
        .waitFor({state:'hidden',timeout:15000});
    }catch(error){
      console.log('R9_SAVE_AS_DIAG_FILE_EXISTS='+fs.existsSync(projectPath));
      console.log('R9_SAVE_AS_DIAG_DIR='+JSON.stringify(fs.readdirSync(path.dirname(projectPath))));
      try {
        const ui=await page.evaluate(()=>document.body.innerText);
        console.log('R9_SAVE_AS_DIAG_UI='+ui.slice(-2300));
        const captured=await page.evaluate(()=>window.__r9NativeDocument);
        if(captured&&process.env.GSCAD_R9_SIDECAR_EXE){
          const input=JSON.stringify({v:1,id:'r9_same_document',op:'parse_document_blob',
            args:{blob:JSON.stringify(captured)}})+'\n';
          const probe=spawnSync(process.env.GSCAD_R9_SIDECAR_EXE,[],{
            input,encoding:'utf8',timeout:25000,windowsHide:true
          });
          console.log('R9_DIRECT_SAME_DOCUMENT_EXIT='+probe.status+' SIGNAL='+probe.signal);
          console.log('R9_DIRECT_SAME_DOCUMENT_STDERR='+String(probe.stderr??'').slice(-750));
          try{
            const response=JSON.parse(probe.stdout?.trim()??'');
            console.log('R9_DIRECT_SAME_DOCUMENT_OK='+response.ok+
              ' CODE='+String(response.error?.code??'none'));
          }catch(e){console.log('R9_DIRECT_SAME_DOCUMENT_PROTOCOL_ERROR='+String(e));}
        }else console.log('R9_DIRECT_SAME_DOCUMENT_CAPTURE_UNAVAILABLE');
      }catch(e){console.log('R9_SAVE_AS_DIAG_UI_UNAVAILABLE '+String(e));}
      throw error;
    }
    const saved=status(projectPath);
    assertModel(saved);
    const sum=digest(projectPath);
    assert.match(sum,/^[0-9a-f]{64}$/);
    fs.writeFileSync(projectPath+'.r9digest',sum+'\n',{flag:'wx'});
    console.log('R9_REAL_NATIVE_SAVE_AS_PASS digest='+sum);
  }else{
    assert(fs.existsSync(projectPath),'SAVED_DOCUMENT_MISSING_BEFORE_REOPEN');
    const original=status(projectPath); assertModel(original);
    const beforeDigest=digest(projectPath);
    assert.equal(beforeDigest,fs.readFileSync(projectPath+'.r9digest','utf8').trim());
    await runDialog('open',projectPath,async()=>{
      await page.getByRole('button',{name:'Файл'}).click();
      await page.getByText('Открыть…',{exact:true}).click();
    });
    try {
      await page.getByTestId('symbol-C9').waitFor({state:'visible',timeout:15000});
    }catch(error){
      console.log('R9_OPEN_DIAG_FILE_EXISTS='+fs.existsSync(projectPath));
      console.log('R9_OPEN_DIAG_DIGEST='+digest(projectPath));
      try {
        console.log('R9_OPEN_DIAG_UI='+(await page.evaluate(()=>document.body.innerText)).slice(-2600));
        console.log('R9_OPEN_DIAG_SYMBOL_COUNT='+await page.locator('[data-testid^="symbol-"]').count());
      }catch(err){console.log('R9_OPEN_DIAG_UI_UNAVAILABLE '+String(err));}
      throw error;
    }
    assert.equal(await page.locator('[data-testid^="symbol-"]').count(),3);
    assert.equal(await page.locator('[data-net-id]').count(),1);
    // A 900px desktop reopens with its inspector collapsed by design.
    // Select C9 through the authoritative project-tree item.
    const narrowReopen=await page.evaluate(()=>window.innerWidth<960);
    if(narrowReopen)
      await page.getByRole('button',{name:'Показать инспектор'}).click();
    await page.getByText('C9',{exact:true}).first().click();
    assert.equal(await page.getByTestId('inspector-nominal').inputValue(),'220н');
    // At Tauri's 900px width the responsive inspector is a floating overlay;
    // close it after reading C9 or it intercepts controls behind the aside.
    if(narrowReopen)
      await page.getByRole('button',{name:'Показать инспектор'}).click();
    console.log('R9_REAL_NATIVE_REOPEN_GUI_PASS');
    // Existing handle: Save must not open a picker and must preserve the exact model.
    // Reapply the same grid setting so the canonical document stays byte-for-byte
    // identical, but mark the UI dirty to observe native Save completion visibly.
    const gridToggle=page.getByTestId('toggle-grid-visible');
    await gridToggle.click();
    await gridToggle.click();
    const dirtyIndicator=page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true});
    await dirtyIndicator.waitFor({state:'visible',timeout:5000});
    await page.getByTestId('save-project').click();
    // Native Save is async; do not begin Save As while its Rust CAS handle is busy.
    await dirtyIndicator.waitFor({state:'hidden',timeout:20000});
    assert.deepStrictEqual(status(projectPath),original);
    assert.equal(digest(projectPath),beforeDigest);
    console.log('R9_REAL_NATIVE_SAVE_SAME_PATH_PASS');
    try {
      await runDialog('save',copyPath,async()=>{
        await page.getByRole('button',{name:'Файл'}).click();
        await page.getByTestId('save-project-as').click();
      });
    }catch(error){
      console.log('R9_SECOND_SAVE_AS_UI_DIAG='+
        (await page.evaluate(()=>document.body.innerText)).slice(-2000));
      throw error;
    }
    await page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true})
      .waitFor({state:'hidden',timeout:20000});
    await awaitNativePublish(copyPath,'save-as-unicode');
    same();
    assert.equal(digest(copyPath),beforeDigest);
    console.log('R9_REAL_NATIVE_SAVE_AS_UNICODE_PASS');
    try {
      await runDialog('save',svgPath,async()=>{
        await page.getByRole('button',{name:'Экспорт',exact:true}).click();
        await page.getByRole('button',{name:'Экспортировать'}).click();
      });
    }catch(error){
      console.log('R9_NATIVE_SVG_EXPORT_UI_DIAG='+
        (await page.evaluate(()=>document.body.innerText)).slice(-2200));
      // Independent installed sidecar receives the exact reopened disk project.
      // This is diagnostic only and can never substitute for the native GUI gate.
      if(process.env.GSCAD_R9_SIDECAR_EXE){
        const request=JSON.stringify({v:1,id:'r9_svg_direct',
          op:'native_export_preview',args:{document:status(copyPath),
            sheet_id:original.workspace.active_sheet_id,format:'svg'}})+'\\n';
        const probe=spawnSync(process.env.GSCAD_R9_SIDECAR_EXE,[],{
          input:request,encoding:'utf8',timeout:25000,maxBuffer:6*1024*1024,
          windowsHide:true});
        console.log('R9_SVG_DIRECT_SIDECAR_EXIT='+probe.status+
          ' STDERR='+String(probe.stderr??'').slice(-400));
        try{
          const result=JSON.parse(String(probe.stdout??'').trim());
          console.log('R9_SVG_DIRECT_SIDECAR_OK='+result.ok+
            ' ERROR='+String(result.error?.code??'none'));
        }catch(e){console.log('R9_SVG_DIRECT_RESPONSE_INVALID='+String(e));}
      }
      throw error;
    }
    await awaitNativePublish(svgPath,'svg');
    const svg=fs.readFileSync(svgPath,'utf8');
    assert.match(svg,/<svg|<\?xml/);
    assert.match(svg,/420mm/);
    assert(!svg.includes('data-selected='));
    console.log('R9_REAL_NATIVE_SVG_PASS');
    await runDialog('save',pngPath,async()=>{
      await page.getByRole('button',{name:'Экспорт',exact:true}).click();
      await page.getByText('PNG 300 DPI',{exact:true}).click();
      await page.getByRole('button',{name:'Экспортировать'}).click();
    });
    await awaitNativePublish(pngPath,'png300');
    const png=fs.readFileSync(pngPath);
    assert.deepStrictEqual([...png.subarray(0,8)],[137,80,78,71,13,10,26,10]);
    assert.equal(png.readUInt32BE(16),Math.round(420/25.4*300));
    assert.equal(png.readUInt32BE(20),Math.round(297/25.4*300));
    const phys=png.indexOf(Buffer.from('pHYs'));
    assert(phys>0,'pHYs chunk missing');
    assert.equal(png.readUInt32BE(phys+4),11811);
    assert.equal(png.readUInt32BE(phys+8),11811);
    assert.equal(png[phys+12],1);
    console.log('R9_REAL_NATIVE_PNG300_PASS');
    console.log('R9_REAL_NATIVE_PROJECT_PERSISTENCE_ACCEPTED digest='+beforeDigest);
  }
}finally{try{await browser?.close();}catch{/* Tauri process stays owned by PowerShell */}}
