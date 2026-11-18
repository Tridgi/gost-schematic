import test from 'node:test';
import assert from 'node:assert/strict';
import { ManualWireEngine, constructWire, WireError } from '../dist/manual-wire.js';
import { hitTest, screen, zoom, pinWorld } from '../../canvas/precision.mjs';

// Pinned Canvas geometry copied from shared branch SHA
// 44dc17d9ea756eadb1656c83cd369ef2b2a3b828 in CHAT7 CI.
// This is an actual cross-module integration test, NOT a DOM/browser E2E test.
const pin=(c,n)=>({kind:'pin',component_id:c,physical_pin_number:n});
const comp=(id,origin,normal)=>({
 id,origin_um:origin,rotation:0,mirror_x:false,
 pins:[{component_id:id,physical_pin_number:'1',local_at_um:[0,0],outward:normal}]
});
const make=()=>new ManualWireEngine({
 schema_version:2,project_id:'canvas-integration',revision:0,source_topology_hash:'pinned-source-sha',
 components:[comp('R1',[0,0],'right'),comp('C1',[14000,8000],'left'),
   comp('D1',[100000,100000],'right'),comp('D2',[120000,100000],'left')],
 nets:[
  {id:'N1',literal_source_name:'SIGNAL',members:[{component_id:'R1',physical_pin_number:'1'},{component_id:'C1',physical_pin_number:'1'}]},
  {id:'N2',literal_source_name:'POWER',members:[{component_id:'D1',physical_pin_number:'1'},{component_id:'D2',physical_pin_number:'1'}]}
 ],wires:[],junctions:[],splices:[]
});
const w1=()=>constructWire('W1','N1','layer-electric',
 [[0,0],[4000,0],[4000,8000],[14000,8000]],pin('R1','1'),pin('C1','1'));
const free=(id,side)=>({kind:'free',free_id:`${id}:${side}`});
const scene=e=>({
 symbols:e.snapshot.components.map(c=>({
  component_id:c.id,origin_um:c.origin_um,rotation_deg:c.rotation,
  mirror_x:c.mirror_x,
  pins:c.pins.map(p=>({physical_pin_number:p.physical_pin_number,at_um:p.local_at_um,normal:p.outward}))
 })),
 wires:e.snapshot.wires,junctions:e.snapshot.junctions
});
const camera={s:.012,x:160,y:210};
const commit=(e,w)=>e.commitWire(e.newTransaction('commit-'+w.id),w);

test('Canvas physical pin hit is authoritative PinRef under zoom+pan; wire commits on exact pins',()=>{
 const e=make(),a=scene(e);
 const before=hitTest(a,camera,screen([0,0],camera));
 const scaled=zoom(camera,{x:180,y:250},1.5);
 const after=hitTest(a,scaled,screen([0,0],scaled));
 assert.equal(before.kind,'pin');
 assert.deepEqual(before.pin,{component_id:'R1',physical_pin_number:'1'});
 assert.deepEqual(after.pin,before.pin);
 assert.deepEqual(pinWorld(a.symbols[0],'1').at_um,[0,0]);
 commit(e,w1());
 assert.equal(e.validateNet('N1').status,'verified');
});

test('Canvas hit segment_id drives actual WireEngine +3000µm drag, Undo and Redo',()=>{
 const e=make();commit(e,w1());
 const pos=screen([4000,3000],camera);
 const hit=hitTest(scene(e),camera,pos);
 assert.equal(hit.kind,'segment');
 assert.deepEqual({wire_id:hit.wire_id,segment_id:hit.segment_id,movable:hit.movable},
                  {wire_id:'W1',segment_id:'W1:s1',movable:true});
 const previous=e.snapshot.wires[0].vertices.map(v=>v.at_um);
 e.moveSegmentById(e.newTransaction('pointer-up'),hit.wire_id,hit.segment_id,3000);
 assert.deepEqual(e.snapshot.wires[0].vertices.map(v=>v.at_um),[[0,0],[7000,0],[7000,8000],[14000,8000]]);
 assert.equal(e.undo(),true);assert.deepEqual(e.snapshot.wires[0].vertices.map(v=>v.at_um),previous);
 assert.equal(e.redo(),true);assert.equal(e.snapshot.wires[0].vertices[1].at_um[0],7000);
});

test('Canvas ambiguous foreign-Net X never creates a junction or shorts source Nets',()=>{
 const e=make();commit(e,w1());
 commit(e,constructWire('WX','N2','layer-electric',
   [[0,4000],[8000,4000]],free('WX','start'),free('WX','end')));
 const click=hitTest(scene(e),camera,screen([4000,4000],camera));
 assert.equal(click.kind,'ambiguous-segment');
 assert.equal(click.candidates.length,2);
 assert.equal(e.snapshot.junctions.length,0);
 assert.deepEqual(e.highlightNet('N1').wire_ids,['W1']);
 assert.deepEqual(e.highlightNet('N2').wire_ids,['WX']);
 const prior=e.serialize();
 assert.throws(()=>e.toggleJunction(e.newTransaction('forbidden-dot'),
   {id:'J-false',net_id:'N1',layer_id:'layer-electric',at_um:[4000,4000]},
   ['W1','WX']),err=>err instanceof WireError&&err.code==='NET_CONFLICT');
 assert.equal(e.serialize(),prior);
});
