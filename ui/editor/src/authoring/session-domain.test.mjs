/** R3 model suite tests actual bundled domain modules, not a new parallel wire graph.
 * esbuild is already a locked Vite dependency. This bundle is transient and
 * exercises the same TypeScript code executed by the browser.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {spawnSync} from 'node:child_process';
import {mkdtempSync,rmSync,readdirSync,readFileSync} from 'node:fs';
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
 assert.equal(doc.project.symbol_definitions.length,36);
 assert.ok(doc.project.symbol_definitions.every(x=>x.status==='draft'));
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

test('R14: connected group translates internal wire exactly and reanchors external wire in one undo',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.place(s.newTransaction('r2'),'symbol/resistor.fixed',[210000,100000]);
 const third=s.file.project.components.find(x=>x.refdes==='R2').id;
 s.connect(s.newTransaction('internal'),pin(r,'2'),pin(c,'1'));
 s.connect(s.newTransaction('external'),pin(c,'2'),pin(third,'1'));
 const before=s.file,rev=s.revision;
 const group=before.project.sheets[0].instances.filter(i=>[r,c].includes(i.component_id)).map(i=>i.id);
 assert.throws(()=>s.moveGroup(s.newTransaction('no-consent'),group,[5000,10000]),/GROUP_REROUTE_REQUIRED/);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 s.moveGroup(s.newTransaction('connected-group'),group,[5000,10000],true);
 const after=s.file,old=before.project.sheets[0],now=after.project.sheets[0];
 assert.equal(s.revision,rev+1);
 assert.deepEqual(after.project.components,before.project.components);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.name,n.members]),before.project.nets.map(n=>[n.id,n.name,n.members]));
 assert.deepEqual(now.instances.find(i=>i.component_id===third),old.instances.find(i=>i.component_id===third));
 assert.deepEqual(now.junctions,old.junctions);assert.deepEqual(now.splices,old.splices);
 for(const wire of now.wires){
  const prior=old.wires.find(w=>w.id===wire.id);
  assert.equal(wire.net_id,prior.net_id);assert.equal(wire.layer_id,prior.layer_id);
  assert.equal(wire.needs_routing_review,true);
  assert.deepEqual(wire.vertices[0].anchor,prior.vertices[0].anchor);
  assert.deepEqual(wire.vertices.at(-1).anchor,prior.vertices.at(-1).anchor);
  assert.ok(wire.vertices.slice(1).every((v,i)=>v.at_um[0]===wire.vertices[i].at_um[0]||v.at_um[1]===wire.vertices[i].at_um[1]));
 }
 const internalOld=old.wires[0],internalNew=now.wires[0];
 assert.deepEqual(internalNew.segments,internalOld.segments);
 assert.deepEqual(internalNew.vertices,internalOld.vertices.map(v=>({...v,at_um:[v.at_um[0]+5000,v.at_um[1]+10000]})));
 assert.deepEqual(now.wires[1].vertices.at(-1).at_um,old.wires[1].vertices.at(-1).at_um);
 assert.ok(after.project.nets.every(n=>n.route_status==='partial'));
 assert.throws(()=>s.moveGroup(s.newTransaction('out-of-range'),group,[1000000000,0],true));
 assert.deepEqual(s.file,after);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,after);
 assert.deepEqual(new AuthoringSession(after).file,after);
});

test('R15 group clipboard copies complete internal Nets with independent IDs and drops external Nets',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.place(s.newTransaction('r2'),'symbol/resistor.fixed',[210000,100000]);
 const third=s.file.project.components.find(x=>x.refdes==='R2').id;
 s.connect(s.newTransaction('internal'),pin(r,'2'),pin(c,'1'));
 s.connect(s.newTransaction('external'),pin(c,'2'),pin(third,'1'));
 const before=s.file,revision=s.revision;
 const ids=before.project.sheets[0].instances.filter(i=>[r,c].includes(i.component_id)).map(i=>i.id);
 const clipboard=s.copyGroup(ids);
 assert.deepEqual(s.file,before);assert.equal(s.revision,revision);
 assert.equal(clipboard.nets.length,1);assert.equal(clipboard.omittedNetCount,1);
 assert.equal(clipboard.wires.length,1);
 const origin=s.suggestGroupPasteOrigin(clipboard,clipboard.anchor,true);
 assert.equal(origin[0]%1000,0);assert.equal(origin[1]%1000,0);
 assert.deepEqual(s.file,before);assert.equal(s.revision,revision);
 const added=s.pasteGroup(s.newTransaction('paste-group'),clipboard,origin);
 const after=s.file,old=before.project.sheets[0],now=after.project.sheets[0];
 assert.equal(s.revision,revision+1);assert.equal(added.length,2);
 assert.deepEqual(after.project.components.slice(0,3),before.project.components);
 assert.deepEqual(after.project.nets.slice(0,2),before.project.nets);
 assert.deepEqual(now.wires.slice(0,2),old.wires);
 const copies=now.instances.filter(i=>added.includes(i.id));
 const copiedComponents=after.project.components.filter(c=>copies.some(i=>i.component_id===c.id));
 assert.deepEqual(copiedComponents.map(c=>c.refdes),['R3','C2']);
 const copiedNet=after.project.nets[2],copiedWire=now.wires[2];
 assert.notEqual(copiedNet.id,before.project.nets[0].id);
 assert.notEqual(copiedNet.name,before.project.nets[0].name);
 assert.equal(copiedNet.route_status,'partial');
 assert.deepEqual(copiedNet.members.map(m=>m.component_id),copies.map(i=>i.component_id));
 assert.ok(!before.project.components.some(c=>copiedNet.members.some(m=>m.component_id===c.id)));
 assert.notEqual(copiedWire.id,old.wires[0].id);
 assert.ok(copiedWire.vertices.every(v=>!old.wires[0].vertices.some(o=>o.id===v.id)));
 assert.ok(copiedWire.segments.every(v=>!old.wires[0].segments.some(o=>o.id===v.id)));
 const delta=[origin[0]-clipboard.anchor[0],origin[1]-clipboard.anchor[1]];
 assert.deepEqual(copiedWire.vertices.map(v=>v.at_um),old.wires[0].vertices.map(v=>[v.at_um[0]+delta[0],v.at_um[1]+delta[1]]));
 assert.equal(copiedWire.needs_routing_review,true);
 assert.deepEqual(copies.map(i=>i.origin_um),old.instances.slice(0,2).map(i=>[i.origin_um[0]+delta[0],i.origin_um[1]+delta[1]]));
 assert.deepEqual(after.project.provenance.expected_counts,{components:5,nets:3,memberships:6,da1_pins:0,b_graphics:0});
 assert.throws(()=>s.pasteGroup(s.newTransaction('bad'),{...clipboard,nets:[{...clipboard.nets[0],members:[pin('unknown','1')]}]},[100000,200000]),/INVALID_CLIPBOARD/);
 assert.deepEqual(s.file,after);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,after);
 assert.deepEqual(new AuthoringSession(after).file,after);
});
test('R15 shared Net is excluded as a whole, detached copy can paste repeatedly on another sheet',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.place(s.newTransaction('r2'),'symbol/resistor.fixed',[210000,100000]);
 const third=s.file.project.components.find(x=>x.refdes==='R2').id;
 s.connect(s.newTransaction('first'),pin(r,'2'),pin(c,'1'));
 s.connect(s.newTransaction('branch'),pin(c,'1'),pin(third,'1'),[[140000,80000],[190000,80000],[190000,100000]]);
 const first=s.file.project.sheets[0].instances;
 const clipboard=s.copyGroup(first.slice(0,2).map(i=>i.id));
 assert.equal(clipboard.omittedNetCount,1);assert.deepEqual(clipboard.nets,[]);assert.deepEqual(clipboard.wires,[]);
 const sheet=s.addSheet(s.newTransaction('sheet'));s.selectSheet(s.newTransaction('switch'),sheet);
 const a=s.pasteGroup(s.newTransaction('paste-a'),clipboard,[80000,80000]);
 const b=s.pasteGroup(s.newTransaction('paste-b'),clipboard,[80000,130000]);
 assert.equal(new Set([...a,...b]).size,4);
 const after=s.file;
 assert.equal(after.project.sheets[1].instances.length,4);
 assert.equal(after.project.nets.length,1);
 assert.deepEqual(after.project.sheets[1].wires,[]);
 assert.ok(after.project.sheets[1].instances.every(i=>i.layer_id===after.project.sheets[1].layers[0].id));
});

test('R15 copy remaps explicit junction, splice and dangling endpoint identities',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.connect(s.newTransaction('connect'),pin(r,'2'),pin(c,'1'));
 const file=s.file,sheet=file.project.sheets[0],old=sheet.wires[0],net=file.project.nets[0];
 const start=old.vertices[0].at_um,end=old.vertices.at(-1).at_um;
 const mid=[Math.round((start[0]+end[0])/2),start[1]],mid2=[mid[0]+3000,mid[1]];
 const j={id:'source-j',net_id:net.id,layer_id:old.layer_id,at_um:mid};
 const sp={id:'source-sp',net_id:net.id,layer_id:old.layer_id,at_um:mid2};
 const wire=(id,a,b,startAnchor,endAnchor)=>{
  const vertices=[{id:id+'-a',at_um:a,anchor:startAnchor},{id:id+'-b',at_um:b,anchor:endAnchor}];
  return {id,net_id:net.id,layer_id:old.layer_id,mode:'orthogonal',vertices,segments:[{id:id+'-s',from_vertex_id:vertices[0].id,to_vertex_id:vertices[1].id}]};
 };
 sheet.junctions=[j];sheet.splices=[sp];
 const ja={kind:'junction',junction_id:j.id},sa={kind:'splice',splice_id:sp.id};
 sheet.wires=[
  wire('source-a',start,mid,old.vertices[0].anchor,ja),
  wire('source-b',mid,mid2,ja,sa),
  wire('source-c',mid2,end,sa,old.vertices.at(-1).anchor),
  wire('source-d',mid,[mid[0],mid[1]+10000],ja,{kind:'free',free_id:'source-free'})
 ];
 net.route_status='partial';
 const a=new AuthoringSession(file),clip=a.copyGroup(sheet.instances.map(i=>i.id));
 const origin=a.suggestGroupPasteOrigin(clip,clip.anchor,true);
 a.pasteGroup(a.newTransaction('paste-nodes'),clip,origin);
 const after=a.file,sh=after.project.sheets[0];
 assert.equal(sh.wires.length,8);assert.equal(sh.junctions.length,2);assert.equal(sh.splices.length,2);
 const copiedNet=after.project.nets[1].id,j2=sh.junctions[1],s2=sh.splices[1];
 assert.notEqual(j2.id,j.id);assert.notEqual(s2.id,sp.id);
 assert.equal(j2.net_id,copiedNet);assert.equal(s2.net_id,copiedNet);
 const anchors=sh.wires.slice(4).flatMap(w=>w.vertices.map(v=>v.anchor));
 assert.equal(anchors.filter(v=>v.kind==='junction'&&v.junction_id===j2.id).length,3);
 assert.equal(anchors.filter(v=>v.kind==='splice'&&v.splice_id===s2.id).length,2);
 assert.ok(anchors.some(v=>v.kind==='free'&&v.free_id!=='source-free'));
 assert.equal(a.engine.validateNet(copiedNet).pin_groups.length,1);
 assert.equal(a.engine.validateNet(copiedNet).status,'partial');
 assert.deepEqual(new AuthoringSession(after).file,after);
});

test('R17 every source JSON symbol can be placed with exact physical pin mapping and roundtrip',()=>{
 const s=newSession(),before=s.file;
 assert.equal(before.project.symbol_definitions.length,36);
 assert.equal(before.project.part_definitions.length,36);
 for(const [i,symbol] of before.project.symbol_definitions.entries()){
  const id=s.place(s.newTransaction('catalog-'+i),symbol.id,[35000+i%6*65000,30000+Math.floor(i/6)*45000]);
  const file=s.file,inst=file.project.sheets[0].instances.find(v=>v.id===id);
  const component=file.project.components.find(c=>c.id===inst.component_id);
  const part=file.project.part_definitions.find(p=>p.id===component.part_id);
  assert.equal(component.part_id,symbol.part_id);
  assert.ok(component.refdes.startsWith(part.reference_prefix));
  assert.equal(symbol.pins.length,part.physical_pins.length);
  for(const p of symbol.pins){
   const resolved=s.beginWire(pin(component.id,p.physical_pin_number));
   assert.deepEqual(resolved.at_um,[inst.origin_um[0]+p.at_um[0],inst.origin_um[1]+p.at_um[1]]);
   assert.equal(resolved.net_id,null);
  }
  if(part.reference_prefix==='VD'||part.reference_prefix==='VT'||part.reference_prefix==='FU')assert.equal(component.value,'');
 }
 const after=s.file;
 assert.equal(after.project.components.length,36);assert.equal(after.project.nets.length,0);
 assert.deepEqual(new AuthoringSession(after).file,after);
});
test('R17 semiconductor terminal names and polarity are retained without inferred electrical edges',()=>{
 const s=newSession();
 const diode=s.place(s.newTransaction('diode'),'symbol/diode.general',[100000,100000]);
 const transistor=s.place(s.newTransaction('transistor'),'symbol/transistor.bjt_npn',[155000,100000]);
 const file=s.file;
 const d=file.project.sheets[0].instances.find(i=>i.id===diode).component_id;
 const t=file.project.sheets[0].instances.find(i=>i.id===transistor).component_id;
 const pd=file.project.part_definitions.find(p=>p.id==='diode.general');
 const pt=file.project.part_definitions.find(p=>p.id==='transistor.bjt_npn');
 assert.deepEqual(pd.physical_pins.map(p=>[p.number,p.name]),[['1','A'],['2','K']]);
 assert.deepEqual(pt.physical_pins.map(p=>[p.number,p.name]),[['1','B'],['2','C'],['3','E']]);
 s.connect(s.newTransaction('connect'),pin(d,'2'),pin(t,'1'));
 assert.deepEqual(s.file.project.nets[0].members,[pin(d,'2'),pin(t,'1')]);
 assert.equal(s.beginWire(pin(t,'2')).net_id,null);
 assert.equal(s.beginWire(pin(t,'3')).net_id,null);
});

test('R17b old R/C project library upgrade is explicit, additive and reversible',()=>{
 const source=newSession(),{r,c}=placePair(source);
 source.connect(source.newTransaction('connect'),pin(r,'2'),pin(c,'1'));
 const legacy=source.file,keep=new Set(['resistor.fixed','capacitor.fixed']);
 legacy.project.part_definitions=legacy.project.part_definitions.filter(p=>keep.has(p.id));
 legacy.project.symbol_definitions=legacy.project.symbol_definitions.filter(p=>keep.has(p.part_id));
 // Simulate older or locally edited pin name/geometry metadata.
 legacy.project.part_definitions[0].physical_pins[0].name='OLD_NAME';
 legacy.project.symbol_definitions[0].standard_refs=['LEGACY_DRAFT'];
 const s=new AuthoringSession(legacy),stale=s.newTransaction('stale');
 assert.equal(s.upgradeCatalog(s.newTransaction('upgrade')),34);
 const after=s.file;
 assert.equal(after.project.symbol_definitions.length,36);
 assert.deepEqual(after.project.part_definitions.slice(0,2),legacy.project.part_definitions);
 assert.deepEqual(after.project.symbol_definitions.slice(0,2),legacy.project.symbol_definitions);
 assert.deepEqual(after.project.components,legacy.project.components);
 assert.deepEqual(after.project.nets,legacy.project.nets);
 assert.deepEqual(after.project.sheets,legacy.project.sheets);
 assert.deepEqual(after.project.provenance,legacy.project.provenance);
 assert.throws(()=>s.upgradeCatalog(stale),/STALE_REVISION/);
 assert.throws(()=>s.upgradeCatalog(s.newTransaction('already')),/NO_CHANGE/);
 assert.deepEqual(s.file,after);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,legacy);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,after);
 s.place(s.newTransaction('new-diode'),'symbol/diode.general',[120000,150000]);
 assert.ok(s.file.project.components.some(c=>c.refdes==='VD1'));
});

test('R17b canonical catalog parity and actual Python SVG export of all 36 placed UGO',()=>{
 const s=newSession(),source=s.file;
 const root=new URL('../../../../src/gost_schematic/catalog/symbols/',import.meta.url);
 const files=readdirSync(root,{recursive:true}).filter(p=>p.endsWith('.json')).sort();
 assert.equal(files.length,21);
 const mm=n=>Math.round(n*1000),point=p=>p.map(mm);
 for(const filename of files){
  const raw=JSON.parse(readFileSync(new URL(filename.replaceAll('\\','/'),root),'utf8'));
  const part=JSON.parse(readFileSync(new URL('../parts/'+filename.replaceAll('\\','/'),root),'utf8'));
  const sym=source.project.symbol_definitions.find(x=>x.id==='symbol/'+raw.id);
  assert.ok(sym,raw.id);
  assert.equal(sym.revision,raw.revision);
  assert.deepEqual(sym.pins,raw.pins.map(p=>({physical_pin_number:p.number,at_um:point(p.at_mm),side:p.side})));
  assert.deepEqual(source.project.part_definitions.find(x=>x.id===part.id).physical_pins,part.pins.map(p=>({number:p.number,name:p.name,electrical_type:p.electrical_type})));
  const expected=[
   ...raw.geometry.rectangles.map(r=>({kind:'rect',points_um:[point(r.slice(0,2)),point(r.slice(2))],stroke_um:mm(raw.line_width_mm)})),
   ...raw.geometry.lines.map(l=>({kind:'line',points_um:l.map(point),stroke_um:mm(raw.line_width_mm)}))
  ];
  assert.deepEqual(sym.graphics.slice(0,expected.length),expected);
  assert.equal(sym.graphics.length,expected.length+raw.geometry.circles.length);
  for(const [i,c] of raw.geometry.circles.entries()){
   const p=sym.graphics[expected.length+i],center=point(c.center_mm),radius=mm(c.radius_mm);
   assert.equal(p.kind,'circle');assert.deepEqual(p.points_um,[center,[center[0]+radius,center[1]]]);
  }
 }
 for(const [i,symbol] of source.project.symbol_definitions.entries())
  s.place(s.newTransaction('export-'+i),symbol.id,[35000+i%6*65000,30000+Math.floor(i/6)*45000]);
 const py=spawnSync('python',['-c',
  'import json,sys;sys.path.insert(0,"../..");from ui.editor.src.model.contract import validate,digest;from ui.bridge.export.project_v2 import render_v2_source;d=json.loads(sys.stdin.buffer.read().decode("utf-8"));validate(d);sys.stdout.buffer.write(render_v2_source(d,d["workspace"]["active_sheet_id"],expected_project_sha256=digest(d)))'
 ],{input:JSON.stringify(s.file),encoding:'utf8',timeout:30000,maxBuffer:2*1024*1024});
 assert.equal(py.status,0,py.stderr);
 assert.match(py.stdout,/<svg\b|<ns0:svg\b/);
});

test('R17c Python canonical curve validation and exact SVG sweep across every pose',()=>{
 const s=newSession();
 s.place(s.newTransaction('case'),'symbol/transistor.bjt_npn.with_case',[100000,100000]);
 const doc=s.file,inst=doc.project.sheets[0].instances[0];
 const sym=doc.project.symbol_definitions.find(s=>s.id===inst.symbol_id);
 sym.graphics.push({kind:'semicircle',points_um:[[-2000,0],[0,-2000],[2000,0]],stroke_um:300});
 const py=spawnSync('python',['-c',
  'import json,sys;sys.path.insert(0,"../..");from ui.editor.src.model.contract import validate,digest;from ui.bridge.export.project_v2 import render_v2_source;import xml.etree.ElementTree as E;d=json.loads(sys.stdin.buffer.read().decode("utf-8"));i=d["project"]["sheets"][0]["instances"][0];ns={"s":"http://www.w3.org/2000/svg"};out=[]\nfor r in (0,90,180,270):\n for m in (False,True):\n  i["rotation_deg"]=r;i["mirror_x"]=m;validate(d);root=E.fromstring(render_v2_source(d,"sheet-1",expected_project_sha256=digest(d)));out.append([root.find(".//s:circle",ns).get("r"),root.find(".//s:path",ns).get("d")])\nprint(json.dumps(out))'
 ],{input:JSON.stringify(doc),encoding:'utf8',timeout:30000});
 assert.equal(py.status,0,py.stderr);
 const results=JSON.parse(py.stdout);
 assert.equal(results.length,8);
 for(const [i,[radius,path]] of results.entries()){
  assert.equal(Number(radius),8);
  assert.match(path,new RegExp(' A 2(?:\\.0+)? 2(?:\\.0+)? 0 0 '+(i%2?0:1)+' '));
 }
 sym.graphics.at(-1).points_um[1]=[0,-1999];
 assert.throws(()=>new AuthoringSession(doc),/INVALID_CURVE/);
 const bad=spawnSync('python',['-c','import json,sys;sys.path.insert(0,"../..");from ui.editor.src.model.contract import validate;validate(json.loads(sys.stdin.buffer.read().decode("utf-8")))'],{input:JSON.stringify(doc),encoding:'utf8',timeout:30000});
 assert.notEqual(bad.status,0);assert.match(bad.stderr,/INVALID_CURVE/);
});

test('R17d all generated winding variants retain true arcs, actual core widths and tap/slider PinRefs',()=>{
 const s=newSession(),catalog=s.file.project;
 const defs=catalog.symbol_definitions.filter(d=>d.part_id.startsWith('inductor.')||d.part_id.startsWith('choke.'));
 assert.equal(defs.length,15);
 const dir=new URL('../../../../src/gost_schematic/catalog/inductors/',import.meta.url);
 for(const symbol of defs){
  const raw=JSON.parse(readFileSync(new URL(symbol.part_id+'.json',dir),'utf8'));
  const turns=raw.turns??4,radius=Math.round(Number(raw.radius_mm??2)*1000),lead=Math.round(Number(raw.lead_mm??4)*1000);
  const arcs=symbol.graphics.filter(g=>g.kind==='semicircle');
  assert.equal(arcs.length,turns);
  for(const [i,arc] of arcs.entries()){
   const x=-turns*radius+2*radius*i;
   assert.deepEqual(arc.points_um,[[x,0],[x+radius,-radius],[x+radius*2,0]]);
  }
  assert.deepEqual(symbol.pins[0].at_um,[-turns*radius-lead,0]);
  assert.deepEqual(symbol.pins[1].at_um,[turns*radius+lead,0]);
  assert.equal(symbol.pins.length,2+(raw.tap_turns?.length??0)+(raw.slider_turns?.length??0));
  const part=catalog.part_definitions.find(p=>p.id===symbol.part_id);
  assert.equal(part.reference_prefix,'L');assert.deepEqual(part.physical_pins.map(p=>p.number),symbol.pins.map(p=>p.physical_pin_number));
  if(raw.core==='ferrite')assert.ok(symbol.graphics.some(g=>g.stroke_um===2*Math.round(Number(raw.line_width_mm??.3)*1000)));
 }
 const id=s.place(s.newTransaction('tapped'),'symbol/inductor.double_tapped',[100000,100000]);
 const c=s.file.project.sheets[0].instances.find(i=>i.id===id).component_id;
 assert.equal(s.snapshot.components.find(p=>p.id===c).pins.length,4);
 s.rotate(s.newTransaction('rotate'),c);
 const actual=s.beginWire(pin(c,'3'));
 assert.equal(actual.net_id,null);assert.deepEqual(actual.normal,[1,0]);
 assert.equal(s.file.project.nets.length,0);
});

test('R17e Cu constant annotation is source-backed, upright and non-electrical across all poses',()=>{
 const s=newSession();
 const id=s.place(s.newTransaction('copper'),'symbol/inductor.trim_copper',[100000,100000]);
 const doc=s.file,inst=doc.project.sheets[0].instances.find(i=>i.id===id);
 const sym=doc.project.symbol_definitions.find(x=>x.id===inst.symbol_id);
 const note=sym.constant_annotations[0];
 assert.equal(note.key,'core_material');assert.equal(note.text,'Cu');
 assert.deepEqual([note.horizontal,note.vertical,note.height_um],['left','center',3500]);
 assert.equal(sym.pins.length,2);
 assert.equal(doc.project.nets.length,0);
 const py=spawnSync('python',['-c',
  'import json,sys;sys.path.insert(0,"../..");sys.path.insert(0,"../../src");from gost_schematic.catalog.inductors import load_inductor;from ui.editor.src.model.contract import validate,digest,pin_world;from ui.bridge.export.project_v2 import render_v2_source;import xml.etree.ElementTree as E;d=json.loads(sys.stdin.buffer.read().decode("utf-8"));i=d["project"]["sheets"][0]["instances"][0];ns={"s":"http://www.w3.org/2000/svg"};source=load_inductor("../../src/gost_schematic/catalog/inductors/inductor.trim_copper.json").symbol;slot=next(s for s in source.annotation_slots if s.key=="core_material");p=slot.candidates[0].at;out=[]\nfor r in (0,90,180,270):\n for m in (False,True):\n  i["rotation_deg"]=r;i["mirror_x"]=m;validate(d);root=E.fromstring(render_v2_source(d,"sheet-1",expected_project_sha256=digest(d)));note=root.find(".//s:text[@data-symbol-note=\'core_material\']",ns);out.append([note.text,note.get("data-electrical"),note.get("transform"),note.get("x"),note.get("y"),pin_world(i,[p.x,p.y])])\nprint(json.dumps({"source":[p.x,p.y],"poses":out}))'
 ],{input:JSON.stringify(doc),encoding:'utf8',timeout:30000});
 assert.equal(py.status,0,py.stderr);
 const result=JSON.parse(py.stdout);
 assert.deepEqual(note.at_um,result.source);
 assert.equal(result.poses.length,8);
 for(const [text,electrical,transform,x,y,at] of result.poses){
  assert.equal(text,'Cu');assert.equal(electrical,'false');assert.equal(transform,null);
  assert.equal(Math.round(Number(x)*1000),at[0]);
  assert.equal(Math.round(Number(y)*1000),at[1]+1167);
 }
 const corrupt=structuredClone(doc);
 const c=corrupt.project.symbol_definitions.find(x=>x.id===inst.symbol_id);
 c.constant_annotations.push({...c.constant_annotations[0]});
 assert.throws(()=>new AuthoringSession(corrupt),/INVALID_CONSTANT_ANNOTATION/);
 assert.deepEqual(new AuthoringSession(doc).file,doc);
});

test('R19 clean route avoids an intervening component and does not change electrical membership',()=>{
 const s=newSession();
 s.place(s.newTransaction('left'),'symbol/resistor.fixed',[60000,100000]);
 s.place(s.newTransaction('right'),'symbol/resistor.fixed',[160000,100000]);
 s.place(s.newTransaction('obstacle'),'symbol/resistor.fixed',[110000,100000]);
 const [a,b,c]=s.file.project.components;
 const before=s.file;
 s.connect(s.newTransaction('smart'),pin(a.id,'2'),pin(b.id,'1'),[],true);
 const after=s.file,w=after.project.sheets[0].wires[0];
 assert.equal(w.vertices.length,6);
 assert.deepEqual(w.vertices[0].at_um,[68000,100000]);
 assert.deepEqual(w.vertices.at(-1).at_um,[152000,100000]);
 assert.ok(w.vertices.some(v=>Math.abs(v.at_um[1]-100000)>=3150));
 assert.deepEqual(after.project.nets[0].members,[pin(a.id,'2'),pin(b.id,'1')]);
 assert.ok(!after.project.nets[0].members.some(p=>p.component_id===c.id));
 assert.deepEqual(after.project.sheets[0].instances,before.project.sheets[0].instances);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,after);
});
test('R19 physical-pin alignment changes only one pose and one route with atomic undo',()=>{
 const s=newSession();
 const ia=s.place(s.newTransaction('left'),'symbol/resistor.fixed',[60000,100000]);
 const ib=s.place(s.newTransaction('right'),'symbol/resistor.fixed',[160000,120000]);
 const [a,b]=s.file.project.components;
 s.connect(s.newTransaction('connect'),pin(a.id,'2'),pin(b.id,'1'),[],true);
 const before=s.file,rev=s.revision,old=before.project.sheets[0].wires[0];
 assert.equal(old.vertices.length,4);
 const result=s.alignConnectedPair(s.newTransaction('align'),[ia,ib]);
 assert.equal(result.moved,ib);assert.deepEqual(result.delta,[0,-20000]);assert.equal(result.beforeBends,2);
 const after=s.file,w=after.project.sheets[0].wires[0];
 assert.equal(s.revision,rev+1);assert.equal(w.id,old.id);assert.equal(w.net_id,old.net_id);
 assert.equal(w.vertices.length,2);assert.deepEqual(w.vertices.map(v=>v.at_um),[[68000,100000],[152000,100000]]);
 assert.deepEqual(w.vertices.map(v=>v.anchor),[old.vertices[0].anchor,old.vertices.at(-1).anchor]);
 assert.deepEqual(w.vertices.map(v=>v.id),[old.vertices[0].id,old.vertices.at(-1).id]);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.equal(w.needs_routing_review,true);
 assert.throws(()=>s.alignConnectedPair(s.newTransaction('again'),[ia,ib]),/NO_CHANGE/);
 assert.deepEqual(s.file,after);assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(new AuthoringSession(s.file).file,after);
});
test('R19 alignment refuses moving both candidates with other attached routes',()=>{
 const s=newSession();
 const ia=s.place(s.newTransaction('left'),'symbol/resistor.fixed',[60000,100000]);
 const ib=s.place(s.newTransaction('right'),'symbol/resistor.fixed',[160000,120000]);
 s.place(s.newTransaction('left-outer'),'symbol/resistor.fixed',[30000,100000]);
 s.place(s.newTransaction('right-outer'),'symbol/resistor.fixed',[200000,120000]);
 const [a,b,c,d]=s.file.project.components;
 s.connect(s.newTransaction('pair'),pin(a.id,'2'),pin(b.id,'1'));
 s.connect(s.newTransaction('left'),pin(c.id,'2'),pin(a.id,'1'));
 s.connect(s.newTransaction('right'),pin(b.id,'2'),pin(d.id,'1'));
 const before=s.file,rev=s.revision;
 assert.throws(()=>s.alignConnectedPair(s.newTransaction('align'),[ia,ib]),/ALIGN_NO_SAFE_STRAIGHT_ROUTE/);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
});

test('R19b magnet aligns actual facing pin axes without creating Net or moving prior components',()=>{
 const s=newSession();
 s.place(s.newTransaction('reference'),'symbol/resistor.fixed',[100000,100000]);
 const before=s.file,rev=s.revision,ref=before.project.components[0];
 const hint=s.suggestAlignedPlacement('symbol/resistor.fixed',[155000,103000]);
 assert.ok(hint);assert.deepEqual(hint.origin,[155000,100000]);
 assert.deepEqual(hint.from,[108000,100000]);assert.deepEqual(hint.to,[147000,100000]);
 assert.deepEqual(hint.target,pin(ref.id,'2'));assert.equal(hint.newPin,'1');
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 s.place(s.newTransaction('placed'),'symbol/resistor.fixed',hint.origin);
 assert.deepEqual(s.file.project.sheets[0].instances[0],before.project.sheets[0].instances[0]);
 assert.deepEqual(s.file.project.nets,[]);assert.deepEqual(s.snapshot.wires,[]);
});
test('R19b placement respects rotated pin normals and exact vertical alignment',()=>{
 const s=newSession();
 const id=s.place(s.newTransaction('reference'),'symbol/resistor.fixed',[100000,100000]);
 const ref=s.file.project.sheets[0].instances.find(i=>i.id===id).component_id;
 s.rotate(s.newTransaction('rotate'),ref);
 const definition=s.file.project.symbol_definitions.find(d=>d.id==='symbol/inductor.tapped');
 const tap=definition.pins.find(p=>p.side==='top');
 assert.ok(tap);
 const hint=s.suggestAlignedPlacement(definition.id,[103000-tap.at_um[0],150000]);
 assert.ok(hint);
 assert.equal(hint.from[0],hint.to[0]);
 assert.equal(hint.target.component_id,ref);
 assert.equal(hint.target.physical_pin_number,'2');
 assert.equal(hint.newPin,tap.physical_pin_number);
 assert.equal(hint.origin[0],100000-tap.at_um[0]);
 assert.equal(s.suggestAlignedPlacement('symbol/resistor.fixed',[100000,145000]),null);
 assert.equal(s.file.project.nets.length,0);
});
test('R19b magnet skips blocked, distant and ambiguous suggestions',()=>{
 const s=newSession();
 s.place(s.newTransaction('reference'),'symbol/resistor.fixed',[100000,100000]);
 assert.equal(s.suggestAlignedPlacement('symbol/resistor.fixed',[155000,107000]),null);
 assert.equal(s.suggestAlignedPlacement('symbol/resistor.fixed',[250000,103000]),null);
 s.place(s.newTransaction('block'),'symbol/resistor.fixed',[127000,100000]);
 // The blocker may itself be the valid nearest target; no proposal may cross it.
 const hint=s.suggestAlignedPlacement('symbol/resistor.fixed',[155000,103000]);
 assert.ok(hint);assert.equal(hint.target.component_id,s.file.project.components[1].id);
 const amb=newSession();
 amb.place(amb.newTransaction('upper'),'symbol/resistor.fixed',[100000,97000]);
 amb.place(amb.newTransaction('lower'),'symbol/resistor.fixed',[100000,103000]);
 assert.equal(amb.suggestAlignedPlacement('symbol/resistor.fixed',[155000,100000]),null);
});

test('R19c removes manually drawn stairs in one transaction and preserves signed endpoint IDs',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.move(s.newTransaction('offset'),c,[155000,120000]);
 s.connect(s.newTransaction('stairs'),pin(r,'2'),pin(c,'1'),[
  [119000,103000],[128000,110000],[137000,117000]
 ]);
 const before=s.file,old=before.project.sheets[0].wires[0],rev=s.revision;
 assert.ok(old.vertices.length>4);
 const stats=s.simplifyRoutes(s.newTransaction('cleanup'));
 const after=s.file,w=after.project.sheets[0].wires[0];
 assert.equal(stats.checked,1);assert.equal(stats.changed,1);assert.ok(stats.removedBends>0);
 assert.equal(w.vertices.length,4);assert.equal(w.id,old.id);
 assert.equal(w.vertices[0].id,old.vertices[0].id);assert.equal(w.vertices.at(-1).id,old.vertices.at(-1).id);
 assert.deepEqual(w.vertices[0].anchor,old.vertices[0].anchor);assert.deepEqual(w.vertices.at(-1).anchor,old.vertices.at(-1).anchor);
 assert.equal(w.needs_routing_review,true);assert.equal(s.revision,rev+1);
 assert.deepEqual(after.project.sheets[0].instances,before.project.sheets[0].instances);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.throws(()=>s.simplifyRoutes(s.newTransaction('again')),/NO_CHANGE/);
 assert.deepEqual(s.file,after);assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(new AuthoringSession(s.file).file,after);
});
test('R19c cleanup does not introduce crossings or alter explicit branch endpoints',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.connect(s.newTransaction('connect'),pin(r,'2'),pin(c,'1'));
 const before=s.file;
 assert.throws(()=>s.simplifyRoutes(s.newTransaction('straight')),/NO_CHANGE/);
 assert.deepEqual(s.file,before);
 const legacy=structuredClone(before),sh=legacy.project.sheets[0],w=sh.wires[0];
 const a=w.vertices[0],b=w.vertices.at(-1),mid=[130000,100000];
 const junction={id:'test-node',net_id:w.net_id,layer_id:w.layer_id,at_um:mid};
 sh.junctions.push(junction);
 const v1={id:'test-v1',at_um:mid,anchor:{kind:'junction',junction_id:junction.id}};
 const v2={id:'test-v2',at_um:mid,anchor:{kind:'junction',junction_id:junction.id}};
 sh.wires=[{...w,vertices:[a,v1],segments:[{id:'test-seg1',from_vertex_id:a.id,to_vertex_id:v1.id}]},
 {...w,id:'test-w2',vertices:[v2,b],segments:[{id:'test-seg2',from_vertex_id:v2.id,to_vertex_id:b.id}]}];
 const aSession=new AuthoringSession(legacy);
 assert.throws(()=>aSession.simplifyRoutes(aSession.newTransaction('skip-branch')),/NO_CHANGE/);
 assert.deepEqual(aSession.file,legacy);
});

function seriesFixture(positions,vertical=false){
 const s=newSession(),ids=positions.map((at,i)=>s.place(s.newTransaction('series-place-'+i),'symbol/resistor.fixed',at));
 const components=s.file.project.components.map(c=>c.id);
 if(vertical)for(const id of components)s.rotate(s.newTransaction('series-rotate'),id);
 for(let i=1;i<components.length;i++)s.connect(s.newTransaction('series-wire-'+i),pin(components[i-1],'2'),pin(components[i],'1'));
 return {s,ids,components};
}
test('R20 series layout minimizes transverse displacement and straightens all internal wires atomically',()=>{
 const {s,ids}=seriesFixture([[60000,90000],[120000,110000],[180000,100000],[240000,140000]]);
 const before=s.file,rev=s.revision,old=before.project.sheets[0];
 const stale=s.newTransaction('stale');
 const result=s.alignSeries(s.newTransaction('align'),ids);
 assert.deepEqual(result,{moved:3,wires:3,removedBends:6,axis:'horizontal'});
 const after=s.file,sh=after.project.sheets[0];
 assert.equal(s.revision,rev+1);
 assert.deepEqual(sh.instances.map(i=>i.origin_um),[[60000,100000],[120000,100000],[180000,100000],[240000,100000]]);
 assert.deepEqual(after.project.components,before.project.components);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 for(const [i,w] of sh.wires.entries()){
  const prior=old.wires[i];
  assert.equal(w.id,prior.id);assert.equal(w.net_id,prior.net_id);assert.equal(w.vertices.length,2);
  assert.deepEqual(w.vertices.map(v=>v.anchor),[prior.vertices[0].anchor,prior.vertices.at(-1).anchor]);
  assert.deepEqual(w.vertices.map(v=>v.id),[prior.vertices[0].id,prior.vertices.at(-1).id]);
  assert.equal(w.vertices[0].at_um[1],w.vertices[1].at_um[1]);
 }
 assert.throws(()=>s.alignSeries(stale,ids),/STALE_REVISION/);
 assert.throws(()=>s.alignSeries(s.newTransaction('again'),ids),/NO_CHANGE/);
 assert.deepEqual(s.file,after);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(new AuthoringSession(s.file).file,after);
});
test('R20 vertical chain uses rotated physical pin normals and preserves longitudinal coordinates',()=>{
 const {s,ids}=seriesFixture([[90000,40000],[100000,100000],[120000,160000]],true);
 assert.equal(s.alignSeries(s.newTransaction('vertical'),ids).axis,'vertical');
 const sh=s.file.project.sheets[0];
 assert.deepEqual(sh.instances.map(i=>i.origin_um),[[100000,40000],[100000,100000],[100000,160000]]);
 assert.ok(sh.instances.every(i=>i.rotation_deg===90));
 assert.ok(sh.wires.every(w=>w.vertices.length===2&&w.vertices[0].at_um[0]===w.vertices[1].at_um[0]));
});
test('R20 external connected component fixes the alignment axis and its wire is unchanged',()=>{
 const {s,ids,components}=seriesFixture([[60000,90000],[120000,110000],[180000,100000]]);
 s.place(s.newTransaction('outer'),'symbol/resistor.fixed',[30000,90000]);
 const outer=s.file.project.components.at(-1).id;
 s.connect(s.newTransaction('outer-wire'),pin(outer,'2'),pin(components[0],'1'));
 const before=s.file;
 assert.equal(s.alignSeries(s.newTransaction('align-fixed'),ids).moved,2);
 const sh=s.file.project.sheets[0];
 assert.deepEqual(sh.instances.slice(0,3).map(i=>i.origin_um),[[60000,90000],[120000,90000],[180000,90000]]);
 assert.deepEqual(sh.wires.at(-1),before.project.sheets[0].wires.at(-1));
 assert.deepEqual(sh.instances.at(-1),before.project.sheets[0].instances.at(-1));
});
test('R20 fixed conflicting endpoints and disconnected selection reject without mutation',()=>{
 const {s,ids,components}=seriesFixture([[60000,90000],[120000,110000],[180000,100000]]);
 const x=s.place(s.newTransaction('outer-left'),'symbol/resistor.fixed',[30000,90000]);
 s.place(s.newTransaction('outer-right'),'symbol/resistor.fixed',[220000,100000]);
 const [left,right]=s.file.project.components.slice(-2).map(c=>c.id);
 s.connect(s.newTransaction('left'),pin(left,'2'),pin(components[0],'1'));
 s.connect(s.newTransaction('right'),pin(components[2],'2'),pin(right,'1'));
 const before=s.file,rev=s.revision;
 assert.throws(()=>s.alignSeries(s.newTransaction('fixed-conflict'),ids),/SERIES_FIXED_CONFLICT/);
 assert.throws(()=>s.alignSeries(s.newTransaction('disconnected'),[ids[0],ids[2],x]),/SERIES_NOT_SIMPLE_PATH/);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
});
