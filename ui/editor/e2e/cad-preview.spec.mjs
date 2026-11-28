import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { ManualWireEngine, constructWire } from '../src/wires/dist/manual-wire.js';

const source = JSON.parse(readFileSync(
  new URL('../public/fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
const wiring = JSON.parse(readFileSync(
  new URL('../public/fixtures/tl494-source-e695-v2.wiring.json',import.meta.url),'utf8'));


/** Immediate hit-test oracle: distinguish a blocked pointer from bad CAD
 * geometry. Do not retry placement or wait for a transient overlay to vanish. */
async function assertCanvasReceivesPointer(page,x,y){
 const hit=await page.evaluate(({x,y})=>{
  const el=document.elementFromPoint(x,y);
  return {canvas:!!el?.closest('[data-testid="gscad-signed-svg-canvas"]'),
    tag:el?.tagName??null,testId:el?.closest('[data-testid]')?.getAttribute('data-testid')??null,
    role:el?.closest('[role]')?.getAttribute('role')??null};
 },{x,y});
 expect(hit.canvas,'Pointer at '+x+','+y+' hits '+JSON.stringify(hit)).toBe(true);
}

function signedPair() {
  // Choose pair using the REAL domain command implementation, not image proximity.
  for (const net of wiring.nets) {
    for (let i=0;i<net.members.length;i++)for (let j=i+1;j<net.members.length;j++) {
      const a=net.members[i],b=net.members[j];
      try {
        const probe=new ManualWireEngine(wiring);
        const points=probe.previewRoute({kind:'pin',...a},{kind:'pin',...b});
        probe.commitWire(probe.newTransaction('e2e-route-test'),
          constructWire('e2e-validated-route',net.id,'layer-electric',
            points,{kind:'pin',...a},{kind:'pin',...b}));
        return [a,b];
      } catch {
        // Real pin normal or route geometry prevents this pair: try another.
      }
    }
  }
  throw Error('NO_MANUALLY_ROUTABLE_SOURCE_PIN_PAIR');
}

test('real frozen TL494 E695 loads 23 physical instances and non-electric b strokes',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(23);
  await expect(page.locator('[data-source-role="source_b_continuation"]')).toHaveCount(2);
  await expect(page.locator('[data-net-id]')).toHaveCount(0);
  await expect(page.getByText(/R2 PREVIEW/)).toBeVisible();
  await expect(page.getByTestId('save-project')).toBeEnabled();
});

test('signed pin-to-pin route, undo/redo and wrong-Net rollback in real browser',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  const [a,b]=signedPair();
  await page.getByRole('button',{name:'Провод W'}).click();
  const pin=ref=>page.getByTestId('signed-pin-'+ref.component_id+'-'+ref.physical_pin_number);
  await expect(pin(a)).toBeVisible();
  await pin(a).click();
  await pin(b).click();
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
  await page.getByRole('button',{name:'Отменить'}).click();
  await expect(page.locator('[data-net-id]')).toHaveCount(0);
  await page.getByRole('button',{name:'Повторить'}).click();
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
  const different=wiring.nets.find(n=>n.id!==wiring.nets.find(x=>x.members.some(m=>
    m.component_id===a.component_id&&m.physical_pin_number===a.physical_pin_number)).id);
  expect(different?.members.length).toBeGreaterThan(0);
  await pin(a).click();
  await pin(different.members[0]).click();
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
  await expect(page.getByRole('alert').filter({hasText:'NET_CONFLICT'})).toContainText('NET_CONFLICT');
});

test('independent grid/snap toggles and light/dark theme',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  const grid=page.getByRole('button',{name:'Показать сетку'});
  const snap=page.getByRole('button',{name:'Привязка к сетке'});
  await expect(grid).toHaveAttribute('aria-pressed','true');
  await expect(snap).toHaveAttribute('aria-pressed','false');
  await grid.click();
  await expect(grid).toHaveAttribute('aria-pressed','false');
  await expect(snap).toHaveAttribute('aria-pressed','false');
  await snap.click();
  await expect(snap).toHaveAttribute('aria-pressed','true');
  await page.getByRole('button',{name:'Настройки',exact:true}).click();
  await page.getByText('Светлая',{exact:true}).click();
  await expect.poll(()=>page.locator('html').getAttribute('data-mantine-color-scheme')).toBe('light');
});

test('browser save and reopen retains frozen Nets and physical PinRefs after verified manual wire',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  const [a,b]=signedPair();
  await page.getByRole('button',{name:'Провод W'}).click();
  const pin=ref=>page.getByTestId('signed-pin-'+ref.component_id+'-'+ref.physical_pin_number);
  await pin(a).click();
  await pin(b).click();
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
  const downloading=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const download=await downloading;
  expect(download.suggestedFilename()).toMatch(/project-v2\.gscad\.json$/);
  const saved=JSON.parse(readFileSync(await download.path(),'utf8'));
  expect(saved.format).toBe('gscad-project');
  expect(saved.format_version).toBe(2);
  expect(saved.project.provenance.source_sha).toBe('e695c415fdced164b0e0c39c5249d030795a0aa6');
  expect(saved.project.components).toHaveLength(23);
  expect(saved.project.nets).toHaveLength(15);
  expect(saved.project.nets.flatMap(n=>n.members)).toHaveLength(62);
  expect(saved.project.sheets[0].wires).toHaveLength(1);
  expect(saved.project.sheets[0].graphics.filter(g=>g.kind==='source_b_continuation')).toHaveLength(2);
  const beforeNets=source.project.nets.map(n=>[n.id,n.name,n.members]);
  expect(saved.project.nets.map(n=>[n.id,n.name,n.members])).toEqual(beforeNets);
  await page.reload();
  await expect(page.locator('[data-net-id]')).toHaveCount(0);
  await page.getByTestId('project-file-input').setInputFiles({
    name:'roundtrip.gscad.json',mimeType:'application/json',
    buffer:Buffer.from(JSON.stringify(saved),'utf8')
  });
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
  await page.getByRole('button',{name:/ERC\/DRC/}).click();
  await expect(page.getByText(/Проверенный ProjectV2 повторно открыт/)).toBeVisible();
  const altered=structuredClone(saved);
  altered.project.nets[0].members[0].physical_pin_number='UNDECLARED';
  await page.getByTestId('project-file-input').setInputFiles({
    name:'corrupt.gscad.json',mimeType:'application/json',
    buffer:Buffer.from(JSON.stringify(altered),'utf8')
  });
  await expect(page.getByRole('alert').filter({hasText:/OPEN_FAILED:.*SOURCE_TOPOLOGY_MISMATCH/})).toBeVisible();
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
});

test('inspector position edits are authoritative and Undo/Redo preserve source Pins and Nets',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  const first=source.project.sheets[0].instances[0];
  const originalMm=first.origin_um[0]/1000;
  const x=page.getByTestId('inspector-axis-x');
  await expect.poll(async()=>Number((await x.inputValue()).replace(',','.'))).toBe(originalMm);
  const newMm=(first.origin_um[0]+5000)/1000;
  await x.fill(String(newMm));
  await x.press('Tab');
  await expect.poll(async()=>Number((await x.inputValue()).replace(',','.'))).toBe(newMm);
  const downloading=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const saved=JSON.parse(readFileSync(await (await downloading).path(),'utf8'));
  expect(saved.project.sheets[0].instances[0].origin_um[0]).toBe(first.origin_um[0]+5000);
  expect(saved.project.nets.map(n=>n.members)).toEqual(source.project.nets.map(n=>n.members));
  await page.getByRole('button',{name:'Отменить'}).click();
  await expect.poll(async()=>Number((await x.inputValue()).replace(',','.'))).toBe(originalMm);
  await page.getByRole('button',{name:'Повторить'}).click();
  await expect.poll(async()=>Number((await x.inputValue()).replace(',','.'))).toBe(newMm);
});

test('canonical browser export emits physical A3 SVG and raster 300 DPI with pHYs metadata',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  const [a,b]=signedPair();
  await page.getByRole('button',{name:'Провод W'}).click();
  const pin=ref=>page.getByTestId('signed-pin-'+ref.component_id+'-'+ref.physical_pin_number);
  await pin(a).click();await pin(b).click();
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
  await page.getByRole('button',{name:'Экспорт',exact:true}).click();
  const downloadingSVG=page.waitForEvent('download');
  await page.getByRole('button',{name:'Экспортировать'}).click();
  const svgDownload=await downloadingSVG;
  expect(svgDownload.suggestedFilename()).toMatch(/preview\.svg$/);
  const svg=readFileSync(await svgDownload.path(),'utf8');
  expect(svg).toMatch(/width="420mm" height="297mm"/);
  expect(svg).toMatch(/data-font-status="unverified-preview"/);
  expect(svg).toMatch(/data-source-net-count="15"/);
  expect(svg).toMatch(/data-authored-wire-count="1"/);
  expect(svg).toMatch(/data-layer="wires"/);
  expect(svg).toMatch(/data-electrical="declared-not-geometry-inferred"/);
  expect((svg.match(/data-kind="source_b_continuation"/g)||[])).toHaveLength(2);
  await page.getByRole('button',{name:'Экспорт',exact:true}).click();
  await page.getByText('PNG 300 DPI',{exact:true}).click();
  const downloadingPNG=page.waitForEvent('download');
  await page.getByRole('button',{name:'Экспортировать'}).click();
  const pngDownload=await downloadingPNG;
  expect(pngDownload.suggestedFilename()).toMatch(/300dpi\.png$/);
  const png=readFileSync(await pngDownload.path());
  expect([...png.subarray(0,8)]).toEqual([137,80,78,71,13,10,26,10]);
  expect(png.readUInt32BE(16)).toBe(Math.round(420/25.4*300));
  expect(png.readUInt32BE(20)).toBe(Math.round(297/25.4*300));
  const phys=png.indexOf(Buffer.from('pHYs'));
  expect(phys).toBeGreaterThan(0);
  expect(png.readUInt32BE(phys+4)).toBe(11811);
  expect(png.readUInt32BE(phys+8)).toBe(11811);
  expect(png[phys+12]).toBe(1);
});

test('explicit 50%, 100% and 200% browser zoom scales physical pin spacing without changing source Nets',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 const zoomButton=page.getByRole('button',{name:'Масштаб'});
 const pair=page.locator('.physical-pin-markers circle');
 await expect(pair.first()).toBeVisible();
 const distance=async()=>{
   const a=pair.nth(0),b=pair.nth(1);
   const [ax,ay,bx,by]=await Promise.all([
    a.getAttribute('cx'),a.getAttribute('cy'),b.getAttribute('cx'),b.getAttribute('cy')]);
   return Math.hypot(Number(ax)-Number(bx),Number(ay)-Number(by));
 };
 const choose=async percent=>{
   await zoomButton.click();
   await page.getByRole('menuitem',{name:percent+'%'}).click();
   await expect(zoomButton).toHaveText(percent+'%');
 };
 await choose(50);
 const fifty=await distance();
 expect(fifty).toBeGreaterThan(0);
 await choose(100);
 await expect.poll(async()=>await distance()/fifty,{timeout:10000}).toBeCloseTo(2,1);
 await choose(200);
 await expect.poll(async()=>await distance()/fifty,{timeout:10000}).toBeCloseTo(4,1);
 await expect(page.locator('[data-net-id]')).toHaveCount(0);
});

test('rejected foreign-Net click preserves live source draft, then correct target commits exactly one wire',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 const [a,b]=signedPair();
 const sourceNet=wiring.nets.find(n=>n.members.some(p=>p.component_id===a.component_id&&p.physical_pin_number===a.physical_pin_number));
 const foreign=wiring.nets.find(n=>n.id!==sourceNet.id&&n.members.length>0).members[0];
 const pin=p=>page.getByTestId('signed-pin-'+p.component_id+'-'+p.physical_pin_number);
 await page.getByRole('button',{name:'Провод W'}).click();
 await pin(a).click();
 await pin(foreign).click();
 await expect(page.getByRole('alert').filter({hasText:'NET_CONFLICT'})).toBeVisible();
 await expect(page.locator('[data-net-id]')).toHaveCount(0);
 // Do NOT select source a again; controller must still have its original signed PinRef.
 await pin(b).click();
 await expect(page.locator('[data-net-id]')).toHaveCount(1);
 const downloading=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const saved=JSON.parse(readFileSync(await (await downloading).path(),'utf8'));
 expect(saved.project.sheets[0].wires).toHaveLength(1);
 expect(saved.project.sheets[0].wires[0].net_id).toBe(sourceNet.id);
 expect(saved.project.nets.map(n=>n.members)).toEqual(source.project.nets.map(n=>n.members));
});

test('physical mouse drag selects and moves C1, R key rotates, Undo/Redo preserve PinRefs',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 const symbol=page.getByTestId('symbol-C1');
 const line=symbol.locator('line').first();
 // Horizontal SVG strokes have a zero-height DOM bounding box; their midpoint
 // remains a valid real mouse target, but Playwright toBeVisible() rejects it.
 await expect(line).toHaveCount(1);
 const midpoint=await line.evaluate(el=>{
   const svg=el.ownerSVGElement;
   const p=svg.createSVGPoint();
   p.x=(Number(el.getAttribute('x1'))+Number(el.getAttribute('x2')))/2;
   p.y=(Number(el.getAttribute('y1'))+Number(el.getAttribute('y2')))/2;
   const result=p.matrixTransform(svg.getScreenCTM());
   return {x:result.x,y:result.y};
 });
 await page.mouse.move(midpoint.x,midpoint.y);
 await page.mouse.down();
 await page.mouse.move(midpoint.x+35,midpoint.y+24,{steps:8});
 await page.mouse.up();
 await expect(symbol).toHaveAttribute('data-selected','true');
 const original=source.project.sheets[0].instances.find(i=>
   source.project.components.find(c=>c.id===i.component_id)?.refdes==='C1');
 const downloading=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const moved=JSON.parse(readFileSync(await (await downloading).path(),'utf8'));
 const after=moved.project.sheets[0].instances.find(i=>i.id===original.id);
 expect(after.origin_um).not.toEqual(original.origin_um);
 expect(after.rotation_deg).toBe(original.rotation_deg);
 expect(moved.project.nets.map(n=>n.members)).toEqual(source.project.nets.map(n=>n.members));
 await page.getByTestId('gscad-signed-svg-canvas').focus();
 await page.keyboard.press('r');
 const downloading2=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const rotated=JSON.parse(readFileSync(await (await downloading2).path(),'utf8'));
 expect(rotated.project.sheets[0].instances.find(i=>i.id===original.id).rotation_deg).toBe(90);
 await page.getByRole('button',{name:'Отменить'}).click();
 await page.getByRole('button',{name:'Отменить'}).click();
 const downloading3=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const restored=JSON.parse(readFileSync(await (await downloading3).path(),'utf8'));
 expect(restored.project.sheets[0].instances.find(i=>i.id===original.id).origin_um).toEqual(original.origin_um);
 expect(restored.project.sheets[0].instances.find(i=>i.id===original.id).rotation_deg).toBe(original.rotation_deg);
 await page.getByRole('button',{name:'Повторить'}).click();
 await page.getByRole('button',{name:'Повторить'}).click();
 const downloading4=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const redone=JSON.parse(readFileSync(await (await downloading4).path(),'utf8'));
 expect(redone.project.sheets[0].instances.find(i=>i.id===original.id)).toEqual(
   rotated.project.sheets[0].instances.find(i=>i.id===original.id));
});

test('real pointer move of stable interior segment uses CAS and Undo/Redo with unchanged Nets',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 const [a,b]=signedPair(),pin=p=>page.getByTestId('signed-pin-'+p.component_id+'-'+p.physical_pin_number);
 await page.getByRole('button',{name:'Провод W'}).click();
 await pin(a).click();await pin(b).click();
 await expect(page.locator('[data-net-id]')).toHaveCount(1);
 const firstDownload=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const before=JSON.parse(readFileSync(await (await firstDownload).path(),'utf8'));
 const wire=before.project.sheets[0].wires[0];
 const state=structuredClone(wiring);
 state.wires=[wire];state.revision=0;
 const geometry=await page.locator('.electric-wires line').evaluateAll(lines=>{
   const svg=lines[0]?.ownerSVGElement;
   const ctm=svg?.getScreenCTM();
   if(!ctm)return [];
   const projected=(x,y)=>({x:ctm.a*x+ctm.c*y+ctm.e,y:ctm.b*x+ctm.d*y+ctm.f});
   const pins=[...svg.querySelectorAll('.physical-pin-markers circle')].map(p=>
     projected(Number(p.getAttribute('cx')),Number(p.getAttribute('cy'))));
   return lines.map((l,index)=>{
     const a=projected(Number(l.getAttribute('x1')),Number(l.getAttribute('y1')));
     const b=projected(Number(l.getAttribute('x2')),Number(l.getAttribute('y2')));
     const x=(a.x+b.x)/2,y=(a.y+b.y)/2;
     return {index,id:l.getAttribute('data-segment-id'),x,y,
       length:Math.hypot(a.x-b.x,a.y-b.y),
       vertical:Math.abs(a.x-b.x)<Math.abs(a.y-b.y),
       closestPin:Math.min(...pins.map(p=>Math.hypot(p.x-x,p.y-y)))};
   });
 });
 const viable=[];
 for(const g of geometry.filter(g=>g.index>0&&g.index<wire.segments.length-1
   &&g.length>14&&g.closestPin>9)){
   const v=wire.vertices[g.index].at_um,w=wire.vertices[g.index+1].at_um;
   const physicalDistance=Math.abs(v[0]-w[0])+Math.abs(v[1]-w[1]);
   for(const offset of [3000,-3000,2000,-2000,5000,-5000]){
     try{
       const engine=new ManualWireEngine(state);
       engine.moveSegmentById(engine.newTransaction('e2e-probe'),wire.id,g.id,offset);
       viable.push({...g,offset,pixelOffset:g.length/physicalDistance*offset});
       break;
     }catch{}
   }
 }
 expect(viable.length,'Must expose a draggable interior segment with real visible hit clearance').toBeGreaterThan(0);
 const chosen=viable[0];
 await page.getByRole('button',{name:'Выбор V'}).click();
 await page.mouse.move(chosen.x,chosen.y);
 await page.mouse.down();
 await page.mouse.move(chosen.x+(chosen.vertical?chosen.pixelOffset:0),
   chosen.y+(chosen.vertical?0:chosen.pixelOffset),{steps:8});
 await page.mouse.up();
 const secondDownload=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const after=JSON.parse(readFileSync(await (await secondDownload).path(),'utf8'));
 const moved=after.project.sheets[0].wires[0];
 expect(moved.segments.map(s=>s.id)).toEqual(wire.segments.map(s=>s.id));
 const coord=chosen.vertical?0:1;
 expect(Math.abs(moved.vertices[chosen.index].at_um[coord]-
   wire.vertices[chosen.index].at_um[coord]-chosen.offset)).toBeLessThanOrEqual(2);
 expect(Math.abs(moved.vertices[chosen.index+1].at_um[coord]-
   wire.vertices[chosen.index+1].at_um[coord]-chosen.offset)).toBeLessThanOrEqual(2);
 expect(after.project.nets.map(n=>n.members)).toEqual(before.project.nets.map(n=>n.members));
 await page.getByRole('button',{name:'Отменить'}).click();
 const thirdDownload=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const undone=JSON.parse(readFileSync(await (await thirdDownload).path(),'utf8'));
 expect(undone.project.sheets[0].wires).toEqual(before.project.sheets[0].wires);
 await page.getByRole('button',{name:'Повторить'}).click();
 const fourthDownload=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const redone=JSON.parse(readFileSync(await (await fourthDownload).path(),'utf8'));
 expect(redone.project.sheets[0].wires).toEqual([moved]);
});

async function openTwoWireCrossing(page,{foreignNet=false}={}){
 const doc=structuredClone(source);
 const [netA,netB]=wiring.nets;
 const free=(name,side)=>({kind:'free',free_id:name+':'+side});
 doc.project.sheets[0].wires=[
  constructWire('QA-H',netA.id,'layer-electric',[[40000,40000],[105000,40000]],
    free('QA-H','a'),free('QA-H','b')),
  constructWire('QA-V',foreignNet?netB.id:netA.id,'layer-electric',[[62000,18000],[62000,65000]],
    free('QA-V','a'),free('QA-V','b'))
 ];
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 await page.getByTestId('project-file-input').setInputFiles({
   name:'manual-crossing.gscad.json',mimeType:'application/json',
   buffer:Buffer.from(JSON.stringify(doc),'utf8')
 });
 await expect(page.locator('[data-wire-id]')).toHaveCount(2);
 await expect(page.locator('[data-junction-id]')).toHaveCount(0);
 const crossing=await page.locator('[data-wire-id="QA-H"] line').evaluate(horizontal=>{
   const svg=horizontal.ownerSVGElement;
   const vertical=svg.querySelector('[data-wire-id="QA-V"] line');
   const pt=svg.createSVGPoint();
   pt.x=Number(vertical.getAttribute('x1'));
   pt.y=Number(horizontal.getAttribute('y1'));
   const xy=pt.matrixTransform(svg.getScreenCTM());
   return {x:xy.x,y:xy.y};
 });
 return {crossing,doc};
}

test('manual explicit X junction tool creates visible dot at exact signed intersection with Undo/Redo',async({page})=>{
 const {crossing,doc}=await openTwoWireCrossing(page);
 await page.getByTestId('tool-junction').click();
 await page.mouse.click(crossing.x,crossing.y);
 await expect(page.locator('[data-junction-id]')).toHaveCount(1);
 await expect(page.locator('[data-wire-id]')).toHaveCount(4);
 await page.getByRole('button',{name:'Отменить'}).click();
 await expect(page.locator('[data-junction-id]')).toHaveCount(0);
 await expect(page.locator('[data-wire-id]')).toHaveCount(2);
 await page.getByRole('button',{name:'Повторить'}).click();
 await expect(page.locator('[data-junction-id]')).toHaveCount(1);
 const downloading=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const saved=JSON.parse(readFileSync(await (await downloading).path(),'utf8'));
 expect(saved.project.sheets[0].junctions).toHaveLength(1);
 expect(saved.project.sheets[0].junctions[0].at_um).toEqual([62000,40000]);
 expect(saved.project.sheets[0].wires).toHaveLength(4);
 expect(saved.project.nets.map(n=>n.members)).toEqual(doc.project.nets.map(n=>n.members));
 expect(saved.project.sheets[0].graphics.filter(g=>g.kind==='source_b_continuation')).toHaveLength(2);
});
test('explicit junction tool refuses coincident crossing of two different source Nets atomically',async({page})=>{
 const {crossing}=await openTwoWireCrossing(page,{foreignNet:true});
 await page.getByTestId('tool-junction').click();
 await page.mouse.click(crossing.x,crossing.y);
 // Inspect the authoritative diagnostic, not an assumed thrown browser event.
 await page.getByRole('button',{name:/ERC/}).click();
 const diagnostic=await page.locator('.gscad-diagnostics').innerText();
 expect(diagnostic,'Actual rejection must identify a foreign signed Net').toContain('NET_CONFLICT');
 await expect(page.getByRole('alert').filter({hasText:'NET_CONFLICT'})).toBeVisible();
 await expect(page.locator('[data-junction-id]')).toHaveCount(0);
 await expect(page.locator('[data-wire-id]')).toHaveCount(2);
});

test('R3 new A3 project: place real DRAFT R/C, edit, wire new Net, Undo/Redo, save and reopen',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  await page.getByRole('button',{name:'Файл'}).click();
  await page.getByTestId('new-project').click();
  await expect(page.getByText(/R3 AUTHORING/)).toBeVisible();
  await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(0);
  const canvas=page.getByTestId('gscad-signed-svg-canvas');
  const bounds=await canvas.boundingBox();
  expect(bounds).toBeTruthy();
  const clickAt=async(x,y)=>page.mouse.click(bounds.x+bounds.width*x,bounds.y+bounds.height*y);
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await clickAt(.30,.44);
  await expect(page.getByTestId('symbol-R1')).toBeVisible();
  await page.getByTestId('catalog-item-symbol/capacitor.fixed').click();
  await clickAt(.67,.44);
  await expect(page.getByTestId('symbol-C1')).toBeVisible();
  await expect(page.locator('[data-testid^="signed-pin-"]')).toHaveCount(4);
  await page.getByLabel('Позиционное обозначение').fill('C9');
  await page.getByLabel('Позиционное обозначение').press('Enter');
  await expect(page.getByTestId('symbol-C9')).toBeVisible();
  await page.getByTestId('inspector-nominal').fill('220н');
  await page.getByTestId('inspector-nominal').press('Enter');
  const initialDownload=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const initial=JSON.parse(readFileSync(await (await initialDownload).path(),'utf8'));
  expect(initial.project.provenance.status).toBe('synthetic');
  expect(initial.project.provenance.source_sha).toBe('0000000000000000000000000000000000000000');
  expect(initial.project.components.map(c=>c.refdes).sort()).toEqual(['C9','R1']);
  expect(initial.project.components.find(c=>c.refdes==='C9').value).toBe('220н');
  expect(initial.project.nets).toHaveLength(0);
  expect(initial.project.sheets[0].frame.size_um).toEqual([420000,297000]);
  const r=initial.project.components.find(c=>c.refdes==='R1');
  const c=initial.project.components.find(c=>c.refdes==='C9');
  await page.getByRole('button',{name:'Провод W'}).click();
  await page.getByTestId('signed-pin-'+r.id+'-2').click();
  await page.getByTestId('signed-pin-'+c.id+'-1').click();
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
  const routeDownload=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const routed=JSON.parse(readFileSync(await (await routeDownload).path(),'utf8'));
  expect(routed.project.nets).toHaveLength(1);
  expect(routed.project.nets[0].members).toEqual([
    {component_id:r.id,physical_pin_number:'2'},
    {component_id:c.id,physical_pin_number:'1'}
  ]);
  expect(routed.project.sheets[0].wires).toHaveLength(1);
  expect(routed.project.sheets[0].junctions).toHaveLength(0);
  await page.getByRole('button',{name:'Отменить'}).click();
  await expect(page.locator('[data-net-id]')).toHaveCount(0);
  await page.getByRole('button',{name:'Повторить'}).click();
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
  await page.reload();
  await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(23);
  await page.getByTestId('project-file-input').setInputFiles({
    name:'authored.gscad.json',mimeType:'application/json',
    buffer:Buffer.from(JSON.stringify(routed),'utf8')
  });
  await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(2);
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
  const reopenedDownload=page.waitForEvent('download');
  await page.getByTestId('save-project').click();
  const reopened=JSON.parse(readFileSync(await (await reopenedDownload).path(),'utf8'));
  expect(reopened.project.components).toEqual(routed.project.components);
  expect(reopened.project.nets.map(n=>[n.id,n.name,n.members])).toEqual(
    routed.project.nets.map(n=>[n.id,n.name,n.members]));
  expect(reopened.project.sheets[0].wires).toEqual(routed.project.sheets[0].wires);
  expect(reopened.project.sheets[0].instances).toEqual(routed.project.sheets[0].instances);
  const py=spawnSync('python',['-c',
    'import sys,json; sys.path.insert(0,"src/model"); from contract import validate; validate(json.load(sys.stdin)); print("PYTHON_V2_ACCEPTED")'
  ],{input:JSON.stringify(reopened),encoding:'utf8',timeout:20000});
  expect(py.status,py.stderr).toBe(0);
  expect(py.stdout).toContain('PYTHON_V2_ACCEPTED');
  await page.getByRole('button',{name:'Экспорт',exact:true}).click();
  const downloadingSVG=page.waitForEvent('download');
  await page.getByRole('button',{name:'Экспортировать'}).click();
  const svg=readFileSync(await (await downloadingSVG).path(),'utf8');
  expect(svg).toContain('width="420mm" height="297mm"');
  expect(svg).toContain('data-source-net-count="1"');
  expect(svg).toContain('data-font-status="unverified-preview"');
  await page.getByRole('button',{name:'Экспорт',exact:true}).click();
  await page.getByText('PNG 300 DPI',{exact:true}).click();
  const downloadingPNG=page.waitForEvent('download');
  await page.getByRole('button',{name:'Экспортировать'}).click();
  const png=readFileSync(await (await downloadingPNG).path());
  expect([...png.subarray(0,8)]).toEqual([137,80,78,71,13,10,26,10]);
  expect(png.readUInt32BE(16)).toBe(Math.round(420/25.4*300));
  expect(png.readUInt32BE(20)).toBe(Math.round(297/25.4*300));
  const phys=png.indexOf(Buffer.from('pHYs'));
  expect(phys).toBeGreaterThan(0);
  expect(png.readUInt32BE(phys+4)).toBe(11811);
  expect(png.readUInt32BE(phys+8)).toBe(11811);
});

test('R3 pointer drag, 90-degree rotation, Delete, Undo/Redo and second A3 sheet',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 const bounds=await canvas.boundingBox();
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await page.mouse.click(bounds.x+bounds.width*.5,bounds.y+bounds.height*.48);
 await expect(page.getByTestId('symbol-R1')).toBeVisible();
 const downloading=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const original=JSON.parse(readFileSync(await (await downloading).path(),'utf8'));
 const instance=original.project.sheets[0].instances[0];
 await page.getByRole('button',{name:'Масштаб'}).click();
 await page.getByText('200%',{exact:true}).click();
 const line=page.getByTestId('symbol-R1').locator('line').first();
 await expect(line).toHaveCount(1);
 const center=await line.evaluate(el=>{
   const svg=el.ownerSVGElement,pt=svg.createSVGPoint();
   pt.x=(Number(el.getAttribute('x1'))+Number(el.getAttribute('x2')))/2;
   pt.y=(Number(el.getAttribute('y1'))+Number(el.getAttribute('y2')))/2;
   const xy=pt.matrixTransform(svg.getScreenCTM());
   return {x:xy.x,y:xy.y};
 });
 await page.mouse.move(center.x,center.y);
 await page.mouse.down();
 await page.mouse.move(center.x+36,center.y+24,{steps:8});
 const ghost=page.getByTestId('gscad-symbol-drag-preview');
 await expect(ghost).toBeVisible();
 await expect(ghost).toHaveAttribute('data-electrical','false');
 await expect(ghost.locator('[data-net-id]')).toHaveCount(0);
 await page.mouse.up();
 await expect(ghost).toHaveCount(0);
 const d1=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const moved=JSON.parse(readFileSync(await (await d1).path(),'utf8'));
 const movedInstance=moved.project.sheets[0].instances.find(i=>i.id===instance.id);
 expect(movedInstance.origin_um).not.toEqual(instance.origin_um);
 // Modified/held/IME key events must not become CAD mutations.
 await canvas.focus();
 for(const event of [
   {key:'r',ctrlKey:true},{key:'r',metaKey:true},{key:'r',altKey:true},
   {key:'r',repeat:true},{key:'Delete',repeat:true},{key:'Delete',isComposing:true}
 ])await canvas.dispatchEvent('keydown',{...event,bubbles:true,cancelable:true});
 await expect(page.getByTestId('symbol-R1')).toHaveCount(1);
 const blockedDownload=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const blocked=JSON.parse(readFileSync(await (await blockedDownload).path(),'utf8'));
 expect(blocked.project).toEqual(moved.project);
 await canvas.focus();await canvas.press('r');
 const d2=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const rotated=JSON.parse(readFileSync(await (await d2).path(),'utf8'));
 expect(rotated.project.sheets[0].instances.find(i=>i.id===instance.id).rotation_deg).toBe(90);
 await canvas.focus();await canvas.press('Delete');
 await expect(page.getByTestId('symbol-R1')).toHaveCount(0);
 const d3=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const deleted=JSON.parse(readFileSync(await (await d3).path(),'utf8'));
 expect(deleted.project.components).toHaveLength(0);
 expect(deleted.project.nets).toHaveLength(0);
 await page.getByRole('button',{name:'Отменить'}).click();
 await expect(page.getByTestId('symbol-R1')).toBeVisible();
 await page.getByRole('button',{name:'Отменить'}).click();
 await page.getByRole('button',{name:'Отменить'}).click();
 const d4=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const undone=JSON.parse(readFileSync(await (await d4).path(),'utf8'));
 expect(undone.project.sheets[0].instances[0].origin_um).toEqual(instance.origin_um);
 expect(undone.project.sheets[0].instances[0].rotation_deg).toBe(0);
 await page.getByRole('button',{name:'Повторить'}).click();
 await page.getByRole('button',{name:'Повторить'}).click();
 await page.getByRole('button',{name:'Повторить'}).click();
 await expect(page.getByTestId('symbol-R1')).toHaveCount(0);
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-sheet').click();
 await expect(page.getByRole('tab')).toHaveCount(2);
 const d5=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const multi=JSON.parse(readFileSync(await (await d5).path(),'utf8'));
 expect(multi.project.sheets).toHaveLength(2);
 expect(multi.project.sheets[1].frame.size_um).toEqual([420000,297000]);
 expect(multi.workspace.active_sheet_id).toBe(multi.project.sheets[0].id);
 await page.getByRole('tab',{name:multi.project.sheets[1].name}).click();
 await page.getByTestId('catalog-item-symbol/capacitor.fixed').click();
 await page.mouse.click(bounds.x+bounds.width*.47,bounds.y+bounds.height*.45);
 await expect(page.getByTestId('symbol-C1')).toBeVisible();
 const d6=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const saved=JSON.parse(readFileSync(await (await d6).path(),'utf8'));
 expect(saved.project.sheets[0].instances).toHaveLength(0);
 expect(saved.project.sheets[1].instances).toHaveLength(1);
 expect(saved.project.components).toHaveLength(1);
 const py=spawnSync('python',['-c',
   'import sys,json;sys.path.insert(0,"src/model");from contract import validate;validate(json.load(sys.stdin))'
 ],{input:JSON.stringify(saved),encoding:'utf8',timeout:20000});
 expect(py.status,py.stderr).toBe(0);
});

test('R3 malformed project and source spoofing are rejected without replacing the live document',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const bounds=await page.getByTestId('gscad-signed-svg-canvas').boundingBox();
 for(const [symbol,x] of [['resistor.fixed',.33],['capacitor.fixed',.63]]){
   await page.getByTestId('catalog-item-symbol/'+symbol).click();
   await page.mouse.click(bounds.x+bounds.width*x,bounds.y+bounds.height*.47);
 }
 await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(2);
 const downloading=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const saved=JSON.parse(readFileSync(await (await downloading).path(),'utf8'));
 const corrupt=[];
 const edit=(fn,name)=>{
   const next=structuredClone(saved);fn(next);corrupt.push([name,JSON.stringify(next)]);
 };
 edit(d=>{d.project.components[1].id=d.project.components[0].id;},'DUPLICATE_COMPONENT');
 edit(d=>{d.project.components[1].refdes=d.project.components[0].refdes;},'DUPLICATE_REFDES');
 edit(d=>{d.project.provenance.source_sha='e695c415fdced164b0e0c39c5249d030795a0aa6';},'SOURCE_SHA_MISMATCH');
 edit(d=>{d.project.sheets[0].instances[0].origin_um=[1.5,20000];},'COORDINATE_RANGE');
 edit(d=>{d.project.nets.push({id:'bad-net',name:'N1',members:[
     {component_id:d.project.components[0].id,physical_pin_number:'999'}
   ],route_status:'unrouted'});
   d.project.provenance.expected_counts.nets=1;
   d.project.provenance.expected_counts.memberships=1;},'UNKNOWN_PIN');
 edit(d=>{d.project.sheets[0].layers.push(structuredClone(d.project.sheets[0].layers[0]));},'DUPLICATE_LAYER');
 corrupt.push(['DUPLICATE_JSON_KEY',JSON.stringify(saved).replace(
   '"format":"gscad-project"','"format":"gscad-project","format":"gscad-project"')]);
 corrupt.push(['INVALID_JSON','{"format":']);
 for(const [label,contents] of corrupt){
   await page.getByTestId('project-file-input').setInputFiles({
     name:label+'.gscad.json',mimeType:'application/json',buffer:Buffer.from(contents)
   });
   await expect(page.getByRole('alert').filter({hasText:'OPEN_FAILED'})).toBeVisible();
   await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(2);
 }
 const downloading2=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const same=JSON.parse(readFileSync(await (await downloading2).path(),'utf8'));
 expect(same.project.components).toEqual(saved.project.components);
 expect(same.project.nets).toEqual(saved.project.nets);
 expect(same.project.sheets[0].instances).toEqual(saved.project.sheets[0].instances);
});

test('R3 two independently authored Nets refuse a foreign-Net short with zero partial edits',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const bbox=await page.getByTestId('gscad-signed-svg-canvas').boundingBox();
 for(const [symbol,x,y] of [
   ['resistor.fixed',.28,.37],['capacitor.fixed',.67,.37],
   ['resistor.fixed',.28,.67],['capacitor.fixed',.67,.67]
 ]){
   await page.getByTestId('catalog-item-symbol/'+symbol).click();
   await page.mouse.click(bbox.x+bbox.width*x,bbox.y+bbox.height*y);
 }
 await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(4);
 const downloading=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const before=JSON.parse(readFileSync(await (await downloading).path(),'utf8'));
 const components=Object.fromEntries(before.project.components.map(c=>[c.refdes,c.id]));
 const pin=(refdes,num)=>page.getByTestId('signed-pin-'+components[refdes]+'-'+num);
 await page.getByRole('button',{name:'Провод W'}).click();
 await pin('R1','2').click();await pin('C1','1').click();
 await pin('R2','2').click();await pin('C2','1').click();
 await expect(page.locator('[data-net-id]')).toHaveCount(2);
 const downloading2=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const baseline=JSON.parse(readFileSync(await (await downloading2).path(),'utf8'));
 expect(baseline.project.nets).toHaveLength(2);
 expect(baseline.project.sheets[0].junctions).toHaveLength(0);
 await pin('R1','2').click();await pin('C2','1').click();
 await expect(page.getByRole('alert').filter({hasText:'NET_CONFLICT'})).toBeVisible();
 await expect(page.locator('[data-net-id]')).toHaveCount(2);
 await page.getByTestId('gscad-signed-svg-canvas').focus();
 await page.keyboard.press('Escape');
 const downloading3=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const rejected=JSON.parse(readFileSync(await (await downloading3).path(),'utf8'));
 expect(rejected.project.nets).toEqual(baseline.project.nets);
 expect(rejected.project.sheets[0].wires).toEqual(baseline.project.sheets[0].wires);
 expect(rejected.project.sheets[0].junctions).toHaveLength(0);
 await page.getByRole('button',{name:'Отменить'}).click();
 await expect(page.locator('[data-net-id]')).toHaveCount(1);
 await page.getByRole('button',{name:'Повторить'}).click();
 await expect(page.locator('[data-net-id]')).toHaveCount(2);
});

test('R4 Chromium connected R1: reject without consent, consent reroute, Undo/Redo and rotate without false Nets',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 const bb=await canvas.boundingBox();
 for(const [symbol,x] of [['resistor.fixed',.30],['capacitor.fixed',.68]]){
   await page.getByTestId('catalog-item-symbol/'+symbol).click();
   await page.mouse.click(bb.x+bb.width*x,bb.y+bb.height*.48);
 }
 const d0=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const initial=JSON.parse(readFileSync(await (await d0).path(),'utf8'));
 const r=initial.project.components.find(c=>c.refdes==='R1');
 const c=initial.project.components.find(c=>c.refdes==='C1');
 await page.getByRole('button',{name:'Провод W'}).click();
 await page.getByTestId('signed-pin-'+r.id+'-2').click();
 await page.getByTestId('signed-pin-'+c.id+'-1').click();
 await expect(page.locator('[data-net-id]')).toHaveCount(1);
 const d1=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const connected=JSON.parse(readFileSync(await (await d1).path(),'utf8'));
 await page.getByRole('button',{name:'Выбор V'}).click();
 // Select the UGO BODY centre, not its graphical lead: at fit-to-A3 zoom
 // a lead is within the physical-pin hit radius and is intentionally NOT draggable.
 const locate=()=>page.getByTestId('symbol-R1').evaluate(group=>{
   const strokes=[...group.querySelectorAll('line')];
   const xs=strokes.flatMap(el=>[Number(el.getAttribute('x1')),Number(el.getAttribute('x2'))]);
   const ys=strokes.flatMap(el=>[Number(el.getAttribute('y1')),Number(el.getAttribute('y2'))]);
   const pt=group.ownerSVGElement.createSVGPoint();
   pt.x=(Math.min(...xs)+Math.max(...xs))/2;
   pt.y=(Math.min(...ys)+Math.max(...ys))/2;
   const point=pt.matrixTransform(group.ownerSVGElement.getScreenCTM());
   return{x:point.x,y:point.y};
 });
 const drag=async(dx,dy)=>{
   const p=await locate();
   await page.mouse.move(p.x,p.y);await page.mouse.down();
   await page.mouse.move(p.x+dx,p.y+dy,{steps:8});await page.mouse.up();
 };
 page.once('dialog',async dialog=>{expect(dialog.type()).toBe('confirm');await dialog.dismiss();});
 await drag(35,22);
 await expect(page.getByTestId('reroute-cancelled')).toBeVisible();
 const d2=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const cancelled=JSON.parse(readFileSync(await (await d2).path(),'utf8'));
 expect(cancelled.project.sheets[0].instances).toEqual(connected.project.sheets[0].instances);
 expect(cancelled.project.sheets[0].wires).toEqual(connected.project.sheets[0].wires);
 page.once('dialog',async dialog=>{expect(dialog.type()).toBe('confirm');await dialog.accept();});
 await drag(35,22);
 await expect(page.getByTestId('reroute-warning')).toBeVisible();
 const d3=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const moved=JSON.parse(readFileSync(await (await d3).path(),'utf8'));
 expect(moved.project.sheets[0].instances.find(i=>i.component_id===r.id).origin_um)
   .not.toEqual(connected.project.sheets[0].instances.find(i=>i.component_id===r.id).origin_um);
 expect(moved.project.sheets[0].wires[0].needs_routing_review).toBe(true);
 expect(moved.project.nets.map(n=>n.members)).toEqual(connected.project.nets.map(n=>n.members));
 expect(moved.project.sheets[0].wires[0].net_id).toBe(connected.project.sheets[0].wires[0].net_id);
 expect(moved.project.sheets[0].junctions).toHaveLength(0);
 await page.getByRole('button',{name:'Отменить'}).click();
 const d4=page.waitForEvent('download');await page.getByTestId('save-project').click();
 const undone=JSON.parse(readFileSync(await (await d4).path(),'utf8'));
 expect(undone.project.sheets[0].wires).toEqual(connected.project.sheets[0].wires);
 await page.getByRole('button',{name:'Повторить'}).click();
 const d5=page.waitForEvent('download');await page.getByTestId('save-project').click();
 const redone=JSON.parse(readFileSync(await (await d5).path(),'utf8'));
 expect(redone.project.sheets[0].wires).toEqual(moved.project.sheets[0].wires);
 page.once('dialog',async dialog=>{expect(dialog.type()).toBe('confirm');await dialog.accept();});
 await canvas.focus();await canvas.press('r');
 const d6=page.waitForEvent('download');await page.getByTestId('save-project').click();
 const rotated=JSON.parse(readFileSync(await (await d6).path(),'utf8'));
 expect(rotated.project.sheets[0].instances.find(i=>i.component_id===r.id).rotation_deg).toBe(90);
 expect(rotated.project.sheets[0].wires[0].needs_routing_review).toBe(true);
 expect(rotated.project.nets.map(n=>n.members)).toEqual(connected.project.nets.map(n=>n.members));
 expect(rotated.project.sheets[0].junctions).toHaveLength(0);
 const py=spawnSync('python',['-c',
    'import sys,json;sys.path.insert(0,"src/model");from contract import validate;validate(json.load(sys.stdin))'],
    {input:JSON.stringify(rotated),encoding:'utf8',timeout:20000});
 expect(py.status,py.stderr).toBe(0);
});

test('R4 connected R1 with two independent Nets: both physical routes reanchor atomically without a false Junction',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 const bbox=await canvas.boundingBox();
 for(const [symbol,x] of [['resistor.fixed',.50],['capacitor.fixed',.22],['capacitor.fixed',.78]]){
  await page.getByTestId('catalog-item-symbol/'+symbol).click();
  await page.mouse.click(bbox.x+bbox.width*x,bbox.y+bbox.height*.46);
 }
 const first=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const initial=JSON.parse(readFileSync(await (await first).path(),'utf8'));
 const refs=Object.fromEntries(initial.project.components.map(c=>[c.refdes,c.id]));
 const pin=(ref,n)=>page.getByTestId('signed-pin-'+refs[ref]+'-'+n);
 await page.getByRole('button',{name:'Провод W'}).click();
 await pin('R1','1').click();await pin('C1','2').click();
 await pin('R1','2').click();await pin('C2','1').click();
 await expect(page.locator('[data-net-id]')).toHaveCount(2);
 const beforeDownload=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const before=JSON.parse(readFileSync(await (await beforeDownload).path(),'utf8'));
 expect(before.project.nets).toHaveLength(2);
 expect(before.project.sheets[0].wires).toHaveLength(2);
 expect(before.project.sheets[0].junctions).toHaveLength(0);
 expect(before.project.sheets[0].splices).toHaveLength(0);
 const originalPins=before.project.nets.map(n=>[n.id,n.members]);
 const originalIds=before.project.sheets[0].wires.map(w=>w.id);
 await page.getByRole('button',{name:'Выбор V'}).click();
 const center=await page.getByTestId('symbol-R1').evaluate(group=>{
  const lines=[...group.querySelectorAll('line')];
  const xx=lines.flatMap(l=>[Number(l.getAttribute('x1')),Number(l.getAttribute('x2'))]);
  const yy=lines.flatMap(l=>[Number(l.getAttribute('y1')),Number(l.getAttribute('y2'))]);
  const pt=group.ownerSVGElement.createSVGPoint();
  pt.x=(Math.min(...xx)+Math.max(...xx))/2;
  pt.y=(Math.min(...yy)+Math.max(...yy))/2;
  const v=pt.matrixTransform(group.ownerSVGElement.getScreenCTM());
  return {x:v.x,y:v.y};
 });
 page.once('dialog',async dlg=>{expect(dlg.type()).toBe('confirm');await dlg.accept();});
 await page.mouse.move(center.x,center.y);await page.mouse.down();
 await page.mouse.move(center.x,center.y+45,{steps:9});await page.mouse.up();
 await expect(page.getByTestId('reroute-warning')).toBeVisible();
 const afterDownload=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const after=JSON.parse(readFileSync(await (await afterDownload).path(),'utf8'));
 expect(after.project.sheets[0].instances.find(i=>i.component_id===refs.R1).origin_um)
  .not.toEqual(before.project.sheets[0].instances.find(i=>i.component_id===refs.R1).origin_um);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(originalPins);
 expect(after.project.sheets[0].wires.map(w=>w.id)).toEqual(originalIds);
 expect(after.project.sheets[0].wires.every(w=>w.needs_routing_review===true)).toBe(true);
 expect(after.project.sheets[0].junctions).toHaveLength(0);
 expect(after.project.sheets[0].splices).toHaveLength(0);
 await page.getByRole('button',{name:'Отменить'}).click();
 const undoDownload=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const undo=JSON.parse(readFileSync(await (await undoDownload).path(),'utf8'));
 expect(undo.project.sheets[0].wires).toEqual(before.project.sheets[0].wires);
 await page.getByRole('button',{name:'Повторить'}).click();
 const redoDownload=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const redo=JSON.parse(readFileSync(await (await redoDownload).path(),'utf8'));
 expect(redo.project.sheets[0].wires).toEqual(after.project.sheets[0].wires);
 const py=spawnSync('python',['-c',
  'import sys,json;sys.path.insert(0,"src/model");from contract import validate;validate(json.load(sys.stdin))'
 ],{input:JSON.stringify(redo),encoding:'utf8',timeout:20000});
 expect(py.status,py.stderr).toBe(0);
});

test('R11: tree, viewport and inspector selection agree and blank click clears them',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await page.mouse.click(paper.x+paper.width*.35,paper.y+paper.height*.4);
 await expect(page.getByTestId('symbol-R1')).toHaveAttribute('data-selected','true');
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await page.mouse.click(paper.x+paper.width*.65,paper.y+paper.height*.6);
 await expect(page.getByTestId('symbol-R2')).toHaveAttribute('data-selected','true');
 await expect(page.getByTestId('symbol-R1')).toHaveAttribute('data-selected','false');
 await page.locator('[data-testid^="tree-item-"]').filter({hasText:/^R1$/}).click();
 await expect(page.getByTestId('symbol-R1')).toHaveAttribute('data-selected','true');
 await expect(page.getByTestId('symbol-R2')).toHaveAttribute('data-selected','false');
 await expect(page.getByLabel('Позиционное обозначение')).toHaveValue('R1');
 await page.mouse.click(paper.x+paper.width*.5,paper.y+paper.height*.85);
 await expect(page.getByTestId('symbol-R1')).toHaveAttribute('data-selected','false');
 await expect(page.getByTestId('inspector')).toHaveCount(0);
 await canvas.focus();await canvas.press('Delete');
 await expect(page.getByTestId('symbol-R1')).toHaveCount(1);
 await expect(page.getByTestId('symbol-R2')).toHaveCount(1);
});

test('R11: Ctrl+C/V duplicates unconnected UGO with new identity; Undo and Redo work',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await page.mouse.click(paper.x+paper.width*.4,paper.y+paper.height*.45);
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await expect(page.getByTestId('symbol-R1')).toHaveAttribute('data-selected','true');
 await canvas.focus();await canvas.press('Control+c');await canvas.press('Control+v');
 await expect(page.getByTestId('symbol-R2')).toHaveAttribute('data-selected','true');
 await expect(page.getByLabel('Позиционное обозначение')).toHaveValue('R2');
 const download=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const saved=JSON.parse(readFileSync(await (await download).path(),'utf8'));
 expect(saved.project.components.map(c=>c.refdes)).toEqual(['R1','R2']);
 expect(saved.project.nets).toEqual([]);
 expect(saved.project.sheets[0].wires).toEqual([]);
 expect(saved.project.sheets[0].instances[0].origin_um).not.toEqual(saved.project.sheets[0].instances[1].origin_um);
 await page.getByRole('button',{name:'Отменить'}).click();
 await expect(page.getByTestId('symbol-R2')).toHaveCount(0);
 await page.getByRole('button',{name:'Повторить'}).click();
 await expect(page.getByTestId('symbol-R2')).toHaveCount(1);
});

test('R13: rectangle selection and group move are one reversible edit',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 const place=async(x,y)=>{
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
 };
 await place(.35,.4);await place(.6,.55);
 const r1=page.getByTestId('symbol-R1'),r2=page.getByTestId('symbol-R2');
 await expect(r2).toBeVisible();
 const saved=async()=>{
  const download=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await download).path(),'utf8'));
 };
 const before=await saved();
 await page.mouse.move(paper.x+paper.width*.25,paper.y+paper.height*.3);
 await page.mouse.down();
 await page.mouse.move(paper.x+paper.width*.7,paper.y+paper.height*.65,{steps:8});
 await expect(page.getByTestId('gscad-selection-marquee')).toBeVisible();
 await page.mouse.up();
 await expect(r1).toHaveAttribute('data-selected','true');
 await expect(r2).toHaveAttribute('data-selected','true');
 await expect(page.getByTestId('group-selection-summary')).toContainText('2');
 const selected=await saved();expect(selected.project).toEqual(before.project);
 const pin=page.getByTestId('signed-pin-'+before.project.components[0].id+'-1');
 const b=await pin.boundingBox();
 await page.mouse.move(b.x+b.width/2,b.y+b.height/2);
 await page.mouse.down();await page.mouse.move(b.x+b.width/2+25,b.y+b.height/2+18,{steps:6});
 await expect(page.getByTestId('gscad-group-drag-preview')).toBeVisible();
 await page.mouse.up();
 const after=await saved();
 const old=before.project.sheets[0].instances,now=after.project.sheets[0].instances;
 const delta=now[0].origin_um.map((v,i)=>v-old[0].origin_um[i]);
 expect(delta.some(Boolean)).toBe(true);
 expect(now[1].origin_um.map((v,i)=>v-old[1].origin_um[i])).toEqual(delta);
 expect(after.project.nets).toEqual(before.project.nets);
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});

test('R14: connected group move requires consent and preserves electrical identity',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const x of [.25,.5,.75]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*.45);
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),[a,b,c]=placed.project.components;
 const pin=(comp,n)=>page.getByTestId('signed-pin-'+comp.id+'-'+n);
 await page.getByRole('button',{name:'Провод W'}).click();
 await pin(a,2).click();await pin(b,1).click();
 await pin(b,2).click();await pin(c,1).click();
 await expect(page.locator('[data-net-id]')).toHaveCount(2);
 await page.getByRole('button',{name:'Выбор V'}).click();
 const before=await saved();
 await page.mouse.move(paper.x+paper.width*.15,paper.y+paper.height*.32);
 await page.mouse.down();
 await page.mouse.move(paper.x+paper.width*.62,paper.y+paper.height*.58,{steps:6});
 await page.mouse.up();
 await expect(page.getByTestId('group-selection-summary')).toContainText('2');
 const p=await pin(a,1).boundingBox();
 const drag=async(accept)=>{
  const onDialog=dialog=>accept?dialog.accept():dialog.dismiss();
  page.once('dialog',onDialog);
  await page.mouse.move(p.x+p.width/2,p.y+p.height/2);
  await page.mouse.down();await page.mouse.move(p.x+p.width/2+15,p.y+p.height/2+22,{steps:6});
  await page.mouse.up();
 };
 await drag(false);
 await expect(page.getByTestId('reroute-cancelled')).toBeVisible();
 expect((await saved()).project).toEqual(before.project);
 await drag(true);
 await expect(page.getByTestId('reroute-warning')).toBeVisible();
 const after=await saved();
 expect(after.project.nets.map(n=>[n.id,n.name,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.name,n.members]));
 expect(after.project.sheets[0].wires.map(w=>w.id)).toEqual(before.project.sheets[0].wires.map(w=>w.id));
 expect(after.project.sheets[0].wires.every(w=>w.needs_routing_review)).toBe(true);
 expect(after.project.sheets[0].instances[2]).toEqual(before.project.sheets[0].instances[2]);
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
});

test('R15: group Ctrl+C/V preserves only internal electrical identities and is undoable',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const x of [.25,.5,.75]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*.35);
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),[a,b,c]=placed.project.components;
 const pin=(comp,n)=>page.getByTestId('signed-pin-'+comp.id+'-'+n);
 await page.getByRole('button',{name:'Провод W'}).click();
 await pin(a,2).click();await pin(b,1).click();
 await pin(b,2).click();await pin(c,1).click();
 await expect(page.locator('[data-net-id]')).toHaveCount(2);
 await page.getByRole('button',{name:'Выбор V'}).click();
 const before=await saved();
 await page.mouse.move(paper.x+paper.width*.15,paper.y+paper.height*.22);
 await page.mouse.down();await page.mouse.move(paper.x+paper.width*.62,paper.y+paper.height*.48,{steps:6});await page.mouse.up();
 await expect(page.getByTestId('group-selection-summary')).toContainText('2');
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await canvas.focus();await canvas.press('Control+c');await canvas.press('Control+v');
 await expect(page.getByTestId('symbol-R4')).toHaveAttribute('data-selected','true');
 await expect(page.getByTestId('symbol-R5')).toHaveAttribute('data-selected','true');
 const after=await saved();
 expect(after.project.components).toHaveLength(5);
 expect(after.project.nets).toHaveLength(3);
 expect(after.project.nets.slice(0,2)).toEqual(before.project.nets);
 const copied=after.project.nets[2],newIds=after.project.components.slice(3).map(c=>c.id);
 expect(copied.members.map(m=>m.component_id)).toEqual(newIds);
 expect(after.project.sheets[0].wires).toHaveLength(3);
 expect(after.project.sheets[0].wires.slice(0,2)).toEqual(before.project.sheets[0].wires);
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});

test('R16 right-click selects UGO, context commands operate on it, Escape closes menu',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const x of [.3,.65]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*.4);
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const before=await saved(),id=before.project.components[0].id;
 const pin=page.getByTestId('signed-pin-'+id+'-1');
 await pin.click({button:'right'});
 const menu=page.getByTestId('canvas-context-menu');
 await expect(menu).toBeVisible();
 await expect(page.getByTestId('symbol-R1')).toHaveAttribute('data-selected','true');
 await expect(page.getByTestId('symbol-R2')).toHaveAttribute('data-selected','false');
 await page.keyboard.press('Escape');await expect(menu).toHaveCount(0);
 expect((await saved()).project).toEqual(before.project);
 await pin.click({button:'right'});await page.getByTestId('context-rotate').click();
 await expect(menu).toHaveCount(0);
 const rotated=await saved();
 expect(rotated.project.sheets[0].instances[0].rotation_deg).toBe(90);
 expect(rotated.project.sheets[0].instances[1]).toEqual(before.project.sheets[0].instances[1]);
 await pin.click({button:'right'});await page.getByTestId('context-copy').click();
 await page.mouse.click(paper.x+paper.width*.5,paper.y+paper.height*.7,{button:'right'});
 await expect(page.getByTestId('context-delete')).toBeDisabled();
 await page.getByTestId('context-paste').click();
 const pasted=await saved();
 expect(pasted.project.components).toHaveLength(3);
 expect(pasted.project.nets).toEqual([]);
 expect(pasted.project.sheets[0].instances[2].rotation_deg).toBe(90);
});

test('R17: source library search and real semiconductor placement',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const search=page.getByTestId('catalog-search');
 await expect(page.locator('[data-testid^="catalog-item-"]')).toHaveCount(36);
 await search.fill('фотодиод');
 await expect(page.locator('[data-testid^="catalog-item-"]')).toHaveCount(1);
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.getByTestId('catalog-item-symbol/diode.photodiode').click();
 await page.mouse.click(paper.x+paper.width*.3,paper.y+paper.height*.5);
 await expect(page.getByTestId('symbol-VD1')).toBeVisible();
 await search.fill('NPN с корпусом');
 await page.getByTestId('catalog-item-symbol/transistor.bjt_npn.with_case').click();
 await page.mouse.click(paper.x+paper.width*.65,paper.y+paper.height*.5);
 await expect(page.getByTestId('symbol-VT1')).toBeVisible();
 const download=page.waitForEvent('download');await page.getByTestId('save-project').click();
 const doc=JSON.parse(readFileSync(await (await download).path(),'utf8'));
 expect(doc.project.components).toHaveLength(2);
 const [d,t]=doc.project.components;
 await expect(page.getByTestId('signed-pin-'+d.id+'-1')).toBeVisible();
 await expect(page.getByTestId('signed-pin-'+d.id+'-2')).toBeVisible();
 for(const n of [1,2,3])await expect(page.getByTestId('signed-pin-'+t.id+'-'+n)).toBeVisible();
 expect(doc.project.nets).toEqual([]);
});

test('R17b: open legacy project, add catalog entries explicitly, undo and redo',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const legacy=await saved();
 const keep=new Set(['resistor.fixed','capacitor.fixed']);
 legacy.project.part_definitions=legacy.project.part_definitions.filter(p=>keep.has(p.id));
 legacy.project.symbol_definitions=legacy.project.symbol_definitions.filter(p=>keep.has(p.part_id));
 await page.getByTestId('project-file-input').setInputFiles({name:'legacy.gscad',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(legacy))});
 await expect(page.locator('[data-testid^="catalog-item-"]')).toHaveCount(2);
 await expect(page.getByTestId('upgrade-catalog')).toContainText('+34');
 await page.getByTestId('upgrade-catalog').click();
 await expect(page.locator('[data-testid^="catalog-item-"]')).toHaveCount(36);
 await expect(page.getByTestId('upgrade-catalog')).toHaveCount(0);
 const upgraded=await saved();
 expect(upgraded.project.part_definitions.slice(0,2)).toEqual(legacy.project.part_definitions);
 expect(upgraded.project.symbol_definitions.slice(0,2)).toEqual(legacy.project.symbol_definitions);
 expect(upgraded.project.sheets).toEqual(legacy.project.sheets);
 await page.getByRole('button',{name:'Отменить'}).click();
 await expect(page.locator('[data-testid^="catalog-item-"]')).toHaveCount(2);
 expect((await saved()).project).toEqual(legacy.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(upgraded.project);
});

test('R17d real winding symbols render analytic arcs and signed tap contacts',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 await page.getByTestId('catalog-search').fill('двумя отводами');
 await page.getByTestId('catalog-item-symbol/inductor.double_tapped').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.mouse.move(paper.x+paper.width*.4,paper.y+paper.height*.5);
 const ghost=page.getByTestId('gscad-placement-preview');
 await expect(ghost).toBeVisible();
 await expect(ghost.locator('path[data-ugo-curve="semicircle"]').first()).toBeVisible();
 await expect(ghost.locator('[data-preview-pin]')).toHaveCount(4);
 await page.mouse.click(paper.x+paper.width*.4,paper.y+paper.height*.5);
 await expect(ghost).toHaveCount(0);
 const symbol=page.getByTestId('symbol-L1');
 await expect(symbol.locator('path[data-ugo-curve="semicircle"]').first()).toBeVisible();
 const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
 const doc=JSON.parse(readFileSync(await (await d).path(),'utf8'));
 const comp=doc.project.components[0];
 const def=doc.project.symbol_definitions.find(s=>s.part_id===comp.part_id);
 await expect(symbol.locator('path[data-ugo-curve="semicircle"]')).toHaveCount(def.graphics.filter(g=>g.kind==='semicircle').length);
 for(const n of ['1','2','3','4'])await expect(page.getByTestId('signed-pin-'+comp.id+'-'+n)).toBeVisible();
 expect(doc.project.nets).toEqual([]);
 await page.getByTestId('gscad-signed-svg-canvas').focus();
 await page.keyboard.press('r');
 await expect(symbol.locator('path[data-ugo-curve="semicircle"]').first()).toBeVisible();
});

test('R17e Cu note is upright in actual editor and stays separate from electrical contacts',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 await page.getByTestId('catalog-search').fill('медным');
 await page.getByTestId('catalog-item-symbol/inductor.trim_copper').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.mouse.move(paper.x+paper.width*.4,paper.y+paper.height*.5);
 const ghost=page.getByTestId('gscad-placement-preview');
 await expect(ghost).toBeVisible();
 await expect(ghost.locator('[data-symbol-note="core_material"]')).toHaveText('Cu');
 await page.mouse.click(paper.x+paper.width*.4,paper.y+paper.height*.5);
 await expect(ghost).toHaveCount(0);
 const symbol=page.getByTestId('symbol-L1'),note=symbol.locator('[data-symbol-note="core_material"]');
 await expect(note).toHaveText('Cu');await expect(note).toHaveAttribute('data-electrical','false');
 const x=await note.getAttribute('x');
 await page.getByTestId('gscad-signed-svg-canvas').focus();await page.keyboard.press('r');
 await expect(note).toHaveText('Cu');await expect(note).not.toHaveAttribute('x',x);
 expect(await note.getAttribute('transform')).toBeNull();
 const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
 const doc=JSON.parse(readFileSync(await (await d).path(),'utf8'));
 expect(doc.project.symbol_definitions.length).toBe(36);
 expect(doc.project.nets).toEqual([]);
 expect(doc.project.sheets[0].instances[0].rotation_deg).toBe(90);
 const comp=doc.project.components[0];
 await expect(page.getByTestId('signed-pin-'+comp.id+'-1')).toBeVisible();
 await expect(page.getByTestId('signed-pin-'+comp.id+'-2')).toBeVisible();
});

test('R18 live diagnostics counts, filters and select affected UGO do not mutate project',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await page.mouse.click(paper.x+paper.width*.3,paper.y+paper.height*.5);
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await page.mouse.click(paper.x+paper.width*.65,paper.y+paper.height*.5);
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const before=await saved();
 await page.getByRole('button',{name:/ERC\/DRC/}).click();
 await expect(page.getByTestId('diagnostics-panel')).toBeVisible();
 await page.getByTestId('diagnostic-filter-warning').click();
 const warnings=page.locator('[data-diagnostic-code="ERC_UNASSIGNED_PIN"]');
 await expect(warnings).toHaveCount(2);
 await warnings.filter({hasText:'R1:'}).getByRole('button',{name:'Выбрать УГО'}).click();
 await expect(page.getByTestId('symbol-R1')).toHaveAttribute('data-selected','true');
 await page.getByTestId('diagnostic-filter-error').click();
 await expect(page.locator('[data-severity="error"]')).toHaveCount(0);
 expect((await saved()).project).toEqual(before.project);
 await page.getByTestId('diagnostic-filter-warning').click();
 // Deleting the selected disconnected resistor updates the report live.
 await page.getByTestId('gscad-signed-svg-canvas').focus();await page.keyboard.press('Delete');
 await expect(warnings).toHaveCount(1);
 await page.getByRole('button',{name:'Отменить'}).click();
 await expect(warnings).toHaveCount(2);
});

test('R19 smart routing and aligned connected pins reduce a Z route to one segment',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const [x,y] of [[.28,.38],[.68,.55]]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),[a,b]=placed.project.components;
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('smart-routing').click();
 await page.getByTestId('tool-wire').click();
 await page.getByTestId('signed-pin-'+a.id+'-2').click();
 await page.getByTestId('signed-pin-'+b.id+'-1').click();
 await page.getByTestId('tool-select').click();
 const before=await saved();
 expect(before.project.sheets[0].wires[0].vertices).toHaveLength(4);
 await page.mouse.move(paper.x+paper.width*.15,paper.y+paper.height*.26);
 await page.mouse.down();await page.mouse.move(paper.x+paper.width*.82,paper.y+paper.height*.68,{steps:6});await page.mouse.up();
 await expect(page.getByTestId('group-selection-summary')).toContainText('2');
 page.once('dialog',d=>d.accept());
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('align-connected-pair').click();
 const after=await saved(),w=after.project.sheets[0].wires[0];
 expect(w.vertices).toHaveLength(2);expect(w.vertices[0].at_um[1]).toBe(w.vertices[1].at_um[1]);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 expect(w.id).toBe(before.project.sheets[0].wires[0].id);
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});

test('RC1 selected UGO is visible under cursor without magnet, cancel is read-only and click matches preview',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas'),ghost=page.getByTestId('gscad-placement-preview');
 await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 const resistor=page.getByTestId('catalog-item-symbol/resistor.fixed'),cap=page.getByTestId('catalog-item-symbol/capacitor.fixed');
 const x=paper.x+paper.width*.4,y=paper.y+paper.height*.4;
 const saved=async()=>{const d=page.waitForEvent('download');await page.getByTestId('save-project').click();return JSON.parse(readFileSync(await (await d).path(),'utf8'));};
 const initial=await saved();
 await resistor.click();await expect(canvas).toHaveAttribute('data-tool','place');
 await assertCanvasReceivesPointer(page,x,y);
 await page.mouse.move(x,y);
 await expect(ghost).toBeVisible();
 await expect(ghost).toHaveAttribute('data-symbol-id','symbol/resistor.fixed');
 await expect(ghost).toHaveAttribute('data-electrical','false');
 expect(await ghost.locator('line').count()).toBeGreaterThan(0);
 await expect(ghost.locator('[data-preview-pin]')).toHaveCount(2);
 await expect(page.getByTestId('pin-placement-guide')).toHaveCount(0);
 await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(0);
 await page.mouse.move(x+50,y+25);
 await expect(ghost).toBeVisible();
 await resistor.hover();await expect(ghost).toHaveCount(0);
 await page.mouse.move(x,y);await expect(ghost).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(ghost).toHaveCount(0);await expect(canvas).toHaveAttribute('data-tool','select');
 expect((await saved()).project).toEqual(initial.project);
 await cap.click();await expect(canvas).toHaveAttribute('data-tool','place');
 await page.mouse.move(x,y);await expect(ghost).toBeVisible();
 await expect(ghost).toHaveAttribute('data-symbol-id','symbol/capacitor.fixed');
 const previewOrigin=[Number(await ghost.getAttribute('data-origin-x-um')),Number(await ghost.getAttribute('data-origin-y-um'))];
 await page.mouse.click(x,y);
 await expect(page.getByTestId('symbol-C1')).toBeVisible();await expect(ghost).toHaveCount(0);
 const doc=await saved();expect(doc.project.components).toHaveLength(1);
 expect(doc.project.sheets[0].instances[0].origin_um).toEqual(previewOrigin);
 expect(doc.project.nets).toEqual([]);expect(doc.project.sheets[0].wires).toEqual([]);
});

test('R19b magnetic placement preview aligns pins without creating a wire',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('pin-magnet').click();
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await expect(canvas).toHaveAttribute('data-tool','place');
 await assertCanvasReceivesPointer(page,paper.x+paper.width*.3,paper.y+paper.height*.4);
 await page.mouse.click(paper.x+paper.width*.3,paper.y+paper.height*.4);
 await expect(page.getByTestId('symbol-R1')).toBeVisible();
 // Use actual signed contact screen position, not an approximate paper ratio.
 const initialDownload=page.waitForEvent('download');await page.getByTestId('save-project').click();
 const initial=JSON.parse(readFileSync(await (await initialDownload).path(),'utf8'));
 const component=initial.project.components[0];
 const contact=await page.getByTestId('signed-pin-'+component.id+'-2').boundingBox();
 const frame=await page.getByTestId('gscad-paper-outline').boundingBox();
 const scale=frame.width/initial.project.sheets[0].frame.size_um[0];
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await expect(canvas).toHaveAttribute('data-tool','place');
 const x=contact.x+contact.width/2+42000*scale,y=contact.y+contact.height/2+3000*scale;
 await page.mouse.move(x,y,{steps:5});
 await expect(page.getByTestId('pin-placement-guide')).toBeVisible();
 await expect(page.getByTestId('pin-placement-guide')).toHaveAttribute('data-electrical','false');
 const ghost=page.getByTestId('gscad-placement-preview');
 await expect(ghost).toBeVisible();
 const previewOrigin=[Number(await ghost.getAttribute('data-origin-x-um')),Number(await ghost.getAttribute('data-origin-y-um'))];
 await page.mouse.click(x,y);
 await expect(page.getByTestId('symbol-R2')).toBeVisible();
 await expect(page.getByTestId('pin-placement-guide')).toHaveCount(0);
 const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
 const doc=JSON.parse(readFileSync(await (await d).path(),'utf8'));
 const [a,b]=doc.project.sheets[0].instances;
 expect(a.origin_um[1]).toBe(b.origin_um[1]);expect(b.origin_um).toEqual(previewOrigin);expect(doc.project.nets).toEqual([]);
 expect(doc.project.sheets[0].wires).toEqual([]);
});

test('R19c existing staircase becomes a clean two-bend wire and Undo restores original route',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const [x,y] of [[.25,.35],[.7,.55]]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),[a,b]=placed.project.components;
 await page.getByTestId('tool-wire').click();
 await page.getByTestId('signed-pin-'+a.id+'-2').click();await page.getByTestId('signed-pin-'+b.id+'-1').click();
 await page.getByTestId('tool-select').click();
 const stairs=await saved(),w=stairs.project.sheets[0].wires[0],start=w.vertices[0],end=w.vertices.at(-1);
 const [x0,y0]=start.at_um,[x1,y1]=end.at_um;
 const xa=Math.round(x0+(x1-x0)*.25),xb=Math.round(x0+(x1-x0)*.5),xc=Math.round(x0+(x1-x0)*.75);
 const ya=Math.round(y0+(y1-y0)/3),yb=Math.round(y0+2*(y1-y0)/3);
 const bends=[[xa,y0],[xa,ya],[xb,ya],[xb,yb],[xc,yb],[xc,y1]];
 w.vertices=[start,...bends.map((at_um,i)=>({id:'stairs-v'+i,at_um,anchor:{kind:'bend'}})),end];
 w.segments=w.vertices.slice(1).map((v,i)=>({id:'stairs-s'+i,from_vertex_id:w.vertices[i].id,to_vertex_id:v.id}));
 await page.getByTestId('project-file-input').setInputFiles({name:'stairs.gscad',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(stairs))});
 await expect(page.locator('[data-wire-id="'+w.id+'"] [data-segment-id]')).toHaveCount(7);
 page.once('dialog',d=>d.accept());
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('simplify-routes').click();
 await expect(page.locator('[data-wire-id="'+w.id+'"] [data-segment-id]')).toHaveCount(3);
 const after=await saved();
 expect(after.project.sheets[0].instances).toEqual(stairs.project.sheets[0].instances);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(stairs.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(stairs.project);
});

test('R20 selected chain becomes straight without altering Net membership, and Undo restores poses',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const [x,y] of [[.22,.35],[.5,.49],[.78,.4]]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),[a,b,c]=placed.project.components;
 await page.getByTestId('tool-wire').click();
 for(const [x,y] of [[a,b],[b,c]]){
  await page.getByTestId('signed-pin-'+x.id+'-2').click();
  await page.getByTestId('signed-pin-'+y.id+'-1').click();
 }
 await page.getByTestId('tool-select').click();
 const before=await saved();
 expect(before.project.sheets[0].wires.map(w=>w.vertices.length)).toEqual([4,4]);
 await page.mouse.move(paper.x+paper.width*.12,paper.y+paper.height*.24);
 await page.mouse.down();await page.mouse.move(paper.x+paper.width*.88,paper.y+paper.height*.61,{steps:6});await page.mouse.up();
 await expect(page.getByTestId('group-selection-summary')).toContainText('3');
 page.once('dialog',d=>d.accept());
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('align-series').click();
 const after=await saved(),sh=after.project.sheets[0];
 expect(new Set(sh.instances.map(i=>i.origin_um[1])).size).toBe(1);
 expect(sh.wires.map(w=>w.vertices.length)).toEqual([2,2]);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});

test('R20b equal pin gaps in actual editor keep the end poses and preserve Undo',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const [i,x] of [.2,.36,.8].entries()){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await expect(canvas).toHaveAttribute('data-tool','place');
  await assertCanvasReceivesPointer(page,paper.x+paper.width*x,paper.y+paper.height*.4);
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*.4);
  await expect(page.getByTestId('symbol-R'+(i+1))).toBeVisible();
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),[a,b,c]=placed.project.components;
 await page.getByTestId('tool-wire').click();
 for(const [x,y] of [[a,b],[b,c]]){
  await page.getByTestId('signed-pin-'+x.id+'-2').click();
  await page.getByTestId('signed-pin-'+y.id+'-1').click();
 }
 await page.getByTestId('tool-select').click();
 const before=await saved(),sh0=before.project.sheets[0];
 await page.mouse.move(paper.x+paper.width*.12,paper.y+paper.height*.29);
 await page.mouse.down();await page.mouse.move(paper.x+paper.width*.88,paper.y+paper.height*.51,{steps:6});await page.mouse.up();
 await expect(page.getByTestId('group-selection-summary')).toContainText('3');
 page.once('dialog',d=>d.accept());
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('distribute-series').click();
 const after=await saved(),sh=after.project.sheets[0];
 expect(sh.instances[0]).toEqual(sh0.instances[0]);expect(sh.instances[2]).toEqual(sh0.instances[2]);
 expect(sh.instances[1].origin_um).not.toEqual(sh0.instances[1].origin_um);
 const gaps=sh.wires.map(w=>w.vertices.at(-1).at_um[0]-w.vertices[0].at_um[0]);
 expect(Math.abs(gaps[0]-gaps[1])).toBeLessThanOrEqual(1);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
});

test('R21 parallel rails replace routes with explicit junctions without changing component poses or Nets',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const x of [.25,.5,.75]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*.45);
  await page.getByTestId('gscad-signed-svg-canvas').focus();
  await page.keyboard.press('r');
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),comps=placed.project.components;
 expect(placed.project.sheets[0].instances.every(i=>i.rotation_deg===90)).toBeTruthy();
 await page.getByRole('button',{name:'Провод W'}).click();
 for(const n of ['1','2'])for(let i=1;i<comps.length;i++){
  await page.getByTestId('signed-pin-'+comps[i-1].id+'-'+n).click();
  await page.getByTestId('signed-pin-'+comps[i].id+'-'+n).click();
 }
 await page.getByRole('button',{name:'Выбор V'}).click();
 const before=await saved();
 expect(before.project.nets).toHaveLength(2);
 await page.mouse.move(paper.x+paper.width*.15,paper.y+paper.height*.32);
 await page.mouse.down();await page.mouse.move(paper.x+paper.width*.85,paper.y+paper.height*.58,{steps:6});await page.mouse.up();
 await expect(page.getByTestId('group-selection-summary')).toContainText('3');
 page.once('dialog',d=>d.accept());
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('parallel-rails').click();
 const after=await saved(),sh=after.project.sheets[0];
 expect(sh.wires).toHaveLength(10);expect(sh.junctions).toHaveLength(2);expect(sh.splices).toHaveLength(4);
 expect(sh.instances).toEqual(before.project.sheets[0].instances);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});

test('R22 automatic layout previews metrics, cancel is harmless, confirm is one undoable edit',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const [i,[x,y]] of [[.22,.35],[.5,.49],[.78,.4]].entries()){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
  await expect(page.getByTestId('symbol-R'+(i+1))).toBeVisible();
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),[a,b,c]=placed.project.components;
 await page.getByTestId('tool-wire').click();
 for(const [x,y] of [[a,b],[b,c]]){
  await page.getByTestId('signed-pin-'+x.id+'-2').click();
  await page.getByTestId('signed-pin-'+y.id+'-1').click();
 }
 await page.getByTestId('tool-select').click();
 const before=await saved();
 const openPlan=async(accept)=>{
  await page.getByRole('button',{name:'Правка',exact:true}).click();
  await page.getByTestId('optimize-layout').click();
  await expect(page.getByTestId('layout-preview-dialog')).toBeVisible();
  await expect(page.getByTestId('layout-bends')).toHaveText('4 → 0');
  const before=page.getByTestId('layout-before'),after=page.getByTestId('layout-after');
  await expect(before).toBeVisible();await expect(after).toBeVisible();
  await expect.poll(()=>before.evaluate(img=>img.complete&&img.naturalWidth>0)).toBeTruthy();
  await expect.poll(()=>after.evaluate(img=>img.complete&&img.naturalWidth>0)).toBeTruthy();
  const svgA=decodeURIComponent((await before.getAttribute('src')).split(',').slice(1).join(','));
  const svgB=decodeURIComponent((await after.getAttribute('src')).split(',').slice(1).join(','));
  expect(svgA).not.toBe(svgB);
  expect(svgA.match(/viewBox="([^"]+)"/)[1]).toBe(svgB.match(/viewBox="([^"]+)"/)[1]);
  await page.getByTestId(accept?'layout-apply':'layout-cancel').click();
  await expect(page.getByTestId('layout-preview-dialog')).toHaveCount(0);
 };
 await openPlan(false);expect((await saved()).project).toEqual(before.project);
 await openPlan(true);
 const after=await saved();
 expect(after.project.sheets[0].wires.map(w=>w.vertices.length)).toEqual([2,2]);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});

test('R23 source TL494 electrical structure is inspectable without authoring or inference',async({page})=>{
 await page.goto('/');
 await expect(page.getByTestId('symbol-DA1')).toBeVisible();
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('topology-inventory').click();
 const report=page.getByTestId('topology-report');
 await expect(report).toBeVisible();
 await expect(report).toContainText('УГО: 23; объявленных цепей: 15.');
 await expect(report).toContainText('DA1 — 16 выводов, 9 цепей');
 await expect(report).toContainText('OSCILLATOR_CT · C7');
 await expect(report).toContainText('OSCILLATOR_RT · R7');
 await expect(report).toContainText('COMMON — 14 выводов, 11 УГО');
 await expect(report).toContainText('Нет явных типов выводов питания в каталоге.');
 await report.getByRole('button',{name:'Выбрать УГО'}).click();
 await expect(report).toHaveCount(0);
 await expect(page.getByTestId('symbol-DA1')).toHaveAttribute('data-selected','true');
});

test('R24 single-Net rail through topology report preserves signed membership and exact Undo',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await expect(canvas).toHaveAttribute('data-camera-ready','true');
 for(const [i,x] of [.25,.5,.75].entries()){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await expect(canvas).toHaveAttribute('data-tool','place');
  const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*(i===1?.51:.4));
  await expect(page.getByTestId('symbol-R'+(i+1))).toBeVisible();
  await canvas.focus();await canvas.press('r');
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),comps=placed.project.components;
 expect(placed.project.sheets[0].instances.every(i=>i.rotation_deg===90)).toBeTruthy();
 await page.getByTestId('tool-wire').click();
 for(let i=1;i<comps.length;i++){
  await page.getByTestId('signed-pin-'+comps[i-1].id+'-1').click();
  await page.getByTestId('signed-pin-'+comps[i].id+'-1').click();
 }
 await page.getByTestId('tool-select').click();
 const before=await saved(),net=before.project.nets[0];
 expect(net.members).toHaveLength(3);
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('topology-inventory').click();
 await expect(page.getByTestId('topology-report')).toBeVisible();
 page.once('dialog',d=>d.accept());
 await page.getByTestId('net-rail-'+net.id).click();
 const after=await saved(),sh=after.project.sheets[0];
 expect(sh.wires).toHaveLength(5);expect(sh.junctions).toHaveLength(1);expect(sh.splices).toHaveLength(2);
 expect(sh.instances).toEqual(before.project.sheets[0].instances);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});

test('R25 mixed-axis Net rail keeps real signed pin directions and undoable geometry',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await expect(canvas).toHaveAttribute('data-camera-ready','true');
 for(const [i,[x,y]] of [[.19,.24],[.38,.34],[.57,.44]].entries()){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await expect(canvas).toHaveAttribute('data-tool','place');
  const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
  await assertCanvasReceivesPointer(page,paper.x+paper.width*x,paper.y+paper.height*y);
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
  await expect(page.getByTestId('symbol-R'+(i+1))).toBeVisible();
  if(i===1){await canvas.focus();await canvas.press('r')}
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),comps=placed.project.components;
 expect(placed.project.sheets[0].instances.map(i=>i.rotation_deg)).toEqual([0,90,0]);
 await page.getByTestId('tool-wire').click();
 for(let i=1;i<comps.length;i++){
  await page.getByTestId('signed-pin-'+comps[i-1].id+'-1').click();
  await page.getByTestId('signed-pin-'+comps[i].id+'-1').click();
 }
 await page.getByTestId('tool-select').click();
 const before=await saved(),net=before.project.nets[0];
 expect(net.members).toHaveLength(3);
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('topology-inventory').click();
 page.once('dialog',d=>d.accept());
 await page.getByTestId('net-rail-'+net.id).click();
 const after=await saved(),sh=after.project.sheets[0];
 expect(sh.wires.filter(w=>w.vertices.length===3)).toHaveLength(1);
 expect(sh.wires.every(w=>w.vertices.length<=3)).toBeTruthy();
 expect(sh.instances).toEqual(before.project.sheets[0].instances);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});

test('R26 tree reconstruction from topology report bypasses a rail obstruction',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const positions=[[.17,.34],[.31,.39],[.45,.32],[.60,.37],[.31,.27]];
 for(const [i,[x,y]] of positions.entries()){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await expect(canvas).toHaveAttribute('data-tool','place');
  const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
  await assertCanvasReceivesPointer(page,paper.x+paper.width*x,paper.y+paper.height*y);
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
  await expect(page.getByTestId('symbol-R'+(i+1))).toBeVisible();
  if(i<4){await canvas.focus();await canvas.press('r')}
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),comps=placed.project.components.slice(0,4);
 await page.getByTestId('tool-wire').click();
 for(let i=1;i<comps.length;i++){
  await page.getByTestId('signed-pin-'+comps[i-1].id+'-1').click();
  await page.getByTestId('signed-pin-'+comps[i].id+'-1').click();
 }
 await page.getByTestId('tool-select').click();
 const before=await saved(),net=before.project.nets[0];
 expect(net.members).toHaveLength(4);
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('topology-inventory').click();
 page.once('dialog',d=>d.accept());
 await page.getByTestId('net-tree-'+net.id).click();
 const after=await saved(),sh=after.project.sheets[0];
 expect(sh.junctions.length).toBeGreaterThanOrEqual(1);
 expect(sh.wires.length).toBe(4+sh.junctions.length-1);
 expect(sh.splices).toHaveLength(0);
 expect(sh.instances).toEqual(before.project.sheets[0].instances);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});


test('R28 explicit first route for a saved declared two-pin Net, Undo and Redo',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await expect(canvas).toHaveAttribute('data-camera-ready','true');
 for(const [i,x] of [.25,.65].entries()){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await expect(canvas).toHaveAttribute('data-tool','place');
  const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
  const px=paper.x+paper.width*x,py=paper.y+paper.height*.4;
  await assertCanvasReceivesPointer(page,px,py);
  await page.mouse.click(px,py);
  await expect(page.getByTestId('symbol-R'+(i+1))).toBeVisible();
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),[a,b]=placed.project.components;
 await page.getByTestId('tool-wire').click();
 await page.getByTestId('signed-pin-'+a.id+'-2').click();
 await page.getByTestId('signed-pin-'+b.id+'-1').click();
 await page.getByTestId('tool-select').click();
 const doc=await saved(),net=doc.project.nets[0];
 expect(doc.project.sheets[0].wires).toHaveLength(1);
 doc.project.sheets[0].wires=[];net.route_status='unrouted';
 await page.getByTestId('project-file-input').setInputFiles({name:'unrouted.gscad',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(doc))});
 await expect(page.locator('[data-net-id]')).toHaveCount(0);
 const before=await saved();
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('topology-inventory').click();
 page.once('dialog',d=>d.accept());
 await page.getByTestId('net-initial-'+net.id).click();
 const after=await saved(),sh=after.project.sheets[0];
 expect(sh.wires).toHaveLength(1);
 expect(sh.wires[0].needs_routing_review).toBe(true);
 expect(sh.instances).toEqual(before.project.sheets[0].instances);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});


test('R29 batch initial routing commits two declared Nets and one Undo restores both',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Файл'}).click();
 await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');
 await expect(canvas).toHaveAttribute('data-camera-ready','true');
 for(const [i,[x,y]] of [[.25,.3],[.65,.3],[.25,.7],[.65,.7]].entries()){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await expect(canvas).toHaveAttribute('data-tool','place');
  const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
  const px=paper.x+paper.width*x,py=paper.y+paper.height*y;
  await assertCanvasReceivesPointer(page,px,py);
  await page.mouse.click(px,py);
  await expect(page.getByTestId('symbol-R'+(i+1))).toBeVisible();
 }
 const saved=async()=>{
  const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
  return JSON.parse(readFileSync(await (await d).path(),'utf8'));
 };
 const placed=await saved(),comps=placed.project.components;
 await page.getByTestId('tool-wire').click();
 for(const [a,b] of [[comps[0],comps[1]],[comps[2],comps[3]]]){
  await page.getByTestId('signed-pin-'+a.id+'-2').click();
  await page.getByTestId('signed-pin-'+b.id+'-1').click();
 }
 await page.getByTestId('tool-select').click();
 const doc=await saved();
 expect(doc.project.nets).toHaveLength(2);
 expect(doc.project.sheets[0].wires).toHaveLength(2);
 doc.project.sheets[0].wires=[];for(const n of doc.project.nets)n.route_status='unrouted';
 await page.getByTestId('project-file-input').setInputFiles({name:'batch-unrouted.gscad',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(doc))});
 await expect(page.locator('[data-net-id]')).toHaveCount(0);
 const before=await saved();
 await page.getByRole('button',{name:'Правка',exact:true}).click();
 await page.getByTestId('topology-inventory').click();
 page.once('dialog',d=>d.accept());
 await page.getByTestId('route-initial-batch').click();
 const after=await saved();
 expect(after.project.sheets[0].wires).toHaveLength(2);
 expect(after.project.sheets[0].instances).toEqual(before.project.sheets[0].instances);
 expect(after.project.nets.map(n=>[n.id,n.members])).toEqual(before.project.nets.map(n=>[n.id,n.members]));
 await page.getByRole('button',{name:'Отменить'}).click();
 expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();
 expect((await saved()).project).toEqual(after.project);
});


test('RC1 pin to existing conductor creates a real T junction and Undo restores the original Net',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Файл'}).click();await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const [x,y] of [[.23,.3],[.75,.3],[.5,.7]]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
 }
 const saved=async()=>{const d=page.waitForEvent('download');await page.getByTestId('save-project').click();return JSON.parse(readFileSync(await (await d).path(),'utf8'));};
 const doc=await saved(),[a,b,c]=doc.project.components;
 await page.getByTestId('tool-wire').click();
 await page.getByTestId('signed-pin-'+a.id+'-2').click();await page.getByTestId('signed-pin-'+b.id+'-1').click();
 await page.getByTestId('tool-select').click();
 const before=await saved(),w=before.project.sheets[0].wires[0];
 const mid=await page.locator('[data-segment-id="'+w.segments[0].id+'"]').evaluate(el=>{
  const pt=el.ownerSVGElement.createSVGPoint();pt.x=(Number(el.getAttribute('x1'))+Number(el.getAttribute('x2')))/2;pt.y=(Number(el.getAttribute('y1'))+Number(el.getAttribute('y2')))/2;
  const p=pt.matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y};
 });
 await page.getByTestId('tool-wire').click();await page.getByTestId('signed-pin-'+c.id+'-1').click();
 await page.mouse.move(mid.x,mid.y);await expect(page.getByTestId('wire-tap-preview')).toBeVisible();await page.mouse.click(mid.x,mid.y);
 await expect(page.locator('[data-junction-id]')).toHaveCount(1);await expect(page.locator('.electric-wires > g')).toHaveCount(3);
 await page.getByTestId('tool-select').click();
 const after=await saved();expect(after.project.nets).toHaveLength(1);expect(after.project.nets[0].members).toHaveLength(3);
 expect(after.project.sheets[0].junctions).toHaveLength(1);
 await page.getByRole('button',{name:'Отменить'}).click();expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();expect((await saved()).project).toEqual(after.project);
});

test('RC1 text placement and double-click component properties persist through model save',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Файл'}).click();await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const font=await page.evaluate(async()=>{const f=await document.fonts.load('14px "GSCAD Technical"','Питание R1');return f.some(x=>x.status==='loaded')});
 expect(font).toBe(true);
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await page.mouse.click(paper.x+paper.width*.4,paper.y+paper.height*.4);
 const symbol=await page.getByTestId('symbol-R1').boundingBox();
 await page.mouse.dblclick(symbol.x+symbol.width/2,symbol.y+symbol.height/2);
 const dialog=page.getByRole('dialog',{name:'Свойства элемента R1'});
 await expect(dialog).toBeVisible();
 await dialog.getByTestId('inspector-nominal').fill('4,7к');await dialog.getByTestId('inspector-nominal').press('Enter');
 await dialog.getByRole('button',{name:'Закрыть',exact:true}).click();
 // Wait for the modal exit/focus trap to finish before sending a canvas shortcut.
 await expect(dialog).toBeHidden();
 await canvas.focus();await expect(canvas).toBeFocused();
 await canvas.press('t');
 await expect(canvas).toHaveAttribute('data-tool','text');
 await page.mouse.click(paper.x+paper.width*.3,paper.y+paper.height*.6);
 await page.getByTestId('sheet-text-input').fill('Питание 24 В');
 await page.getByTestId('add-sheet-text').click();
 await expect(page.getByTestId('sheet-text-input')).toBeHidden();
 const annotation=canvas.locator('text[data-testid^="sheet-text-"]');
 await expect(annotation).toHaveCount(1);
 await expect(annotation).toHaveText('Питание 24 В');
 const d=page.waitForEvent('download');await page.getByTestId('save-project').click();
 const doc=JSON.parse(readFileSync(await (await d).path(),'utf8'));
 expect(doc.project.components[0].value).toBe('4,7к');expect(doc.project.nets).toEqual([]);
 expect(doc.project.sheets[0].texts[0].text).toBe('Питание 24 В');
 await page.getByRole('button',{name:'Отменить'}).click();
 await expect(annotation).toHaveCount(0);
});

test('RC1 library categories and reserved scrollbar fit long Russian names in both themes at 900px',async({page},testInfo)=>{
 await page.setViewportSize({width:900,height:650});
 await page.goto('/');await page.getByRole('button',{name:'Файл'}).click();await page.getByTestId('new-project').click();
 await page.getByRole('button',{name:'Показать библиотеку УГО'}).click();
 const heading=page.getByRole('button',{name:/Катушки индуктивности/});
 await expect(heading).toBeVisible();await heading.click();
 await expect(page.getByTestId('catalog-item-symbol/inductor.double_tapped')).toHaveCount(0);
 await heading.click();await expect(page.getByTestId('catalog-item-symbol/inductor.double_tapped')).toHaveCount(1);
 await page.getByTestId('catalog-search').fill('магнитодиэлектр');
 await expect(page.getByTestId('catalog-item-symbol/inductor.magnetodielectric')).toBeVisible();
 for(let i=0;i<2;i++){
  const result=await page.locator('.gscad-catalog-scroll .mantine-ScrollArea-viewport').evaluate(el=>({width:el.clientWidth,scroll:el.scrollWidth,
    clipped:[...el.querySelectorAll('.gscad-symbol-info')].some(n=>n.scrollWidth>n.clientWidth+1)}));
  expect(result.scroll).toBeLessThanOrEqual(result.width+1);expect(result.clipped).toBe(false);
  await page.screenshot({path:testInfo.outputPath('library-theme-'+i+'.png')});
  if(i===0)await page.getByTestId('toggle-theme').click();
 }
});


test('R41 About is accessible in both themes and does not change the document',async({page})=>{
  await page.goto('/');
  const canvas=page.getByTestId('gscad-signed-svg-canvas');
  await expect(canvas).toBeVisible();
  const original=await page.locator('[data-testid^="symbol-"]').count();
  const dirty=await page.getByText('Не сохранено',{exact:true}).count();
  for(let i=0;i<2;i++){
    await page.getByTestId('help-menu').click();
    await page.getByTestId('open-about').click();
    const dialog=page.getByRole('dialog',{name:'О программе'});
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('Мирослав Лихачёв',{exact:false})).toBeVisible();
    await expect(dialog.getByTestId('about-version')).toContainText('0.1.0');
    await expect(dialog.getByTestId('check-updates')).toBeDisabled();
    await dialog.getByRole('button',{name:'Показать MIT License'}).click();
    await expect(dialog.getByText(/Permission is hereby granted/)).toBeVisible();
    await dialog.getByRole('button',{name:'Скрыть MIT License'}).click();
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(original);
    await expect(page.getByText('Не сохранено',{exact:true})).toHaveCount(dirty);
    if(i===0)await page.getByTestId('toggle-theme').click();
  }
});


test('R41 native release check uses actual version, displays update and leaves project unchanged',async({page})=>{
  await page.addInitScript(()=>{
    window.__TAURI__={core:{invoke:async(command)=>{
      if(command==='native_app_version')return '0.1.0';
      if(command==='native_close_trace')return;
      throw Error('UNEXPECTED_NATIVE_COMMAND: '+command);
    }},window:{getCurrentWindow:()=>({onCloseRequested:async()=>()=>{}})}};
  });
  let count=0;
  await page.route('https://api.github.com/repos/Tridgi/gost-schematic/releases/latest',async route=>{
    count++;
    await route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify({tag_name:'v0.2.0',draft:false,prerelease:false})});
  });
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  expect(count).toBe(0);
  const dirty=page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true});
  await expect(dirty).toHaveCount(0);
  await page.getByTestId('help-menu').click();
  await page.getByTestId('open-about').click();
  const dialog=page.getByRole('dialog',{name:'О программе'});
  await expect(dialog.getByTestId('about-version')).toHaveText('Версия: 0.1.0');
  await dialog.getByTestId('check-updates').click();
  await expect(dialog.getByTestId('update-result')).toContainText('v0.2.0');
  expect(count).toBe(1);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(page.getByTestId('update-available-badge')).toBeVisible();
  await expect(dirty).toHaveCount(0);
  await page.getByTestId('help-menu').click();
  await page.getByTestId('open-about').click();
  await dialog.getByRole('switch',{name:'Проверять обновления при запуске'}).check();
  await page.reload();
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  await expect(page.getByTestId('update-available-badge')).toBeVisible();
  expect(count).toBeGreaterThanOrEqual(2);
  await expect(dirty).toHaveCount(0);
});


test('R41 signed update does not install while project is dirty or confirmation is declined',async({page})=>{
  await page.addInitScript(()=>{
    window.__gscadMock={stage:{kind:'idle'},installs:[]};
    window.__TAURI__={core:{invoke:async(command,args)=>{
      const mock=window.__gscadMock;
      if(command==='native_app_version')return '0.1.0';
      if(command==='native_close_trace'||command==='native_close_project')return;
      if(command==='native_signed_update_enabled')return true;
      if(command==='native_signed_update_status')return mock.stage;
      if(command==='native_prepare_signed_update'){
        if(args.version!=='0.2.0')throw Error('VERSION_MISMATCH');
        mock.stage={kind:'ready',version:'0.2.0',token:'verified-test-token'};return;
      }
      if(command==='native_install_signed_update'){
        mock.installs.push(args);mock.stage={kind:'idle'};return;
      }
      if(command==='native_save_as_project')return {handle:'saved-test-handle',generation:0,
        project_sha256:'a'.repeat(64),filename:'test.gscad.json',document:args.document};
      throw Error('UNEXPECTED_NATIVE_COMMAND: '+command);
    }},window:{getCurrentWindow:()=>({onCloseRequested:async()=>()=>{}})}};
  });
  await page.route('https://api.github.com/repos/Tridgi/gost-schematic/releases/latest',route=>route.fulfill({
    status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},
    body:JSON.stringify({tag_name:'v0.2.0',draft:false,prerelease:false})
  }));
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  await page.getByRole('button',{name:'Показать сетку'}).click();
  const dirty=page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true});
  await expect(dirty).toBeVisible();
  const openAbout=async()=>{
    await page.getByTestId('help-menu').click();await page.getByTestId('open-about').click();
    await expect(page.getByRole('dialog',{name:'О программе'})).toBeVisible();
  };
  await openAbout();
  const dialog=page.getByRole('dialog',{name:'О программе'});
  await dialog.getByTestId('check-updates').click();
  await dialog.getByTestId('download-signed-update').click();
  await expect(dialog.getByTestId('install-signed-update')).toBeVisible();
  await dialog.getByTestId('install-signed-update').click();
  await expect(dialog.getByTestId('signed-update-error')).toContainText('Сначала сохраните проект');
  expect(await page.evaluate(()=>window.__gscadMock.installs.length)).toBe(0);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await page.getByTestId('save-project').click();
  await expect(dirty).toHaveCount(0);
  await openAbout();
  page.once('dialog',d=>d.dismiss());
  await dialog.getByTestId('install-signed-update').click();
  expect(await page.evaluate(()=>window.__gscadMock.installs.length)).toBe(0);
  page.once('dialog',d=>d.accept());
  await dialog.getByTestId('install-signed-update').click();
  await expect.poll(()=>page.evaluate(()=>window.__gscadMock.installs)).toEqual([
    {token:'verified-test-token',projectSafe:true}
  ]);
});


test('R42 cancel pending signed download, keep project, retry without installing',async({page})=>{
  await page.addInitScript(()=>{
    window.__gscadMock={stage:{kind:'idle'},cancelled:[],installs:0,attempts:0};
    window.__TAURI__={core:{invoke:async(command,args)=>{
      const m=window.__gscadMock;
      if(command==='native_app_version')return '0.1.0';
      if(command==='native_close_trace')return;
      if(command==='native_signed_update_enabled')return true;
      if(command==='native_signed_update_status')return m.stage;
      if(command==='native_prepare_signed_update'){
        m.attempts++;
        if(m.attempts===2){m.stage={kind:'ready',version:'0.2.0',token:'verified-retry'};return;}
        m.stage={kind:'downloading',received:65536,total:null,id:'download-one',cancelling:false};
        return new Promise((_,reject)=>{m.reject=reject;});
      }
      if(command==='native_cancel_signed_download'){
        if(args.id!==m.stage.id)throw Error('STALE_UPDATE_DOWNLOAD');
        m.cancelled.push(args.id);m.stage={kind:'idle'};m.reject('UPDATE_DOWNLOAD_CANCELLED');return;
      }
      if(command==='native_install_signed_update'){m.installs++;throw Error('UNEXPECTED_INSTALL');}
      throw Error('UNEXPECTED_NATIVE_COMMAND: '+command);
    }},window:{getCurrentWindow:()=>({onCloseRequested:async()=>()=>{}})}};
  });
  await page.route('https://api.github.com/repos/Tridgi/gost-schematic/releases/latest',route=>route.fulfill({
    status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},
    body:JSON.stringify({tag_name:'v0.2.0',draft:false,prerelease:false})
  }));
  await page.goto('/');
  await expect(page.getByTestId('gscad-signed-svg-canvas')).toBeVisible();
  const dirty=page.getByTestId('project-toolbar').getByText('Не сохранено',{exact:true});
  await expect(dirty).toHaveCount(0);
  await page.getByTestId('help-menu').click();await page.getByTestId('open-about').click();
  const dialog=page.getByRole('dialog',{name:'О программе'});
  await dialog.getByTestId('check-updates').click();
  await dialog.getByTestId('download-signed-update').click();
  const cancel=dialog.getByTestId('cancel-signed-download');
  await expect(cancel).toBeEnabled();
  await cancel.click();
  await expect(dialog.getByTestId('signed-update-error')).toContainText('Загрузка отменена');
  await expect(dialog.getByTestId('install-signed-update')).toHaveCount(0);
  await expect(dirty).toHaveCount(0);
  await dialog.getByTestId('download-signed-update').click();
  await expect(dialog.getByTestId('install-signed-update')).toBeVisible();
  expect(await page.evaluate(()=>({cancelled:window.__gscadMock.cancelled,attempts:window.__gscadMock.attempts,installs:window.__gscadMock.installs}))).toEqual({cancelled:['download-one'],attempts:2,installs:0});
  await expect(dirty).toHaveCount(0);
});

test('R43 fourth conductor snaps to an existing Junction, retains ID and supports Undo/Redo',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Файл',exact:true}).click();await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const [x,y] of [[.23,.4],[.75,.4],[.5,.75],[.56,.17]]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
 }
 const saved=async()=>{const d=page.waitForEvent('download');await page.getByTestId('save-project').click();return JSON.parse(readFileSync(await (await d).path(),'utf8'));};
 const doc=await saved(),[a,b,c,d]=doc.project.components;
 await page.getByTestId('tool-wire').click();
 await page.getByTestId('signed-pin-'+a.id+'-2').click();await page.getByTestId('signed-pin-'+b.id+'-1').click();
 await page.getByTestId('tool-select').click();
 const trunk=(await saved()).project.sheets[0].wires[0];
 const mid=await page.locator('[data-segment-id="'+trunk.segments[0].id+'"]').evaluate(el=>{
  const pt=el.ownerSVGElement.createSVGPoint();pt.x=(Number(el.getAttribute('x1'))+Number(el.getAttribute('x2')))/2;pt.y=(Number(el.getAttribute('y1'))+Number(el.getAttribute('y2')))/2;
  const p=pt.matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y};
 });
 await page.getByTestId('tool-wire').click();await page.getByTestId('signed-pin-'+c.id+'-1').click();
 await page.mouse.click(mid.x,mid.y);await expect(page.locator('[data-junction-id]')).toHaveCount(1);
 await page.getByTestId('tool-select').click();
 const before=await saved(),node=before.project.sheets[0].junctions[0];
 const at=await page.locator('[data-junction-id="'+node.id+'"]').evaluate(el=>{
  const pt=el.ownerSVGElement.createSVGPoint();pt.x=Number(el.getAttribute('cx'));pt.y=Number(el.getAttribute('cy'));
  const p=pt.matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y};
 });
 await page.getByTestId('tool-wire').click();await page.getByTestId('signed-pin-'+d.id+'-1').click();
 await page.mouse.move(at.x,at.y);await expect(page.getByTestId('wire-tap-preview')).toBeVisible();
 await canvas.focus();await canvas.press('Escape');
 await expect(page.locator('.electric-wires > g')).toHaveCount(3);
 await page.getByTestId('tool-wire').click();await page.getByTestId('signed-pin-'+d.id+'-1').click();
 await page.mouse.move(at.x,at.y);await expect(page.getByTestId('wire-tap-preview')).toBeVisible();
 await page.mouse.click(at.x,at.y);
 await expect(page.locator('.electric-wires > g')).toHaveCount(4);await expect(page.locator('[data-junction-id]')).toHaveCount(1);
 await page.getByTestId('tool-select').click();
 const after=await saved();expect(after.project.nets).toHaveLength(1);expect(after.project.nets[0].members).toHaveLength(4);
 expect(after.project.sheets[0].junctions).toEqual(before.project.sheets[0].junctions);
 for(const wire of before.project.sheets[0].wires)expect(after.project.sheets[0].wires.find(w=>w.id===wire.id)).toEqual(wire);
 await page.getByRole('button',{name:'Отменить'}).click();expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();expect((await saved()).project).toEqual(after.project);
});


test('R44 start at Junction, reject free endpoint, cancel and connect physical pin',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Файл',exact:true}).click();await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 for(const [x,y] of [[.23,.4],[.75,.4],[.5,.75],[.56,.17]]){
  await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
  await page.mouse.click(paper.x+paper.width*x,paper.y+paper.height*y);
 }
 const saved=async()=>{const d=page.waitForEvent('download');await page.getByTestId('save-project').click();return JSON.parse(readFileSync(await (await d).path(),'utf8'));};
 const doc=await saved(),[a,b,c,d]=doc.project.components;
 await page.getByTestId('tool-wire').click();
 await page.getByTestId('signed-pin-'+a.id+'-2').click();await page.getByTestId('signed-pin-'+b.id+'-1').click();
 await page.getByTestId('tool-select').click();
 const trunk=(await saved()).project.sheets[0].wires[0];
 const mid=await page.locator('[data-segment-id="'+trunk.segments[0].id+'"]').evaluate(el=>{
  const pt=el.ownerSVGElement.createSVGPoint();pt.x=(Number(el.getAttribute('x1'))+Number(el.getAttribute('x2')))/2;pt.y=(Number(el.getAttribute('y1'))+Number(el.getAttribute('y2')))/2;
  const p=pt.matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y};
 });
 await page.getByTestId('tool-wire').click();await page.getByTestId('signed-pin-'+c.id+'-1').click();
 await page.mouse.click(mid.x,mid.y);await expect(page.locator('[data-junction-id]')).toHaveCount(1);
 await page.getByTestId('tool-select').click();
 const before=await saved(),node=before.project.sheets[0].junctions[0];
 const at=await page.locator('[data-junction-id="'+node.id+'"]').evaluate(el=>{
  const pt=el.ownerSVGElement.createSVGPoint();pt.x=Number(el.getAttribute('cx'));pt.y=Number(el.getAttribute('cy'));
  const p=pt.matrixTransform(el.getScreenCTM());return {x:p.x,y:p.y};
 });
 await page.getByTestId('tool-wire').click();await page.mouse.click(at.x,at.y);
 await page.mouse.move(paper.x+paper.width*.5,paper.y+paper.height*.2);
 await canvas.focus();await canvas.press('Enter');
 await expect(page.locator('.electric-wires > g')).toHaveCount(3);
 await canvas.press('Escape');
 await expect(page.locator('.electric-wires > g')).toHaveCount(3);
 await page.getByTestId('tool-wire').click();await page.mouse.click(at.x,at.y);
 await page.getByTestId('signed-pin-'+d.id+'-1').click();
 await expect(page.locator('.electric-wires > g')).toHaveCount(4);await expect(page.locator('[data-junction-id]')).toHaveCount(1);
 await page.getByTestId('tool-select').click();
 const after=await saved();expect(after.project.nets).toHaveLength(1);expect(after.project.nets[0].members).toHaveLength(4);
 expect(after.project.sheets[0].junctions).toEqual(before.project.sheets[0].junctions);
 for(const wire of before.project.sheets[0].wires)expect(after.project.sheets[0].wires.find(w=>w.id===wire.id)).toEqual(wire);
 await page.getByRole('button',{name:'Отменить'}).click();expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();expect((await saved()).project).toEqual(after.project);
});


test('R45 edit text via double click, exact coordinates, rotate, delete and Undo/Redo',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Файл',exact:true}).click();await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await canvas.focus();await canvas.press('t');
 await page.mouse.click(paper.x+paper.width*.25,paper.y+paper.height*.5);
 await page.getByTestId('sheet-text-input').fill('Питание 24 В');
 await page.getByTestId('add-sheet-text').click();await expect(page.getByTestId('sheet-text-input')).toBeHidden();
 const annotation=canvas.locator('text[data-testid^="sheet-text-"]');
 await expect(annotation).toHaveCount(1);
 const saved=async()=>{const d=page.waitForEvent('download');await page.getByTestId('save-project').click();return JSON.parse(readFileSync(await (await d).path(),'utf8'));};
 const before=await saved(),t=before.project.sheets[0].texts[0];
 await annotation.dblclick();
 const dialog=page.getByRole('dialog',{name:'Свойства надписи'});
 await expect(dialog).toBeVisible();
 await expect(dialog.getByTestId('sheet-text-input')).toHaveValue('Питание 24 В');
 await dialog.getByTestId('sheet-text-input').fill('Цепь 24 В');
 await dialog.getByTestId('sheet-text-x').fill('65,125');
 await dialog.getByTestId('sheet-text-y').fill('140');
 await dialog.getByText('5',{exact:true}).click();
 await dialog.getByText('90',{exact:true}).click();
 await dialog.getByTestId('add-sheet-text').click();
 await expect(dialog).toBeHidden();await expect(annotation).toHaveText('Цепь 24 В');
 const after=await saved();
 expect(after.project.sheets[0].texts).toEqual([{...t,text:'Цепь 24 В',at_um:[65125,140000],height_um:5000,rotation_deg:90}]);
 expect(after.project.nets).toEqual(before.project.nets);
 await page.getByRole('button',{name:'Отменить'}).click();expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();expect((await saved()).project).toEqual(after.project);
 await annotation.click({button:'right'});await expect(dialog).toBeVisible();
 page.once('dialog',d=>d.dismiss());await dialog.getByTestId('delete-sheet-text').click();await expect(dialog).toBeVisible();
 page.once('dialog',d=>d.accept());await dialog.getByTestId('delete-sheet-text').click();await expect(dialog).toBeHidden();
 await expect(annotation).toHaveCount(0);const deleted=await saved();expect(deleted.project.sheets[0].texts).toEqual([]);
 await page.getByRole('button',{name:'Отменить'}).click();expect((await saved()).project).toEqual(after.project);
 await page.getByRole('button',{name:'Повторить'}).click();expect((await saved()).project).toEqual(deleted.project);
});


test('R46 drag annotation with grid preview, Escape and one Undo/Redo transaction',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Файл',exact:true}).click();await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await canvas.focus();await canvas.press('t');await page.mouse.click(paper.x+paper.width*.25,paper.y+paper.height*.5);
 await page.getByTestId('sheet-text-input').fill('Питание 24 В');
 await page.getByTestId('add-sheet-text').click();await expect(page.getByTestId('sheet-text-input')).toBeHidden();
 const annotation=canvas.locator('text[data-testid^="sheet-text-"]');
 await expect(annotation).toHaveCount(1);
 const saved=async()=>{const d=page.waitForEvent('download');await page.getByTestId('save-project').click();return JSON.parse(readFileSync(await (await d).path(),'utf8'));};
 const before=await saved(),t=before.project.sheets[0].texts[0],grid=before.project.settings.grid_step_um;
 const p=await annotation.boundingBox(),x=p.x+p.width/2,y=p.y+p.height/2;
 const dx=paper.width*.13,dy=-paper.height*.1;
 await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+dx,y+dy,{steps:8});
 await expect(page.getByTestId('sheet-text-drag-preview')).toBeVisible();
 await canvas.press('Escape');await expect(page.getByTestId('sheet-text-drag-preview')).toHaveCount(0);
 await page.mouse.up();expect((await saved()).project).toEqual(before.project);
 await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+dx,y+dy,{steps:8});
 await expect(page.getByTestId('sheet-text-drag-preview')).toBeVisible();
 await page.mouse.up();await expect(page.getByTestId('sheet-text-drag-preview')).toHaveCount(0);
 const after=await saved(),moved=after.project.sheets[0].texts[0];
 expect(moved.id).toBe(t.id);expect(moved.at_um).not.toEqual(t.at_um);
 expect(moved.at_um.map(n=>n%grid)).toEqual([0,0]);
 expect(moved.at_um[0]).toBeGreaterThan(t.at_um[0]);expect(moved.at_um[1]).toBeLessThan(t.at_um[1]);
 const expected=structuredClone(before.project);expected.sheets[0].texts[0].at_um=moved.at_um;
 expect(after.project).toEqual(expected);
 await page.getByRole('button',{name:'Отменить'}).click();expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Повторить'}).click();expect((await saved()).project).toEqual(after.project);
 await annotation.dblclick();await expect(page.getByRole('dialog',{name:'Свойства надписи'})).toBeVisible();
});


test('R47 annotation selection, arrow nudge, Shift, F2, Delete and Undo',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Файл',exact:true}).click();await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await canvas.focus();await canvas.press('t');await page.mouse.click(paper.x+paper.width*.25,paper.y+paper.height*.5);
 await page.getByTestId('sheet-text-input').fill('Питание 24 В');
 await page.getByTestId('add-sheet-text').click();await expect(page.getByTestId('sheet-text-input')).toBeHidden();
 const annotation=canvas.locator('text[data-testid^="sheet-text-"]');
 const saved=async()=>{const d=page.waitForEvent('download');await page.getByTestId('save-project').click();return JSON.parse(readFileSync(await (await d).path(),'utf8'));};
 const before=await saved(),t=before.project.sheets[0].texts[0],grid=before.project.settings.grid_step_um;
 await annotation.click();await expect(annotation).toHaveAttribute('data-text-selected','true');
 await expect(page.getByTestId('sheet-text-selection')).toBeVisible();
 await canvas.press('ArrowRight');await canvas.press('Shift+ArrowUp');
 const moved=await saved(),expected=structuredClone(before.project);
 expected.sheets[0].texts[0].at_um=[t.at_um[0]+grid,t.at_um[1]-10*grid];
 expect(moved.project).toEqual(expected);
 await canvas.press('F2');const dialog=page.getByRole('dialog',{name:'Свойства надписи'});await expect(dialog).toBeVisible();
 await dialog.getByTestId('sheet-text-input').focus();await page.keyboard.press('Delete');await expect(annotation).toHaveCount(1);
 await dialog.getByRole('button',{name:'Отмена',exact:true}).click();await expect(dialog).toBeHidden();
 await annotation.click();await canvas.press('Escape');await expect(page.getByTestId('sheet-text-selection')).toHaveCount(0);
 await canvas.press('Delete');expect((await saved()).project).toEqual(moved.project);
 await annotation.click();await canvas.press('Delete');await expect(annotation).toHaveCount(0);
 await page.getByRole('button',{name:'Отменить'}).click();expect((await saved()).project).toEqual(moved.project);
 await page.getByRole('button',{name:'Повторить'}).click();await expect(annotation).toHaveCount(0);
});


test('R54 R and Shift+R rotate only the selected annotation; modified Delete is isolated',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Файл',exact:true}).click();await page.getByTestId('new-project').click();
 const canvas=page.getByTestId('gscad-signed-svg-canvas');await expect(canvas).toHaveAttribute('data-camera-ready','true');
 const paper=await page.getByTestId('gscad-paper-outline').boundingBox();
 await page.getByTestId('catalog-item-symbol/resistor.fixed').click();
 await page.mouse.click(paper.x+paper.width*.6,paper.y+paper.height*.4);
 await expect(page.getByTestId('symbol-R1')).toBeVisible();
 await canvas.focus();await canvas.press('t');await page.mouse.click(paper.x+paper.width*.25,paper.y+paper.height*.5);
 await page.getByTestId('sheet-text-input').fill('MMMMMM');
 await page.getByTestId('add-sheet-text').click();await expect(page.getByTestId('sheet-text-input')).toBeHidden();
 const annotation=canvas.locator('text[data-testid^="sheet-text-"]');
 const saved=async()=>{const d=page.waitForEvent('download');await page.getByTestId('save-project').click();return JSON.parse(readFileSync(await (await d).path(),'utf8'));};
 const before=await saved();
 await page.getByTestId('symbol-R1').click();
 await annotation.click();await expect(annotation).toHaveAttribute('data-text-selected','true');
 await canvas.press('Shift+Delete');await canvas.press('Shift+Backspace');await canvas.press('Shift+F2');
 await expect(page.getByRole('dialog',{name:'Свойства надписи'})).toBeHidden();
 expect((await saved()).project).toEqual(before.project);
 await canvas.press('r');await expect(annotation).toHaveAttribute('transform',/^rotate\(90 /);
 const rotated=await saved(),expected=structuredClone(before.project);
 expected.sheets[0].texts[0].rotation_deg=90;expect(rotated.project).toEqual(expected);
 await canvas.press('Shift+r');expect((await saved()).project).toEqual(before.project);
 await page.getByRole('button',{name:'Отменить'}).click();expect((await saved()).project).toEqual(rotated.project);
 await page.getByRole('button',{name:'Повторить'}).click();expect((await saved()).project).toEqual(before.project);
});
