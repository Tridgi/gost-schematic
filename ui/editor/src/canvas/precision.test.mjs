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
test('physical pin hit band 6.99px hit, 7.01px miss (CHAT3 QA)',()=>{
 const p=screen([12000,10000],camera),only={...shape,symbols:[symbol],wires:[]};
 assert.equal(hitTest(only,camera,{x:p.x+6.99,y:p.y})?.kind,'pin');
 assert.notEqual(hitTest(only,camera,{x:p.x+7.01,y:p.y})?.kind,'pin');
});
test('wire segment hit band 4.99px hit, 5.01px miss (CHAT3 QA)',()=>{
 const only={symbols:[],junctions:[],wires:[{id:'w',net_id:'N',vertices:[{id:'v0',at_um:[0,0]},{id:'v1',at_um:[20000,0]}],segments:[{id:'s0',from_vertex_id:'v0',to_vertex_id:'v1'}]}]};
 const p=screen([10000,0],camera);
 assert.equal(hitTest(only,camera,{x:p.x,y:p.y+4.99})?.kind,'segment');
 assert.notEqual(hitTest(only,camera,{x:p.x,y:p.y+5.01})?.kind,'segment');
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

test('CHAT3 regression: invalid camera scale and offsets are rejected before zoom',()=>{
 for(const c of [{s:0,x:0,y:0},{s:-1,x:0,y:0},{s:NaN,x:0,y:0},{s:.008,x:Infinity,y:0},{s:.008,x:0,y:NaN}])
  assert.throws(()=>zoom(c,{x:100,y:100},2),/INVALID_ZOOM/);
 assert.throws(()=>zoom(camera,{x:Infinity,y:100},2),/INVALID_POINTER/);
});
test('CHAT3 regression: zero-length segment is never selectable',()=>{
 const invalid={symbols:[],junctions:[],wires:[{id:'w0',net_id:'N',vertices:[{id:'p',at_um:[10000,20000]},{id:'q',at_um:[10000,20000]}],
 segments:[{id:'s0',from_vertex_id:'p',to_vertex_id:'q'}]}]};
 assert.throws(()=>hitTest(invalid,camera,screen([10000,20000],camera)),/ZERO_LENGTH_SEGMENT/);
});
test('CHAT3 regression: canonical v2 SymbolPin.side maps physical terminal normals',()=>{
 const canonical={...symbol,pins:[{physical_pin_number:'1',at_um:[2000,0],side:'right'}]};
 assert.deepEqual(hitTest({symbols:[canonical],wires:[],junctions:[]},camera,screen([12000,10000],camera)).pin,{component_id:'U',physical_pin_number:'1'});
 const north={...canonical,pins:[{physical_pin_number:'1',at_um:[0,-2000],side:'top'}]};
 assert.equal(hitTest({symbols:[north],wires:[],junctions:[]},camera,screen([10000,8000],camera)).normal,'up');
});
