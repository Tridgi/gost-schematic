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
const full=process.env.GSCAD_R33_FULL_TL494==='1';
const editorQA=process.env.GSCAD_R51_EDITOR_PHASE==='1';
if(full&&editorQA)throw Error('R51_CONFLICTING_NATIVE_PHASES');
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
  if(full){
    const sh=doc.project.sheets[0];
    assert.equal(doc.project.components.length,23);
    assert.equal(doc.project.nets.length,15);
    assert.equal(doc.project.nets.reduce((n,v)=>n+v.members.length,0),62);
    assert.equal(sh.graphics.filter(g=>g.kind==='source_b_continuation').length,2);
    if(process.env.GSCAD_R35_EXTENDED==='1')assert.ok(sh.wires.length>0&&sh.wires.length<=512);
    else assert.equal(sh.wires.length,78);
    assert.deepStrictEqual(sh.frame.size_um,[420000,297000]);
    const da=doc.project.components.find(c=>c.refdes==='DA1');
    assert.equal(new Set(doc.project.nets.flatMap(n=>n.members.filter(m=>m.component_id===da.id).map(m=>m.physical_pin_number))).size,16);
    return;
  }
  if(editorQA){
    const sh=doc.project.sheets[0];
    assert.equal(doc.project.components.length,4);
    assert.deepEqual(doc.project.components.map(c=>c.refdes).sort(),['R1','R2','R3','R4']);
    assert.equal(doc.project.nets.length,1);
    assert.equal(doc.project.nets[0].members.length,4);
    assert.equal(sh.wires.length,4);assert.equal(sh.junctions.length,1);
    assert.equal(sh.texts.length,1);
    assert.equal(sh.texts[0].text,'MMMMMM');
    assert.equal(sh.texts[0].rotation_deg,90);
    assert.equal(sh.texts[0].height_um,5000);
    assert.deepEqual(sh.texts[0].at_um,[65125,140000]);
    assert.deepEqual(sh.frame.size_um,[420000,297000]);
    return;
  }
  assert.equal(doc.project.components.length,3);
  assert.deepStrictEqual(doc.project.components.map(x=>x.refdes).sort(),['C9','R1','R2']);
  assert.equal(doc.project.components.find(x=>x.refdes==='C9').value,'220н');
  assert.deepStrictEqual(doc.project.sheets[0].frame.size_um,[420000,297000]);
  assert.equal(doc.project.nets.length,1);
  assert.equal(doc.project.nets[0].members.length,2);
  assert.equal(doc.project.sheets[0].wires.length,1);
  assert.equal(doc.project.sheets[0].junctions.length,0);
  assert(doc.project.sheets[0].instances.every(i=>i.origin_um.every(Number.isInteger)));
  // Export must never rescale or silently clip symbols outside A3.
  // This is a valid in-page authoring acceptance, not an out-of-frame test.
  const [pw,ph]=doc.project.sheets[0].frame.size_um;
  for(const instance of doc.project.sheets[0].instances){
    const [x,y]=instance.origin_um;
    assert(x>=20000&&x<=pw-20000&&y>=20000&&y<=ph-20000,
      'R9_NATIVE_SCHEMATIC_ORIGIN_OUTSIDE_A3 '+JSON.stringify(instance.origin_um));
  }
  for(const wire of doc.project.sheets[0].wires)
    for(const vertex of wire.vertices){
      const [x,y]=vertex.at_um;
      assert(x>=0&&x<=pw&&y>=0&&y<=ph,'R9_NATIVE_WIRE_OUTSIDE_A3');
    }
}
let browser=null,page=null;

// All actions use the installed WebView and actual native file IPC.
// Do not use page.goto, browser downloads, injected model or mock commands.
async function createEditorAcceptance(){
  await page.getByRole('button',{name:'Файл',exact:true}).click();
  await page.getByTestId('new-project').click();
  await page.getByText(/R3 AUTHORING/).first().waitFor({state:'visible'});
  const canvas=page.getByTestId('gscad-signed-svg-canvas');
  const paper=page.getByTestId('gscad-paper-outline');
  const narrow=await page.evaluate(()=>window.innerWidth<960);
  const position=async(x,y)=>{const b=await paper.boundingBox();assert(b);return {x:b.x+b.width*x,y:b.y+b.height*y};};
  const dirty=page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true});
  const save=async()=>{
    if(!fs.existsSync(projectPath)){
      await runDialog('save',projectPath,()=>page.getByTestId('save-project').click());
      await awaitNativePublish(projectPath,'r51-create');
    }else if(await dirty.count()){
      await page.getByTestId('save-project').click();
    }
    await dirty.waitFor({state:'hidden',timeout:20000});
    return status(projectPath);
  };
  const waitCount=async(selector,n)=>page.waitForFunction(({selector,n})=>document.querySelectorAll(selector).length===n,{selector,n},{timeout:10000});
  const wires='.electric-wires > g[data-wire-id]';
  const junctions='[data-junction-id]';
  const undo=()=>page.getByRole('button',{name:'Отменить'}).click();
  const redo=()=>page.getByRole('button',{name:'Повторить'}).click();
  for(const [i,[x,y]] of [[.23,.4],[.75,.4],[.5,.75],[.56,.17]].entries()){
    if(narrow)await page.getByRole('button',{name:'Показать библиотеку УГО'}).click();
    await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
    if(narrow)await page.getByRole('button',{name:'Показать библиотеку УГО'}).click();
    const p=await position(x,y);
    await page.mouse.move(p.x,p.y);
    await page.getByTestId('gscad-placement-preview').waitFor({state:'visible'});
    await page.mouse.click(p.x,p.y);
    await page.getByTestId('symbol-R'+(i+1)).waitFor({state:'visible'});
  }
  const doc=await save(),[a,b,c,d]=doc.project.components;
  const wireTool=()=>page.getByTestId('tool-wire').click();
  const selectTool=()=>page.getByTestId('tool-select').click();
  const pin=(component,n)=>page.getByTestId('signed-pin-'+component.id+'-'+n).click();
  await wireTool();await pin(a,2);await pin(b,1);await waitCount(wires,1);
  await selectTool();
  const trunk=(await save()).project.sheets[0].wires[0];
  const mid=await page.locator('[data-segment-id="'+trunk.segments[0].id+'"]').evaluate(el=>{
    const pt=el.ownerSVGElement.createSVGPoint();
    pt.x=(Number(el.getAttribute('x1'))+Number(el.getAttribute('x2')))/2;
    pt.y=(Number(el.getAttribute('y1'))+Number(el.getAttribute('y2')))/2;
    const p=pt.matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y};
  });
  await wireTool();await pin(c,1);await page.mouse.move(mid.x,mid.y);
  await page.getByTestId('wire-tap-preview').waitFor({state:'visible'});
  await page.mouse.click(mid.x,mid.y);await waitCount(junctions,1);await waitCount(wires,3);
  await selectTool();const before=await save(),node=before.project.sheets[0].junctions[0];
  const at=await page.locator('[data-junction-id="'+node.id+'"]').evaluate(el=>{
    const pt=el.ownerSVGElement.createSVGPoint();pt.x=Number(el.getAttribute('cx'));pt.y=Number(el.getAttribute('cy'));
    const p=pt.matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y};
  });
  const checkFourth=after=>{
    assert.equal(after.project.nets.length,1);assert.equal(after.project.nets[0].members.length,4);
    assert.deepEqual(after.project.sheets[0].junctions,before.project.sheets[0].junctions);
    for(const w of before.project.sheets[0].wires)
      assert.deepEqual(after.project.sheets[0].wires.find(x=>x.id===w.id),w);
  };
  await wireTool();await pin(d,1);await page.mouse.move(at.x,at.y);
  await page.getByTestId('wire-tap-preview').waitFor({state:'visible'});
  await canvas.focus();await canvas.press('Escape');await waitCount(wires,3);
  await wireTool();await pin(d,1);await page.mouse.click(at.x,at.y);
  await waitCount(wires,4);await selectTool();checkFourth(await save());
  await undo();await waitCount(wires,3);assert.deepEqual((await save()).project,before.project);
  await wireTool();await page.mouse.click(at.x,at.y);await canvas.focus();await canvas.press('Enter');
  await waitCount(wires,3);await canvas.press('Escape');await waitCount(wires,3);
  await wireTool();await page.mouse.click(at.x,at.y);await pin(d,1);await waitCount(wires,4);
  await selectTool();const connected=await save();checkFourth(connected);
  await undo();await waitCount(wires,3);assert.deepEqual((await save()).project,before.project);
  await redo();await waitCount(wires,4);assert.deepEqual((await save()).project,connected.project);
  console.log('R51_REAL_NATIVE_JUNCTION_BOTH_DIRECTIONS_PASS');

  await canvas.focus();await canvas.press('t');const p=await position(.25,.55);
  await page.mouse.click(p.x,p.y);await page.getByTestId('sheet-text-input').fill('MMMMMM');
  await page.getByTestId('add-sheet-text').click();await page.getByTestId('sheet-text-input').waitFor({state:'hidden'});
  const annotation=canvas.locator('text[data-testid^="sheet-text-"]');
  await annotation.waitFor({state:'visible'});const textBefore=await save();
  const original=textBefore.project.sheets[0].texts[0],grid=textBefore.project.settings.grid_step_um;
  const b0=await annotation.boundingBox(),pb=await paper.boundingBox();assert(b0&&pb);
  const x=b0.x+b0.width/2,y=b0.y+b0.height/2,dx=pb.width*.13,dy=pb.height*.06;
  const drag=async()=>{await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+dx,y+dy,{steps:8});
    await page.getByTestId('sheet-text-drag-preview').waitFor({state:'visible'});};
  await drag();await canvas.press('Escape');await page.getByTestId('sheet-text-drag-preview').waitFor({state:'detached'});
  await page.mouse.up();assert.deepEqual((await save()).project,textBefore.project);
  await drag();await page.mouse.up();await page.getByTestId('sheet-text-drag-preview').waitFor({state:'detached'});
  const dragged=await save(),moved=dragged.project.sheets[0].texts[0];
  assert.equal(moved.id,original.id);assert(moved.at_um[0]>original.at_um[0]&&moved.at_um[1]>original.at_um[1]);
  assert.deepEqual(moved.at_um.map(n=>n%grid),[0,0]);
  const expected=structuredClone(textBefore.project);expected.sheets[0].texts[0].at_um=moved.at_um;
  assert.deepEqual(dragged.project,expected);
  await undo();assert.deepEqual((await save()).project,textBefore.project);
  await redo();assert.deepEqual((await save()).project,dragged.project);
  await annotation.click();await page.getByTestId('sheet-text-selection').waitFor({state:'visible'});
  await canvas.press('ArrowRight');await canvas.press('Shift+ArrowUp');
  const nudged=await save(),nudgeExpected=structuredClone(dragged.project);
  nudgeExpected.sheets[0].texts[0].at_um=[moved.at_um[0]+grid,moved.at_um[1]-10*grid];
  assert.deepEqual(nudged.project,nudgeExpected);
  await canvas.press('F2');
  const dialog=page.getByRole('dialog',{name:'Свойства надписи'});
  await dialog.waitFor({state:'visible'});
  await dialog.getByTestId('sheet-text-input').focus();await page.keyboard.press('Delete');
  assert.equal(await annotation.count(),1);
  await dialog.getByRole('button',{name:'Отмена',exact:true}).click();await dialog.waitFor({state:'hidden'});
  await annotation.click();await canvas.press('Escape');await canvas.press('Delete');
  assert.deepEqual((await save()).project,nudged.project);
  await annotation.click();await canvas.press('Delete');await annotation.waitFor({state:'detached'});
  const deleted=await save();const deleteExpected=structuredClone(nudged.project);deleteExpected.sheets[0].texts=[];
  assert.deepEqual(deleted.project,deleteExpected);
  await undo();await annotation.waitFor({state:'visible'});assert.deepEqual((await save()).project,nudged.project);
  await redo();await annotation.waitFor({state:'detached'});assert.deepEqual((await save()).project,deleted.project);
  await undo();await annotation.waitFor({state:'visible'});
  await annotation.dblclick();await dialog.waitFor({state:'visible'});
  await dialog.getByTestId('sheet-text-x').fill('65,125');
  await dialog.getByTestId('sheet-text-y').fill('140');
  await dialog.getByText('5',{exact:true}).click();await dialog.getByText('90',{exact:true}).click();
  await dialog.getByTestId('add-sheet-text').click();await dialog.waitFor({state:'hidden'});
  const final=await save(),finalExpected=structuredClone(nudged.project);
  Object.assign(finalExpected.sheets[0].texts[0],{at_um:[65125,140000],height_um:5000,rotation_deg:90});
  assert.deepEqual(final.project,finalExpected);assertModel(final);
  assert.match(await annotation.getAttribute('transform'),/^rotate\(90 /);
  if(process.env.GSCAD_R59_ROTATION_KEYS==='1'){
    // Real WebView2 keyboard events; no direct model mutation or mocked IPC.
    await annotation.click();
    await page.getByTestId('sheet-text-selection').waitFor({state:'visible'});
    assert.equal(await annotation.getAttribute('data-text-selected'),'true');
    await canvas.press('Shift+Delete');
    await canvas.press('Shift+Backspace');
    await canvas.press('Shift+F2');
    await dialog.waitFor({state:'hidden'});
    assert.deepEqual((await save()).project,final.project);
    await canvas.press('r');
    await page.waitForFunction(()=>/^rotate\\(180 /.test(document.querySelector('text[data-testid^="sheet-text-"]')?.getAttribute('transform')??''));
    const rotated=await save(),rotatedExpected=structuredClone(final.project);
    rotatedExpected.sheets[0].texts[0].rotation_deg=180;
    assert.deepEqual(rotated.project,rotatedExpected);
    await canvas.press('Shift+r');
    assert.deepEqual((await save()).project,final.project);
    await undo();assert.deepEqual((await save()).project,rotated.project);
    await redo();assert.deepEqual((await save()).project,final.project);
    assert.match(await annotation.getAttribute('transform'),/^rotate\\(90 /);
    console.log('R59_REAL_NATIVE_ANNOTATION_ROTATION_KEYS_PASS');
  }
  if(process.env.GSCAD_R56_PAPER_ANNOTATIONS==='1'){
    // Temporarily move the existing rotated annotation so only its lower
    // envelope crosses A4. Preserve and restore the original R51 project.
    await annotation.dblclick();await dialog.waitFor({state:'visible'});
    await dialog.getByTestId('sheet-text-x').fill('150');
    await dialog.getByTestId('sheet-text-y').fill('180');
    await dialog.getByTestId('add-sheet-text').click();await dialog.waitFor({state:'hidden'});
    const placed=await save(),placedExpected=structuredClone(final.project);
    placedExpected.sheets[0].texts[0].at_um=[150000,180000];
    assert.deepEqual(placed.project,placedExpected);
    const warning=page.getByTestId('gscad-paper-warning');
    await warning.waitFor({state:'hidden'});
    await page.getByRole('button',{name:'Файл',exact:true}).click();
    await page.getByTestId('paper-format-A4').click();
    await warning.waitFor({state:'visible'});
    assert.match(await warning.textContent(),/1 надписей/);
    const a4=await save(),a4Expected=structuredClone(placed.project);
    a4Expected.sheets[0].frame={...a4Expected.sheets[0].frame,paper:'A4 landscape',size_um:[297000,210000]};
    assert.deepEqual(a4.project,a4Expected);
    await undo();await warning.waitFor({state:'hidden'});
    assert.deepEqual((await save()).project,placed.project);
    await redo();await warning.waitFor({state:'visible'});
    assert.match(await warning.textContent(),/1 надписей/);
    assert.deepEqual((await save()).project,a4.project);
    await undo();await warning.waitFor({state:'hidden'});
    await undo();await warning.waitFor({state:'hidden'});
    const restored=await save();assert.deepEqual(restored.project,final.project);assertModel(restored);
    console.log('R56_REAL_NATIVE_PAPER_ANNOTATION_WARNING_AND_HISTORY_PASS');
  }
  const sum=digest(projectPath);assert.match(sum,/^[0-9a-f]{64}$/);
  fs.writeFileSync(projectPath+'.r9digest',sum+'\n',{flag:'wx'});
  console.log('R51_REAL_NATIVE_TEXT_PROPERTIES_DRAG_KEYS_HISTORY_PASS digest='+sum);
}
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
    if(editorQA){await createEditorAcceptance();}else{
    // Real installed WebView and actual native IPC; no mocked updater or download.
    const expectedVersion=JSON.parse(fs.readFileSync('ui/desktop/src-tauri/tauri.conf.json','utf8')).version;
    const updater=await page.evaluate(async()=>{
      const invoke=window.__TAURI__.core.invoke;
      const reject=async(command,args)=>{
        try{await invoke(command,args);return null;}catch(error){return String(error);}
      };
      return {version:await invoke('native_app_version'),
        enabled:await invoke('native_signed_update_enabled'),
        status:await invoke('native_signed_update_status'),
        badLink:await reject('native_open_project_link',{link:'https://example.invalid'}),
        prepare:await reject('native_prepare_signed_update',{version:'9999.0.0'}),
        install:await reject('native_install_signed_update',{token:'unverified',projectSafe:true})};
    });
    assert.equal(updater.version,expectedVersion,'R41_NATIVE_PACKAGE_VERSION_MISMATCH');
    assert.equal(updater.enabled,false,'R41_UNSIGNED_PREVIEW_MUST_NOT_ENABLE_UPDATER');
    assert.deepEqual(updater.status,{kind:'idle'});
    assert.match(updater.badLink??'',/INVALID_PROJECT_LINK/);
    assert.match(updater.prepare??'',/SIGNED_UPDATE_NOT_CONFIGURED/);
    assert.match(updater.install??'',/SIGNED_UPDATE_NOT_CONFIGURED/);
    const originalSymbols=await page.locator('[data-testid^="symbol-"]').count();
    const dirtyBefore=await page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true}).count();
    for(let i=0;i<2;i++){
      await page.getByTestId('help-menu').click();
      await page.getByTestId('open-about').click();
      const about=page.getByRole('dialog',{name:'О программе'});
      await about.waitFor({state:'visible'});
      await page.waitForFunction(v=>document.querySelector('[data-testid="about-version"]')?.textContent==='Версия: '+v,expectedVersion);
      await about.getByText('Мирослав Лихачёв',{exact:false}).waitFor({state:'visible'});
      await about.getByRole('button',{name:'Показать MIT License'}).click();
      await about.getByText(/Permission is hereby granted/).waitFor({state:'visible'});
      await about.getByRole('button',{name:'Скрыть MIT License'}).click();
      assert.equal(await about.getByTestId('download-signed-update').count(),0);
      assert.equal(await about.getByTestId('install-signed-update').count(),0);
      await page.keyboard.press('Escape');
      await about.waitFor({state:'hidden'});
      assert.equal(await page.locator('[data-testid^="symbol-"]').count(),originalSymbols);
      assert.equal(await page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true}).count(),dirtyBefore);
      await page.getByTestId('toggle-theme').click();
    }
    console.log('R41_NATIVE_ABOUT_AND_UNSIGNED_UPDATE_REFUSAL_PASS version='+expectedVersion);
    await page.getByRole('button',{name:'Файл',exact:true}).click();
    await page.getByTestId('new-project').click();
    await page.getByText(/R3 AUTHORING/).first().waitFor({state:'visible'});
    const canvas=page.getByTestId('gscad-signed-svg-canvas');
    const narrow=await page.evaluate(()=>window.innerWidth<960);
    console.log('R9_NATIVE_VIEWPORT_NARROW='+narrow);
    const font=await page.evaluate(async()=>{const f=await document.fonts.load('14px "GSCAD Technical"','Питание R1');return f.some(x=>x.status==='loaded')});
    assert.equal(font,true,'RC1_OPENGOST_FONT_NOT_LOADED_IN_INSTALLED_WEBVIEW');
    console.log('RC1_NATIVE_OPENGOST_FACE_LOADED');
    // Native Tauri starts at 900px. On that width the UGO library and
    // inspector are intentionally collapsed; exercise the real toggle UI.
    const place=async(symbol,xUm,yUm,refdes)=>{
      if(narrow)await page.getByRole('button',{name:'Показать библиотеку УГО'}).click();
      await page.getByTestId('catalog-item-symbol/'+symbol).click();
      if(narrow)await page.getByRole('button',{name:'Показать библиотеку УГО'}).click();
      const box=await canvas.boundingBox();assert(box);
      // The blank A3 sheet is initially fit by CanvasViewport using a
      // 32px border. Fractional viewport clicks may be outside the actual
      // physical page on a height-constrained 900px Windows app.
      const widthUm=420000,heightUm=297000;
      const scale=Math.min(.02,(box.width-64)/widthUm,(box.height-64)/heightUm);
      const left=box.x+(box.width-widthUm*scale)/2;
      const top=box.y+(box.height-heightUm*scale)/2;
      assert(xUm>=20000&&xUm<=widthUm-20000);
      assert(yUm>=20000&&yUm<=heightUm-20000);
      const x=left+xUm*scale,y=top+yUm*scale;
      await page.mouse.move(x,y);
      const ghost=page.getByTestId('gscad-placement-preview');
      await ghost.waitFor({state:'visible',timeout:5000});
      assert.equal(await ghost.getAttribute('data-symbol-id'),'symbol/'+symbol);
      assert.equal(await ghost.getAttribute('data-electrical'),'false');
      assert.equal(await ghost.locator('[data-preview-pin]').count(),2);
      await page.mouse.click(x,y);
      await page.getByTestId('symbol-'+refdes).waitFor({state:'visible',timeout:5000});
      await ghost.waitFor({state:'detached',timeout:5000});
      console.log('RC1_NATIVE_PLACEMENT_PREVIEW_PASS '+refdes);
    };
    await place('resistor.fixed',90000,90000,'R1');
    await place('capacitor.fixed',250000,90000,'C1');
    if(narrow)await page.getByRole('button',{name:'Показать инспектор'}).click();
    await page.getByLabel('Позиционное обозначение').fill('C9');
    await page.getByLabel('Позиционное обозначение').press('Enter');
    await page.getByTestId('symbol-C9').waitFor({state:'visible',timeout:5000});
    await page.getByTestId('inspector-nominal').fill('220н');
    await page.getByTestId('inspector-nominal').press('Enter');
    if(narrow)await page.getByRole('button',{name:'Показать инспектор'}).click();
    await place('resistor.fixed',340000,180000,'R2');
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
    }
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
      await page.getByTestId(full?'symbol-DA1':editorQA?'symbol-R4':'symbol-C9').waitFor({state:'visible',timeout:15000});
    }catch(error){
      console.log('R9_OPEN_DIAG_FILE_EXISTS='+fs.existsSync(projectPath));
      console.log('R9_OPEN_DIAG_DIGEST='+digest(projectPath));
      try {
        console.log('R9_OPEN_DIAG_UI='+(await page.evaluate(()=>document.body.innerText)).slice(-2600));
        console.log('R9_OPEN_DIAG_SYMBOL_COUNT='+await page.locator('[data-testid^="symbol-"]').count());
      }catch(err){console.log('R9_OPEN_DIAG_UI_UNAVAILABLE '+String(err));}
      throw error;
    }
    // The initial frozen preview also contains DA1 and 23 symbols.
    // Wait for the opened document's exact wire identities, not just a
    // symbol that may already exist before the asynchronous native Open.
    const expectedWireIds=original.project.sheets[0].wires.map(w=>w.id).sort();
    try {
      await page.waitForFunction(ids=>{
        const actual=Array.from(document.querySelectorAll('.electric-wires > g[data-wire-id][data-net-id]'),
          el=>el.getAttribute('data-wire-id')).sort();
        return actual.length===ids.length&&actual.every((id,i)=>id===ids[i]);
      },expectedWireIds,{timeout:30000});
    }catch(error){
      console.log('R9_OPEN_WIRE_DIAG='+JSON.stringify(await page.evaluate(()=>({
        ids:Array.from(document.querySelectorAll('.electric-wires > g[data-wire-id]'),el=>el.getAttribute('data-wire-id')),
        ui:document.body.innerText.slice(-2500)
      }))));
      throw error;
    }
    assert.equal(await page.locator('[data-testid^="symbol-"]').count(),full?23:editorQA?4:3);
    assert.equal(await page.locator('.electric-wires > g[data-net-id]').count(),full||editorQA?original.project.sheets[0].wires.length:1);
    if(full){
      assert.equal(await page.locator('.component-labels [data-label-role="reference"]').count(),23);
      assert.equal(await page.locator('.component-labels').getAttribute('data-unplaced-label-count'),'0');
      const reach=execFileSync('python',['-c',
        'import json,sys;from ui.editor.src.model.contract import validate,route_is_complete;d=json.load(open(sys.argv[1],encoding="utf-8"));validate(d);p=d["project"];assert all(route_is_complete(p,n) for n in p["nets"]);print("15/15")',
        projectPath],{encoding:'utf8',timeout:30000}).trim();
      assert.equal(reach,'15/15');
      console.log('R33_FULL_NATIVE_OPEN_23_15_62_LABELS_PASS');
    }else if(editorQA){
      const t=original.project.sheets[0].texts[0];
      const annotation=page.getByTestId('sheet-text-'+t.id);
      await annotation.waitFor({state:'visible'});
      assert.equal(await annotation.textContent(),t.text);
      assert.match(await annotation.getAttribute('transform'),/^rotate\(90 /);
      assert.equal(await page.locator('[data-junction-id]').count(),1);
      console.log('R51_REAL_NATIVE_EDITOR_REOPEN_PASS');
    }else{
    // A 900px desktop reopens with its inspector collapsed by design.
    // Select C9 through the authoritative project-tree item.
    const narrowReopen=await page.evaluate(()=>window.innerWidth<960);
    if(narrowReopen)
      await page.getByRole('button',{name:'Показать инспектор'}).click();
    // C9 is now also a visible non-interactive SVG label. Select the
    // authoritative tree instance, not an ambiguous text match.
    const c9=original.project.components.find(c=>c.refdes==='C9');
    const instance=original.project.sheets[0].instances.find(i=>i.component_id===c9.id);
    await page.getByTestId('tree-item-'+instance.id).click();
    assert.equal(await page.getByTestId('inspector-nominal').inputValue(),'220н');
    // At Tauri's 900px width the responsive inspector is a floating overlay;
    // close it after reading C9 or it intercepts controls behind the aside.
    if(narrowReopen)
      await page.getByRole('button',{name:'Показать инспектор'}).click();
    }
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
            sheet_id:original.workspace.active_sheet_id,format:'svg'}})+'\n';
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
      // Expose the underlying deterministic ExportError from the *same*
      // canonical Python converter; the IPC intentionally returns only a
      // stable public error code and does not leak exception internals.
      const diagnostic=[
        'import json,sys,traceback',
        'from ui.bridge.export.canonical import ExportRequest',
        'from ui.bridge.export.project_v2 import export_v2_svg',
        'from ui.editor.src.model.contract import digest',
        'doc=json.load(open(sys.argv[1],encoding="utf-8"))',
        'req=ExportRequest(page="A3",orientation="landscape",dpi=300,include_frame=False,include_title=False,strict_font=False)',
        'result=export_v2_svg(doc,doc["workspace"]["active_sheet_id"],req,expected_project_sha256=digest(doc))',
        'print("R9_PY_DIRECT_SVG_BYTES="+str(len(result[0])))'
      ].join(String.fromCharCode(10));
      const py=spawnSync('python',['-c',diagnostic,copyPath],{
        encoding:'utf8',timeout:20000,maxBuffer:2*1024*1024,windowsHide:true});
      console.log('R9_PY_SVG_DIAG_EXIT='+py.status+
        ' STDOUT='+String(py.stdout??'').slice(-450)+
        ' STDERR='+String(py.stderr??'').slice(-1700));
      throw error;
    }
    await awaitNativePublish(svgPath,'svg');
    const svg=fs.readFileSync(svgPath,'utf8');
    assert.match(svg,/<svg|<\?xml/);
    assert.match(svg,/420mm/);
    assert(!svg.includes('data-selected='));
    if(full){
      assert.match(svg,/data-component-label-count="23"/);
      assert.match(svg,/data-unplaced-label-count="0"/);
      assert.equal((svg.match(/data-label-role="reference"/g)??[]).length,23);
      assert.equal((svg.match(/data-layer="wires"/g)??[]).length,original.project.sheets[0].wires.length);
      assert.match(svg,/data-source-net-count="15"/);
    }
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
    if(editorQA){
      const py=[
        'import sys,json,re',
        'from xml.etree import ElementTree as ET',
        'from PIL import Image',
        't=json.load(open(sys.argv[1],encoding="utf-8"))["project"]["sheets"][0]["texts"][0]',
        's="{http://www.w3.org/2000/svg}"',
        'root=ET.parse(sys.argv[2]).getroot()',
        'a=next(e for e in root.iter(s+"text") if e.get("data-id")==t["id"])',
        'assert a.text==t["text"] and float(a.get("font-size"))==5',
        'assert float(a.get("x"))*1000==t["at_um"][0] and float(a.get("y"))*1000==t["at_um"][1]',
        'm=re.fullmatch(r"rotate\\(90 ([^ ]+) ([^ ]+)\\)",a.get("transform",""))',
        'assert m and [round(float(v)*1000) for v in m.groups()]==t["at_um"]',
        'with Image.open(sys.argv[3]) as im:',
        '    x,y=[v/1000 for v in t["at_um"]]',
        '    scale=300/25.4',
        '    crop=im.crop(tuple(round(v*scale) for v in (x-7,y-7,x+12,y+38)))',
        '    mask=crop.convert("RGB").convert("L").point(lambda p:255 if p<128 else 0)',
        '    box=mask.getbbox()',
        '    assert box is not None and box[3]-box[1]>2*(box[2]-box[0]),box',
        'print("R51_REAL_NATIVE_ROTATED_SVG_PNG_INK_PASS")'
      ].join('\n');
      console.log(execFileSync('python',['-c',py,copyPath,svgPath,pngPath],{encoding:'utf8',timeout:30000}).trim());
    }
    console.log('R9_REAL_NATIVE_PROJECT_PERSISTENCE_ACCEPTED digest='+beforeDigest);
    if(full)console.log('R33_FULL_NATIVE_PERSISTENCE_EXPORT_PASS digest='+beforeDigest);
  }
}finally{try{await browser?.close();}catch{/* Tauri process stays owned by PowerShell */}}
