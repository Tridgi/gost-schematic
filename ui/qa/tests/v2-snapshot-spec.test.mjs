import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { tests, source, validateManifest } from '../acceptance-contract.mjs';

test('CAD-UX contract describes all 12 R2-R4 scenarios with exact source identity', () => {
  assert.deepEqual(validateManifest(),[]);
  assert.equal(tests.length,12);
  assert.equal(source.sha,'e695c415fdced164b0e0c39c5249d030795a0aa6');
});
test('Playwright snapshot uses #122 canonical ProjectV2 fields, not R0/obsolete aliases', () => {
  const body=readFileSync(new URL('../visual-cad.ux.spec.mjs',import.meta.url),'utf8');
  for(const forbidden of [
    '.project.source_nets','.project.wires','.project.junctions',
    '.project.da1_physical_pins','.project.non_electrical_b_graphics',
    '.project.source_sha',
  ]) assert(!body.includes(forbidden), `obsolete field in E2E spec: ${forbidden}`);
  for(const field of [
    '.project.nets','.project.provenance',
    '.project.part_definitions','.project.sheets',
    '.project.settings.grid_visible','.project.settings.snap_enabled',
  ]) assert(body.includes(field), `missing canonical field: ${field}`);
  assert.match(body,/diagnostic-PIN_ANCHOR_MISMATCH/);
  assert.match(body,/diagnostic-NET_CONFLICT/);
  assert.match(body,/pHYs/);
});
