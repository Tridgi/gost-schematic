import test from 'node:test';
import assert from 'node:assert/strict';
import {captureSegmentDrag,commitSegmentDrag} from './wire-intents.mjs';
const make=()=>({
 project_id:'toy',source_topology_hash:'sha-locked',revision:12,
 wires:[{id:'W',vertices:[
  {id:'v0',at_um:[0,0]},{id:'v1',at_um:[5000,0]},
  {id:'v2',at_um:[5000,5000]},{id:'v3',at_um:[10000,5000]}],
 segments:[{id:'s0',from_vertex_id:'v0',to_vertex_id:'v1'},
 {id:'s1',from_vertex_id:'v1',to_vertex_id:'v2'},
 {id:'s2',from_vertex_id:'v2',to_vertex_id:'v3'}]}]
});
const engine=(doc=make())=>({
 state:doc,
 get snapshot(){return structuredClone(this.state)},
 newTransaction(id){return {schema_version:2,project_id:this.state.project_id,source_topology_hash:this.state.source_topology_hash,base_revision:this.state.revision,command_id:id}},
 moveSegment(tx,wireId,index,delta){
  if(tx.base_revision!==this.state.revision)throw Error('STALE_REVISION');
  const wire=this.state.wires.find(w=>w.id===wireId);
  if(index!==1)throw Error('UNEXPECTED_INDEX');
  wire.vertices[1].at_um[0]+=delta;wire.vertices[2].at_um[0]+=delta;
  this.state.revision++;
  return this.snapshot;
 }
});
test('stable ID is resolved against current snapshot at same revision',()=>{
 const e=engine(),token=captureSegmentDrag(e.snapshot,'W','s1');
 assert.deepEqual(token,{wire_id:'W',segment_id:'s1',base_revision:12,project_id:'toy',source_topology_hash:'sha-locked',axis:'v'});
 const next=commitSegmentDrag(e,token,3000,'drag-1');
 assert.equal(next.revision,13);
 assert.deepEqual(next.wires[0].vertices[1].at_um,[8000,0]);
 assert.equal(e.state.wires[0].segments[1].id,'s1');
});
test('stale revision prevents drifting to different index after wire split',()=>{
 const e=engine(),token=captureSegmentDrag(e.snapshot,'W','s1');
 e.state.wires[0].segments.splice(0,0,{id:'s-new',from_vertex_id:'v0',to_vertex_id:'v1'});
 e.state.revision++;
 const before=JSON.stringify(e.state);
 assert.throws(()=>commitSegmentDrag(e,token,3000,'drag-stale'),/STALE_REVISION/);
 assert.equal(JSON.stringify(e.state),before);
});
test('missing ID at unchanged revision fails rather than moving positional fallback',()=>{
 const e=engine(),token=captureSegmentDrag(e.snapshot,'W','s1');
 e.state.wires[0].segments[1].id='different';
 const before=JSON.stringify(e.state);
 assert.throws(()=>commitSegmentDrag(e,token,3000,'drag-missing'),/UNKNOWN_SEGMENT/);
 assert.equal(JSON.stringify(e.state),before);
});
test('edge segments and diagonal or zero-length inner segment rejected',()=>{
 const doc=make();
 assert.throws(()=>captureSegmentDrag(doc,'W','s0'),/PIN_ANCHOR_PROTECTED/);
 assert.throws(()=>captureSegmentDrag(doc,'W','s2'),/PIN_ANCHOR_PROTECTED/);
 doc.wires[0].vertices[2].at_um=[5000,0];
 assert.throws(()=>captureSegmentDrag(doc,'W','s1'),/ZERO_LENGTH_SEGMENT/);
 doc.wires[0].vertices[2].at_um=[6000,5000];
 assert.throws(()=>captureSegmentDrag(doc,'W','s1'),/NON_ORTHOGONAL/);
});
test('invalid or zero micrometre moves do not mutate document',()=>{
 const e=engine(),token=captureSegmentDrag(e.snapshot,'W','s1');
 const before=JSON.stringify(e.snapshot);
 for(const v of [0,.5,NaN,Infinity,1_000_000_001])
  assert.throws(()=>commitSegmentDrag(e,token,v,'drag'),/INVALID_DRAG_DELTA/);
 assert.equal(JSON.stringify(e.snapshot),before);
});
test('CAS is rechecked after mapping and before engine operation',()=>{
 const e=engine(),token=captureSegmentDrag(e.snapshot,'W','s1');
 e.newTransaction=()=>({base_revision:13,project_id:'toy',source_topology_hash:'sha-locked'});
 assert.throws(()=>commitSegmentDrag(e,token,3000,'drag-race'),/STALE_REVISION/);
});

test('foreign source lock and forged transaction reject without mutation',()=>{
 const e=engine(),token=captureSegmentDrag(e.snapshot,'W','s1');
 e.state.source_topology_hash='other';
 assert.throws(()=>commitSegmentDrag(e,token,3000,'bad'),/SOURCE_MISMATCH/);
 e.state.source_topology_hash='sha-locked';
 e.newTransaction=()=>({base_revision:12,project_id:'wrong',source_topology_hash:'sha-locked'});
 assert.throws(()=>commitSegmentDrag(e,token,3000,'bad'),/FOREIGN_TRANSACTION/);
 assert.equal(e.state.revision,12);
});
test('duplicate segment ID rejected and unsafe snapshot lacks source lock',()=>{
 const doc=make();doc.wires[0].segments[0].id='s1';
 assert.throws(()=>captureSegmentDrag(doc,'W','s1'),/DUPLICATE_SEGMENT|PIN_ANCHOR_PROTECTED/);
 const invalid=make();delete invalid.source_topology_hash;
 assert.throws(()=>captureSegmentDrag(invalid,'W','s1'),/INVALID_SNAPSHOT_IDENTITY/);
});
