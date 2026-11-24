import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { ManualWireEngine, constructWire } from '../src/wires/dist/manual-wire.js';

const source = JSON.parse(readFileSync(
  new URL('../public/fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
const wiring = JSON.parse(readFileSync(
  new URL('../public/fixtures/tl494-source-e695-v2.wiring.json',import.meta.url),'utf8'));

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
 await page.mouse.up();
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
 await expect(page.getByRole('alert').filter({hasText:'REROUTE_CANCELLED'})).toBeVisible();
 const d2=page.waitForEvent('download');
 await page.getByTestId('save-project').click();
 const cancelled=JSON.parse(readFileSync(await (await d2).path(),'utf8'));
 expect(cancelled.project.sheets[0].instances).toEqual(connected.project.sheets[0].instances);
 expect(cancelled.project.sheets[0].wires).toEqual(connected.project.sheets[0].wires);
 page.once('dialog',async dialog=>{expect(dialog.type()).toBe('confirm');await dialog.accept();});
 await drag(35,22);
 await expect(page.getByRole('alert').filter({hasText:'REROUTE_REVIEW_REQUIRED'})).toBeVisible();
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
 await expect(page.getByRole('alert').filter({hasText:'REROUTE_REVIEW_REQUIRED'})).toBeVisible();
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
