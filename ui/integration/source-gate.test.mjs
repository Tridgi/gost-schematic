import test from "node:test";
import assert from "node:assert/strict";
import {auditCandidateV2,SOURCE_SHA} from "./source-gate.mjs";
const ref=(component_id,physical_pin_number)=>({component_id,physical_pin_number});
function toy(){return {format:"gscad-project",format_version:2,project:{
 components:[{id:"a",source_refdes:"R1"},{id:"b",source_refdes:"C1"}],
 nets:[{id:"N",members:[ref("a","1"),ref("b","2")],route_status:"partial"}],
 sheets:[{id:"S",instances:[],junctions:[],splices:[],graphics:[],wires:[{id:"W",net_id:"N",
 vertices:[{id:"v1",at_um:[1000,2000],anchor:{kind:"pin",...ref("a","1")}},
 {id:"v2",at_um:[5000,2000],anchor:{kind:"bend"}},
 {id:"v3",at_um:[5000,9000],anchor:{kind:"bend"}},
 {id:"v4",at_um:[9000,9000],anchor:{kind:"pin",...ref("b","2")}}],
 segments:[{id:"s1",from_vertex_id:"v1",to_vertex_id:"v2"},
 {id:"s2",from_vertex_id:"v2",to_vertex_id:"v3"},
 {id:"s3",from_vertex_id:"v3",to_vertex_id:"v4"}]}]}],
 provenance:{source_sha:"SYNTHETIC_FIXTURE"}}};}
const modify=f=>{const t=toy();f(t.project);return t;};
const world=a=>a.component_id==="a"?[1000,2000]:[9000,9000];
test("typed toy structural gate",()=>assert.equal(auditCandidateV2(toy(),{pinWorld:world}).counts.memberships,2));
test("R0 format must not be downcast",()=>assert.throws(()=>auditCandidateV2({format:"gscad-spike",version:1}),/UNSUPPORTED_SCHEMA/));
test("future schema rejected",()=>assert.throws(()=>auditCandidateV2({...toy(),format_version:3}),/UNSUPPORTED_SCHEMA/));
test("duplicate PinRef in two source nets rejected",()=>assert.throws(()=>auditCandidateV2(modify(p=>p.nets.push({id:"K",members:[ref("a","1")]}))),/DUPLICATE_PIN_OWNERSHIP/));
test("wrong net rejected",()=>assert.throws(()=>auditCandidateV2(modify(p=>p.sheets[0].wires[0].net_id="foreign")),/INVALID_WIRE/));
test("1um drift rejected",()=>assert.throws(()=>auditCandidateV2(modify(p=>p.sheets[0].wires[0].vertices[0].at_um[0]++),{pinWorld:world}),/PIN_DRIFT/));
test("diagonal rejected",()=>assert.throws(()=>auditCandidateV2(modify(p=>p.sheets[0].wires[0].vertices[1].at_um[1]++)),/NON_ORTHOGONAL/));
test("zero length rejected",()=>assert.throws(()=>auditCandidateV2(modify(p=>p.sheets[0].wires[0].vertices[1].at_um=[1000,2000])),/NON_ORTHOGONAL/));
test("false T junction rejected",()=>assert.throws(()=>auditCandidateV2(modify(p=>p.sheets[0].junctions.push({id:"J",net_id:"N",at_um:[5000,2000]}))),/ORPHAN_JUNCTION/));
test("non electrical b cannot claim Net",()=>assert.throws(()=>auditCandidateV2(modify(p=>p.sheets[0].graphics.push({kind:"source_b_continuation",electrical:true}))),/NON_ELECTRICAL_GRAPHIC/));
test("identical free endpoint IDs rejected",()=>assert.throws(()=>auditCandidateV2(modify(p=>{const v=p.sheets[0].wires[0].vertices;v[0].anchor={kind:"free",free_id:"f"};v[3].anchor={kind:"free",free_id:"f"};})),/FREE_ENDPOINT_ID/));
test("toy cannot masquerade as frozen source",()=>assert.throws(()=>auditCandidateV2(toy(),{requireFrozen:true}),/FROZEN_SHA_MISMATCH/));
test("empty sheets rejected",()=>assert.throws(()=>auditCandidateV2(modify(p=>p.sheets=[])),/EMPTY_PROJECT/));
test("duplicate sheets rejected",()=>assert.throws(()=>auditCandidateV2(modify(p=>p.sheets.push(structuredClone(p.sheets[0])))),/DUPLICATE_SHEET/));
test("source lock SHA is fixed",()=>assert.equal(SOURCE_SHA,"e695c415fdced164b0e0c39c5249d030795a0aa6"));
