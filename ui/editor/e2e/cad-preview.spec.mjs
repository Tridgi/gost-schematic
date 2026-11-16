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
  await expect(page.getByTestId('gscad-real-v2-canvas')).toBeVisible();
  await expect(page.locator('[data-testid^="symbol-"]')).toHaveCount(23);
  await expect(page.locator('[data-source-role="source_b_continuation"]')).toHaveCount(2);
  await expect(page.locator('[data-net-id]')).toHaveCount(0);
  await expect(page.getByText(/R2 PREVIEW/)).toBeVisible();
  await expect(page.getByRole('button',{name:'Сохранить',exact:true}).first()).toBeDisabled();
});

test('signed pin-to-pin route, undo/redo and wrong-Net rollback in real browser',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-real-v2-canvas')).toBeVisible();
  const [a,b]=signedPair();
  await page.getByRole('button',{name:'Провод W'}).click();
  const pin=ref=>page.getByTestId('pin-'+ref.component_id+'-'+ref.physical_pin_number);
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
  await expect(page.getByText(/NET_CONFLICT/)).toBeVisible();
});

test('independent grid/snap toggles and light/dark theme',async({page})=>{
  await page.goto('/');
  await expect(page.getByTestId('gscad-real-v2-canvas')).toBeVisible();
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
