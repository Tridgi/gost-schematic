/**
 * CHAT1 / #117 — executable Playwright interaction contract.
 * PENDING app integration; tests intentionally FAIL instead of silently skipping.
 * Test-only read-only __GSCAD_QA__.snapshot() is required in dev builds.
 * See ui/qa/README.md; DO NOT ship the QA bridge in production.
 */
import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { qaFixtures, source } from './acceptance-contract.mjs';

const origin = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173';
const sel = id => `[data-testid="${id}"]`;
const pin = (id,n) => `[data-testid="pin-target"][data-component-id="${id}"][data-physical-pin-number="${n}"]`;
const snapshot = page => page.evaluate(() => window.__GSCAD_QA__.snapshot());

async function openFixture(page, fixture) {
  await page.goto(`${origin}/?qaFixture=${qaFixtures[fixture]}`);
  await expect(page.locator(sel('editor-root'))).toBeVisible();
  await expect.poll(() => page.evaluate(() => typeof window.__GSCAD_QA__?.snapshot), {
    message: 'BLOCKED: read-only QA snapshot adapter missing in actual app'
  }).toBe('function');
}
function invariantSource(a,b) {
  expect(b.project.source_topology_hash).toBe(a.project.source_topology_hash);
  expect(b.project.source_nets).toEqual(a.project.source_nets);
}
function assertOrtho(vertices) {
  expect(vertices.length).toBeGreaterThanOrEqual(3);
  for (let i=1;i<vertices.length;i++) {
    const a=vertices[i-1].at_um,b=vertices[i].at_um;
    for (const n of [...a,...b]) expect(Number.isSafeInteger(n)).toBeTruthy();
    expect((a[0]===b[0]) !== (a[1]===b[1])).toBeTruthy();
  }
}
test('CAD-UX-R2-01 — full shell, not screenshot-only', async ({page}) => {
  await openFixture(page,'basic');
  for (const id of ['project-toolbar','sheet-tabs','catalog','cad-canvas','object-tree',
                    'inspector','status-bar','tool-select','tool-wire']) {
    await expect(page.locator(sel(id))).toBeVisible();
  }
});

test('CAD-UX-R2-02 — place/rotate/undo real resistor pins', async ({page}) => {
  await openFixture(page,'basic');
  const before=await snapshot(page);
  await page.locator(sel('catalog-search')).fill('резистор');
  await page.locator(sel('catalog-item-resistor')).click();
  await page.locator(sel('cad-canvas')).click({position:{x:350,y:250}});
  await expect(page.locator(sel('selected-component'))).toBeVisible();
  await page.keyboard.press('r');
  const after=await snapshot(page);
  const added=after.project.components.filter(c => !before.project.components.some(p=>p.id===c.id));
  expect(added).toHaveLength(1);
  expect(added[0].rotation).toBe(90);
  expect(added[0].physical_pin_numbers).toEqual(['1','2']);
  await page.keyboard.press('Control+z');
  expect((await snapshot(page)).project.components.find(c=>c.id===added[0].id)?.rotation).toBe(0);
  invariantSource(before,after);
});

test('CAD-UX-R2-03 — grid display and snapping independent', async ({page}) => {
  await openFixture(page,'basic');
  await page.locator(sel('toggle-grid-visible')).click();
  let s=await snapshot(page);
  expect(s.workspace.grid_visible).toBe(false);
  expect(s.workspace.snap_enabled).toBe(true);
  await page.locator(sel('toggle-grid-visible')).click();
  await page.locator(sel('toggle-grid-snap')).click();
  s=await snapshot(page);
  expect(s.workspace.grid_visible).toBe(true);
  expect(s.workspace.snap_enabled).toBe(false);
});

test('CAD-UX-R2-04 — 1280/1440/1920 responsive and theme reachable', async ({page}) => {
  await openFixture(page,'basic');
  for (const width of [1280,1440,1920]) {
    await page.setViewportSize({width,height:900});
    await expect(page.locator(sel('cad-canvas'))).toBeVisible();
    await expect(page.locator(sel('project-toolbar'))).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  }
  const theme=(await snapshot(page)).workspace.theme;
  await page.locator(sel('toggle-theme')).click();
  expect((await snapshot(page)).workspace.theme).not.toBe(theme);
});

test('CAD-UX-R2-05 — shortcuts do not steal inspector input focus', async ({page}) => {
  await openFixture(page,'basic');
  await page.locator(sel('inspector-nominal')).fill('47W');
  expect((await snapshot(page)).workspace.active_tool).not.toBe('wire');
  await page.keyboard.press('Escape');
  await page.keyboard.press('Control+k');
  await expect(page.locator(sel('command-palette'))).toBeVisible();
});

test('CAD-UX-R3-01 — click physical pin, click bend, finish pin', async ({page}) => {
  await openFixture(page,'twoNets');
  const a=await snapshot(page);
  await page.locator(sel('tool-wire')).click();
  await page.locator(pin('R1','1')).click();
  await page.locator(sel('cad-canvas')).click({position:{x:310,y:210}});
  await page.locator(pin('C1','1')).click();
  const b=await snapshot(page);
  const fresh=b.project.wires.filter(w=>!a.project.wires.some(x=>x.id===w.id));
  expect(fresh).toHaveLength(1);
  expect(fresh[0].vertices[0].anchor).toEqual({kind:'pin',component_id:'R1',physical_pin_number:'1'});
  expect(fresh[0].vertices.at(-1).anchor).toEqual({kind:'pin',component_id:'C1',physical_pin_number:'1'});
  assertOrtho(fresh[0].vertices);
  invariantSource(a,b);
});

test('CAD-UX-R3-02 — move interior segment, Undo/Redo exact model', async ({page}) => {
  await openFixture(page,'twoNets');
  const before=await snapshot(page);
  const handle=page.locator(sel('wire-segment-handle')).first();
  const b=await handle.boundingBox();
  expect(b).toBeTruthy();
  const x=b.x+b.width/2,y=b.y+b.height/2;
  await page.mouse.move(x,y); await page.mouse.down();
  await page.mouse.move(x+70,y,{steps:8}); await page.mouse.up();
  const edited=await snapshot(page);
  expect(edited.project.wires).not.toEqual(before.project.wires);
  invariantSource(before,edited);
  await page.keyboard.press('Control+z');
  expect((await snapshot(page)).project.wires).toEqual(before.project.wires);
  await page.keyboard.press('Control+y');
  expect((await snapshot(page)).project.wires).toEqual(edited.project.wires);
});

test('CAD-UX-R3-03 — unmarked X never joins same/different Net', async ({page}) => {
  await openFixture(page,'crossing');
  const s=await snapshot(page);
  expect(s.topology.auto_connected_crossings).toBe(0);
  expect(s.topology.junctions_at_unmarked_crossings).toEqual([]);
  expect(s.topology.electrical_graph).toBeTruthy();
});

test('CAD-UX-R3-04 — explicit junction dot, invisible splice', async ({page}) => {
  await openFixture(page,'crossing');
  await page.locator(sel('tool-junction')).click();
  await page.locator(sel('junction-target')).click();
  const s=await snapshot(page);
  expect(s.project.junctions.length).toBeGreaterThan(0);
  expect(s.topology.visible_junction_dot_count).toBe(s.project.junctions.length);
  expect(s.topology.visible_splice_dot_count).toBe(0);
});

test('CAD-UX-R3-05 — wrong-Net atomic rollback', async ({page}) => {
  await openFixture(page,'twoNets');
  const before=await snapshot(page);
  await page.locator(sel('tool-wire')).click();
  await page.locator(pin('R1','1')).click();
  await page.locator(pin('R2','1')).click();
  await expect(page.locator(sel('diagnostic-NET_CONFLICT'))).toBeVisible();
  const after=await snapshot(page);
  expect(after.project).toEqual(before.project);
  expect(after.revision).toBe(before.revision);
  expect(after.history_depth).toBe(before.history_depth);

  // New negative fixture state: an anchored endpoint's X-coordinate edit by
  // exactly +0.001 mm must fail atomically, never silently rebind the PinRef.
  await openFixture(page,'twoNets');
  const pinnedBefore=await snapshot(page);
  await page.locator(sel('anchored-wire-endpoint')).first().click();
  const field=page.locator(sel('inspector-vertex-x'));
  const old=Number(await field.inputValue());
  expect(Number.isFinite(old)).toBeTruthy();
  await field.fill((old+0.001).toFixed(3));
  await field.press('Enter');
  await expect(page.locator(sel('diagnostic-PIN_ANCHOR_MISMATCH'))).toBeVisible();
  const pinnedAfter=await snapshot(page);
  expect(pinnedAfter.project).toEqual(pinnedBefore.project);
  expect(pinnedAfter.revision).toBe(pinnedBefore.revision);
  expect(pinnedAfter.history_depth).toBe(pinnedBefore.history_depth);
});

test('CAD-UX-R3-06 — real save/reopen and SVG/PNG300 downloaded bytes', async ({page}) => {
  await openFixture(page,'twoNets');
  const before=await snapshot(page);
  await page.locator(sel('save-project')).click();
  await expect.poll(async () => (await snapshot(page)).persistence?.last_saved_sha256, {
    message:'BLOCKED: canonical disk save and hash not observable'
  }).toMatch(/^[a-f0-9]{64}$/i);
  const saved=await snapshot(page);
  // Dev/test readback route must reopen the actual saved bytes, not reset the fixture.
  await page.goto(origin+'/?qaOpenLastSaved=1');
  await expect(page.locator(sel('editor-root'))).toBeVisible();
  const reopened=await snapshot(page);
  expect(reopened.project).toEqual(saved.project);
  invariantSource(before,reopened);

  // Require genuine browser downloads and inspect the bytes; metadata-only
  // receipts and editor screenshots are NOT sufficient for R3.
  const [svgDownload] = await Promise.all([
    page.waitForEvent('download'),page.locator(sel('export-svg')).click()
  ]);
  const xml=await readFile(await svgDownload.path(),'utf8');
  expect(xml).toMatch(/<svg\\b/);
  expect(xml).toMatch(/\\bwidth="[0-9.]+mm"/);
  expect(xml).toMatch(/\\bheight="[0-9.]+mm"/);
  expect(xml).toMatch(/\\bviewBox="/);
  expect(xml).toMatch(/<(path|line|polyline|rect)\\b/);
  expect(xml).not.toMatch(/<image\\b/i);
  expect(xml).not.toMatch(/data-layer="(geometry-review|selection|grid)"/);

  const [pngDownload] = await Promise.all([
    page.waitForEvent('download'),page.locator(sel('export-png300')).click()
  ]);
  const png=await readFile(await pngDownload.path());
  expect(png.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))).toBeTruthy();
  expect(png.readUInt32BE(16)).toBeGreaterThan(0);
  expect(png.readUInt32BE(20)).toBeGreaterThan(0);
  const chunk=png.indexOf(Buffer.from('pHYs'));
  expect(chunk).toBeGreaterThan(0);
  // PNG pHYs stores integer pixels per meter. 300dpi ~= 11811 px/m.
  const ppmX=png.readUInt32BE(chunk+4),ppmY=png.readUInt32BE(chunk+8),unit=png[chunk+12];
  expect(unit).toBe(1);
  expect(Math.abs(ppmX*0.0254-300)).toBeLessThan(0.1);
  expect(Math.abs(ppmY*0.0254-300)).toBeLessThan(0.1);
});

test('CAD-UX-R4-01 — genuine frozen TL494 source and incomplete nets', async ({page}) => {
  await openFixture(page,'tl494');
  const s=await snapshot(page);
  expect(s.project.source_sha).toBe(source.sha);
  expect(s.project.components).toHaveLength(source.components);
  expect(s.project.source_nets).toHaveLength(source.nets);
  expect(s.project.source_nets.flatMap(n=>n.members)).toHaveLength(source.pinMemberships);
  expect(s.project.da1_physical_pins).toHaveLength(source.da1PhysicalPins);
  expect(s.project.non_electrical_b_graphics).toHaveLength(source.nonElectricalBContinuations);
  expect(s.project.source_nets.some(n=>n.route_status!=='verified')).toBeTruthy();
});
