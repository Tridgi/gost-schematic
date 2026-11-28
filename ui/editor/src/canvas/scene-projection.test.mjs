import test from 'node:test';
import assert from 'node:assert/strict';
import {projectToCanvasScene} from './scene-projection.mjs';
import {readFileSync,existsSync} from 'node:fs';

const file=()=>({
  format:'gscad-project',format_version:2,project:{
    components:[{id:'u',part_id:'part'}],
    part_definitions:[{id:'part',symbol_ids:['symbol'],physical_pins:[{number:'1'},{number:'2'}]}],
    symbol_definitions:[{id:'symbol',part_id:'part',status:'draft',
      pins:[{physical_pin_number:'1',at_um:[-10000,0],side:'left'},{physical_pin_number:'2',at_um:[10000,0],side:'right'}],
      graphics:[{kind:'rect',points_um:[[-4000,-2000],[4000,2000]]},{kind:'polyline',points_um:[[0,0],[0,1000],[1000,1000]]}]
    }],
    nets:[{id:'literal-net',members:[{component_id:'u',physical_pin_number:'1'}]}],
    sheets:[{id:'sheet',instances:[{id:'instance',component_id:'u',symbol_id:'symbol',origin_um:[15000,20000],rotation_deg:90,mirror_x:true,layer_id:'electrical'}],
      wires:[{id:'wire',net_id:'literal-net',vertices:[],segments:[],mode:'orthogonal'}],
      junctions:[],splices:[],graphics:[{id:'b-graphic',source_role:'source_b_continuation',layer_id:'draw',kind:'line',points_um:[[1000,2000],[2000,2000]]}]
    }]
  }
});
test('two signed physical pins projected without changing source net',()=>{
 const f=file(),before=JSON.stringify(f),s=projectToCanvasScene(f,'sheet');
 assert.deepEqual(s.symbols[0].pins.map(p=>p.physical_pin_number),['1','2']);
 assert.equal(s.symbols[0].pins[0].normal,'left');
 assert.equal(s.wires[0].net_id,'literal-net');
 assert.equal(JSON.stringify(f),before);
});
test('rect and polyline flatten into six strokes while b remains graphical',()=>{
 const s=projectToCanvasScene(file(),'sheet');
 assert.equal(s.symbols[0].strokes.length,6);
 assert.equal(s.graphics.length,1);
 assert.equal(s.graphics[0].source_role,'source_b_continuation');
 assert.equal(s.wires.length,1);
});
test('reject forged physical pin and mismatched part-symbol provenance',()=>{
 const bad=file();bad.project.symbol_definitions[0].pins[0].physical_pin_number='17';
 assert.throws(()=>projectToCanvasScene(bad,'sheet'),/INVALID_SYMBOL_PIN/);
 const mismatch=file();mismatch.project.symbol_definitions[0].part_id='alien';
 assert.throws(()=>projectToCanvasScene(mismatch,'sheet'),/PART_SYMBOL_MISMATCH/);
});
test('projection edits never mutate authoritative wires, do not downcast version',()=>{
 const f=file(),s=projectToCanvasScene(f,'sheet');
 s.wires[0].net_id='forged';
 assert.equal(f.project.sheets[0].wires[0].net_id,'literal-net');
 assert.throws(()=>projectToCanvasScene({...file(),format_version:3},'sheet'),/UNSUPPORTED_PROJECT_V2/);
 assert.throws(()=>projectToCanvasScene(file(),'missing'),/UNKNOWN_SHEET/);
});

test('latest ProjectV2 graphic.kind=source_b_continuation projects as non-electric ink',()=>{
 const f=file(),sh=f.project.sheets[0];
 sh.graphics=[{id:'b1',layer_id:'drawing',kind:'source_b_continuation',points_um:[[1,2],[4000,2]],stroke_um:300},
              {id:'b2',layer_id:'drawing',kind:'source_b_continuation',points_um:[[0,7],[5000,7]],stroke_um:300}];
 const before=JSON.stringify(f),s=projectToCanvasScene(f,'sheet');
 assert.equal(s.graphics.length,2);
 assert.equal(s.graphics.filter(g=>g.kind==='source_b_continuation').length,2);
 assert.equal(s.graphics.every(g=>g.electrical===false&&g.strokes.length===1),true);
 assert.equal(s.wires.length,1);
 assert.equal(JSON.stringify(f),before);
});
test('source_b graphic cannot masquerade as Net wire, PinRef or junction',()=>{
 for(const forged of [{net_id:'literal-net'},{pinrefs:[{component_id:'u',physical_pin_number:'1'}]},
                       {junction_id:'j1'},{wire_id:'x'},{electrical:true},{electrical:false}]){
  const f=file(),base=f.project.sheets[0].graphics[0];
  f.project.sheets[0].graphics=[{...base,kind:'source_b_continuation',...forged}];
  assert.throws(()=>projectToCanvasScene(f,'sheet'),/NON_ELECTRICAL_GRAPHIC/);
 }
});
const fixtureUrl=new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url);
test('frozen source TL494 23/15/62/16/2b renders as unrouted visual projection',
 {skip:!existsSync(fixtureUrl)},()=>{
 const file=JSON.parse(readFileSync(fixtureUrl,'utf8')),p=file.project;
 assert.equal(p.components.length,23);assert.equal(p.nets.length,15);
 assert.equal(p.nets.reduce((a,n)=>a+n.members.length,0),62);
 const da=p.components.find(c=>c.source_refdes==='DA1');
 assert.equal(new Set(p.nets.flatMap(n=>n.members.filter(pin=>pin.component_id===da.id).map(pin=>pin.physical_pin_number))).size,16);
 const s=projectToCanvasScene(file,p.sheets[0].id);
 assert.equal(s.symbols.length,23);
 assert.equal(s.wires.length,0);
 assert.equal(s.graphics.filter(g=>g.kind==='source_b_continuation').length,2);
 assert.equal(p.nets.every(n=>n.route_status==='unrouted'),true);
});

test('circle remains native geometry, not strokes, pins or wire junctions',()=>{
 const f=file(),g=f.project.symbol_definitions[0].graphics;
 g.push({kind:'circle',points_um:[[1000,2000],[6000,2000]],stroke_um:300});
 const projected=projectToCanvasScene(f,'sheet');
 assert.deepEqual(projected.symbols[0].circles,[{center_um:[1000,2000],radius_um:5000,stroke_um:300}]);
 assert.equal(projected.symbols[0].strokes.length,6);
 assert.equal(projected.symbols[0].pins.length,2);
 assert.equal(projected.junctions.length,0);
 for(const points of [[[0,0],[0,0]],[[0,0],[1,1]],[[0,0],[-1,0]],[[999999999,0],[1000000000,1]]]){
  g.at(-1).points_um=points;
  assert.throws(()=>projectToCanvasScene(f,'sheet'),/INVALID_CIRCLE/);
 }
});
