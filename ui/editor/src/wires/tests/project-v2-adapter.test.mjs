import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {loadProjectWires} from '../dist/project-v2-adapter.js';
import {WireError, constructWire} from '../dist/manual-wire.js';
const fixture=name=>JSON.parse(readFileSync(new URL(`../../../../fixtures/${name}`,import.meta.url),'utf8'));
const options={sheet_id:'sheet-1',revision:0,source_topology_hash:'locked-test-topology'};
const expectCode=(f,code)=>assert.throws(f,e=>e instanceof WireError&&e.code===code);
const source=()=>fixture('tl494-source-e695-v2.gscad.json');
const toy=()=>{
 const p=fixture('toy-v2.gscad.json');
 // The original CHAT6 toy has an inward-facing R2.2/C2.1 wire; remove that
 // bad route rather than making an engine silently accept wrong pin normals.
 p.project.sheets[0].wires.pop();
 p.project.nets[1].route_status='unrouted';
 return p;
};
test('source E695 imports with exact 23/15/62 and two non-electric b strokes',()=>{
 const p=source(),s=loadProjectWires(p,options),d=s.engine.snapshot;
 assert.equal(d.components.length,23);assert.equal(d.nets.length,15);
 assert.equal(d.nets.reduce((n,x)=>n+x.members.length,0),62);
 assert.equal(d.wires.length,0);
 assert.equal(p.project.sheets[0].graphics.filter(g=>g.kind==='source_b_continuation').length,2);
 assert.deepEqual(d.nets.map(n=>n.literal_source_name),p.project.nets.map(n=>n.name));
 assert.ok(d.nets.every(n=>s.engine.validateNet(n.id).status==='unrouted'));
 const round=s.materialize(p);
 assert.deepEqual(round,p);assert.notStrictEqual(round,p);
});

test('source E695 16 DA1 pin memberships are not regenerated or reassigned',()=>{
 const p=source(),s=loadProjectWires(p,options),d=s.engine.snapshot;
 const da=p.project.components.find(x=>x.source_refdes==='DA1');
 assert.ok(da);
 assert.equal(d.nets.flatMap(n=>n.members).filter(m=>m.component_id===da.id).length,16);
});

test('real source single-sheet route changes leave source inventory/provenance/graphics untouched',()=>{
 const p=source(),s=loadProjectWires(p,options);
 const d=s.engine.snapshot,net=d.nets[0],endA={kind:'free',free_id:'stable:A'},endB={kind:'free',free_id:'stable:B'};
 const wire=constructWire('MANUAL_TEST',net.id,'layer-electric',[[900000,900000],[900001,900000]],endA,endB);
 // Production data may use a different electrical layer ID than this test;
 // select it from the source sheet without converting drawing/diagnostic ink.
 wire.layer_id=p.project.sheets[0].layers.find(x=>x.kind==='electrical').id;
 s.engine.commitWire(s.engine.newTransaction('manual:open'),wire);
 const round=s.materialize(p);
 assert.equal(round.project.sheets[0].wires.length,1);
 assert.equal(round.project.nets[0].route_status,'partial');
 assert.deepEqual(round.project.nets.map(n=>({id:n.id,name:n.name,members:n.members})),
                  p.project.nets.map(n=>({id:n.id,name:n.name,members:n.members})));
 assert.deepEqual(round.project.provenance,p.project.provenance);
 assert.deepEqual(round.project.sheets[0].graphics,p.project.sheets[0].graphics);
 assert.equal(p.project.sheets[0].wires.length,0);
});

test('canonical toy valid horizontal route imports and retains Net names',()=>{
 const p=toy(),s=loadProjectWires(p,options),round=s.materialize(p);
 assert.deepEqual(s.engine.snapshot.nets.map(n=>n.literal_source_name),['N_HORIZONTAL','N_VERTICAL']);
 assert.equal(s.engine.validateNet(p.project.nets[0].id).status,'verified');
 assert.equal(s.engine.validateNet(p.project.nets[1].id).status,'unrouted');
 assert.deepEqual(round.project.nets.map(n=>n.route_status),['verified','unrouted']);
});

test('canonical toy inward pin-normal route fails rather than corrupts connected Nets',()=>{
 expectCode(()=>loadProjectWires(fixture('toy-v2.gscad.json'),options),'PIN_NORMAL');
});

test('1µm source physical PinRef anchor drift is rejected',()=>{
 const p=toy();p.project.sheets[0].wires[0].vertices[0].at_um[0]+=1;
 expectCode(()=>loadProjectWires(p,options),'PIN_ANCHOR_MISMATCH');
});

test('multisheet routes explicitly BLOCKED rather than joining matching screen positions',()=>{
 const p=source();const s=structuredClone(p.project.sheets[0]);
 s.id='sheet-2';s.instances=[];s.wires=[];s.junctions=[];s.splices=[];
 p.project.sheets.push(s);
 expectCode(()=>loadProjectWires(p,options),'MULTISHEET_UNSUPPORTED');
});

test('multi-unit component explicitly BLOCKED pending aggregate PinRef adapter',()=>{
 const p=source();p.project.sheets[0].instances.push({...p.project.sheets[0].instances[0],id:'second-unit'});
 expectCode(()=>loadProjectWires(p,options),'MULTI_UNIT_UNSUPPORTED');
});

test('unrecognized manufacturer physical pin in symbol is rejected before import',()=>{
 const p=source(),instance=p.project.sheets[0].instances[0];
 p.project.symbol_definitions.find(s=>s.id===instance.symbol_id).pins[0].physical_pin_number='fake-999';
 expectCode(()=>loadProjectWires(p,options),'SYMBOL_UNKNOWN_PIN');
});

test('source Net member without a placed graphic terminal cannot be silently invented',()=>{
 const p=source(),n=p.project.nets[0];
 n.members.push({component_id:'missing',physical_pin_number:'1'});
 expectCode(()=>loadProjectWires(p,options),'UNPLACED_NET_PIN');
});

test('mutated canonical source Net name fails CAS, existing source remains unmodified',()=>{
 const p=source(),session=loadProjectWires(p,options),modified=structuredClone(p);
 modified.project.nets[0].name='unapproved rename';
 expectCode(()=>session.materialize(modified),'STALE_PROJECT');
 assert.deepEqual(p.project.nets.map(n=>n.name),source().project.nets.map(n=>n.name));
});

test('concurrent wire mutation fails local CAS and materialize never overwrites it',()=>{
 const p=source(),session=loadProjectWires(p,options),modified=structuredClone(p);
 modified.project.sheets[0].junctions.push({id:'external',net_id:p.project.nets[0].id,layer_id:'layer-electric',at_um:[0,0]});
 expectCode(()=>session.materialize(modified),'STALE_PROJECT');
});

test('mirror/rotation writes back exact symbol coordinates without changing physical pin ID',()=>{
 const p=source(),s=loadProjectWires(p,options),initial=s.engine.snapshot.components[0],ref=initial.pins[0];
 s.engine.rotateAndReanchor(s.engine.newTransaction('r90'),initial.id,90,false);
 const round=s.materialize(p);
 const before=p.project.sheets[0].instances.find(x=>x.component_id===initial.id);
 const after=round.project.sheets[0].instances.find(x=>x.component_id===initial.id);
 assert.equal(before.rotation_deg,0);
 assert.equal(after.rotation_deg,90);
 assert.equal(s.engine.snapshot.components[0].pins[0].physical_pin_number,ref.physical_pin_number);
});
