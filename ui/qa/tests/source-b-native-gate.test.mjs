import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { projectToCanvasScene } from '../../editor/src/canvas/scene-projection.mjs';

const sourceFixture = new URL('../../fixtures/tl494-source-e695-v2.gscad.json', import.meta.url);

/**
 * RED regression gate for #120 + #122. Must PASS before integrated R2/R4.
 * Do not alter the E695 source fixture or silently convert b to electrical wire.
 */
test('CAD-UX-R4-02 — native canvas must import authentic E695 non-electrical b', () => {
  const original=readFileSync(sourceFixture,'utf8');
  const file=JSON.parse(original);
  assert.equal(file.project.provenance.source_sha,
    'e695c415fdced164b0e0c39c5249d030795a0aa6');
  const sheetId=file.project.sheets[0].id;
  const scene=projectToCanvasScene(file,sheetId); // FAILS at current #120 blob: UNKNOWN_GRAPHIC_KIND
  assert.equal(scene.symbols.length,23);
  assert.equal(scene.graphics.filter(g=>g.source_role==='source_b_continuation').length,2);
  assert.equal(scene.wires.length,0);
  assert.equal(readFileSync(sourceFixture,'utf8'),original,'immutable E695 fixture must not change');
  assert.equal(JSON.stringify(file),JSON.stringify(JSON.parse(original)));
  for(const b of scene.graphics.filter(g=>g.source_role==='source_b_continuation')) {
    assert.equal(b.electrical,false);
    assert.equal(b.strokes.length,1);
  }
});
