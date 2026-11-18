/**
 * CHAT3 cross-review, directly importing PRODUCTION R1 modules.
 * Tests intentionally assert CAD-v2 requirements; regressions must fail CI.
 * No parallel electrical Net graph, no screenshots, no invented source identities.
 * Tested source base: 44dc17d9ea756eadb1656c83cd369ef2b2a3b828.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {performance} from 'node:perf_hooks';
import {projectToCanvasScene} from '../../editor/src/canvas/scene-projection.mjs';
import {screen,world,hitTest,pinWorld,zoom,snap} from '../../editor/src/canvas/precision.mjs';

const load = name => JSON.parse(readFileSync(
  new URL(`../../fixtures/${name}`,import.meta.url), 'utf8'));
const camera = scale => ({s:scale,x:61.25,y:-30.5});
const fixtureToy = load('toy-v2.gscad.json');
const fixtureE695 = load('tl494-source-e695-v2.gscad.json');
const sceneToy = projectToCanvasScene(fixtureToy,fixtureToy.project.sheets[0].id);
const X = [50000,30000];

test('production projection uses authentic ProjectV2 symbols, wire IDs, immutable literal Nets',()=>{
  const before = JSON.stringify(fixtureToy);
  assert.equal(sceneToy.symbols.length,4);
  assert.equal(sceneToy.wires.length,2);
  assert.deepEqual(sceneToy.wires.map(w=>w.net_id),fixtureToy.project.sheets[0].wires.map(w=>w.net_id));
  assert.deepEqual(sceneToy.symbols.flatMap(s=>s.pins).map(p=>p.physical_pin_number).length,8);
  assert.equal(JSON.stringify(fixtureToy),before);
});

for (const scale of [.004,.008,.016]) {
  test(`real X is ambiguous at ${scale*1000} px/mm, not a joined junction`,()=>{
    const c=camera(scale),hit=hitTest(sceneToy,c,screen(X,c));
    assert.equal(hit.kind,'ambiguous-segment');
    assert.equal(hit.candidates.length,2);
    assert.equal(sceneToy.junctions.length,0);
    assert.equal(fixtureToy.project.nets.length,2);
  });
  test(`physical PinRef identity survives screen/world/hitTest at scale ${scale}`,()=>{
    const c=camera(scale),symbol=sceneToy.symbols[0];
    const original=symbol.pins[0],physical=pinWorld(symbol,original.physical_pin_number);
    const pt=screen(physical.at_um,c);
    assert.deepEqual(world(pt,c),physical.at_um);
    const hit=hitTest(sceneToy,c,pt);
    assert.equal(hit.kind,'pin');
    assert.deepEqual(hit.pin,physical.pin);
    assert.equal(hit.pin.component_id,symbol.component_id);
    assert.equal(hit.pin.physical_pin_number,original.physical_pin_number);
  });
}

test('90 degree rotation changes geometry and pin normal, NEVER physical PinRef',()=>{
  const symbol=sceneToy.symbols[0];
  const before=pinWorld(symbol,symbol.pins[0].physical_pin_number);
  const after=pinWorld({...symbol,rotation_deg:90},symbol.pins[0].physical_pin_number);
  assert.notDeepEqual(after.at_um,before.at_um);
  assert.deepEqual(after.pin,before.pin);
});
test('independent snap disabled is exact micrometre coordinate',()=>{
  assert.deepEqual(snap([1001,1002],1000,false),[1001,1002]);
  assert.deepEqual(snap([1001,1002],1000,true),[1000,1000]);
});

// Contract-required FAIL cases against real integrated canvas, not a mock.
test('E695 23-symbol frozen project projects both nonconductive source-b graphics',()=>{
  const original=JSON.stringify(fixtureE695);
  const p=fixtureE695.project,sheet=p.sheets[0];
  assert.equal(p.components.length,23);
  assert.equal(p.nets.length,15);
  assert.equal(p.nets.reduce((n,net)=>n+net.members.length,0),62);
  assert.equal(sheet.wires.length,0);
  assert.equal(sheet.graphics.filter(g=>g.kind==='source_b_continuation').length,2);
  const scene=projectToCanvasScene(fixtureE695,sheet.id);
  assert.equal(scene.symbols.length,23);
  assert.equal(scene.graphics.length,2);
  assert.equal(scene.wires.length,0);
  assert.ok(scene.graphics.every(g=>g.source_role==='source_b_continuation'));
  assert.equal(JSON.stringify(fixtureE695),original);
});
test('invalid zero-length wire is not hit-testable as genuine segment',()=>{
  const bad={symbols:[],junctions:[],wires:[
    {id:'invalid',vertices:[
      {id:'a',at_um:[20000,20000]},
      {id:'b',at_um:[20000,20000]}
    ],segments:[{id:'s',from_vertex_id:'a',to_vertex_id:'b'}]}
  ]};
  const c=camera(.008);
  assert.throws(()=>hitTest(bad,c,screen([20000,20000],c)),/NON_ORTHOGONAL|ZERO_LENGTH/);
});
test('zoom must reject a degenerate existing camera scale before division',()=>{
  assert.throws(()=>zoom({s:0,x:0,y:0},{x:5,y:5},2),/INVALID_ZOOM/);
});

test('real geometry probe: 1000 nodes and 2000 segments, non-DOM reference timings',()=>{
  const symbols=Array.from({length:1000},(_,i)=>({
    component_id:'U'+i,origin_um:[(i%40)*15000,Math.floor(i/40)*15000],
    rotation_deg:0,mirror_x:false,
    pins:[{physical_pin_number:'1',at_um:[-8000,0],normal:'left'},
          {physical_pin_number:'2',at_um:[8000,0],normal:'right'}]
  }));
  const wires=Array.from({length:2000},(_,i)=>({
    id:'w'+i,
    vertices:[{id:'a',at_um:[100000+(i%100)*1200,500000+Math.floor(i/100)*1200]},
              {id:'b',at_um:[110000+(i%100)*1200,500000+Math.floor(i/100)*1200]}],
    segments:[{id:'seg',from_vertex_id:'a',to_vertex_id:'b'}]
  }));
  const scene={symbols,wires,junctions:[]},c=camera(.008);
  const start=performance.now();
  for(let i=0;i<100;i++)assert.equal(hitTest(scene,c,{x:1e7+i,y:-1e7}),null);
  const duration=performance.now()-start;
  console.log(`CHAT3 PRODUCTION-MODULE ALGORITHM PROBE: 1000 symbols/2000 segments, 100 misses, ${duration.toFixed(1)}ms total, ${(duration/100).toFixed(3)}ms/hit; NOT React/SVG DOM fps`);
});
