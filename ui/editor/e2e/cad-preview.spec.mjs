import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
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
  await expect(page.getByText(/Проверенный ProjectV2 повторно открыт/)).toBeVisible();
  const altered=structuredClone(saved);
  altered.project.nets[0].members[0].physical_pin_number='UNDECLARED';
  await page.getByTestId('project-file-input').setInputFiles({
    name:'corrupt.gscad.json',mimeType:'application/json',
    buffer:Buffer.from(JSON.stringify(altered),'utf8')
  });
  await expect(page.getByText(/OPEN_FAILED:.*SOURCE_TOPOLOGY_MISMATCH/)).toBeVisible();
  await expect(page.locator('[data-net-id]')).toHaveCount(1);
});
