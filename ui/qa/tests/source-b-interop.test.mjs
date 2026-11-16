import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { projectToCanvasScene } from '../../editor/src/canvas/scene-projection.mjs';
import { projectForUXReview } from '../source-b-compat.mjs';

const fixtureUrl = new URL('../../fixtures/tl494-source-e695-v2.gscad.json', import.meta.url);
const file = () => JSON.parse(readFileSync(fileURLToPath(fixtureUrl), 'utf8'));
const project = () => { const f=file();return [f,f.project.sheets[0].id]; };

test('signed E695 fixture has original 23/15/62/16+2b and no bad routes', () => {
  const f=file(),p=f.project;
  assert.equal(f.format,'gscad-project');
  assert.equal(f.format_version,2);
  assert.equal(p.provenance.source_sha,'e695c415fdced164b0e0c39c5249d030795a0aa6');
  assert.equal(p.components.length,23);
  assert.equal(p.nets.length,15);
  assert.equal(p.nets.reduce((n,net)=>n+net.members.length,0),62);
  const da=p.components.find(c=>c.source_refdes==='DA1');
  assert(da);
  const part=p.part_definitions.find(x=>x.id===da.part_id);
  assert.equal(part.physical_pins.length,16);
  assert.equal(p.sheets.flatMap(s=>s.graphics).filter(g=>g.kind==='source_b_continuation').length,2);
  assert.equal(p.sheets.flatMap(s=>s.wires).length,0);
  assert(p.nets.every(n=>n.route_status==='unrouted'));
});

test('read-only bridge produces 23 authentic symbols + TWO non-electric b strokes', () => {
  const [f,sheet]=project(),original=JSON.stringify(f);
  const view=projectForUXReview(f,sheet);
  assert.equal(JSON.stringify(f),original,'Canonical source must be unmodified');
  assert.equal(view.symbols.length,23);
  assert.equal(view.wires.length,0);
  assert.equal(view.graphics.length,2);
  assert(view.graphics.every(g=>g.kind==='source_b_continuation' &&
    g.source_role==='source_b_continuation' && g.electrical===false &&
    g.strokes.length===1));
  assert.deepEqual(view.graphics[0].strokes[0],
    {from_um:[5000,280000],to_um:[7000,280000]});
});

test('source b graphics reject forged electrical flag and bad geometry', () => {
  const mutations=[
    g=>{g.electrical=true;},
    g=>{g.points_um=[[0,0],[0,0]];},
    g=>{g.points_um=[[0.5,0],[1000,0]];},
    g=>{g.points_um=[[0,0],[1000,0],[2000,0]];},
    g=>{g.stroke_um=0;},
    g=>{g.id='';},
  ];
  for (const mutate of mutations) {
    const [f,sheet]=project();
    const src=f.project.sheets[0].graphics[0];
    mutate(src);
    assert.throws(()=>projectForUXReview(f,sheet),/INVALID_SOURCE_B_GRAPHIC/);
  }
});

test('unknown graphic kind still rejects, and source b IDs cannot alias each other', () => {
  let [f,sheet]=project();
  f.project.sheets[0].graphics[0].kind='forged';
  assert.throws(()=>projectForUXReview(f,sheet),/UNKNOWN_GRAPHIC_KIND/);
  [f,sheet]=project();
  f.project.sheets[0].graphics[1].id=f.project.sheets[0].graphics[0].id;
  assert.throws(()=>projectForUXReview(f,sheet),/INVALID_SOURCE_B_GRAPHIC/);
});

test('known FAIL in native #120 projector is documented; adapter is QA-only', () => {
  const [f,sheet]=project();
  // This is a negative reproduction, NOT a passing acceptance criterion.
  assert.throws(()=>projectToCanvasScene(f,sheet),/UNKNOWN_GRAPHIC_KIND/);
});
