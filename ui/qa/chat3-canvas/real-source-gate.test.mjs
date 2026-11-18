/** Direct, source-backed negative review of MASTER's STRUCTURAL_ONLY preflight.
 * Expected fail at SHA 44dc17d9... until #125 fixes foreign-Net junctions and source-b.
 * Not an authoritative replacement for #122 Python ProjectV2 validator.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {auditCandidateV2} from '../../integration/source-gate.mjs';
const fixture=()=>JSON.parse(readFileSync(new URL('../../fixtures/toy-v2.gscad.json',import.meta.url),'utf8'));
const frozen=()=>JSON.parse(readFileSync(new URL('../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));

test('real toy-v2 two nets crossing without junction is still only structural',()=>{
  const f=fixture();const before=JSON.stringify(f);
  const result=auditCandidateV2(f);
  assert.equal(result.status,'STRUCTURAL_ONLY');
  assert.equal(result.counts.nets,2);
  assert.equal(JSON.stringify(f),before);
});
test('original E695 unrouted inventory stays 23/15/62 and non-electrical b',()=>{
  const f=frozen();const result=auditCandidateV2(f,{requireFrozen:true});
  assert.equal(result.status,'STRUCTURAL_ONLY');
  assert.deepEqual([result.counts.components,result.counts.nets,result.counts.memberships,result.counts.wires],[23,15,62,0]);
  assert.equal(f.project.sheets[0].graphics.filter(g=>g.kind==='source_b_continuation').length,2);
});
test('explicit Junction on a different-Net X must fail closed',()=>{
  const f=fixture(),sheet=f.project.sheets[0];
  const original=sheet.wires[0],source=structuredClone(original.vertices[0]),target=structuredClone(original.vertices.at(-1));
  const at_um=[50000,30000],junction_id='foreign-X-junction',anchor={kind:'junction',junction_id};
  const j=(id)=>({id,at_um:[...at_um],anchor:{...anchor}});
  sheet.junctions.push({id:junction_id,net_id:original.net_id,layer_id:original.layer_id,at_um});
  sheet.wires[0]={...original,id:original.id+':left',vertices:[source,j('v-left')],segments:[{id:'seg-left',from_vertex_id:source.id,to_vertex_id:'v-left'}]};
  sheet.wires.push({...original,id:original.id+':right',vertices:[j('v-right'),target],segments:[{id:'seg-right',from_vertex_id:'v-right',to_vertex_id:target.id}]});
  // Foreign vertical Net passes through [50000,30000] but must not become electrically contacted.
  assert.throws(()=>auditCandidateV2(f),/JUNCTION_CROSSES_FOREIGN_NET|NET_CONFLICT/);
});
test('source b graphic cannot carry an electrical net_id, even when electrical flag omitted',()=>{
  const f=frozen(),g=f.project.sheets[0].graphics[0];g.net_id=f.project.nets[0].id;
  assert.throws(()=>auditCandidateV2(f),/NON_ELECTRICAL_GRAPHIC/);
});
