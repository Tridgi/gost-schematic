import test from 'node:test';
import assert from 'node:assert/strict';
import {analyzeDiagnostics} from './diagnostics.mjs';

const pin=(component_id,physical_pin_number)=>({component_id,physical_pin_number});
const p=(c,n)=>({kind:'pin',...pin(c,n)});
const free=id=>({kind:'free',free_id:id});
const shape=(id,origin=[100,100],type='passive')=>({
 instance_id:'I-'+id,component_id:id,origin_um:origin,rotation_deg:0,mirror_x:false,
 pins:[{physical_pin_number:'1',at_um:[0,0],normal:'right'}],strokes:[
 {from_um:[-100,-100],to_um:[100,100]}],inkStrokes:[
 {from_um:[-100,-100],to_um:[100,100],stroke_um:20}],curves:[],notes:[],type
});
function wire(id,net,points,a=free(id+'-a'),b=free(id+'-b')){
 const vertices=points.map((at_um,i)=>({id:id+'-v'+i,at_um,anchor:i===0?a:i===points.length-1?b:{kind:'bend'}}));
 return {id,net_id:net,vertices,segments:vertices.slice(1).map((v,i)=>({id:id+'-s'+i,from_vertex_id:vertices[i].id,to_vertex_id:v.id}))};
}
const fixture=(symbols=[],wires=[],nets=[])=>{
 const project={components:symbols.map(s=>({id:s.component_id,part_id:'P-'+s.component_id,refdes:s.component_id})),
 part_definitions:symbols.map(s=>({id:'P-'+s.component_id,physical_pins:[{number:'1',electrical_type:s.type}]})),nets};
 const snapshot={wires,nets};const scene={symbols};
 return {file:{project},scene,snapshot};
};
const net=(id,members=[])=>({id,name:id,members});
function inspect(f,statuses={},options={}){
 const before=structuredClone(f);
 const report=analyzeDiagnostics(f.file,f.scene,f.snapshot,statuses,options);
 assert.deepEqual(f,before);
 return report;
}
const codes=r=>r.items.map(d=>d.code);
test('R18 ordinary X crossing remains non-electrical; T and collinear overlap are reported',()=>{
 const nets=[net('A'),net('B')];
 const a=wire('a','A',[[0,10000],[20000,10000]]);
 const crossing=wire('b','B',[[10000,0],[10000,20000]]);
 assert.ok(!codes(inspect(fixture([],[a,crossing],nets))).some(c=>c.startsWith('DRC_')));
 const t=wire('b','B',[[10000,10000],[10000,20000]]);
 assert.ok(codes(inspect(fixture([],[a,t],nets))).includes('DRC_FOREIGN_WIRE_TOUCH'));
 const overlap=wire('b','B',[[5000,10000],[25000,10000]]);
 const r=inspect(fixture([],[a,overlap],nets));
 assert.ok(codes(r).includes('DRC_FOREIGN_WIRE_OVERLAP'));assert.equal(r.counts.error,1);
});
test('R18 explicit shared signed junction is not reported as an unmarked touch',()=>{
 const ja={kind:'junction',junction_id:'J'};
 const a=wire('a','A',[[0,10000],[10000,10000]],free('a'),ja);
 const b=wire('b','A',[[10000,10000],[10000,20000]],ja,free('b'));
 assert.ok(!codes(inspect(fixture([],[a,b],[net('A')]))).includes('DRC_UNMARKED_TOUCH'));
 const unsign=wire('b','A',[[10000,10000],[10000,20000]]);
 assert.ok(codes(inspect(fixture([],[a,unsign],[net('A')]))).includes('DRC_UNMARKED_TOUCH'));
});
test('R18 route/driver/pin diagnostics respect signed membership and do not mutate geometry',()=>{
 const a=shape('R1',[0,10000],'output'),b=shape('R2',[20000,10000],'power_output'),c=shape('R3',[10000,10000]),d=shape('R4',[30000,30000]);
 const w=wire('a','A',[[0,10000],[20000,10000]],p('R1','1'),p('R2','1'));w.needs_routing_review=true;
 const r=inspect(fixture([a,b,c,d],[w],[net('A',[pin('R1','1'),pin('R2','1')]),net('B',[pin('R3','1')])]),{A:'partial',B:'unrouted'});
 assert.ok(codes(r).includes('ERC_MULTIPLE_OUTPUTS'));assert.ok(codes(r).includes('ERC_PARTIAL_NET'));
 assert.ok(codes(r).includes('ERC_UNROUTED_NET'));assert.ok(codes(r).includes('DRC_ROUTE_REVIEW'));
 const unassigned=r.items.find(x=>x.code==='ERC_UNASSIGNED_PIN');assert.equal(unassigned.instanceId,'I-R4');
 assert.ok(codes(r).includes('DRC_FOREIGN_PIN_CONTACT'));
 assert.equal(r.items.filter(x=>x.code==='DRC_FOREIGN_PIN_CONTACT').length,1);
 assert.equal(r.items.filter(x=>x.code==='DRC_UNSIGNED_PIN_CONTACT').length,0);
});
test('R18 overlapping symbol bounds, bounded report and incomplete scan are explicit',()=>{
 const a=shape('R1',[10000,10000]),b=shape('R2',[10050,10050]);
 const f=fixture([a,b]);
 assert.ok(codes(inspect(f)).includes('DRC_SYMBOL_BOUNDS'));
 const capped=inspect(f,{}, {maxItems:1,maxComparisons:0});
 assert.equal(capped.incomplete,true);assert.ok(codes(capped).includes('CHECK_LIMIT'));
 assert.equal(capped.items.length,2);assert.equal(capped.omitted,1);
});

test('R18 report cap keeps a critical overlap ahead of many unassigned pins',()=>{
 const symbols=Array.from({length:20},(_,i)=>shape('R'+i,[1000+i*1000,30000]));
 const a=wire('a','A',[[0,10000],[20000,10000]]);
 const b=wire('b','B',[[5000,10000],[25000,10000]]);
 const report=inspect(fixture(symbols,[a,b],[net('A'),net('B')]),{}, {maxItems:2});
 assert.equal(report.items[0].code,'DRC_FOREIGN_WIRE_OVERLAP');
 assert.equal(report.counts.error,1);
 assert.equal(report.counts.warning,22);
 assert.equal(report.omitted,21);
 assert.ok(codes(report).includes('CHECK_LIMIT'));
});

test('R18b exact signed pin exit is allowed, but wire along inward symbol ink is diagnosed',()=>{
 const s=shape('R1',[10000,10000]);
 s.inkStrokes=[{from_um:[-1000,0],to_um:[0,0],stroke_um:300}];
 const out=wire('a','A',[[10000,10000],[15000,10000]],p('R1','1'),free('out'));
 const inward=wire('b','A',[[10000,10000],[5000,10000]],p('R1','1'),free('in'));
 const nets=[net('A',[pin('R1','1')])];
 assert.ok(!codes(inspect(fixture([s],[out],nets))).includes('DRC_WIRE_SYMBOL_INK'));
 assert.ok(codes(inspect(fixture([s],[inward],nets))).includes('DRC_WIRE_SYMBOL_INK'));
});
test('R18b diagonal rational crossing and analytic circle/semicircle ink are detected without false lower-half arc',()=>{
 const s=shape('R1',[20000,20000]);
 s.pins=[];s.inkStrokes=[{from_um:[-1000,-1000],to_um:[1000,999],stroke_um:300}];
 const diagonal=wire('a','A',[[17000,20000],[23000,20000]]);
 assert.ok(codes(inspect(fixture([s],[diagonal],[net('A')]))).includes('DRC_WIRE_SYMBOL_INK'));
 s.inkStrokes=[];
 s.curves=[{kind:'semicircle',center:[0,0],radius:2000,stroke_um:300,points_um:[[-2000,0],[0,-2000],[2000,0]],bounds:[[-2000,0],[0,-2000],[2000,0]],sweep:1}];
 const top=wire('top','A',[[17000,19000],[23000,19000]]);
 const bottom=wire('bottom','A',[[17000,21000],[23000,21000]]);
 assert.ok(codes(inspect(fixture([s],[top],[net('A')]))).includes('DRC_WIRE_SYMBOL_INK'));
 assert.ok(!codes(inspect(fixture([s],[bottom],[net('A')]))).includes('DRC_WIRE_SYMBOL_INK'));
 s.rotation_deg=180;
 assert.ok(!codes(inspect(fixture([s],[top],[net('A')]))).includes('DRC_WIRE_SYMBOL_INK'));
 assert.ok(codes(inspect(fixture([s],[bottom],[net('A')]))).includes('DRC_WIRE_SYMBOL_INK'));
 s.curves=[{kind:'circle',center:[0,0],radius:2000,stroke_um:300,points_um:[[0,0],[2000,0]],bounds:[[-2000,-2000],[2000,2000]],sweep:0}];
 const tangent=wire('tangent','A',[[17000,22000],[23000,22000]]);
 assert.ok(codes(inspect(fixture([s],[tangent],[net('A')]))).includes('DRC_WIRE_SYMBOL_INK'));
});


test('R31 warns on straight stroke width even without centerline intersection',()=>{
 const s=shape('R1',[20000,20000]);s.pins=[];
 s.inkStrokes=[{from_um:[-2000,0],to_um:[2000,0],stroke_um:400}];
 const near=wire('near','A',[[17000,20199],[23000,20199]]);
 const clear=wire('clear','A',[[17000,20201],[23000,20201]]);
 assert.ok(codes(inspect(fixture([s],[near],[net('A')]))).includes('DRC_WIRE_SYMBOL_INK'));
 assert.ok(!codes(inspect(fixture([s],[clear],[net('A')]))).includes('DRC_WIRE_SYMBOL_INK'));
 s.rotation_deg=90;
 const vertical=wire('vertical','A',[[20199,17000],[20199,23000]]);
 assert.ok(codes(inspect(fixture([s],[vertical],[net('A')]))).includes('DRC_WIRE_SYMBOL_INK'));
});
test('R31 checks rotated/mirrored upright annotation envelopes without changing Net membership',()=>{
 const s=shape('R1',[20000,20000]);s.pins=[];s.inkStrokes=[];s.strokes=[];
 s.notes=[{key:'polarity',text:'+',at_um:[4000,2000],height_um:1000,horizontal:'center',vertical:'center'}];
 s.rotation_deg=90;s.mirror_x=true;
 // transformed note anchor [18000,16000], text itself remains upright.
 const crossing=wire('a','A',[[16000,16000],[20000,16000]]);
 const clear=wire('b','A',[[16000,19000],[20000,19000]]);
 const report=inspect(fixture([s],[crossing,clear],[net('A')]));
 const notes=report.items.filter(d=>d.code==='DRC_WIRE_SYMBOL_TEXT');
 assert.equal(notes.length,1);assert.equal(notes[0].instanceId,'I-R1');
 assert.equal(notes[0].severity,'warning');assert.equal(report.counts.error,0);
});
