import test from 'node:test';
import assert from 'node:assert/strict';
import {auditCandidateV2} from '../../integration/source-gate.mjs';
const p=(component_id,physical_pin_number)=>({component_id,physical_pin_number});
const pin=(component_id,physical_pin_number)=>({kind:'pin',component_id,physical_pin_number});
const j=(junction_id)=>({kind:'junction',junction_id});
const f=(free_id)=>({kind:'free',free_id});
const wire=(id,net_id,from,to,fromA,toA)=>({id,net_id,layer_id:'E',mode:'orthogonal',vertices:[
 {id:'v0',at_um:from,anchor:fromA}, {id:'v1',at_um:to,anchor:toA}],segments:[{id:'s',from_vertex_id:'v0',to_vertex_id:'v1'}]});
const project=(components,nets,wires,junctions=[])=>({format:'gscad-project',format_version:2,project:{components,nets,sheets:[{id:'S1',instances:[],graphics:[],splices:[],junctions,wires}]}});

test('FAIL-GATE: authored Junction on foreign-Net backbone must reject JUNCTION_CROSSES_FOREIGN_NET',()=>{
 const sample=project(
  [{id:'a'},{id:'b'},{id:'c'},{id:'d'}],
  [{id:'NA',members:[p('a','1'),p('b','1')]},{id:'NB',members:[p('c','1'),p('d','1')]}],
  [wire('A1','NA',[0,0],[10_000,0],pin('a','1'),j('J')),
   wire('A2','NA',[10_000,0],[20_000,0],j('J'),pin('b','1')),
   wire('B','NB',[10_000,-10_000],[10_000,10_000],pin('c','1'),pin('d','1'))],
  [{id:'J',net_id:'NA',layer_id:'E',at_um:[10_000,0]}]
 );
 // Contract ui/contracts/manual-wire-v2.md: visible Junction cannot cross FOREIGN Net.
 assert.throws(()=>auditCandidateV2(sample),/JUNCTION_CROSSES_FOREIGN_NET/);
});

test('FAIL-GATE: PinRef tuple collision must not fabricate membership in declared Net',()=>{
 // key(component,pin) joins strings by colon and is not injective.
 const sample=project(
  [{id:'a:b'},{id:'a'}],
  [{id:'N',members:[p('a:b','c')]}],
  [wire('W','N',[0,0],[10_000,0],pin('a','b:c'),f('f1'))]
 );
 // A pin on component `a` / pin `b:c` is NOT declared in N. It only
 // shares the lossy joined string "a:b:c" with component `a:b` / pin `c`.
 assert.throws(()=>auditCandidateV2(sample),/PIN_NET_MISMATCH/);
});
test('FAIL-GATE: graphic source-b with net_id never becomes an electrical connection',()=>{
 const sample=project([{id:'a'},{id:'b'}],[{id:'N',members:[p('a','1'),p('b','1')]}],[]);
 sample.project.sheets[0].graphics.push({
   id:'b',layer_id:'D',kind:'source_b_continuation',
   points_um:[[0,0],[1000,0]],stroke_um:300,net_id:'N'
 });
 assert.throws(()=>auditCandidateV2(sample),/NON_ELECTRICAL_GRAPHIC/);
});
test('FAIL-GATE: empty physical component and pin identifiers rejected',()=>{
 const c=project([{id:''}],[{id:'N',members:[p('','1')]}],[]);
 assert.throws(()=>auditCandidateV2(c),/DUPLICATE_COMPONENT/);
 const d=project([{id:'a'}],[{id:'N',members:[p('a','')]}],[]);
 assert.throws(()=>auditCandidateV2(d),/INVALID_PINREF/);
});
