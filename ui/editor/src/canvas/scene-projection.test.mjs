import test from 'node:test';
import assert from 'node:assert/strict';
import {projectToCanvasScene} from './scene-projection.mjs';

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
