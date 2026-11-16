import test from 'node:test';
import assert from 'node:assert/strict';
import {selectMovableSegment,moveSelectedSegment} from './segment-id-command-adapter.mjs';
function fake(ids=['lead','vertical-middle','tail']) {
  const state={calls:[],snapshot:{revision:7,project_id:'P',source_topology_hash:'locked',wires:[{id:'W',segments:ids.map(id=>({id}))}]}};
  const engine={get snapshot(){return structuredClone(state.snapshot)},newTransaction(command_id){return {base_revision:state.snapshot.revision,project_id:'P',source_topology_hash:'locked',command_id}},moveSegment(...args){state.calls.push(args);return 'COMMITTED'}};
  return {engine,state};
}
test('real hit -> stable segment ID -> index at current CAS revision',()=>{
 const hit={kind:'segment',movable:true,wire_id:'W',segment_id:'vertical-middle'};
 const selection=selectMovableSegment(hit),{engine,state}=fake();
 assert.deepEqual(selection,{wire_id:'W',segment_id:'vertical-middle'});
 assert.equal(moveSelectedSegment(engine,selection,3000,7,'cmd1'),'COMMITTED');
 assert.equal(state.calls.length,1);
 assert.equal(state.calls[0][2],1); assert.equal(state.calls[0][3],3000);
});
test('nonmovable lead or ambiguous overlapping hits refuse mutation',()=>{
 for(const hit of [null,{kind:'ambiguous-segment',candidates:[]},{kind:'pin'},{kind:'segment',movable:false,wire_id:'W',segment_id:'lead'}])
   assert.throws(()=>selectMovableSegment(hit),/NOT_MOVABLE_SEGMENT/);
});
test('stale revision cannot silently move a different indexed segment',()=>{
 const {engine,state}=fake(['lead','new-bend','vertical-middle','tail']);
 assert.throws(()=>moveSelectedSegment(engine,{wire_id:'W',segment_id:'vertical-middle'},3000,6,'cmd2'),/STALE_REVISION/);
 assert.equal(state.calls.length,0);
 assert.equal(moveSelectedSegment(engine,{wire_id:'W',segment_id:'vertical-middle'},3000,7,'cmd3'),'COMMITTED');
 assert.equal(state.calls[0][2],2);
});
test('unknown, duplicate or endpoint segment ID fails closed',()=>{
 const {engine,state}=fake();
 for(const segment_id of ['unknown','lead','tail'])
  assert.throws(()=>moveSelectedSegment(engine,{wire_id:'W',segment_id},1000,7,'cmd'),/UNKNOWN_SEGMENT|PIN_ANCHOR_PROTECTED/);
 assert.equal(state.calls.length,0);
});
test('overflow/float/zero displacement and mismatched source lock rejected',()=>{
 const {engine,state}=fake();
 for(const n of [0,1.25,1_000_000_001,Infinity])
  assert.throws(()=>moveSelectedSegment(engine,{wire_id:'W',segment_id:'vertical-middle'},n,7,'cmd'));
 const foreign={...engine,newTransaction:()=>({base_revision:7,project_id:'P',source_topology_hash:'different'})};
 assert.throws(()=>moveSelectedSegment(foreign,{wire_id:'W',segment_id:'vertical-middle'},1000,7,'cmd'),/STALE_OR_FOREIGN_TRANSACTION/);
 assert.equal(state.calls.length,0);
});