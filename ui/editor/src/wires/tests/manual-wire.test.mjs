import test from 'node:test';
import assert from 'node:assert/strict';
import { ManualWireEngine, WireError, constructWire, routeManhattan, transform, validateDocument } from '../dist/manual-wire.js';
const p=(component_id,physical_pin_number)=>({component_id,physical_pin_number});
const pin=(c,n)=>({kind:'pin',...p(c,n)});
const free=(w,side)=>({kind:'free',free_id:`${w}:${side}`});
const comp=(id,origin,side='right')=>({id,origin_um:origin,rotation:0,mirror_x:false,pins:[{...p(id,'1'),local_at_um:[0,0],outward:side}]});
const toy=()=>({schema_version:2,project_id:'toy',revision:0,source_topology_hash:'sha-frozen',
  components:[comp('R1',[0,0]),comp('C1',[14000,8000],'left'),comp('D1',[0,14000]),comp('D2',[14000,22000],'left')],
  nets:[{id:'N1',literal_source_name:'SIGNAL',members:[p('R1','1'),p('C1','1')]},
        {id:'N2',literal_source_name:'POWER',members:[p('D1','1'),p('D2','1')]}],
  wires:[],junctions:[],splices:[]});
const make=(d=toy())=>{
 // Every declared source Net must have at least one real PinRef even in negative free-wire fixtures.
 d.nets.forEach((n,i)=>{if(n.members.length===0){const id=`SEED_${i}`;d.components.push(comp(id,[800000+i*20000,800000]));n.members=[p(id,'1')];}});
 return new ManualWireEngine(d);
};
const w1=()=>constructWire('W1','N1','default',[[0,0],[4000,0],[4000,8000],[14000,8000]],pin('R1','1'),pin('C1','1'));
const w2=()=>constructWire('W2','N2','default',[[0,14000],[2000,14000],[2000,22000],[14000,22000]],pin('D1','1'),pin('D2','1'));
const commit=(e,w)=>e.commitWire(e.newTransaction(`add:${w.id}`),w);
const err=(fn,code)=>assert.throws(fn,(e)=>e instanceof WireError&&e.code===code,`expected ${code}`);
const tx=(e,kind)=>e.newTransaction(kind);
const modelHashInput=e=>JSON.stringify((({revision,...rest})=>rest)(e.snapshot));

test('physical pin→pin with 3-segment Manhattan route yields verified Net',()=>{
 const e=make();commit(e,w1()); assert.equal(e.validateNet('N1').status,'verified');assert.deepEqual(e.highlightNet('N1').wire_ids,['W1']);
});
test('other declared Net remains unrouted',()=>{const e=make();commit(e,w1());assert.equal(e.validateNet('N2').status,'unrouted');});
test('interior vertical segment moves perpendicular +3000µm',()=>{
 const e=make();commit(e,w1());e.moveSegment(tx(e,'slide'),'W1',1,3000);
 assert.deepEqual(e.snapshot.wires[0].vertices.map(v=>v.at_um),[[0,0],[7000,0],[7000,8000],[14000,8000]]);
});
test('undo+redo roundtrip exact serialized engineering snapshot',()=>{
 const e=make();commit(e,w1());const before=modelHashInput(e),rev=e.snapshot.revision;
 e.moveSegment(tx(e,'slide'),'W1',1,3000);const after=modelHashInput(e);
 assert.equal(e.undo(),true);assert.equal(modelHashInput(e),before);assert.ok(e.snapshot.revision>rev);
 assert.equal(e.redo(),true);assert.equal(modelHashInput(e),after);
});
test('X crossing different Nets is not electrical and requires no dot',()=>{
 const e=make();commit(e,w1());commit(e,w2());assert.equal(e.snapshot.junctions.length,0);
 assert.equal(e.validateNet('N1').status,'verified');assert.equal(e.validateNet('N2').status,'verified');
});
test('X crossing on same Net still disconnected without a junction',()=>{
 const d=toy();d.nets[0].members=[];
 d.components=[];d.nets=d.nets.slice(0,1);d.wires=[
  constructWire('A','N1','default',[[0,0],[10000,0]],free('A','start'),free('A','end')),
  constructWire('B','N1','default',[[5000,-5000],[5000,5000]],free('B','start'),free('B','end'))
 ];const e=make(d);assert.equal(e.snapshot.junctions.length,0);assert.equal(e.snapshot.wires.length,2);
});
test('explicit X same-Net junction splits two backbones into 4 connected branches',()=>{
 const d=toy();d.components=[];d.nets=[{id:'N1',literal_source_name:'TEST',members:[]}];d.wires=[
  constructWire('A','N1','default',[[0,0],[10000,0]],free('A','start'),free('A','end')),
  constructWire('B','N1','default',[[5000,-5000],[5000,5000]],free('B','start'),free('B','end'))];
 const e=make(d);e.toggleJunction(tx(e,'dot'),{id:'J1',net_id:'N1',layer_id:'default',at_um:[5000,0]},['A','B']);
 assert.equal(e.snapshot.wires.length,4);assert.equal(e.snapshot.junctions.length,1);
 assert.equal(e.snapshot.wires.flatMap(w=>[w.vertices[0],w.vertices.at(-1)]).filter(v=>v.anchor.kind==='junction').length,4);
});
test('T branch attaches at explicit junction, underlying conductor is split',()=>{
 const d=toy();d.components=[];d.nets=[{id:'N1',literal_source_name:'TEST',members:[]}];d.wires=[
  constructWire('A','N1','default',[[0,0],[10000,0]],free('A','start'),free('A','end')),
  constructWire('B','N1','default',[[5000,0],[5000,-5000]],free('B','start'),free('B','end'))];
 const e=make(d);e.toggleJunction(tx(e,'T'),{id:'J1',net_id:'N1',layer_id:'default',at_um:[5000,0]},['A','B']);
 assert.equal(e.snapshot.wires.length,3);assert.equal(e.snapshot.junctions.length,1);
});
test('explicit foreign-Net junction rejects with atomic rollback',()=>{
 const e=make();commit(e,w1());commit(e,w2());const before=e.serialize();
 err(()=>e.toggleJunction(tx(e,'bad'),{id:'J',net_id:'N1',layer_id:'default',at_um:[4000,4000]},['W1','W2']),'NET_CONFLICT');
 assert.equal(e.serialize(),before);
});
test('junction on foreign-Net ink fails even if only own wires selected',()=>{
 const d=toy();d.components=[];d.nets=[{id:'A',literal_source_name:'A',members:[]},{id:'B',literal_source_name:'B',members:[]}];
 d.wires=[constructWire('W1','A','default',[[0,0],[10000,0]],free('W1','start'),free('W1','end')),
          constructWire('W2','A','default',[[5000,0],[5000,5000]],free('W2','start'),free('W2','end')),
          constructWire('W3','B','default',[[5000,-2000],[5000,2000]],free('W3','start'),free('W3','end'))];
 const e=make(d),before=e.serialize();
 err(()=>e.toggleJunction(tx(e,'cross'),{id:'J1',net_id:'A',layer_id:'default',at_um:[5000,0]},['W1','W2']),'NET_CONFLICT');
 assert.equal(e.serialize(),before);
});
test('splice preserves graph continuity with invisible degree-2 node',()=>{
 const e=make();commit(e,w1());e.splitWire(tx(e,'splice'),'W1',[4000,4000],'S1');
 assert.equal(e.snapshot.splices.length,1);assert.equal(e.snapshot.wires.length,2);
 assert.equal(e.snapshot.junctions.length,0);assert.equal(e.validateNet('N1').status,'verified');
});
test('splice can split segment at 1µm precise point',()=>{
 const e=make();commit(e,w1());e.splitWire(tx(e,'one-um'),'W1',[4000,1],'S1');
 assert.deepEqual(e.snapshot.splices[0].at_um,[4000,1]);
});
test('split point must be on wire interior; old state remains intact',()=>{
 const e=make();commit(e,w1());const before=e.serialize();
 err(()=>e.splitWire(tx(e,'bad'),'W1',[4001,1],'S1'),'SPLIT_POINT');assert.equal(e.serialize(),before);
});
test('delete split half leaves nonaliasing free endpoint and cleans orphan splice',()=>{
 const e=make();commit(e,w1());e.splitWire(tx(e,'split'),'W1',[4000,4000],'S1');
 const second=e.snapshot.wires.find(w=>w.id!=='W1');e.deleteWire(tx(e,'delete'),second.id);
 assert.equal(e.snapshot.splices.length,0);assert.equal(e.snapshot.wires[0].vertices.at(-1).anchor.kind,'free');
 assert.equal(e.validateNet('N1').status,'partial');
});
test('remove junction makes coincident ends electrically separate free endpoints',()=>{
 const d=toy();d.components=[];d.nets=[{id:'N1',literal_source_name:'TEST',members:[]}];d.wires=[
  constructWire('A','N1','default',[[0,0],[10000,0]],free('A','start'),free('A','end')),
  constructWire('B','N1','default',[[5000,0],[5000,-5000]],free('B','start'),free('B','end'))];
 const e=make(d);e.toggleJunction(tx(e,'add'),{id:'J1',net_id:'N1',layer_id:'default',at_um:[5000,0]},['A','B']);
 e.removeJunction(tx(e,'remove'),'J1');assert.equal(e.snapshot.junctions.length,0);
 assert.equal(new Set(e.snapshot.wires.flatMap(w=>[w.vertices[0],w.vertices.at(-1)]).filter(v=>v.anchor.kind==='free').map(v=>v.anchor.free_id)).size,6);
});
test('pin world transform R90 clockwise Y-down, source physical identity retained',()=>{
 const c=comp('X',[10000,20000]); c.pins[0].local_at_um=[123,456];c.rotation=90;
 assert.deepEqual(transform(c.pins[0].local_at_um,c),[9544,20123]);
});
test('attached rotate fails with REROUTE_REQUIRED unless explicit consent, no mutation',()=>{
 const e=make();commit(e,w1());const before=e.serialize();
 err(()=>e.rotateAndReanchor(tx(e,'rotate'),'R1',90),'REROUTE_REQUIRED');assert.equal(e.serialize(),before);
});
test('rotate with consent moves pin anchor, marks route for review, retains PinRef',()=>{
 const d=toy();d.components[0].pins[0].local_at_um=[1000,0];d.components[0].origin_um=[-1000,0];
 const e=make(d);commit(e,w1());e.rotateAndReanchor(tx(e,'rotate'),'R1',90,true);
 assert.equal(e.snapshot.wires[0].vertices[0].anchor.component_id,'R1');
 assert.equal(e.snapshot.wires[0].vertices[0].anchor.physical_pin_number,'1');
 assert.equal(e.snapshot.wires[0].needs_routing_review,true);
});
test('1µm physical pin mismatch never snaps electrically',()=>{
 const e=make();const w=w1();w.vertices[0].at_um=[1,0];const before=e.serialize();
 err(()=>commit(e,w),'PIN_ANCHOR_MISMATCH');assert.equal(e.serialize(),before);
});
test('wrong Net binding fails closed',()=>{
 const e=make();const w=w1();w.net_id='N2';const before=e.serialize();
 err(()=>commit(e,w),'NET_CONFLICT');assert.equal(e.serialize(),before);
});
test('pin normal constraint must be outward',()=>{
 const e=make();const w=w1();w.vertices[1].at_um=[-4000,0];w.vertices[2].at_um=[-4000,8000];
 err(()=>commit(e,w),'PIN_NORMAL');
});
test('stale revision CAS rejects atomic wire commit',()=>{
 const e=make();const stale=tx(e,'stale');commit(e,w1());const before=e.serialize();
 err(()=>e.commitWire(stale,w2()),'STALE_REVISION');assert.equal(e.serialize(),before);
});
test('source hash mismatch fails closed',()=>{
 const e=make();const t=tx(e,'stale');t.source_topology_hash='other';
 err(()=>e.commitWire(t,w1()),'SOURCE_MISMATCH');
});
test('invalid schema version rejected on parse',()=>{
 const d=toy();d.schema_version=3;err(()=>ManualWireEngine.parse(JSON.stringify(d)),'SCHEMA_VERSION');
});
test('JSON roundtrip retains exact 1µm and physical identity',()=>{
 const e=make();commit(e,w1());e.moveSegment(tx(e,'offset'),'W1',1,1);
 const saved=e.serialize(),restored=ManualWireEngine.parse(saved);assert.equal(restored.serialize(),saved);
});
test('gridless pin start resolves exact PinRef not pointer pixels',()=>{
 const e=make();assert.deepEqual(e.beginWire(p('R1','1')),{at_um:[0,0],normal:[1,0],net_id:'N1'});
});
test('source Net identities and literal names do not change on geometry edits',()=>{
 const e=make();const original=e.snapshot.nets;commit(e,w1());e.moveSegment(tx(e,'edit'),'W1',1,3000);
 assert.deepEqual(e.snapshot.nets,original);
});
test('malformed decimal micrometres rejected',()=>{
 const d=toy();d.components[0].origin_um=[0.1,0];err(()=>validateDocument(d),'COORDINATE_RANGE');
});
test('coordinate bounds and unsafe integers fail closed',()=>{
 const d=toy();d.components[0].origin_um=[Number.MAX_SAFE_INTEGER+1,0];err(()=>validateDocument(d),'COORDINATE_RANGE');
});
test('free endpoints with matching coordinates never form electrical junction',()=>{
 const d=toy();d.components=[];d.nets=[{id:'N1',literal_source_name:'N1',members:[]}];d.wires=[
 constructWire('A','N1','default',[[0,0],[1000,0]],free('A','start'),free('A','end')),
 constructWire('B','N1','default',[[1000,0],[1000,1000]],free('B','start'),free('B','end'))];
 const e=make(d);assert.equal(e.snapshot.junctions.length,0);assert.notEqual(e.snapshot.wires[0].vertices.at(-1).anchor.free_id,e.snapshot.wires[1].vertices[0].anchor.free_id);
});
test('bare auto-routing proposal does not mutate any electrical state',()=>{
 const e=make(),before=e.serialize();const route=routeManhattan([0,0],[14000,8000],[1,0],[-1,0]);
 assert.ok(route.length>=4);assert.equal(e.serialize(),before);
});

test('Undo cannot recreate a stale CAS generation (ABA protection)',()=>{
 const e=make();commit(e,w1());const old=tx(e,'old-client');
 assert.equal(e.undo(),true);assert.ok(e.snapshot.revision>old.base_revision);
 const before=e.serialize();err(()=>e.commitWire(old,w2()),'STALE_REVISION');assert.equal(e.serialize(),before);
});
test('redo increments generation without sacrificing engineering geometry hash',()=>{
 const e=make();commit(e,w1());const original=modelHashInput(e),rev=e.snapshot.revision;
 e.undo();e.redo();assert.equal(modelHashInput(e),original);assert.equal(e.snapshot.revision,rev+2);
});
test('hidden splice can merge again preserving Net and contact identities',()=>{
 const e=make();commit(e,w1());e.splitWire(tx(e,'split'),'W1',[4000,4000],'S1');
 e.mergeSplice(tx(e,'merge'),'S1');assert.equal(e.snapshot.wires.length,1);
 assert.equal(e.snapshot.splices.length,0);assert.deepEqual(e.snapshot.wires[0].vertices[0].anchor,pin('R1','1'));
 assert.deepEqual(e.snapshot.wires[0].vertices.at(-1).anchor,pin('C1','1'));
 assert.equal(e.validateNet('N1').status,'verified');
});
test('vertex drag inserts orthogonal elbows without changing pin identity',()=>{
 const e=make();commit(e,w1());e.moveVertex(tx(e,'vertex'),'W1',1,[6000,2000]);
 const pts=e.snapshot.wires[0].vertices.map(v=>v.at_um);
 for(let i=1;i<pts.length;i++)assert.ok(pts[i][0]===pts[i-1][0]||pts[i][1]===pts[i-1][1]);
 assert.deepEqual(e.snapshot.wires[0].vertices[0].anchor,pin('R1','1'));
 assert.equal(e.snapshot.wires[0].needs_routing_review,true);
});
test('vertex drag must not edit anchored terminal',()=>{
 const e=make();commit(e,w1());const before=e.serialize();
 err(()=>e.moveVertex(tx(e,'bad'),'W1',0,[1000,1000]),'PIN_ANCHOR_PROTECTED');assert.equal(e.serialize(),before);
});

test('source Net with single declared pin and unrelated free ink is not VERIFIED',()=>{
 const d=toy();d.components=d.components.slice(0,1);d.nets=[{id:'N1',literal_source_name:'SINGLE',members:[p('R1','1')]}];
 d.wires=[constructWire('F1','N1','default',[[5000,10000],[7000,10000]],free('F1','start'),free('F1','end'))];
 const e=make(d);assert.equal(e.validateNet('N1').status,'partial');
});
test('explicit visible junction cannot overlap foreign declared physical pin even without foreign wire',()=>{
 const d=toy();d.components=[comp('P1',[5000,0])];
 d.nets=[{id:'A',literal_source_name:'A',members:[]},{id:'B',literal_source_name:'B',members:[p('P1','1')]}];
 d.wires=[constructWire('W1','A','default',[[0,0],[10000,0]],free('W1','start'),free('W1','end')),
          constructWire('W2','A','default',[[5000,0],[5000,5000]],free('W2','start'),free('W2','end'))];
 const e=make(d),before=e.serialize();
 err(()=>e.toggleJunction(tx(e,'invalid-dot'),{id:'J',net_id:'A',layer_id:'default',at_um:[5000,0]},['W1','W2']),'NET_CONFLICT');
 assert.equal(e.serialize(),before);
});

test('declared source Net must have physical members (no fake 0-pin electric Net)',()=>{
 const d=toy();d.nets[0].members=[];err(()=>validateDocument(d),'INVALID_NET');
});
test('connected source pins with a dangling branch cannot claim VERIFIED',()=>{
 const e=make();commit(e,w1());commit(e,constructWire('OPEN','N1','default',[[50000,50000],[51000,50000]],free('OPEN','start'),free('OPEN','end')));
 assert.equal(e.validateNet('N1').status,'partial');
});
test('reroute tagged needs_routing_review blocks VERIFIED even with all pins connected',()=>{
 const d=toy();d.components[0].pins[0].local_at_um=[1000,0];d.components[0].origin_um=[-1000,0];
 const e=make(d);commit(e,w1());e.rotateAndReanchor(tx(e,'rebuild'),'R1',90,true);
 assert.equal(e.validateNet('N1').status,'partial');
});

test('dangling endpoint diagnostic is explicit and scoped to declared Net',()=>{
 const e=make();commit(e,w1());commit(e,constructWire('OPEN','N1','default',[[50000,50000],[51000,50000]],free('OPEN','start'),free('OPEN','end')));
 assert.deepEqual(e.danglingEndpoints('N1'),['OPEN:end','OPEN:start']);
 assert.deepEqual(e.danglingEndpoints('N2'),[]);
});

test('ProjectV2 arbitrary globally unique free IDs remain stable across split/merge',()=>{
 const e=make(), start={kind:'free',free_id:'external-free-α'}, end={kind:'free',free_id:'external-free-β'};
 commit(e,constructWire('CUSTOM','N1','default',[[30000,30000],[40000,30000]],start,end));
 assert.deepEqual([e.snapshot.wires[0].vertices[0].anchor,e.snapshot.wires[0].vertices.at(-1).anchor],[start,end]);
 e.splitWire(tx(e,'split-custom'),'CUSTOM',[35000,30000],'S-custom');
 assert.deepEqual(
  e.snapshot.wires.flatMap(w=>[w.vertices[0].anchor,w.vertices.at(-1).anchor]).filter(a=>a.kind==='free').map(a=>a.free_id).sort(),
  ['external-free-α','external-free-β']);
 e.mergeSplice(tx(e,'merge-custom'),'S-custom');
 assert.deepEqual([e.snapshot.wires[0].vertices[0].anchor,e.snapshot.wires[0].vertices.at(-1).anchor],[start,end]);
});

test('ProjectV2 duplicate free IDs across wire endpoints fail atomically',()=>{
 const e=make(), anchor={kind:'free',free_id:'external-UUID'};
 commit(e,constructWire('A','N1','default',[[25000,40000],[30000,40000]],anchor,{kind:'free',free_id:'other-UUID'}));
 const before=e.serialize();
 err(()=>commit(e,constructWire('B','N1','default',[[50000,40000],[60000,40000]],anchor,{kind:'free',free_id:'third-UUID'})),'FREE_ALIAS');
 assert.equal(e.serialize(),before);
});

test('ProjectV2 empty arbitrary free ID fails closed without history mutation',()=>{
 const e=make(),before=e.serialize();
 err(()=>commit(e,constructWire('E','N1','default',[[35000,40000],[36000,40000]],{kind:'free',free_id:''},{kind:'free',free_id:'ok'})),'INVALID_ID');
 assert.equal(e.serialize(),before);
});

test('SVG canvas segment_id moves exactly the selected interior vertical segment by 3000µm',()=>{
 const e=make();commit(e,w1());
 const wire=e.snapshot.wires.find(w=>w.id==='W1');
 assert.equal(wire.segments[1].id,'W1:s1');
 e.moveSegmentById(tx(e,'canvas-handle'),'W1',wire.segments[1].id,3000);
 assert.deepEqual(e.snapshot.wires.find(w=>w.id==='W1').vertices.map(v=>v.at_um),
                  [[0,0],[7000,0],[7000,8000],[14000,8000]]);
});

test('SVG canvas stale or unknown segment_id refuses movement and preserves history',()=>{
 const e=make();commit(e,w1());const prior=e.serialize(),txn=tx(e,'wrong-handle');
 err(()=>e.moveSegmentById(txn,'W1','unrelated:s1',3000),'UNKNOWN_SEGMENT');
 assert.equal(e.serialize(),prior);
 e.moveSegmentById(txn,'W1','W1:s1',3000);
 err(()=>e.moveSegmentById(txn,'W1','W1:s1',3000),'STALE_REVISION');
});
