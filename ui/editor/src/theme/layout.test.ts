import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { normalizeDockLayout, safeLayoutFromJSON, layoutForStorage } from './layout.ts';

test('corrupted localStorage entries are ignored', () => {
  assert.deepEqual(safeLayoutFromJSON('{broken'), {});
  assert.deepEqual(normalizeDockLayout(null), {});
  assert.deepEqual(normalizeDockLayout(['unexpected']), {});
});
test('persistent dock widths leave useful canvas area at feasible sizes', () => {
  assert.deepEqual(normalizeDockLayout({navbar:900,aside:700,inspectorPercent:95},1440), {navbar:420,aside:460,inspectorPercent:75});
  const sized = normalizeDockLayout({navbar:420,aside:460},960);
  assert.equal(sized.navbar,200);
  assert.equal(sized.aside,340);
  assert.ok(sized.navbar! + sized.aside! <= 960 - 420);
});
test('bad typed values are ignored and splitter percent is clamped', () => {
  assert.deepEqual(normalizeDockLayout({navbar:'300',aside:Infinity,inspectorPercent:0}),{inspectorPercent:25});
});
test('layout-only storage contract does not contain PinRef', () => {
  const s=layoutForStorage({navbar:256,aside:318,inspectorPercent:52});
  assert.deepEqual(safeLayoutFromJSON(s),{navbar:256,aside:318,inspectorPercent:52});
  assert.ok(!s.includes('PinRef'));
});
