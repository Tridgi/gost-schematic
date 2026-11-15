import test from 'node:test';
import assert from 'node:assert/strict';
import {assertUm,screen,world,zoom,snap,pinWorld,hitTest} from './precision.mjs';
const camera={s:.008,x:35,y:12};
const symbol={component_id:'U',origin_um:[10000,10000],rotation_deg:0,mirror_x:false,pins:[{physical_pin_number:'1',at_um:[2000,0],normal:'right'}]};
const shape={symbols:[symbol],junctions:[],wires:[]};
for(const scale of [.004,.008,.016]){
 test('world↔screen exact 1um at zoom '+scale,()=>{
  const c={s:scale,x:121.123,y:-57.932};
  for(const p of [[1,-1],[999999999,-999999999],[123456,-789101]])assert.deepEqual(world(screen(p,c),c),p);
 });
}
test('cursor anchored zoom does not mutate signed world coordinates',()=>{
 const cursor={x:211,y:77};
 assert.deepEqual(world(cursor,zoom(camera,cursor,2)),world(cursor,camera));
});
test('90-degree pin rotation changes location and normal, not immutable pin identity',()=>{
 const p=pinWorld({...symbol,rotation_deg:90},'1');
 assert.deepEqual(p.at_um,[10000,12000]);
 assert.equal(p.normal,'down');
 assert.deepEqual(p.pin,{component_id:'U',physical_pin_number:'1'});
});
test('mirror pin normal without changing physical pin number',()=>{
 const p=pinWorld({...symbol,mirror_x:true},'1');
 assert.equal(p.normal,'left');assert.equal(p.pin.physical_pin_number,'1');
});
test('snap OFF leaves integer micrometres unchanged',()=>{
 assert.deepEqual(snap([1001,1002],1000,false),[1001,1002]);
 assert.deepEqual(snap([1001,1002],1000,true),[1000,1000]);
});
test('unsafe coordinates fail closed',()=>{
 for(const v of [1.25,Infinity,1e9+1,NaN])assert.throws(()=>assertUm(v),/INVALID_UM/);
});
test('hit returns signed PinRef not canvas Handle id',()=>{
 assert.deepEqual(hitTest(shape,camera,screen([12000,10000],camera)).pin,{component_id:'U',physical_pin_number:'1'});
});
test('overlapping physical pins are ambiguous; never connect arbitrary first',()=>{
 const s={...shape,symbols:[symbol,{...symbol,component_id:'V'}]};
 assert.equal(hitTest(s,camera,screen([12000,10000],camera)).kind,'ambiguous-pin');
});
const cross={symbols:[],junctions:[],wires:[
 {id:'A',net_id:'A',vertices:[{id:'a',at_um:[0,10000]},{id:'b',at_um:[20000,10000]}],segments:[{id:'s1',from_vertex_id:'a',to_vertex_id:'b'}]},
 {id:'B',net_id:'B',vertices:[{id:'c',at_um:[10000,0]},{id:'d',at_um:[10000,20000]}],segments:[{id:'s2',from_vertex_id:'c',to_vertex_id:'d'}]}
]};
test('bare X cross stays ambiguous, never inferred as electrical junction',()=>{
 const q=hitTest(cross,camera,screen([10000,10000],camera));
 assert.equal(q.kind,'ambiguous-segment');
 assert.equal(q.candidates.length,2);
});
test('explicit junction has priority over coincident bare wires',()=>{
 const s={...cross,junctions:[{id:'j1',at_um:[10000,10000]}]};
 assert.equal(hitTest(s,camera,screen([10000,10000],camera)).kind,'junction');
});
test('invalid diagonal authored segment rejected',()=>{
 const invalid={...cross,wires:[{...cross.wires[0],vertices:[{id:'a',at_um:[0,10000]},{id:'b',at_um:[20000,20000]}]}]};
 assert.throws(()=>hitTest(invalid,camera,screen([10000,10000],camera)),/NON_ORTHOGONAL/);
});
