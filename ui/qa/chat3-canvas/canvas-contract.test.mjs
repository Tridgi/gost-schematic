import test from 'node:test';
import assert from 'node:assert/strict';
import {integerUm,pointUm,localToWorld,viewport,hitPin,hitSegment,connected,validateWire} from './oracle.mjs';

const point = at_um=>({at_um, pin:{component_id:'R1',physical_pin_number:'1'}});
const view = viewport({zoom:1,pan_px:[40,-20],px_per_mm:4});
const v=(id,at_um,anchor)=>({id,at_um,anchor});
const bend={kind:'bend'};
const pin=(component_id,physical_pin_number)=>({kind:'pin',component_id,physical_pin_number});
const free=free_id=>({kind:'free',free_id});
const junction=junction_id=>({kind:'junction',junction_id});
const splice=splice_id=>({kind:'splice',splice_id});
const segment=(id,a,b)=>({id,from_vertex_id:a,to_vertex_id:b});
const wire=(id,net_id,vertices,segments)=>({id,net_id,layer_id:'electrical',mode:'orthogonal',vertices,segments});

const A=wire('wa','N_A',[
 v('a0',[24000,24000],pin('R1','2')),
 v('a1',[28000,24000],bend),
 v('a2',[28000,40000],bend),
 v('a3',[32000,40000],pin('C1','1')),
],[segment('a01','a0','a1'),segment('a12','a1','a2'),segment('a23','a2','a3')]);
const B=wire('wb','N_B',[
 v('b0',[20000,32000],pin('TP1','1')),
 v('b1',[36000,32000],pin('TP2','1')),
],[segment('b01','b0','b1')]);
const inputA={
  net_members:['R1/2','C1/1'],
  pin_positions:{'R1/2':[24000,24000],'C1/1':[32000,40000]},
  other_wires:[B],
};

// 1. Strong numeric domain: no accidental mm float, huge numbers or unsafe integers.
test('accepts exact +/-1e9 µm and rejects invalid integer types',()=>{
 assert.equal(integerUm(1_000_000_000),1_000_000_000);
 assert.equal(integerUm(-1_000_000_000),-1_000_000_000);
 for(const bad of [1_000_000_001,-1_000_000_001,0.1,NaN,Infinity,Number.MAX_SAFE_INTEGER+1,'1000'])
   assert.throws(()=>integerUm(bad));
 assert.deepEqual(pointUm([-1,999_999_999]),[-1,999_999_999]);
});
test('quarter-turn clockwise y-down physical PinRef positions remain exact',()=>{
 const p=[-8000,3000];
 const xy=[[12000,23000],[17000,12000],[28000,17000],[23000,28000]];
 for(const [i,rotation_deg] of [0,90,180,270].entries())
   assert.deepEqual(localToWorld(p,{origin_um:[20000,20000],rotation_deg,mirror_x:false}),xy[i]);
});
test('mirror applied before rotation and not after',()=>{
 assert.deepEqual(localToWorld([8000,3000],{origin_um:[0,0],rotation_deg:90,mirror_x:true}),[-3000,-8000]);
});
test('rotation cannot silently accept arbitrary degree',()=>{
 assert.throws(()=>localToWorld([1000,0],{origin_um:[0,0],rotation_deg:45,mirror_x:false}),/ROTATION/);
});
test('transform exceeding um limits rejected rather than wrapped',()=>{
 assert.throws(()=>localToWorld([100,0],{origin_um:[1_000_000_000,0],rotation_deg:0}),/INVALID_UM/);
});

// 2. Real CSS pixel/zoom/pan projection tests; no device-pixel-ratio multiplication.
for(const zoom of [0.5,1,2]) {
 test(`world↔pointer roundtrip and viewport page offset at zoom ${zoom}`,()=>{
  const t=viewport({zoom,pan_px:[17.25,-43.75],px_per_mm:4});
  const world=[123_456,-78_901];
  const local=t.worldToLocal(world);
  assert.deepEqual(t.localToWorld(local),world);
  assert.deepEqual(t.clientToWorld([local[0]+310.125,local[1]+120.5],{left:310.125,top:120.5}),world);
 });
 test(`pin hit threshold invariant in CSS pixels at zoom ${zoom}`,()=>{
  const t=viewport({zoom,pan_px:[0,0]});
  const [px,py]=t.worldToLocal([10_000,10_000]);
  const candidates=[point([10_000,10_000])];
  assert.equal(hitPin([px+6.99,py],candidates,t,7).kind,'pin');
  assert.equal(hitPin([px+7.01,py],candidates,t,7).kind,'none');
 });
 test(`segment hit threshold independent of zoom ${zoom}`,()=>{
  const t=viewport({zoom,pan_px:[3,7]});
  const line=[{id:'s1',from_um:[0,0],to_um:[0,50_000]}];
  const [px,py]=t.worldToLocal([0,25_000]);
  assert.equal(hitSegment([px+4.99,py],line,t,5).kind,'segment');
  assert.equal(hitSegment([px+5.01,py],line,t,5).kind,'none');
 });
}
test('independent grid visibility and snapping do not change exact pin selection',()=>{
 const modes=[{grid_visible:false,snap_enabled:false},{grid_visible:false,snap_enabled:true},{grid_visible:true,snap_enabled:false},{grid_visible:true,snap_enabled:true}];
 const [px,py]=view.worldToLocal([8000,24000]);
 const pins=[point([8000,24000])];
 for(const mode of modes){
  assert.equal(typeof mode.grid_visible,'boolean');
  assert.deepEqual(hitPin([px+3,py],pins,view,7).pin,{component_id:'R1',physical_pin_number:'1'});
 }
});
test('overlapping pins produce ambiguous selection, not guessed electrical connection',()=>{
 const t=viewport({zoom:1});
 const [px,py]=t.worldToLocal([1000,2000]);
 const result=hitPin([px,py],[{at_um:[1000,2000],pin:{component_id:'A',physical_pin_number:'1'}},{at_um:[1000,2000],pin:{component_id:'B',physical_pin_number:'7'}}],t);
 assert.equal(result.kind,'ambiguous');
 assert.equal(result.candidates.length,2);
});
test('two overlapping wire segments require explicit disambiguation',()=>{
 const segs=[{id:'one',from_um:[0,0],to_um:[10_000,0]},{id:'two',from_um:[0,0],to_um:[10_000,0]}];
 const hit=hitSegment(view.worldToLocal([5000,0]),segs,view,5);
 assert.equal(hit.kind,'ambiguous');
});
test('diagonal and zero-length wire segments fail closed in hit-test',()=>{
 assert.throws(()=>hitSegment([0,0],[{id:'s',from_um:[0,0],to_um:[1000,1000]}],view),/NON_ORTHOGONAL/);
 assert.throws(()=>hitSegment([0,0],[{id:'s',from_um:[0,0],to_um:[0,0]}],view),/ZERO_LENGTH/);
});

// 3. Independent path connectivity: at visually identical XY no automatic join.
test('real routed wire has continuous path between physical pins',()=>{
 assert.equal(connected([A],'wa/a0','wa/a3'),true);
});
test('visual X crossing of two different Nets remains disconnected',()=>{
 assert.equal(connected([A,B],'wa/a0','wb/b0'),false);
});
test('visual X crossing of same declared Net remains disconnected',()=>{
 assert.equal(connected([A,{...B,net_id:'N_A'}],'wa/a0','wb/b0'),false);
});
test('coincident free endpoints never auto-connect even with reused free id',()=>{
 const w1=wire('w1','NET',[v('a',[0,0],free('reused')),v('b',[10_000,0],free('free2'))],[segment('s1','a','b')]);
 const w2=wire('w2','NET',[v('c',[0,0],free('reused')),v('d',[0,10_000],free('free4'))],[segment('s2','c','d')]);
 assert.equal(connected([w1,w2],'w1/b','w2/d'),false);
});
test('explicit same-Net T uses shared junction ID only after split',()=>{
 const a1=wire('a1','NET',[v('a0',[0,0],free('f0')),v('ja',[10_000,0],junction('J1'))],[segment('s1','a0','ja')]);
 const a2=wire('a2','NET',[v('jb',[10_000,0],junction('J1')),v('a3',[20_000,0],free('f3'))],[segment('s2','jb','a3')]);
 const branch=wire('branch','NET',[v('p0',[10_000,10_000],free('p0')),v('jc',[10_000,0],junction('J1'))],[segment('s3','p0','jc')]);
 assert.equal(connected([a1,a2,branch],'a1/a0','branch/p0'),true);
 assert.equal(connected([a1,a2,branch],'a2/a3','branch/p0'),true);
 const isolated={...branch,vertices:branch.vertices.map(v=>v.id==='jc'?{...v,anchor:free('f4')}:v)};
 assert.equal(connected([a1,a2,isolated],'a1/a0','branch/p0'),false);
});
test('explicit splice joins two same-Net segments while remaining invisible semantic anchor',()=>{
 const w1=wire('left','NET',[v('u',[0,0],free('u')),v('x',[10_000,0],splice('S1'))],[segment('s1','u','x')]);
 const w2=wire('right','NET',[v('y',[10_000,0],splice('S1')),v('v',[20_000,0],free('v'))],[segment('s2','y','v')]);
 assert.equal(connected([w1,w2],'left/u','right/v'),true);
 assert.notEqual(w1.vertices[1].anchor.kind,'junction');
});
test('Net labels are namespaces, no merge from identical junction IDs across nets',()=>{
 const w1=wire('a','A',[v('u',[0,0],free('u')),v('x',[10_000,0],junction('J'))],[segment('s1','u','x')]);
 const w2=wire('b','B',[v('y',[10_000,0],junction('J')),v('v',[20_000,0],free('v'))],[segment('s2','y','v')]);
 assert.equal(connected([w1,w2],'a/u','b/v'),false);
});

// 4. Contract failures: immutable snapshot, exact anchor and source Net guards.
test('valid H/V physical pin-to-pin route passes negative validator',()=>{
 assert.deepEqual(validateWire(A,inputA),[]);
});
test('1µm wrong pin coordinate is PIN_ANCHOR_MISMATCH',()=>{
 const altered=structuredClone(A); altered.vertices[0].at_um[0]++;
 assert.ok(validateWire(altered,inputA).includes('PIN_ANCHOR_MISMATCH'));
 assert.deepEqual(A.vertices[0].at_um,[24000,24000]);
});
test('declared Net membership mismatch is rejected',()=>{
 assert.ok(validateWire(A,{...inputA,net_members:['R1/2']}).includes('PIN_NET_MISMATCH'));
});
test('unknown physical pin rejected rather than synthesizing a port',()=>{
 const altered=structuredClone(A); altered.vertices[0].anchor=pin('UNKNOWN','999');
 const errors=validateWire(altered,inputA);
 assert.ok(errors.includes('UNKNOWN_PIN'));assert.ok(errors.includes('PIN_NET_MISMATCH'));
});
test('different-Net explicit dot at crossing rejected even if X is valid',()=>{
 const bad={...A,vertices:A.vertices.map(v=>v),segments:A.segments};
 assert.ok(validateWire(bad,{...inputA,junctions:[{id:'jX',net_id:'N_A',at_um:[28000,32000]}]}).includes('JUNCTION_CROSSES_FOREIGN_NET'));
 assert.deepEqual(validateWire(A,inputA),[]);
});
test('nonorthogonal, zero-length, broken segment chain rejected',()=>{
 const diagonal=structuredClone(A);diagonal.vertices[1].at_um[1]++;
 assert.ok(validateWire(diagonal,inputA).includes('NON_ORTHOGONAL'));
 const zero=structuredClone(A);zero.vertices[1].at_um=[24000,24000];
 assert.ok(validateWire(zero,inputA).includes('ZERO_LENGTH'));
 const broken=structuredClone(A);broken.segments[2].from_vertex_id='a0';
 assert.ok(validateWire(broken,inputA).includes('NON_CONTIGUOUS'));
});
test('invalid internal terminal anchor rejected',()=>{
 const altered=structuredClone(A);altered.vertices[1].anchor=junction('J_bad');
 assert.ok(validateWire(altered,inputA).includes('ANCHOR_POSITION'));
});
test('invalid free identifier rejected without mutating source',()=>{
 const w=wire('f','NET',[v('a',[0,0],{kind:'free',free_id:''}),v('b',[1000,0],free('b'))],[segment('s','a','b')]);
 assert.ok(validateWire(w,{net_members:[],pin_positions:{}}).includes('INVALID_FREE_ID'));
});
test('stable identity independent of mutable refdes in view hit-testing',()=>{
 const base={component_id:'uuid-1234',physical_pin_number:'1'};
 const pinBefore={pin:base,at_um:[1000,0],refdes:'R1'};
 const pinAfter={...pinBefore,refdes:'R99'};
 const vp=viewport({zoom:1});
 const p=vp.worldToLocal([1000,0]);
 assert.deepEqual(hitPin(p,[pinBefore],vp).pin,hitPin(p,[pinAfter],vp).pin);
});
test('manual segment normal drag +3000um is world-integer and inverse exact',()=>{
 const shifted=structuredClone(A);
 for(const i of [1,2]) shifted.vertices[i].at_um[0]+=3000;
 assert.deepEqual(validateWire(shifted,inputA),[]);
 assert.equal(shifted.vertices[1].at_um[0],31000);
 for(const i of [1,2]) shifted.vertices[i].at_um[0]-=3000;
 assert.deepEqual(shifted,A);
});
test('geometry oracle does not mutate caller input',()=>{
 const before=structuredClone(A);
 const screen=view.worldToLocal(A.vertices[2].at_um);
 hitSegment(screen,[{id:'test',from_um:A.vertices[1].at_um,to_um:A.vertices[2].at_um}],view);
 validateWire(A,inputA);
 assert.deepEqual(A,before);
});