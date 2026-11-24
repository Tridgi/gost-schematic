/** R3 model suite tests actual bundled domain modules, not a new parallel wire graph.
 * esbuild is already a locked Vite dependency. This bundle is transient and
 * exercises the same TypeScript code executed by the browser.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const temp=mkdtempSync(join(tmpdir(),'gscad-r3-domain-'));
process.on('exit',()=>rmSync(temp,{force:true,recursive:true}));
const bundle=join(temp,'authoring.mjs');
await build({
 entryPoints:[fileURLToPath(new URL('./session.ts',import.meta.url))],
 outfile:bundle,bundle:true,platform:'node',format:'esm',target:'node22',
 logLevel:'silent'
});
const {AuthoringSession,newBlankProject}=await import(pathToFileURL(bundle).href);
function newSession(){return new AuthoringSession(newBlankProject());}
function placePair(session){
 session.place(session.newTransaction('place-r'),'symbol/resistor.fixed',[100000,100000]);
 session.place(session.newTransaction('place-c'),'symbol/capacitor.fixed',[155000,100000]);
 const parts=Object.fromEntries(session.file.project.components.map(c=>[c.refdes,c.id]));
 return {r:parts.R1,c:parts.C1};
}
const pin=(id,number)=>({component_id:id,physical_pin_number:number});

test('empty project A3 uses DRAFT Python-source R/C library, no fabricated TL494 SHA',()=>{
 const doc=newBlankProject(),s=new AuthoringSession(doc);
 assert.equal(doc.format,'gscad-project');
 assert.equal(doc.project.components.length,0);
 assert.equal(doc.project.nets.length,0);
 assert.equal(s.snapshot.wires.length,0);
 assert.deepEqual(doc.project.sheets[0].frame.size_um,[420000,297000]);
 assert.equal(doc.project.provenance.status,'synthetic');
 assert.equal(doc.project.provenance.source_sha,'0'.repeat(40));
 assert.deepEqual(doc.project.symbol_definitions.map(x=>x.status),['draft','draft']);
 const resistor=doc.project.symbol_definitions.find(x=>x.id==='symbol/resistor.fixed');
 const capacitor=doc.project.symbol_definitions.find(x=>x.id==='symbol/capacitor.fixed');
 assert.deepEqual(resistor.pins.map(x=>x.at_um),[[-8000,0],[8000,0]]);
 assert.deepEqual(capacitor.graphics.map(x=>x.kind),['line','line','line','line']);
});

test('stale command CAS and duplicate refdes are rejected atomically',()=>{
 const s=newSession(),old=s.newTransaction('old');
 const {r,c}=placePair(s);
 const before=JSON.stringify(s.file);
 assert.throws(()=>s.place(old,'symbol/resistor.fixed',[20_000,20_000]),/STALE_REVISION/);
 const id=s.file.project.sheets[0].instances.find(x=>x.component_id===c).id;
 assert.throws(()=>s.updateProperty(s.newTransaction('duplicate'),id,'refdes','R1'),/DUPLICATE_REFDES/);
 assert.equal(JSON.stringify(s.file),before);
 assert.equal(s.snapshot.components.length,2);
 assert.notEqual(r,c);
});

test('real physical pin-to-pin Net is created once; Undo/Redo replaces full canonical model',()=>{
 const s=newSession(),{r,c}=placePair(s);
 const before=s.file;
 s.connect(s.newTransaction('connect'),pin(r,'2'),pin(c,'1'));
 const file=s.file;
 assert.equal(file.project.nets.length,1);
 assert.equal(file.project.sheets[0].wires.length,1);
 assert.deepEqual(file.project.nets[0].members,[pin(r,'2'),pin(c,'1')]);
 assert.equal(file.project.sheets[0].junctions.length,0);
 assert.deepEqual(file.project.sheets[0].instances,before.project.sheets[0].instances);
 assert.throws(()=>s.connect(s.newTransaction('bad'),pin(r,'2'),pin(c,'999')),/UNKNOWN_PIN/);
 assert.deepEqual(s.file,file);
 const stale=s.newTransaction('future');
 assert.equal(s.undo(),true);
 assert.deepEqual(s.file,before);
 assert.throws(()=>s.connect(stale,pin(r,'2'),pin(c,'1')),/STALE_REVISION/);
 assert.equal(s.redo(),true);
 assert.deepEqual(s.file,file);
});

test('two different user Nets never short at visual crossing or malformed physical PinRef',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.place(s.newTransaction('r2'),'symbol/resistor.fixed',[100000,150000]);
 s.place(s.newTransaction('c2'),'symbol/capacitor.fixed',[155000,150000]);
 const ids=Object.fromEntries(s.file.project.components.map(x=>[x.refdes,x.id]));
 s.connect(s.newTransaction('n1'),pin(r,'2'),pin(c,'1'));
 s.connect(s.newTransaction('n2'),pin(ids.R2,'2'),pin(ids.C2,'1'));
 const source=JSON.stringify(s.file);
 assert.throws(()=>s.connect(s.newTransaction('short'),pin(r,'2'),pin(ids.C2,'1')),/NET_CONFLICT/);
 assert.equal(JSON.stringify(s.file),source);
 assert.equal(s.file.project.nets.length,2);
 assert.equal(s.file.project.sheets[0].junctions.length,0);
});

test('deleting connected component requires route disposition; delete wire is separately Undoable',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.connect(s.newTransaction('route'),pin(r,'2'),pin(c,'1'));
 const wire=s.file.project.sheets[0].wires[0].id,connected=s.file;
 assert.throws(()=>s.deleteComponent(s.newTransaction('unsafe-remove'),r),/REROUTE_REQUIRED/);
 assert.deepEqual(s.file,connected);
 s.deleteWire(s.newTransaction('remove-route'),wire);
 assert.equal(s.file.project.sheets[0].wires.length,0);
 assert.equal(s.file.project.nets.length,1);
 s.deleteComponent(s.newTransaction('remove-c'),c);
 assert.equal(s.file.project.components.length,1);
 assert.equal(s.file.project.nets[0].members.length,1);
 assert.equal(s.undo(),true);
 assert.equal(s.file.project.components.length,2);
 assert.equal(s.undo(),true);
 assert.deepEqual(s.file,connected);
});

test('serialized user project refuses spoofed source, duplicate IDs, duplicate layer and invalid µm',()=>{
 const s=newSession();placePair(s);
 const d=s.file;
 const cases=[
   f=>{f.project.provenance.source_sha='e695c415fdced164b0e0c39c5249d030795a0aa6';},
   f=>{f.project.components[1].id=f.project.components[0].id;},
   f=>{f.project.components[1].refdes='R1';},
   f=>{f.project.sheets[0].instances[0].origin_um=[1.25,0];},
   f=>{f.project.sheets[0].layers.push(structuredClone(f.project.sheets[0].layers[0]));}
 ];
 for(const mutate of cases){
   const forged=structuredClone(d);mutate(forged);
   assert.throws(()=>new AuthoringSession(forged));
 }
 assert.deepEqual(s.file,d);
});


test('R5: removing an early Net cannot duplicate a surviving Net name on the next connection',()=>{
 const s=newSession();
 for(let i=0;i<3;i++){
   s.place(s.newTransaction('place-r-'+i),'symbol/resistor.fixed',[100000,50000+i*60000]);
   s.place(s.newTransaction('place-c-'+i),'symbol/capacitor.fixed',[155000,50000+i*60000]);
 }
 const ids=Object.fromEntries(s.file.project.components.map(c=>[c.refdes,c.id]));
 s.connect(s.newTransaction('net-1'),pin(ids.R1,'2'),pin(ids.C1,'1'));
 s.connect(s.newTransaction('net-2'),pin(ids.R2,'2'),pin(ids.C2,'1'));
 const initial=s.file;
 assert.deepEqual(initial.project.nets.map(n=>n.name),['N1','N2']);
 const firstId=initial.project.nets[0].id;
 const firstWire=initial.project.sheets[0].wires.find(w=>w.net_id===firstId);
 assert.ok(firstWire);
 s.deleteWire(s.newTransaction('unroute-net-1'),firstWire.id);
 s.deleteComponent(s.newTransaction('delete-r1'),ids.R1);
 s.deleteComponent(s.newTransaction('delete-c1'),ids.C1);
 assert.deepEqual(s.file.project.nets.map(n=>n.name),['N2']);
 s.connect(s.newTransaction('net-3'),pin(ids.R3,'2'),pin(ids.C3,'1'));
 const names=s.file.project.nets.map(n=>n.name);
 assert.equal(new Set(names).size,names.length,'all user-authored Net names must be unique');
 assert.equal(s.file.project.nets.length,2);
 assert.deepEqual(s.file.project.nets[0].members,[pin(ids.R2,'2'),pin(ids.C2,'1')]);
});

test('R5: imported synthetic ProjectV2 refuses duplicate Net names despite distinct Net IDs',()=>{
 const s=newSession();
 for(let i=0;i<2;i++){
   s.place(s.newTransaction('r-'+i),'symbol/resistor.fixed',[100000,60000+i*80000]);
   s.place(s.newTransaction('c-'+i),'symbol/capacitor.fixed',[155000,60000+i*80000]);
 }
 const ids=Object.fromEntries(s.file.project.components.map(c=>[c.refdes,c.id]));
 s.connect(s.newTransaction('n1'),pin(ids.R1,'2'),pin(ids.C1,'1'));
 s.connect(s.newTransaction('n2'),pin(ids.R2,'2'),pin(ids.C2,'1'));
 const forged=s.file,original=JSON.stringify(forged);
 forged.project.nets[1].name=forged.project.nets[0].name;
 assert.notEqual(forged.project.nets[0].id,forged.project.nets[1].id);
 assert.throws(()=>new AuthoringSession(forged),/DUPLICATE_NET_NAME/);
 assert.equal(JSON.stringify(s.file),original,'invalid import must not mutate original session');
});

test('R5: unplaced catalogue parts cannot declare duplicate physical pin numbers',()=>{
 const forged=newBlankProject();
 const part=forged.project.part_definitions[0];
 part.physical_pins.push(structuredClone(part.physical_pins[0]));
 assert.throws(()=>new AuthoringSession(forged),/DUPLICATE_PHYSICAL_PIN/);
});


test('R5: unplaced symbol catalogue rejects duplicate and unknown physical PinRefs',()=>{
 const duplicate=newBlankProject();
 const symbol=duplicate.project.symbol_definitions[0];
 symbol.pins.push(structuredClone(symbol.pins[0]));
 assert.throws(()=>new AuthoringSession(duplicate),/DUPLICATE_SYMBOL_PIN/);
 const unknown=newBlankProject();
 unknown.project.symbol_definitions[1].pins[0].physical_pin_number='999';
 assert.throws(()=>new AuthoringSession(unknown),/UNKNOWN_PIN/);
});


test('R6: two independent Nets and two A3 sheets survive ProjectV2 reopen with identical Python digest',()=>{
 const session=newSession();
 for(let i=0;i<2;i++){
  session.place(session.newTransaction('r'+i),'symbol/resistor.fixed',[80000,65000+i*85000]);
  session.place(session.newTransaction('c'+i),'symbol/capacitor.fixed',[150000,65000+i*85000]);
 }
 const ids=Object.fromEntries(session.file.project.components.map(c=>[c.refdes,c.id]));
 session.connect(session.newTransaction('wire-one'),pin(ids.R1,'2'),pin(ids.C1,'1'));
 session.connect(session.newTransaction('wire-two'),pin(ids.R2,'2'),pin(ids.C2,'1'));
 const second= session.addSheet(session.newTransaction('new-a3-sheet'));
 session.selectSheet(session.newTransaction('switch-to-second'),second);
 session.place(session.newTransaction('part-second-sheet'),'symbol/resistor.fixed',[95000,90000]);
 const saved=JSON.parse(JSON.stringify(session.file));
 assert.equal(saved.project.sheets.length,2);
 assert.deepEqual(saved.project.sheets.map(s=>s.frame.size_um),[
  [420000,297000],[420000,297000]]);
 assert.equal(saved.project.nets.length,2);
 assert.equal(saved.project.sheets[0].wires.length,2);
 assert.equal(saved.project.sheets[1].instances.length,1);
 assert.equal(saved.project.sheets[1].wires.length,0);
 assert.equal(new Set(saved.project.nets.map(n=>n.name)).size,2);
 assert.equal(saved.project.nets.flatMap(n=>n.members).length,4);
 const pythonDigest=doc=>{
  const py=spawnSync('python',['-c',
   'import json,sys;sys.path.insert(0,"../..");from ui.editor.src.model.contract import validate,digest;d=json.loads(sys.stdin.buffer.read().decode("utf-8"));validate(d);print(digest(d))'
  ],{input:JSON.stringify(doc),encoding:'utf8',timeout:20000});
  assert.equal(py.status,0,py.stderr);
  assert.match(py.stdout,/^[0-9a-f]{64}\s*$/);
  return py.stdout.trim();
 };
 const originalHash=pythonDigest(saved);
 const reopened=new AuthoringSession(JSON.parse(JSON.stringify(saved)));
 assert.deepEqual(reopened.file,saved);
 assert.equal(pythonDigest(reopened.file),originalHash);
 assert.deepEqual(reopened.file.project.nets.map(n=>[n.id,n.name,n.members]),
   saved.project.nets.map(n=>[n.id,n.name,n.members]));
 assert.deepEqual(reopened.file.project.sheets.map(s=>s.wires),
   saved.project.sheets.map(s=>s.wires));
 assert.deepEqual(reopened.file.project.sheets.map(s=>s.instances),
   saved.project.sheets.map(s=>s.instances));
 assert.equal(reopened.file.workspace.active_sheet_id,second);
});

test('R9: native serde_json key ordering preserves authored components, wire and count identity',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.place(s.newTransaction('r9-spare'),'symbol/resistor.fixed',[210000,150000]);
 s.connect(s.newTransaction('r9-route'),pin(r,'2'),pin(c,'1'));
 const authored=s.file;
 const normalize=value=>Array.isArray(value)?value.map(normalize):
  value&&typeof value==='object'
   ?Object.fromEntries(Object.keys(value).sort().map(k=>[k,normalize(value[k])]))
   :value;
 const nativeReload=JSON.parse(JSON.stringify(normalize(authored)));
 assert.notEqual(
  JSON.stringify(nativeReload.project.provenance.expected_counts),
  JSON.stringify(authored.project.provenance.expected_counts),
  'test must reproduce the native lexical serialization key order'
 );
 const reopened=new AuthoringSession(nativeReload);
 assert.deepEqual(reopened.file,nativeReload);
 assert.deepEqual(reopened.file.project.nets,authored.project.nets);
 assert.deepEqual(reopened.file.project.sheets[0].wires,authored.project.sheets[0].wires);
 assert.deepEqual(reopened.file.project.components,authored.project.components);
 assert.equal(reopened.snapshot.wires.length,1);
 const forged=structuredClone(nativeReload);
 forged.project.provenance.expected_counts.nets=0;
 assert.throws(()=>new AuthoringSession(forged),/SOURCE_COUNT_MISMATCH/);
 const extra=structuredClone(nativeReload);
 extra.project.provenance.expected_counts.unexpected=0;
 assert.throws(()=>new AuthoringSession(extra),/SOURCE_COUNT_MISMATCH/);
});


test('R10: A4/A3/A2 physical paper is exact µm and undoable without editing signed Nets',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.connect(s.newTransaction('initial-net'),pin(r,'2'),pin(c,'1'));
 const original=s.file;
 const net=structuredClone(original.project.nets);
 const wires=structuredClone(original.project.sheets[0].wires);
 const oldRevision=s.revision;
 s.setPaper(s.newTransaction('paper-a4'),'A4');
 assert.deepEqual(s.file.project.sheets[0].frame,{size_um:[297000,210000],margin_um:10000,paper:'A4 landscape'});
 assert.equal(s.revision,oldRevision+1);
 s.setPaper(s.newTransaction('paper-a2'),'A2');
 assert.deepEqual(s.file.project.sheets[0].frame.size_um,[594000,420000]);
 assert.deepEqual(s.file.project.nets,net);
 assert.deepEqual(s.file.project.sheets[0].wires,wires);
 const last=s.file;
 assert.throws(()=>s.setPaper(s.newTransaction('repeat'),'A2'),/NO_CHANGE/);
 assert.throws(()=>s.setPaper(s.newTransaction('bad'),'A1'),/UNKNOWN_PAPER/);
 assert.deepEqual(s.file,last);
 assert.equal(s.undo(),true);
 assert.equal(s.file.project.sheets[0].frame.paper,'A4 landscape');
 assert.equal(s.undo(),true);
 assert.deepEqual(s.file,original);
 assert.equal(s.redo(),true);
 assert.equal(s.redo(),true);
 assert.deepEqual(s.file,last);
 assert.deepEqual(s.file.project.nets,net);
});


test('R10: two physical wires reanchor on consented move, preserve distinct Nets and Undo/Redo/reopen',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.place(s.newTransaction('place-r2'),'symbol/resistor.fixed',[55000,150000]);
 const r2=s.file.project.components.find(x=>x.refdes==='R2').id;
 s.connect(s.newTransaction('net-right'),pin(r,'2'),pin(c,'1'));
 s.connect(s.newTransaction('net-left'),pin(r2,'2'),pin(r,'1'));
 const before=s.file;
 assert.equal(before.project.nets.length,2);
 assert.equal(before.project.sheets[0].wires.length,2);
 assert.throws(()=>s.move(s.newTransaction('unapproved'),r,[110000,110000]),
   error=>error.code==='REROUTE_REQUIRED');
 assert.deepEqual(s.file,before);
 const stale=s.newTransaction('stale-before-move');
 s.move(s.newTransaction('consented'),r,[110000,110000],true);
 const after=s.file;
 assert.deepEqual(after.project.nets.map(({id,name,members})=>({id,name,members})),
   before.project.nets.map(({id,name,members})=>({id,name,members})));
 assert.ok(after.project.nets.every(n=>n.route_status==='partial'));
 assert.deepEqual(after.project.components,before.project.components);
 assert.equal(after.project.sheets[0].wires.length,2);
 const originalAnchors=Object.fromEntries(before.project.sheets[0].wires.map(w=>
   [w.id,[w.vertices[0].anchor,w.vertices.at(-1).anchor]]));
 for(const w of after.project.sheets[0].wires){
   assert.deepEqual([w.vertices[0].anchor,w.vertices.at(-1).anchor],originalAnchors[w.id]);
   assert.equal(w.needs_routing_review,true);
   for(const seg of w.segments){
     const a=w.vertices.find(v=>v.id===seg.from_vertex_id).at_um;
     const b=w.vertices.find(v=>v.id===seg.to_vertex_id).at_um;
     assert.ok(a[0]===b[0]||a[1]===b[1]);
   }
   for(const endpoint of [w.vertices[0],w.vertices.at(-1)]){
     if(endpoint.anchor.kind==='pin')
       assert.deepEqual(endpoint.at_um,s.beginWire(endpoint.anchor).at_um);
   }
 }
 assert.throws(()=>s.move(stale,r,[115000,115000],true),/STALE_REVISION/);
 assert.equal(s.undo(),true);
 assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);
 assert.deepEqual(s.file,after);
 const loaded=new AuthoringSession(after);
 assert.deepEqual(loaded.file,after);
 assert.deepEqual(loaded.file.project.nets,after.project.nets);
});


test('R10: connected 90-degree rotation reanchors each physical pin, fails closed before consent',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.place(s.newTransaction('r2'),'symbol/resistor.fixed',[55000,150000]);
 const r2=s.file.project.components.find(x=>x.refdes==='R2').id;
 s.connect(s.newTransaction('wire-one'),pin(r,'2'),pin(c,'1'));
 s.connect(s.newTransaction('wire-two'),pin(r2,'2'),pin(r,'1'));
 const baseline=s.file;
 assert.throws(()=>s.rotate(s.newTransaction('deny-turn'),r),
   e=>e.code==='REROUTE_REQUIRED');
 assert.deepEqual(s.file,baseline);
 s.rotate(s.newTransaction('permit-turn'),r,true);
 const rotated=s.file;
 const original=Object.fromEntries(baseline.project.sheets[0].wires.map(w=>
   [w.id,[w.vertices[0].anchor,w.vertices.at(-1).anchor]]));
 const moved=rotated.project.sheets[0].instances.find(i=>i.component_id===r);
 assert.equal(moved.rotation_deg,90);
 assert.equal(rotated.project.nets.length,2);
 assert.ok(rotated.project.nets.every(n=>n.route_status==='partial'));
 assert.deepEqual(rotated.project.nets.map(n=>n.members),baseline.project.nets.map(n=>n.members));
 assert.equal(rotated.project.sheets[0].wires.length,2);
 for(const w of rotated.project.sheets[0].wires){
   assert.deepEqual([w.vertices[0].anchor,w.vertices.at(-1).anchor],original[w.id]);
   assert.equal(w.needs_routing_review,true);
   for(const end of [w.vertices[0],w.vertices.at(-1)])if(end.anchor.kind==='pin')
     assert.deepEqual(end.at_um,s.beginWire(end.anchor).at_um);
 }
 assert.equal(s.undo(),true);assert.deepEqual(s.file,baseline);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,rotated);
 assert.deepEqual(new AuthoringSession(rotated).file,rotated);
});

test('clipboard duplicates component attributes but never its physical Net membership',()=>{
 const s=newSession(),{r,c}=placePair(s);
 const inst=s.file.project.sheets[0].instances.find(i=>i.component_id===r);
 s.updateProperty(s.newTransaction('value'),inst.id,'value','47к');
 // Copy connected C1 separately; its wire must not be inherited by a pasted C2.
 s.connect(s.newTransaction('connect'),pin(r,'2'),pin(c,'1'));
 const before=s.file;
 const source=before.project.sheets[0].instances.find(i=>i.component_id===c);
 const template=s.copyComponent(source.id);
 const stale=s.newTransaction('stale');
 const added=s.pasteComponent(s.newTransaction('paste-c'),template,[180000,120000]);
 const after=s.file,copy=after.project.sheets[0].instances.find(i=>i.id===added);
 const comp=after.project.components.find(c=>c.id===copy.component_id);
 assert.notEqual(copy.component_id,source.component_id);
 assert.notEqual(copy.id,source.id);
 assert.equal(comp.refdes,'C2');
 assert.equal(comp.source_refdes,'C2');
 assert.equal(comp.value,template.value);
 assert.deepEqual(after.project.nets,before.project.nets);
 assert.deepEqual(after.project.sheets[0].wires,before.project.sheets[0].wires);
 assert.deepEqual(after.project.sheets[0].junctions,before.project.sheets[0].junctions);
 assert.equal(after.project.provenance.expected_counts.components,3);
 assert.throws(()=>s.pasteComponent(stale,template,[200000,150000]),/STALE_REVISION/);
 assert.throws(()=>s.pasteComponent(s.newTransaction('invalid'),{...template,rotation_deg:45},[200000,150000]),/INVALID_CLIPBOARD/);
 assert.deepEqual(s.file,after);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,after);
 assert.deepEqual(new AuthoringSession(after).file,after);
});

test('detached clipboard retains value/rotation after source changes; fresh refdes on another sheet',()=>{
 const s=newSession();
 const id=s.place(s.newTransaction('r'),'symbol/resistor.fixed',[100000,100000]);
 const component=s.file.project.components[0];
 s.updateProperty(s.newTransaction('value'),id,'value','47к');
 s.rotate(s.newTransaction('rotate'),component.id);
 const template=s.copyComponent(id);
 s.updateProperty(s.newTransaction('rename'),id,'refdes','R10');
 s.updateProperty(s.newTransaction('new-value'),id,'value','10к');
 const sheet=s.addSheet(s.newTransaction('sheet'));
 s.selectSheet(s.newTransaction('switch'),sheet);
 assert.throws(()=>s.copyComponent(id),/UNKNOWN_INSTANCE/);
 const pasted=s.pasteComponent(s.newTransaction('paste'),template,[80000,90000]);
 const file=s.file,instance=file.project.sheets[1].instances[0];
 assert.equal(instance.id,pasted);
 assert.equal(instance.rotation_deg,90);
 assert.equal(instance.layer_id,file.project.sheets[1].layers[0].id);
 assert.equal(file.project.components[1].refdes,'R2');
 assert.equal(file.project.components[1].value,'47к');
 assert.equal(file.project.nets.length,0);
});

test('repeated paste near sheet edge stays inside print margins with unique grid-aligned origins',()=>{
 const s=newSession();
 const id=s.place(s.newTransaction('edge'),'symbol/resistor.fixed',[395000,275000]);
 const template=s.copyComponent(id);
 let anchor=template.origin_um;
 const seen=new Set([anchor.join(',')]);
 for(let i=0;i<12;i++){
  const before=s.file,rev=s.revision;
  const p=s.suggestPasteOrigin(template,anchor,true);
  assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
  assert.equal(p[0]%1000,0);assert.equal(p[1]%1000,0);
  assert.ok(p[0]>=18000&&p[0]<=402000);
  assert.ok(p[1]>=12000&&p[1]<=285000);
  assert.ok(!seen.has(p.join(',')));seen.add(p.join(','));
  s.pasteComponent(s.newTransaction('paste-edge'),template,p);
  anchor=p;
 }
 assert.equal(s.file.project.components.length,13);
 assert.deepEqual(s.file.project.nets,[]);
 assert.deepEqual(s.file.project.sheets[0].wires,[]);
});

test('R13 group move is one reversible CAS transaction and rejects attached Nets atomically',()=>{
 const s=newSession(),{r,c}=placePair(s);
 const before=s.file;
 const ids=before.project.sheets[0].instances.map(i=>i.id);
 const stale=s.newTransaction('stale');
 s.moveGroup(s.newTransaction('group'),ids,[5000,10000]);
 const after=s.file;
 assert.deepEqual(after.project.sheets[0].instances.map(i=>i.origin_um),[[105000,110000],[160000,110000]]);
 assert.deepEqual(after.project.components,before.project.components);
 assert.deepEqual(after.project.nets,before.project.nets);
 assert.throws(()=>s.moveGroup(stale,ids,[1000,1000]),/STALE_REVISION/);
 assert.throws(()=>s.moveGroup(s.newTransaction('bad'),[ids[0],ids[0]],[1000,1000]),/INVALID_GROUP/);
 assert.throws(()=>s.moveGroup(s.newTransaction('unknown'),[ids[0],'unknown'],[1000,1000]),/UNKNOWN_INSTANCE/);
 assert.deepEqual(s.file,after);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,after);
 s.connect(s.newTransaction('connect'),pin(r,'2'),pin(c,'1'));
 const connected=s.file,revision=s.revision;
 assert.throws(()=>s.moveGroup(s.newTransaction('connected'),ids,[1000,1000]),/GROUP_REROUTE_REQUIRED/);
 assert.equal(s.revision,revision);assert.deepEqual(s.file,connected);
});
