import test from 'node:test';
import assert from 'node:assert/strict';
import {detectPaperOverflow} from './paper-bounds.mjs';
const make=()=>({symbols:[{
 instance_id:'I1',component_id:'R1',origin_um:[290000,100000],mirror_x:false,
 rotation_deg:0,pins:[{at_um:[8000,0]}],
 strokes:[{from_um:[-3000,0],to_um:[3000,0]}]
 }],graphics:[]});
const snapshot=()=>({wires:[],junctions:[],splices:[]});
test('R10: exact A4 boundary checks include transformed physical pin not just origin',()=>{
 const scene=make(),wire=snapshot();
 const frozen=JSON.stringify({scene,wire});
 const a4=detectPaperOverflow(scene,wire,[297000,210000]);
 assert.deepEqual(a4.symbols,['R1']);
 assert.equal(a4.total,1);
 assert.equal(detectPaperOverflow(scene,wire,[594000,420000]).total,0);
 assert.equal(JSON.stringify({scene,wire}),frozen);
});
test('R10: rotated/mirrored symbol contacts and line ink are checked against signed frame',()=>{
 const scene=make(),wire=snapshot();
 scene.symbols[0].rotation_deg=90;
 scene.symbols[0].mirror_x=true;
 // Rotated negative local X becomes negative Y; origin is still inside A4.
 scene.symbols[0].origin_um=[100000,3000];
 assert.deepEqual(detectPaperOverflow(scene,wire,[297000,210000]).symbols,['R1']);
});
test('R10: paper overflow reports each electrical/non-electrical group without connecting Nets',()=>{
 const scene={symbols:[],graphics:[{id:'annotation',strokes:[{
   from_um:[297000,10000],to_um:[297001,10000]}]}]};
 const wire={wires:[{id:'W',vertices:[{at_um:[1,1]},{at_um:[1,210001]}]}],
   junctions:[{id:'J',at_um:[-1,0]}],splices:[{id:'S',at_um:[300000,0]}]};
 const v=detectPaperOverflow(scene,wire,[297000,210000]);
 assert.deepEqual(v,{symbols:[],graphics:['annotation'],wires:['W'],junctions:['J'],splices:['S'],total:4});
 assert.throws(()=>detectPaperOverflow(scene,wire,[0,0]),/INVALID_FRAME/);
});
