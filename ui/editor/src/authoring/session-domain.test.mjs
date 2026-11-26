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

test('R20b equal distribution uses physical pin gaps across mixed-size UGO, not centers',()=>{
 const s=newSession();
 const ids=[
  s.place(s.newTransaction('first'),'symbol/resistor.fixed',[60000,100000]),
  s.place(s.newTransaction('middle'),'symbol/inductor.air_core',[100000,100000]),
  s.place(s.newTransaction('last'),'symbol/resistor.fixed',[210001,100000])
 ];
 const [a,b,c]=s.file.project.components;
 s.connect(s.newTransaction('first-wire'),pin(a.id,'2'),pin(b.id,'1'));
 s.connect(s.newTransaction('second-wire'),pin(b.id,'2'),pin(c.id,'1'));
 const before=s.file,sh0=before.project.sheets[0];
 const oldGaps=sh0.wires.map(w=>w.vertices.at(-1).at_um[0]-w.vertices[0].at_um[0]);
 const result=s.alignSeries(s.newTransaction('distribute'),ids,true);
 assert.equal(result.moved,1);
 const after=s.file,sh=after.project.sheets[0],gaps=sh.wires.map(w=>w.vertices.at(-1).at_um[0]-w.vertices[0].at_um[0]);
 assert.equal(gaps.reduce((a,b)=>a+b,0),oldGaps.reduce((a,b)=>a+b,0));
 assert.ok(Math.abs(gaps[0]-gaps[1])<=1);
 assert.deepEqual(sh.instances[0],sh0.instances[0]);assert.deepEqual(sh.instances[2],sh0.instances[2]);
 assert.ok(sh.wires.every(w=>w.vertices.length===2));
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.throws(()=>s.alignSeries(s.newTransaction('again'),ids,true),/NO_CHANGE/);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,after);
});
test('R20b fixed intermediate component cannot be moved to equalize pin gaps',()=>{
 const {s,ids,components}=seriesFixture([[60000,100000],[100000,100000],[210000,100000]]);
 // A locked middle UGO can participate in alignment, but must stay stationary.
 const doc=s.file,sh=doc.project.sheets[0];
 sh.layers.push({...sh.layers[0],id:'locked-middle',locked:true});
 sh.instances[1].layer_id='locked-middle';
 const locked=new AuthoringSession(doc),before=locked.file,rev=locked.revision;
 assert.throws(()=>locked.alignSeries(locked.newTransaction('fixed-spacing'),ids,true),/SERIES_FIXED_SPACING_CONFLICT/);
 assert.deepEqual(locked.file,before);assert.equal(locked.revision,rev);
});

test('R20 actual offset pins align each conductor rather than imposing equal symbol centers',()=>{
 const s=newSession();
 const ids=[
  s.place(s.newTransaction('r1'),'symbol/resistor.fixed',[60000,90000]),
  s.place(s.newTransaction('vt'),'symbol/transistor.bjt_npn',[120000,110000]),
  s.place(s.newTransaction('r2'),'symbol/resistor.fixed',[180000,100000])
 ];
 const [r1,vt,r2]=s.file.project.components;
 s.connect(s.newTransaction('first'),pin(r1.id,'2'),pin(vt.id,'1'));
 s.connect(s.newTransaction('second'),pin(vt.id,'2'),pin(r2.id,'1'));
 const before=s.file;
 s.alignSeries(s.newTransaction('offset-pins'),ids);
 const sh=s.file.project.sheets[0];
 assert.ok(sh.wires.every(w=>w.vertices.length===2&&w.vertices[0].at_um[1]===w.vertices[1].at_um[1]));
 assert.deepEqual(sh.instances.map(i=>i.origin_um),[[60000,110000],[120000,110000],[180000,100000]]);
 assert.deepEqual(s.file.project.nets.map(n=>n.members),before.project.nets.map(n=>n.members));
});
test('R20 blocked fixed axis rejects entire chain layout without moving any UGO',()=>{
 const {s,ids,components}=seriesFixture([[60000,90000],[120000,110000],[180000,100000]]);
 s.place(s.newTransaction('outer'),'symbol/resistor.fixed',[30000,90000]);
 const outer=s.file.project.components.at(-1).id;
 s.connect(s.newTransaction('outer-wire'),pin(outer,'2'),pin(components[0],'1'));
 s.place(s.newTransaction('blocker'),'symbol/resistor.fixed',[120000,90000]);
 const before=s.file,rev=s.revision;
 assert.throws(()=>s.alignSeries(s.newTransaction('blocked'),ids),/SERIES_NO_SAFE_LAYOUT/);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
});

function parallelFixture(vertical=true){
 const s=newSession();
 const positions=vertical?[[70000,100000],[130000,105000],[190000,95000]]:[[100000,60000],[105000,120000],[95000,180000]];
 const ids=positions.map((at,i)=>s.place(s.newTransaction('parallel-place-'+i),'symbol/resistor.fixed',at));
 const components=s.file.project.components.map(c=>c.id);
 if(vertical)for(const id of components)s.rotate(s.newTransaction('parallel-rotate'),id);
 for(const n of ['1','2'])for(let i=1;i<components.length;i++)
  s.connect(s.newTransaction('parallel-'+n+'-'+i),pin(components[i-1],n),pin(components[i],n));
 return {s,ids,components};
}
test('R21 parallel rails preserve two complete signed Nets and create only explicit degree-3 dots',()=>{
 const {s,ids}=parallelFixture(),before=s.file,rev=s.revision;
 const result=s.buildParallelRails(s.newTransaction('rails'),ids);
 assert.deepEqual(result,{branches:3,wires:10,junctions:2,axis:'horizontal'});
 const after=s.file,sh=after.project.sheets[0];
 assert.equal(s.revision,rev+1);
 assert.deepEqual(sh.instances,before.project.sheets[0].instances);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.name,n.members]),before.project.nets.map(n=>[n.id,n.name,n.members]));
 assert.equal(sh.splices.length,4);assert.equal(sh.junctions.length,2);
 for(const n of after.project.nets){
  assert.equal(s.engine.validateNet(n.id).pin_groups.length,1);
  const ws=sh.wires.filter(w=>w.net_id===n.id);
  assert.equal(ws.length,5);assert.ok(ws.every(w=>w.vertices.length===2&&w.needs_routing_review));
  const ends=ws.flatMap(w=>w.vertices.map(v=>v.anchor));
  const dot=sh.junctions.find(j=>j.net_id===n.id);
  assert.equal(ends.filter(a=>a.kind==='junction'&&a.junction_id===dot.id).length,3);
  for(const splice of sh.splices.filter(j=>j.net_id===n.id))
   assert.equal(ends.filter(a=>a.kind==='splice'&&a.splice_id===splice.id).length,2);
 }
 assert.throws(()=>s.buildParallelRails(s.newTransaction('again'),ids),/NO_CHANGE/);
 assert.deepEqual(s.file,after);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(new AuthoringSession(s.file).file,after);
});
test('R21 horizontal components get vertical rails without rotating the symbols',()=>{
 const {s,ids}=parallelFixture(false);
 const before=s.file;
 assert.equal(s.buildParallelRails(s.newTransaction('rails'),ids).axis,'vertical');
 assert.deepEqual(s.file.project.sheets[0].instances,before.project.sheets[0].instances);
 for(const n of s.file.project.nets){
  const nodes=[...s.file.project.sheets[0].junctions,...s.file.project.sheets[0].splices].filter(j=>j.net_id===n.id);
  assert.equal(new Set(nodes.map(j=>j.at_um[0])).size,1);
 }
});
test('R21 refuses shared external Net, incomplete geometry and blocked branch without mutation',()=>{
 const {s,ids,components}=parallelFixture();
 s.place(s.newTransaction('extra'),'symbol/resistor.fixed',[250000,100000]);
 const ext=s.file.project.components.at(-1).id;
 s.connect(s.newTransaction('external'),pin(components[2],'1'),pin(ext,'1'));
 const before=s.file,rev=s.revision;
 assert.throws(()=>s.buildParallelRails(s.newTransaction('external'),ids),/PARALLEL_REQUIRES_CLOSED_NETS/);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 const f=parallelFixture(),doc=f.s.file;
 doc.project.sheets[0].wires.shift();
 const disconnected=new AuthoringSession(doc);
 assert.throws(()=>disconnected.buildParallelRails(disconnected.newTransaction('incomplete'),f.ids),/PARALLEL_UNCONNECTED_NET/);
 assert.deepEqual(disconnected.file,doc);
 const b=parallelFixture();
 b.s.place(b.s.newTransaction('block'),'symbol/resistor.fixed',[130000,80000]);
 const blocked=b.s.file;
 assert.throws(()=>b.s.buildParallelRails(b.s.newTransaction('blocked'),b.ids),/PARALLEL_NO_SAFE_RAIL/);
 assert.deepEqual(b.s.file,blocked);
});

test('R21b symmetric parallel layout aligns both pin rows and distributes lateral physical contacts',()=>{
 const {s,ids}=parallelFixture();
 const beforeMove=s.file;
 // Shift the middle component and its attached route geometry using the
 // authoritative editor move rather than manually altering pin coordinates.
 const mid=beforeMove.project.components[1].id;
 s.move(s.newTransaction('unequal-spacing'),mid,[110000,105000],true);
 const before=s.file,rev=s.revision;
 const result=s.buildParallelRails(s.newTransaction('symmetry'),ids,true);
 const after=s.file,sh=after.project.sheets[0];
 assert.equal(result.branches,3);assert.equal(s.revision,rev+1);
 assert.deepEqual(sh.instances.map(i=>i.origin_um),[[70000,100000],[130000,100000],[190000,100000]]);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.ok(sh.wires.every(w=>w.vertices.length===2));
 assert.throws(()=>s.buildParallelRails(s.newTransaction('repeat'),ids,true),/NO_CHANGE/);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,after);
});
test('R21b fixed conflicting pin rows and blocked new component poses roll back atomically',()=>{
 const {s,ids}=parallelFixture();
 const doc=s.file,sh=doc.project.sheets[0];
 sh.layers.push({...sh.layers[0],id:'parallel-fixed',locked:true});
 sh.instances[0].layer_id='parallel-fixed';sh.instances[1].layer_id='parallel-fixed';
 const fixed=new AuthoringSession(doc),before=fixed.file;
 assert.throws(()=>fixed.buildParallelRails(fixed.newTransaction('fixed'),ids,true),/PARALLEL_FIXED_CONFLICT/);
 assert.deepEqual(fixed.file,before);
});

test('R22 read-only preview combines detected chain layout and commits once with signed topology unchanged',()=>{
 const {s,ids}=seriesFixture([[60000,90000],[120000,110000],[180000,100000]]);
 const before=s.file,rev=s.revision;
 const plan=s.previewLayout();
 assert.ok(plan.token);assert.equal(plan.before.bends,4);assert.equal(plan.after.bends,0);
 assert.ok(plan.after.lengthUm<plan.before.lengthUm);
 assert.ok(plan.operations.some(n=>n.includes('цепочки')));
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 s.applyLayoutPreview(s.newTransaction('apply'),plan.token);
 const after=s.file;
 assert.equal(s.revision,rev+1);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.ok(after.project.sheets[0].wires.every(w=>w.vertices.length===2));
 assert.throws(()=>s.applyLayoutPreview(s.newTransaction('repeat'),plan.token),/LAYOUT_PLAN_UNKNOWN/);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,after);
});
test('R22 canceled, overwritten and stale previews cannot modify the project',()=>{
 const {s,ids}=seriesFixture([[60000,90000],[120000,110000],[180000,100000]]);
 const before=s.file;
 const a=s.previewLayout(ids);s.discardLayoutPreview(a.token);
 assert.throws(()=>s.applyLayoutPreview(s.newTransaction('discarded'),a.token),/LAYOUT_PLAN_UNKNOWN/);
 assert.deepEqual(s.file,before);
 const b=s.previewLayout(ids),c=s.previewLayout(ids);
 assert.throws(()=>s.applyLayoutPreview(s.newTransaction('superseded'),b.token),/LAYOUT_PLAN_UNKNOWN/);
 s.undo();
 const next=s.file;
 assert.throws(()=>s.applyLayoutPreview(s.newTransaction('stale'),c.token),/STALE_REVISION/);
 assert.deepEqual(s.file,next);
});
test('R22 already clean circuit yields no mutation or plan; selected subset leaves other instances unchanged',()=>{
 const f=seriesFixture([[60000,100000],[120000,100000],[180000,100000]]);
 const before=f.s.file,rev=f.s.revision;
 const p=f.s.previewLayout();
 assert.equal(p.token,null);assert.deepEqual(p.before,p.after);
 assert.deepEqual(f.s.file,before);assert.equal(f.s.revision,rev);
 const g=seriesFixture([[60000,90000],[120000,110000],[180000,100000]]);
 g.s.place(g.s.newTransaction('unrelated'),'symbol/resistor.fixed',[250000,160000]);
 const outer=g.s.file.project.sheets[0].instances.at(-1);
 const selected=g.s.previewLayout(g.ids);
 assert.ok(selected.token);g.s.applyLayoutPreview(g.s.newTransaction('selected'),selected.token);
 assert.deepEqual(g.s.file.project.sheets[0].instances.at(-1),outer);
});
test('R22 automatic planning rejects sheets with unmodeled annotation envelopes',()=>{
 const {s}=seriesFixture([[60000,90000],[120000,110000],[180000,100000]]);
 const doc=s.file,sh=doc.project.sheets[0];
 sh.texts.push({id:'note',layer_id:sh.layers[0].id,text:'test',at_um:[100000,100000],rotation_deg:0,height_um:3500});
 const a=new AuthoringSession(doc);
 assert.throws(()=>a.previewLayout(),/LAYOUT_ANNOTATIONS_UNSUPPORTED/);
 assert.deepEqual(a.file,doc);
});

test('R22b preview document is detached and cannot change the committed candidate',()=>{
 const {s}=seriesFixture([[60000,90000],[120000,110000],[180000,100000]]);
 const before=s.file,plan=s.previewLayout();
 assert.ok(plan.token);
 const candidate=s.layoutPreviewDocument(plan.token),expected=structuredClone(candidate);
 candidate.project.sheets[0].instances[0].origin_um=[1,1];
 candidate.project.nets.length=0;
 assert.deepEqual(s.layoutPreviewDocument(plan.token),expected);
 assert.deepEqual(s.file,before);
 s.applyLayoutPreview(s.newTransaction('apply'),plan.token);
 assert.deepEqual(s.file,expected);
 assert.throws(()=>s.layoutPreviewDocument(plan.token),/LAYOUT_PLAN_UNKNOWN/);
});
test('R22b hidden or nonprintable used layers reject automatic preview, with no change',()=>{
 const {s}=seriesFixture([[60000,90000],[120000,110000],[180000,100000]]);
 for(const flag of ['visible','printable']){
  const doc=s.file;doc.project.sheets[0].layers[0][flag]=false;
  const a=new AuthoringSession(doc),before=a.file;
  assert.throws(()=>a.previewLayout(),/LAYOUT_HIDDEN_LAYER_UNSUPPORTED/);
  assert.deepEqual(a.file,before);assert.equal(a.revision,0);
 }
});

function hubFixture(){
 const doc=newBlankProject();
 const pins=[
  {physical_pin_number:'1',at_um:[-10000,-10000],side:'left'},
  {physical_pin_number:'2',at_um:[-10000,10000],side:'left'},
  {physical_pin_number:'3',at_um:[10000,-10000],side:'right'},
  {physical_pin_number:'4',at_um:[10000,10000],side:'right'}
 ];
 doc.project.part_definitions.push({id:'part/test-hub',reference_prefix:'DA',symbol_ids:['symbol/test-hub'],
  physical_pins:pins.map(p=>({number:p.physical_pin_number,name:p.physical_pin_number,electrical_type:'unspecified'}))});
 doc.project.symbol_definitions.push({id:'symbol/test-hub',part_id:'part/test-hub',revision:1,status:'draft',
  pins,standard_refs:[],graphics:[{kind:'rect',points_um:[[-5000,-15000],[5000,15000]],stroke_um:300},
   ...pins.map(p=>({kind:'line',points_um:[p.at_um,[p.at_um[0]/2,p.at_um[1]]],stroke_um:300}))]});
 const s=new AuthoringSession(doc);
 const hub=s.place(s.newTransaction('hub'),'symbol/test-hub',[150000,100000]);
 const leaves=[[80000,80000],[220000,75000],[220000,125000]].map((p,i)=>s.place(s.newTransaction('leaf'+i),'symbol/resistor.fixed',p));
 const [h,a,b,c]=s.file.project.components.map(c=>c.id);
 s.connect(s.newTransaction('left'),pin(a,'2'),pin(h,'1'));
 s.connect(s.newTransaction('right-top'),pin(h,'3'),pin(b,'1'));
 s.connect(s.newTransaction('right-bottom'),pin(h,'4'),pin(c,'1'));
 return {s,hub,leaves,h,a,b,c};
}
test('R23 fixed four-pin hub aligns facing satellites to individual signed pin rows',()=>{
 const {s,hub,leaves}=hubFixture(),before=s.file,rev=s.revision;
 const plan=s.previewLayout();
 assert.ok(plan.token);assert.equal(plan.before.bends,6);assert.equal(plan.after.bends,0);
 assert.equal(plan.operations.filter(n=>n.includes('Выводы DA1')).length,3);
 assert.deepEqual(s.file,before);
 const next=s.layoutPreviewDocument(plan.token),sh=next.project.sheets[0];
 assert.deepEqual(sh.instances.find(i=>i.id===hub),before.project.sheets[0].instances.find(i=>i.id===hub));
 assert.deepEqual(leaves.map(id=>sh.instances.find(i=>i.id===id).origin_um),[[80000,90000],[220000,90000],[220000,110000]]);
 assert.ok(sh.wires.every(w=>w.vertices.length===2));
 assert.deepEqual(next.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 s.applyLayoutPreview(s.newTransaction('apply-hub'),plan.token);
 assert.equal(s.revision,rev+1);assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,next);
});
test('R23 satellite with an external route stays fixed; unselected satellites are not moved',()=>{
 const {s,hub,leaves,b}=hubFixture();
 s.place(s.newTransaction('outside'),'symbol/resistor.fixed',[290000,75000]);
 const outside=s.file.project.components.at(-1).id;
 s.connect(s.newTransaction('outside-wire'),pin(b,'2'),pin(outside,'1'));
 const before=s.file,sh0=before.project.sheets[0];
 const plan=s.previewLayout([hub,leaves[0],leaves[1]]);
 assert.ok(plan.token);
 const next=s.layoutPreviewDocument(plan.token),sh=next.project.sheets[0];
 for(const id of [hub,leaves[1],leaves[2],sh0.instances.at(-1).id])
  assert.deepEqual(sh.instances.find(i=>i.id===id),sh0.instances.find(i=>i.id===id));
 assert.deepEqual(sh.wires.at(-1),sh0.wires.at(-1));
 assert.equal(sh.instances.find(i=>i.id===leaves[0]).origin_um[1],90000);
});

test('R23 topology inventory checks the real frozen TL494 source without mutating it',async()=>{
 const {topologyInventory}=await import('./topology-inventory.mjs');
 const file=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const before=structuredClone(file),report=topologyInventory(file,file.workspace.active_sheet_id);
 assert.equal(report.components,23);assert.equal(report.nets,15);
 const da=report.hubs.find(h=>h.refdes==='DA1');
 assert.equal(da.pins.length,16);assert.equal(da.netCount,9);
 assert.equal(da.pins.find(p=>p.number==='5').net,'OSCILLATOR_CT');
 assert.deepEqual(da.pins.find(p=>p.number==='5').neighbors,['C7']);
 assert.equal(da.pins.find(p=>p.number==='6').net,'OSCILLATOR_RT');
 assert.deepEqual(da.pins.find(p=>p.number==='6').neighbors,['R7']);
 const common=report.shared.find(n=>n.name==='COMMON');
 assert.equal(common.pins,14);assert.equal(common.devices,11);
 // The source uses mostly passive/unspecified pin types. Do not claim
 // a supply simply because a literal Net name resembles one.
 assert.equal(common.powerEvidence.length,0);
 assert.deepEqual(file,before);
});
test('R23 inventory distinguishes declared power evidence from literal Net names',async()=>{
 const {topologyInventory}=await import('./topology-inventory.mjs');
 const {s}=hubFixture(),file=s.file;
 const p=file.project.part_definitions.find(p=>p.id==='part/test-hub');
 p.physical_pins[0].electrical_type='power_input';
 const net=file.project.nets[0];net.name='not_a_supply_label';
 const r=topologyInventory(file,file.workspace.active_sheet_id);
 assert.equal(r.hubs[0].pins.find(p=>p.number==='1').type,'power_input');
 assert.equal(r.hubs[0].pins.find(p=>p.number==='1').net,'not_a_supply_label');
 assert.equal(r.shared.length,0);
});

function railFixture(opposed=false){
 const s=newSession();
 const positions=opposed?[[80000,70000],[220000,70000],[80000,130000],[220000,130000]]:
  [[70000,100000],[130000,115000],[190000,95000],[250000,110000]];
 const ids=positions.map((p,i)=>s.place(s.newTransaction('rail-place'+i),'symbol/resistor.fixed',p));
 const components=s.file.project.components.map(c=>c.id);
 if(!opposed)for(const id of components)s.rotate(s.newTransaction('rail-rotate'),id);
 const refs=components.map((id,i)=>pin(id,opposed?(i%2?'1':'2'):'1'));
 for(let i=1;i<refs.length;i++)s.connect(s.newTransaction('rail-connect'+i),refs[i-1],refs[i]);
 return {s,ids,components,refs,net:s.file.project.nets[0].id};
}
test('R24 reconstructs a single four-pin Net, leaves every symbol fixed and preserves exact signed connectivity',()=>{
 const {s,net}=railFixture(),before=s.file,rev=s.revision;
 const result=s.buildNetRail(s.newTransaction('rail'),net);
 assert.equal(result.axis,'horizontal');assert.equal(result.pins,4);assert.equal(result.wires,7);assert.equal(result.junctions,2);
 const after=s.file,sh=after.project.sheets[0];
 assert.equal(s.revision,rev+1);assert.deepEqual(sh.instances,before.project.sheets[0].instances);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.equal(sh.splices.length,2);assert.ok(sh.wires.every(w=>w.vertices.length===2));
 assert.equal(s.engine.validateNet(net).pin_groups.length,1);
 assert.throws(()=>s.buildNetRail(s.newTransaction('repeat'),net),/NO_CHANGE/);
 assert.deepEqual(s.file,after);assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(new AuthoringSession(s.file).file,after);
});
test('R24 opposed leads share taps only as explicit junctions, not geometrical inference',()=>{
 const {s,net}=railFixture(true),before=s.file;
 const result=s.buildNetRail(s.newTransaction('opposed'),net);
 assert.deepEqual({...result,lengthUm:0},{pins:4,wires:5,junctions:2,axis:'vertical',lengthUm:0});
 const sh=s.file.project.sheets[0];assert.equal(sh.splices.length,0);
 assert.deepEqual(sh.instances,before.project.sheets[0].instances);
 assert.equal(new Set(sh.junctions.map(n=>n.at_um[0])).size,1);
 for(const j of sh.junctions){
  const ends=sh.wires.flatMap(w=>w.vertices.map(v=>v.anchor));
  assert.equal(ends.filter(a=>a.kind==='junction'&&a.junction_id===j.id).length,3);
 }
 assert.equal(s.engine.validateNet(net).pin_groups.length,1);
});
test('R24 foreign obstruction and incomplete Net reject without mutation',()=>{
 const {s,net}=railFixture();
 s.place(s.newTransaction('obstruction'),'symbol/resistor.fixed',[130000,80000]);
 const before=s.file,rev=s.revision;
 assert.throws(()=>s.buildNetRail(s.newTransaction('blocked'),net),/RAIL_NO_SAFE_CHANNEL/);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 const f=railFixture(),doc=f.s.file;
 doc.project.sheets[0].wires.shift();
 const incomplete=new AuthoringSession(doc);
 assert.throws(()=>incomplete.buildNetRail(incomplete.newTransaction('incomplete'),f.net),/RAIL_UNCONNECTED_NET/);
 assert.deepEqual(incomplete.file,doc);
});
function mixedRailFixture(){
 const s=newSession();
 for(const p of [[80000,70000],[160000,100000],[240000,130000]])s.place(s.newTransaction('p'),'symbol/resistor.fixed',p);
 const [a,b,c]=s.file.project.components.map(c=>c.id);
 s.rotate(s.newTransaction('r'),b);
 s.connect(s.newTransaction('ab'),pin(a,'1'),pin(b,'1'));
 s.connect(s.newTransaction('bc'),pin(b,'1'),pin(c,'1'));
 return {s,net:s.file.project.nets[0].id};
}
test('R25 mixed-axis Net uses a direct trunk and one L-shaped lead while preserving the signed model',()=>{
 const {s,net}=mixedRailFixture(),before=s.file,rev=s.revision;
 const result=s.buildNetRail(s.newTransaction('mixed'),net);
 assert.equal(result.axis,'vertical');assert.equal(result.pins,3);
 const after=s.file,sh=after.project.sheets[0];
 assert.deepEqual(sh.instances,before.project.sheets[0].instances);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.equal(sh.wires.filter(w=>w.vertices.length===3).length,1);
 assert.ok(sh.wires.every(w=>w.vertices.length<=3));
 assert.equal(s.engine.validateNet(net).pin_groups.length,1);
 for(const w of sh.wires){
  const v=w.vertices[0];if(v.anchor.kind!=='pin')continue;
  const p=s.beginWire(v.anchor),q=w.vertices[1].at_um;
  assert.deepEqual([Math.sign(q[0]-v.at_um[0]),Math.sign(q[1]-v.at_um[1])],p.normal.map(v=>v===0?0:v));
 }
 assert.equal(s.revision,rev+1);
 assert.throws(()=>s.buildNetRail(s.newTransaction('repeat'),net),/NO_CHANGE/);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(new AuthoringSession(s.file).file,after);
});
test('R25 selected common trunk keeps unrelated Net geometry byte-for-byte',()=>{
 const {s,net}=mixedRailFixture();
 const ids=[];
 for(const p of [[300000,200000],[360000,200000]]){
  s.place(s.newTransaction('other'),'symbol/resistor.fixed',p);ids.push(s.file.project.components.at(-1).id);
 }
 s.connect(s.newTransaction('other-wire'),pin(ids[0],'2'),pin(ids[1],'1'));
 const before=s.file,other=before.project.nets.at(-1);
 s.buildNetRail(s.newTransaction('mixed'),net);
 assert.deepEqual(s.file.project.sheets[0].wires.filter(w=>w.net_id===other.id),before.project.sheets[0].wires.filter(w=>w.net_id===other.id));
 assert.deepEqual(s.file.project.nets.at(-1),other);
});


test('R26 orthogonal tree bypasses obstruction that blocks a single straight rail',()=>{
 const {s,net}=railFixture();
 s.place(s.newTransaction('obstruction'),'symbol/resistor.fixed',[130000,80000]);
 const before=s.file,rev=s.revision;
 assert.throws(()=>s.buildNetRail(s.newTransaction('blocked'),net),/RAIL_NO_SAFE_CHANNEL/);
 assert.deepEqual(s.file,before);
 const result=s.buildNetTree(s.newTransaction('tree'),net),after=s.file,sh=after.project.sheets[0];
 assert.equal(result.pins,4);assert.ok(result.junctions>=1);
 assert.equal(s.revision,rev+1);assert.deepEqual(sh.instances,before.project.sheets[0].instances);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.equal(s.engine.validateNet(net).pin_groups.length,1);
 assert.equal(sh.splices.length,0);
 const terminals=sh.wires.flatMap(w=>[w.vertices[0].anchor,w.vertices.at(-1).anchor]);
 assert.equal(terminals.filter(a=>a.kind==='pin').length,4);
 for(const j of sh.junctions)assert.ok(terminals.filter(a=>a.kind==='junction'&&a.junction_id===j.id).length>=3);
 assert.equal(sh.wires.length,4+sh.junctions.length-1);
 for(const w of sh.wires)for(let i=1;i<w.vertices.length;i++){
  const a=w.vertices[i-1].at_um,b=w.vertices[i].at_um;
  assert.ok((a[0]===b[0])!== (a[1]===b[1]));
 }
 assert.throws(()=>s.buildNetTree(s.newTransaction('repeat'),net),/NO_CHANGE/);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(new AuthoringSession(s.file).file,after);
});
test('R26 tree rejects disconnected signed membership without modifying the document',()=>{
 const {s,net}=railFixture(),doc=s.file;
 doc.project.sheets[0].wires.shift();
 const a=new AuthoringSession(doc);
 assert.throws(()=>a.buildNetTree(a.newTransaction('incomplete'),net),/RAIL_UNCONNECTED_NET/);
 assert.deepEqual(a.file,doc);assert.equal(a.revision,0);
});


// Direct production planner regression: the visible bends at the physical
// pin leads must count, not merely the internal visibility-grid edges.
test('R27 signed leads remove three unnecessary bends without increasing length',async()=>{
 const {planOrthogonalTree}=await import('./orthogonal-tree.ts');
 const ports=[
  {pin:[20000,50000],tip:[22000,50000]},
  {pin:[70000,60000],tip:[70000,58000]},
  {pin:[80000,30000],tip:[78000,30000]},
 ];
 const frame={minX:0,minY:0,maxX:100000,maxY:100000};
 const before=structuredClone(ports),plan=planOrthogonalTree(ports,[],frame);
 assert.ok(plan);
 // R26 produced 98 mm and four bends on exactly these ports.
 assert.equal(plan.lengthUm,90000);assert.equal(plan.bends,1);
 assert.deepEqual(plan.nodes,[[70000,50000]]);
 const seen=[];
 for(const path of plan.paths){
  for(const [idx,points] of [[path.startPin,path.points],[path.endPin,[...path.points].reverse()]]){
   if(idx===null)continue;
   seen.push(idx);
   assert.deepEqual(points[0],ports[idx].pin);
   const d=ports[idx].tip.map((v,i)=>v-ports[idx].pin[i]);
   const next=points[1].map((v,i)=>v-points[0][i]);
   const axis=d[0]!==0?0:1;
   assert.equal(next[1-axis],0);
   assert.ok(next[axis]*Math.sign(d[axis])>=Math.abs(d[axis]));
  }
 }
 assert.deepEqual(seen.sort((a,b)=>a-b),[0,1,2]);
 assert.deepEqual(ports,before);
 assert.deepEqual(planOrthogonalTree(ports,[],frame),plan);
});

test('R27 terminal entry axis improves equal-length tree rather than adding a staircase',async()=>{
 const {planOrthogonalTree}=await import('./orthogonal-tree.ts');
 const ports=[
  {pin:[30000,20000],tip:[32000,20000]},
  {pin:[40000,70000],tip:[38000,70000]},
  {pin:[10000,80000],tip:[10000,78000]},
 ];
 const plan=planOrthogonalTree(ports,[],{minX:0,minY:0,maxX:100000,maxY:100000});
 assert.ok(plan);
 // R26: 98 mm, 3 bends. R27: same length, 2 bends.
 assert.equal(plan.lengthUm,98000);assert.equal(plan.bends,2);
});


// R28 deliberately starts only with a fully declared, wholly unrouted Net.
test('R28 initial routing joins four declared PinRefs, leaves foreign route and membership unchanged, and roundtrips Undo/Redo',async()=>{
 const {s,net}=railFixture();
 const ids=[];
 for(const p of [[300000,200000],[360000,200000]]){
  s.place(s.newTransaction('foreign'),'symbol/resistor.fixed',p);ids.push(s.file.project.components.at(-1).id);
 }
 s.connect(s.newTransaction('foreign-wire'),pin(ids[0],'2'),pin(ids[1],'1'));
 const doc=s.file,sh=doc.project.sheets[0];
 sh.wires=sh.wires.filter(w=>w.net_id!==net);
 doc.project.nets.find(n=>n.id===net).route_status='unrouted';
 const a=new AuthoringSession(doc),before=a.file;
 const {topologyInventory}=await import('./topology-inventory.mjs');
 assert.ok(topologyInventory(before,sh.id).unrouted.some(n=>n.id===net));
 assert.equal(a.engine.validateNet(net).pin_groups.length,4);
 const result=a.buildNetTree(a.newTransaction('initial'),net,true),after=a.file;
 assert.equal(result.pins,4);assert.equal(a.revision,1);
 assert.deepEqual(after.project.components,before.project.components);
 assert.deepEqual(after.project.sheets[0].instances,sh.instances);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.deepEqual(after.project.sheets[0].wires.filter(w=>w.net_id!==net),sh.wires);
 assert.deepEqual(after.project.nets.filter(n=>n.id!==net),before.project.nets.filter(n=>n.id!==net));
 assert.equal(a.engine.validateNet(net).pin_groups.length,1);
 assert.ok(after.project.sheets[0].wires.filter(w=>w.net_id===net).every(w=>w.needs_routing_review));
 assert.ok(!topologyInventory(after,sh.id).unrouted.some(n=>n.id===net));
 assert.throws(()=>a.buildNetTree(a.newTransaction('again'),net,true),/TREE_ALREADY_ROUTED/);
 assert.deepEqual(a.file,after);assert.equal(a.revision,1);
 assert.equal(a.undo(),true);assert.deepEqual(a.file,before);
 assert.equal(a.redo(),true);assert.deepEqual(new AuthoringSession(a.file).file,after);
});
test('R28 two facing physical pins create a single straight route',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.connect(s.newTransaction('declare'),pin(r,'2'),pin(c,'1'));
 const doc=s.file,net=doc.project.nets[0];doc.project.sheets[0].wires=[];net.route_status='unrouted';
 const a=new AuthoringSession(doc);
 const plan=a.buildNetTree(a.newTransaction('route'),net.id,true);
 assert.equal(plan.pins,2);assert.equal(plan.wires,1);assert.equal(plan.junctions,0);assert.equal(plan.bends,0);
 assert.equal(a.engine.validateNet(net.id).pin_groups.length,1);
});
test('R28 refuses partial/manual geometry, stale revision and locked layer without mutation',()=>{
 const {s,net}=railFixture(),doc=s.file;
 doc.project.sheets[0].wires.shift();
 const partial=new AuthoringSession(doc);
 assert.throws(()=>partial.buildNetTree(partial.newTransaction('partial'),net,true),/TREE_ALREADY_ROUTED/);
 assert.deepEqual(partial.file,doc);assert.equal(partial.revision,0);
 doc.project.sheets[0].wires=[];doc.project.nets[0].route_status='unrouted';
 const a=new AuthoringSession(doc),stale=a.newTransaction('stale');
 a.place(a.newTransaction('other'),'symbol/resistor.fixed',[320000,220000]);
 const before=a.file;
 assert.throws(()=>a.buildNetTree(stale,net,true),/STALE_REVISION/);
 assert.deepEqual(a.file,before);
 doc.project.sheets[0].layers.find(l=>l.kind==='electrical').locked=true;
 const locked=new AuthoringSession(doc);
 assert.throws(()=>locked.buildNetTree(locked.newTransaction('locked'),net,true),/TREE_ELECTRICAL_LAYER_AMBIGUOUS/);
 assert.deepEqual(locked.file,doc);assert.equal(locked.revision,0);
});


function batchRouteFixture(){
 const s=newSession();
 for(const p of [[80000,80000],[180000,80000],[80000,180000],[180000,180000]])
  s.place(s.newTransaction('batch-place'),'symbol/resistor.fixed',p);
 const [a,b,c,d]=s.file.project.components.map(c=>c.id);
 s.connect(s.newTransaction('ab'),pin(a,'2'),pin(b,'1'));
 s.connect(s.newTransaction('cd'),pin(c,'2'),pin(d,'1'));
 const doc=s.file,ids=doc.project.nets.map(n=>n.id);
 doc.project.sheets[0].wires=[];for(const n of doc.project.nets)n.route_status='unrouted';
 return {doc,ids,session:new AuthoringSession(doc)};
}
test('R29 two untouched Nets are routed in a single history entry with fixed physical topology',()=>{
 const {session:s,ids,doc}=batchRouteFixture();
 const result=s.routeInitialNets(s.newTransaction('batch'),ids),after=s.file;
 assert.equal(result.nets,2);assert.equal(result.wires,2);assert.equal(result.bends,0);
 assert.equal(result.attempts,2);assert.equal(s.revision,1);
 assert.deepEqual(after.project.components,doc.project.components);
 assert.deepEqual(after.project.sheets[0].instances,doc.project.sheets[0].instances);
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),doc.project.nets.map(n=>[n.id,n.members]));
 for(const id of ids)assert.equal(s.engine.validateNet(id).pin_groups.length,1);
 assert.ok(after.project.sheets[0].wires.every(w=>w.needs_routing_review));
 assert.equal(s.undo(),true);assert.deepEqual(s.file,doc);assert.equal(s.canUndo,false);
 assert.equal(s.redo(),true);assert.deepEqual(new AuthoringSession(s.file).file,after);
});
test('R29 failure of a later Net rolls back the entire batch, including successful earlier trial',()=>{
 const {session:s,ids}=batchRouteFixture();
 s.buildNetTree(s.newTransaction('existing'),ids[1],true);
 const before=s.file,rev=s.revision;
 assert.throws(()=>s.routeInitialNets(s.newTransaction('batch'),ids),/BATCH_NO_SAFE_ROUTE.*TREE_ALREADY_ROUTED/);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 assert.equal(s.engine.validateNet(ids[0]).status,'unrouted');
 assert.equal(s.undo(),true);assert.equal(s.file.project.sheets[0].wires.length,0);
 assert.equal(s.canUndo,false);
});
test('R29 rejects stale, duplicate, unknown and oversized batches without modifying history',()=>{
 const {session:s,ids,doc}=batchRouteFixture();
 assert.throws(()=>s.routeInitialNets(s.newTransaction('empty'),[]),/BATCH_NET_COUNT/);
 assert.throws(()=>s.routeInitialNets(s.newTransaction('large'),Array(9).fill(ids[0])),/BATCH_NET_COUNT/);
 assert.throws(()=>s.routeInitialNets(s.newTransaction('duplicate'),[ids[0],ids[0]]),/BATCH_DUPLICATE_NET/);
 assert.throws(()=>s.routeInitialNets(s.newTransaction('unknown'),['not-a-net']),/UNKNOWN_NET/);
 assert.deepEqual(s.file,doc);assert.equal(s.canUndo,false);
 const old=s.newTransaction('stale');
 s.buildNetTree(s.newTransaction('single'),ids[0],true);const before=s.file;
 assert.throws(()=>s.routeInitialNets(old,[ids[1]]),/STALE_REVISION/);
 assert.deepEqual(s.file,before);
});


function multiAlignFixture(){
 const f=hubFixture(),{s,b}=f;
 const outside=s.place(s.newTransaction('outside'),'symbol/resistor.fixed',[290000,90000]);
 const external=s.file.project.components.at(-1).id;
 s.connect(s.newTransaction('second-route'),pin(b,'2'),pin(external,'1'));
 return {...f,outside,external,moving:f.leaves[1]};
}
test('R30 aligns a two-pin satellite with two direct routes, keeping both neighbors fixed',()=>{
 const {s,moving,b}=multiAlignFixture(),before=s.file,rev=s.revision,sh=before.project.sheets[0];
 const ids=sh.wires.filter(w=>w.vertices.some(v=>v.anchor.kind==='pin'&&v.anchor.component_id===b)).map(w=>w.id);
 const result=s.alignMultiConnected(s.newTransaction('multi-align'),moving);
 const after=s.file,ns=after.project.sheets[0];
 assert.equal(result.moved,moving);assert.deepEqual(result.delta,[0,15000]);assert.equal(result.wires,2);
 assert.deepEqual(ns.instances.find(i=>i.id===moving).origin_um,[220000,90000]);
 assert.deepEqual(ns.instances.filter(i=>i.id!==moving),sh.instances.filter(i=>i.id!==moving));
 assert.deepEqual(ns.wires.filter(w=>!ids.includes(w.id)),sh.wires.filter(w=>!ids.includes(w.id)));
 for(const id of ids){
  const old=sh.wires.find(w=>w.id===id),now=ns.wires.find(w=>w.id===id);
  assert.equal(now.vertices.length,2);assert.equal(now.vertices[0].id,old.vertices[0].id);
  assert.equal(now.vertices.at(-1).id,old.vertices.at(-1).id);
 }
 assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),before.project.nets.map(n=>[n.id,n.members]));
 assert.equal(s.revision,rev+1);assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(new AuthoringSession(s.file).file,after);
});
test('R30 global preview discovers the multi-connected satellite missed by the simple chain solver',()=>{
 const {s,moving}=multiAlignFixture(),before=s.file,rev=s.revision;
 const plan=s.previewLayout();
 assert.ok(plan.token);assert.ok(plan.operations.some(n=>n.includes('Совместное выравнивание')));
 assert.equal(plan.after.bends,0);assert.ok(plan.after.lengthUm<plan.before.lengthUm);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 const candidate=s.layoutPreviewDocument(plan.token);
 assert.deepEqual(candidate.project.sheets[0].instances.find(i=>i.id===moving).origin_um,[220000,90000]);
 s.applyLayoutPreview(s.newTransaction('apply'),plan.token);
 assert.deepEqual(s.file,candidate);
});
test('R30 refuses external scope, locked layer and occupied target with exact rollback',()=>{
 const f=multiAlignFixture(),{s,moving,hub}=f;
 const before=s.file,rev=s.revision;
 assert.throws(()=>s.alignMultiConnected(s.newTransaction('scope'),moving,[hub,moving]),/MULTI_EXTERNAL_OR_BRANCH/);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 const doc=s.file,sh=doc.project.sheets[0];
 sh.layers.push({...sh.layers[0],id:'fixed-satellite',locked:true});
 sh.instances.find(i=>i.id===moving).layer_id='fixed-satellite';
 const locked=new AuthoringSession(doc);
 assert.throws(()=>locked.alignMultiConnected(locked.newTransaction('locked'),moving),/LAYER_LOCKED/);
 assert.deepEqual(locked.file,doc);
 s.place(s.newTransaction('block'),'symbol/resistor.fixed',[220000,90000]);
 const blocked=s.file,r=s.revision;
 assert.throws(()=>s.alignMultiConnected(s.newTransaction('blocked'),moving),/MULTI_NO_SAFE_IMPROVEMENT/);
 assert.deepEqual(s.file,blocked);assert.equal(s.revision,r);
});


test('R32a initial route goes around non-electrical sheet ink and preserves it byte-for-byte',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.connect(s.newTransaction('declare'),pin(r,'2'),pin(c,'1'));
 const doc=s.file,sh=doc.project.sheets[0],net=doc.project.nets[0];
 sh.wires=[];net.route_status='unrouted';
 const layer=sh.layers.find(l=>l.kind==='electrical').id;
 sh.graphics.push({id:'visual-line',layer_id:layer,kind:'line',points_um:[[127500,95000],[127500,105000]],stroke_um:300});
 sh.labels.push({id:'visual-label',layer_id:layer,role:'visual',net_id:null,text:'b',at_um:[120000,120000]});
 const a=new AuthoringSession(doc);
 const route=a.buildNetTree(a.newTransaction('route-visual'),net.id,true),after=a.file.project.sheets[0];
 assert.ok(route.bends>=2);
 assert.deepEqual(after.graphics,sh.graphics);assert.deepEqual(after.labels,sh.labels);
 for(const w of after.wires)for(let i=1;i<w.vertices.length;i++){
  const p=w.vertices[i-1].at_um,q=w.vertices[i].at_um;
  assert.ok(Math.max(p[0],q[0])<126350||Math.min(p[0],q[0])>128650||
    Math.max(p[1],q[1])<93850||Math.min(p[1],q[1])>106150);
 }
 assert.equal(a.engine.validateNet(net.id).pin_groups.length,1);
 assert.equal(a.undo(),true);assert.deepEqual(a.file,doc);
 const bad=structuredClone(doc);bad.project.sheets[0].labels[0].role='net_annotation';
 bad.project.sheets[0].labels[0].net_id=net.id;
 const b=new AuthoringSession(bad);
 assert.throws(()=>b.buildNetTree(b.newTransaction('reject-label'),net.id,true),/LAYOUT_ANNOTATIONS_UNSUPPORTED/);
 assert.deepEqual(b.file,bad);
});

test('R32a frozen TL494 independent-Net preflight on a detached test-only synthetic copy',t=>{
 const source=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const original=structuredClone(source);
 assert.throws(()=>new AuthoringSession(source),/SOURCE_SHA_MISMATCH/);
 const doc=structuredClone(source),p=doc.project,sh=p.sheets[0];
 p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/TL494-routing-preflight',
   expected_counts:{...p.provenance.expected_counts}};
 const outcomes=[];
 for(const net of p.nets){
  const session=new AuthoringSession(doc);
  let route;
  try{route=session.buildNetTree(session.newTransaction('preflight'),net.id,true)}
  catch(e){
   assert.equal(e.name,'WireError');assert.deepEqual(session.file,doc);assert.equal(session.revision,0);
   outcomes.push({net:net.name,pins:net.members.length,rejected:e.code});continue;
  }
  const after=session.file;
  assert.equal(session.engine.validateNet(net.id).pin_groups.length,1);
  assert.deepEqual(after.project.nets.map(n=>[n.id,n.members]),p.nets.map(n=>[n.id,n.members]));
  assert.deepEqual(after.project.sheets[0].instances,sh.instances);
  assert.deepEqual(after.project.sheets[0].graphics,sh.graphics);
  assert.deepEqual(after.project.sheets[0].labels,sh.labels);
  assert.ok(after.project.sheets[0].wires.every(w=>w.net_id===net.id&&w.needs_routing_review));
  outcomes.push({net:net.name,pins:net.members.length,bends:route.bends,lengthUm:route.lengthUm});
 }
 assert.equal(outcomes.length,15);
 assert.equal(outcomes.reduce((n,o)=>n+o.pins,0),62);
 assert.equal(sh.graphics.length,2);assert.deepEqual(source,original);
 t.diagnostic('TL494_R32A_PREFLIGHT '+JSON.stringify(outcomes));
 // Diagnostic only: independent feasibility is not simultaneous routing.
});


test('R32b margin repair reserves signed leads before routing, preserves membership and supports Undo',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.connect(s.newTransaction('declare'),pin(r,'1'),pin(c,'1'));
 const doc=s.file,sh=doc.project.sheets[0],net=doc.project.nets[0];
 sh.wires=[];net.route_status='unrouted';sh.instances.find(i=>i.component_id===r).origin_um=[18000,100000];
 const a=new AuthoringSession(doc);
 assert.throws(()=>a.buildNetTree(a.newTransaction('blocked'),net.id,true),/TREE_PIN_LEAD_OUTSIDE_FRAME/);
 assert.deepEqual(a.file,doc);
 const repair=a.prepareInitialRouting(a.newTransaction('prepare')),prepared=a.file;
 assert.equal(repair.moved,1);assert.ok(repair.maxShiftUm>=3000);
 assert.deepEqual(prepared.project.nets,doc.project.nets);
 assert.deepEqual(prepared.project.sheets[0].instances.find(i=>i.component_id===c),sh.instances.find(i=>i.component_id===c));
 assert.throws(()=>a.prepareInitialRouting(a.newTransaction('repeat')),/NO_CHANGE/);
 assert.equal(a.undo(),true);assert.deepEqual(a.file,doc);
 assert.equal(a.redo(),true);assert.deepEqual(a.file,prepared);
 a.buildNetTree(a.newTransaction('route'),net.id,true);
 assert.equal(a.engine.validateNet(net.id).pin_groups.length,1);
 assert.throws(()=>a.prepareInitialRouting(a.newTransaction('wired')),/PREPARE_REQUIRES_UNROUTED_SHEET/);
});
test('R32b rejects locked edge component and occupied inset target atomically',()=>{
 const s=newSession(),{r}=placePair(s),doc=s.file,sh=doc.project.sheets[0];
 sh.instances.find(i=>i.component_id===r).origin_um=[18000,100000];
 const locked=structuredClone(doc);locked.project.sheets[0].layers.find(l=>l.kind==='electrical').locked=true;
 const a=new AuthoringSession(locked);
 assert.throws(()=>a.prepareInitialRouting(a.newTransaction('locked')),/LAYER_LOCKED/);
 assert.deepEqual(a.file,locked);assert.equal(a.revision,0);
 sh.graphics.push({id:'block',kind:'line',layer_id:sh.layers[0].id,points_um:[[29500,96000],[29500,104000]],stroke_um:300});
 const b=new AuthoringSession(doc);
 assert.throws(()=>b.prepareInitialRouting(b.newTransaction('blocked')),/PREPARE_NO_SAFE_PLACEMENT/);
 assert.deepEqual(b.file,doc);assert.equal(b.revision,0);
});
test('R32b real TL494 independent-Net preflight after explicit margin repair',t=>{
 const source=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const original=structuredClone(source),doc=structuredClone(source),p=doc.project,sh=p.sheets[0];
 p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/TL494-margin-preflight',
  expected_counts:{...p.provenance.expected_counts}};
 const preparation=new AuthoringSession(doc);
 const repair=preparation.prepareInitialRouting(preparation.newTransaction('inset')),prepared=preparation.file;
 assert.ok(repair.moved>=4);
 assert.deepEqual(prepared.project.nets,p.nets);
 assert.deepEqual(prepared.project.sheets[0].graphics,sh.graphics);
 assert.deepEqual(prepared.project.sheets[0].labels,sh.labels);
 assert.equal(preparation.undo(),true);assert.deepEqual(preparation.file,doc);
 const outcomes=[];
 for(const net of p.nets){
  const trial=new AuthoringSession(prepared);
  try{
   const route=trial.buildNetTree(trial.newTransaction('preflight'),net.id,true);
   assert.equal(trial.engine.validateNet(net.id).pin_groups.length,1);
   assert.deepEqual(trial.file.project.nets.map(n=>[n.id,n.members]),p.nets.map(n=>[n.id,n.members]));
   assert.deepEqual(trial.file.project.sheets[0].instances,prepared.project.sheets[0].instances);
   assert.deepEqual(trial.file.project.sheets[0].graphics,sh.graphics);
   assert.deepEqual(trial.file.project.sheets[0].labels,sh.labels);
   outcomes.push({net:net.name,pins:net.members.length,bends:route.bends,lengthUm:route.lengthUm});
  }catch(e){
   assert.equal(e.name,'WireError');assert.notEqual(e.code,'TREE_PIN_LEAD_OUTSIDE_FRAME');
   assert.deepEqual(trial.file,prepared);outcomes.push({net:net.name,pins:net.members.length,rejected:e.code});
  }
 }
 t.diagnostic('TL494_R32B_PREFLIGHT '+JSON.stringify({repair,outcomes}));
 assert.equal(outcomes.length,15);assert.equal(outcomes.reduce((n,o)=>n+o.pins,0),62);
 assert.deepEqual(source,original);
});


test('R32c complete multi-order preview is read-only until explicit atomic Apply',()=>{
 const {session:s,ids,doc}=batchRouteFixture();
 const p=s.previewInitialBatch(ids);
 assert.equal(p.requested,2);assert.equal(p.routed,2);assert.ok(p.token);
 assert.ok(p.attempted>=2&&p.attempted<=6);assert.equal(p.quality.bends,0);
 assert.deepEqual(s.file,doc);assert.equal(s.revision,0);assert.equal(s.canUndo,false);
 const candidate=s.layoutPreviewDocument(p.token);
 assert.equal(candidate.project.sheets[0].wires.length,2);
 s.applyLayoutPreview(s.newTransaction('apply'),p.token);
 for(const id of ids)assert.equal(s.engine.validateNet(id).pin_groups.length,1);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,doc);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,candidate);
});
test('R32c partial feasibility has no Apply token and cannot mutate the live document',()=>{
 const {doc,ids}=batchRouteFixture(),sh=doc.project.sheets[0];
 sh.instances[0].rotation_deg=180;sh.instances[0].origin_um=[18000,80000];
 const s=new AuthoringSession(doc);
 const p=s.previewInitialBatch(ids);
 assert.equal(p.routed,1);assert.equal(p.requested,2);assert.equal(p.token,null);
 assert.equal(p.outcomes.find(o=>o.id===ids[0]).rejected,'TREE_PIN_LEAD_OUTSIDE_FRAME');
 assert.deepEqual(s.file,doc);assert.equal(s.revision,0);assert.equal(s.canUndo,false);
 assert.throws(()=>s.previewInitialBatch([ids[0],ids[0]]),/BATCH_DUPLICATE_NET/);
 assert.throws(()=>s.previewInitialBatch(Array(17).fill(ids[0])),/BATCH_NET_COUNT/);
 assert.deepEqual(s.file,doc);
});
test('R32c whole-sheet TL494 multi-order simultaneous routing diagnostic',t=>{
 const source=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const original=structuredClone(source),doc=structuredClone(source),p=doc.project,sh=p.sheets[0];
 p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/TL494-multinet-preflight',
  expected_counts:{...p.provenance.expected_counts}};
 const s=new AuthoringSession(doc);
 s.prepareInitialRouting(s.newTransaction('prepare'));
 const prepared=s.file,rev=s.revision;
 const report=s.previewInitialBatch(p.nets.map(n=>n.id));
 assert.equal(report.requested,15);assert.ok(report.attempted<=45);
 assert.equal(report.outcomes.reduce((a,o)=>a+o.pins,0),62);
 assert.deepEqual(s.file,prepared);assert.equal(s.revision,rev);
 assert.equal(report.quality.crossings,0);
 if(report.token){
  const candidate=s.layoutPreviewDocument(report.token);
  assert.equal(report.routed,15);
  s.applyLayoutPreview(s.newTransaction('apply'),report.token);
  for(const n of p.nets)assert.equal(s.engine.validateNet(n.id).pin_groups.length,1);
  assert.deepEqual(s.file,candidate);assert.deepEqual(s.file.project.nets.map(n=>[n.id,n.members]),p.nets.map(n=>[n.id,n.members]));
  assert.deepEqual(s.file.project.sheets[0].graphics,sh.graphics);assert.deepEqual(s.file.project.sheets[0].labels,sh.labels);
 }else assert.ok(report.routed<15);
 t.diagnostic('TL494_R32C_MULTINET '+JSON.stringify({...report,token:!!report.token}));
 assert.deepEqual(source,original);
});


test('R32d crossing graph spans foreign keepout only at strict interior, never with an anchor',async()=>{
 const {planOrthogonalTree}=await import('./orthogonal-tree.ts');
 const frame={minX:0,minY:0,maxX:100000,maxY:100000};
 const ports=[{pin:[10000,50000],tip:[12000,50000]},{pin:[90000,50000],tip:[88000,50000]}];
 const foreign={a:[50000,0],b:[50000,100000],clearance:1000};
 assert.equal(planOrthogonalTree(ports,[{minX:49000,maxX:51000,minY:-1000,maxY:101000}],frame),null);
 const p=planOrthogonalTree(ports,[],frame,[foreign]);
 assert.ok(p);assert.equal(p.bends,0);assert.equal(p.nodes.length,0);
 assert.deepEqual(p.paths[0].points,[[10000,50000],[90000,50000]]);
 // A physical lead ending inside foreign keepout is never a crossing.
 const blocked=[ports[0],{pin:[52000,50000],tip:[50000,50000]}];
 assert.equal(planOrthogonalTree(blocked,[],frame,[foreign]),null);
 // A perpendicular edge cannot cross inside an explicit junction obstacle.
 const full=[{minX:49000,maxX:51000,minY:0,maxY:100000}];
 assert.equal(planOrthogonalTree(ports,full,frame,[foreign]),null);
});
test('R32d controlled whole-sheet preview preserves existing strict success and atomicity',()=>{
 const {session:s,ids,doc}=batchRouteFixture();
 const p=s.previewInitialBatch(ids,true);
 assert.equal(p.routed,2);assert.ok(p.token);assert.equal(p.quality.crossings,0);
 assert.deepEqual(s.file,doc);assert.equal(s.revision,0);
 s.applyLayoutPreview(s.newTransaction('apply'),p.token);
 for(const id of ids)assert.equal(s.engine.validateNet(id).pin_groups.length,1);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,doc);
});
test('R32e actual TL494 adaptive-grid and blocked-first diagnostic',t=>{
 const source=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const original=structuredClone(source),doc=structuredClone(source),p=doc.project,sh=p.sheets[0];
 p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/TL494-controlled-crossing',
  expected_counts:{...p.provenance.expected_counts}};
 const s=new AuthoringSession(doc);
 s.prepareInitialRouting(s.newTransaction('prepare'));
 const prepared=s.file,rev=s.revision;
 const report=s.previewInitialBatch(p.nets.map(n=>n.id),true);
 assert.equal(report.requested,15);assert.ok(report.attempted<=75);
 assert.equal(report.outcomes.reduce((a,o)=>a+o.pins,0),62);
 assert.equal(report.quality.errors,0);assert.equal(report.quality.geometryWarnings,0);
 assert.deepEqual(s.file,prepared);assert.equal(s.revision,rev);
 if(report.token){
  s.applyLayoutPreview(s.newTransaction('apply'),report.token);
  for(const n of p.nets)assert.equal(s.engine.validateNet(n.id).pin_groups.length,1);
  assert.deepEqual(s.file.project.nets.map(n=>[n.id,n.members]),p.nets.map(n=>[n.id,n.members]));
  assert.deepEqual(s.file.project.sheets[0].graphics,sh.graphics);assert.deepEqual(s.file.project.sheets[0].labels,sh.labels);
 }else assert.ok(report.routed<15);
 t.diagnostic('TL494_R32E_ADAPTIVE '+JSON.stringify({...report,token:!!report.token}));
 assert.deepEqual(source,original);
});


test('R32e adaptive channels retain every terminal axis and still respect all omitted obstacle extents',async()=>{
 const {planOrthogonalTree}=await import('./orthogonal-tree.ts');
 const frame={minX:0,minY:0,maxX:100000,maxY:100000};
 const ports=[{pin:[10000,50000],tip:[12000,50000]},{pin:[90000,50000],tip:[88000,50000]}];
 const obstacles=Array.from({length:60},(_,i)=>({minX:1000+i*1400,maxX:1200+i*1400,minY:10000+i*10,maxY:10200+i*10}));
 assert.throws(()=>planOrthogonalTree(ports,obstacles,frame),/TREE_GRID_LIMIT/);
 const p=planOrthogonalTree(ports,obstacles,frame,[],true);
 assert.ok(p);assert.equal(p.bends,0);assert.equal(p.lengthUm,80000);
 assert.deepEqual(p.paths[0].points,[[10000,50000],[90000,50000]]);
 assert.deepEqual(planOrthogonalTree(ports,obstacles,frame,[],true),p);
 const blocked=[...obstacles,{minX:49000,maxX:51000,minY:0,maxY:100000}];
 assert.equal(planOrthogonalTree(ports,blocked,frame,[],true),null);
});


test('R32f signed hub placement moves only local two-pin satellites, may rotate them, and is undoable',()=>{
 const fixture=hubFixture(),doc=fixture.s.file,sh=doc.project.sheets[0];
 sh.wires=[];sh.junctions=[];sh.splices=[];
 for(const n of doc.project.nets)n.route_status='unrouted';
 sh.instances.find(i=>i.component_id===fixture.b).rotation_deg=180;
 const s=new AuthoringSession(doc),before=s.file;
 const p=s.previewHubPlacement();
 assert.ok(p.token);assert.ok(p.moved.includes(fixture.b));
 assert.ok(p.afterSpanUm<p.beforeSpanUm);assert.ok(p.attempted<=48);
 assert.deepEqual(s.file,before);assert.equal(s.revision,0);
 const next=s.layoutPreviewDocument(p.token);
 assert.deepEqual(next.project.nets,before.project.nets);
 assert.deepEqual(next.project.components,before.project.components);
 assert.deepEqual(next.project.sheets[0].instances.find(i=>i.component_id===fixture.h),sh.instances.find(i=>i.component_id===fixture.h));
 assert.equal(next.project.sheets[0].instances.find(i=>i.component_id===fixture.b).rotation_deg,0);
 s.applyLayoutPreview(s.newTransaction('place'),p.token);
 const a=s.beginWire(pin(fixture.h,'3')),b=s.beginWire(pin(fixture.b,'1'));
 assert.equal(a.at_um[1],b.at_um[1]);assert.ok(b.at_um[0]>a.at_um[0]);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,next);
});
test('R32f wired sheets refuse preplacement and locked unrouted sheets yield no proposal',()=>{
 const {s}=hubFixture(),before=s.file;
 assert.throws(()=>s.previewHubPlacement(),/PREPARE_REQUIRES_UNROUTED_SHEET/);
 assert.deepEqual(s.file,before);
 const doc=structuredClone(before),sh=doc.project.sheets[0];
 sh.wires=[];sh.junctions=[];sh.splices=[];
 for(const n of doc.project.nets)n.route_status='unrouted';
 for(const l of sh.layers)l.locked=true;
 const locked=new AuthoringSession(doc),p=locked.previewHubPlacement();
 assert.equal(p.token,null);assert.equal(p.moved.length,0);assert.deepEqual(locked.file,doc);
});
test('R32f TL494 topology-based preplacement and controlled multinet feasibility',t=>{
 const source=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const original=structuredClone(source),doc=structuredClone(source),p=doc.project,sh=p.sheets[0];
 p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/TL494-hub-preplacement',
  expected_counts:{...p.provenance.expected_counts}};
 const s=new AuthoringSession(doc);s.prepareInitialRouting(s.newTransaction('prepare'));
 const before=s.file,rev=s.revision;
 const placement=s.previewHubPlacement();
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 if(placement.token)s.applyLayoutPreview(s.newTransaction('place'),placement.token);
 const prepared=s.file;
 assert.deepEqual(prepared.project.nets,p.nets);
 assert.deepEqual(prepared.project.components,p.components);
 assert.deepEqual(prepared.project.sheets[0].graphics,sh.graphics);
 assert.deepEqual(prepared.project.sheets[0].labels,sh.labels);
 const report=s.previewInitialBatch(p.nets.map(n=>n.id),true);
 assert.equal(report.requested,15);assert.ok(report.attempted<=75);
 assert.equal(report.quality.errors,0);assert.equal(report.quality.geometryWarnings,0);
 assert.equal(report.quality.overflow,0);
 assert.deepEqual(s.file,prepared);
 if(report.token){
  s.applyLayoutPreview(s.newTransaction('apply'),report.token);
  for(const n of p.nets)assert.equal(s.engine.validateNet(n.id).pin_groups.length,1);
  assert.deepEqual(s.file.project.nets.map(n=>[n.id,n.members]),p.nets.map(n=>[n.id,n.members]));
 }
 t.diagnostic('TL494_R32F_PREPLACEMENT '+JSON.stringify({placement:{...placement,token:!!placement.token,moved:placement.moved.map(id=>p.components.find(c=>c.id===id)?.refdes??id)},routing:{...report,token:!!report.token}}));
 assert.deepEqual(source,original);
});


test('R32g review-marked staircase refinement preserves foreign geometry and all signed membership',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.move(s.newTransaction('offset'),c,[155000,120000]);
 s.connect(s.newTransaction('stairs'),pin(r,'2'),pin(c,'1'),[
  [119000,103000],[128000,110000],[137000,117000]
 ]);
 const foreignA=s.place(s.newTransaction('foreign-a'),'symbol/resistor.fixed',[80000,180000]);
 const foreignB=s.place(s.newTransaction('foreign-b'),'symbol/resistor.fixed',[180000,180000]);
 const doc=s.file,sh=doc.project.sheets[0],target=doc.project.nets[0].id;
 const a=sh.instances.find(i=>i.id===foreignA).component_id,b=sh.instances.find(i=>i.id===foreignB).component_id;
 s.connect(s.newTransaction('foreign-wire'),pin(a,'2'),pin(b,'1'));
 const ready=s.file,rs=ready.project.sheets[0];
 rs.wires.find(w=>w.net_id===target).needs_routing_review=true;
 rs.wires.find(w=>w.net_id!==target).needs_routing_review=false;
 const session=new AuthoringSession(ready),p=session.previewRouteRefinement();
 assert.ok(p.token);assert.ok(p.after.bends<p.before.bends);
 assert.ok(p.after.lengthUm<=p.before.lengthUm);assert.ok(p.after.crossings<=p.before.crossings);
 assert.deepEqual(session.file,ready);assert.equal(session.revision,0);
 const next=session.layoutPreviewDocument(p.token),ns=next.project.sheets[0];
 assert.deepEqual(ns.instances,rs.instances);
 assert.deepEqual(ns.wires.filter(w=>w.net_id!==target),rs.wires.filter(w=>w.net_id!==target));
 assert.deepEqual(next.project.nets.map(n=>[n.id,n.members]),ready.project.nets.map(n=>[n.id,n.members]));
 session.applyLayoutPreview(session.newTransaction('apply'),p.token);
 for(const n of ready.project.nets)assert.equal(session.engine.validateNet(n.id).pin_groups.length,1);
 assert.equal(session.undo(),true);assert.deepEqual(session.file,ready);
 assert.equal(session.redo(),true);assert.deepEqual(session.file,next);
});
test('R32g unmarked or already straight routes cannot be replaced by refinement',()=>{
 const s=newSession(),{r,c}=placePair(s);
 s.connect(s.newTransaction('straight'),pin(r,'2'),pin(c,'1'));
 const doc=s.file,net=doc.project.nets[0].id;
 doc.project.sheets[0].wires[0].needs_routing_review=false;
 const a=new AuthoringSession(doc);
 assert.throws(()=>a.buildNetTree(a.newTransaction('unmarked'),net,false,true),/REFINE_REVIEW_REQUIRED/);
 assert.equal(a.previewRouteRefinement().token,null);
 assert.deepEqual(a.file,doc);assert.equal(a.revision,0);
 doc.project.sheets[0].wires[0].needs_routing_review=true;
 const b=new AuthoringSession(doc);
 assert.equal(b.previewRouteRefinement().token,null);
 assert.deepEqual(b.file,doc);assert.equal(b.revision,0);
});
test('R32g actual TL494 full-connectivity refinement benchmark',t=>{
 const source=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const original=structuredClone(source),doc=structuredClone(source),p=doc.project,sh=p.sheets[0];
 p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/TL494-route-refinement',
  expected_counts:{...p.provenance.expected_counts}};
 const s=new AuthoringSession(doc);s.prepareInitialRouting(s.newTransaction('prepare'));
 const placement=s.previewHubPlacement();
 if(placement.token)s.applyLayoutPreview(s.newTransaction('place'),placement.token);
 const route=s.previewInitialBatch(p.nets.map(n=>n.id),true);
 assert.equal(route.routed,15);assert.ok(route.token);
 s.applyLayoutPreview(s.newTransaction('route'),route.token);
 const before=s.file,rev=s.revision,refine=s.previewRouteRefinement();
 assert.ok(refine.attempted<=32);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 assert.ok(refine.after.bends<=refine.before.bends);
 assert.ok(refine.after.lengthUm<=refine.before.lengthUm);
 assert.ok(refine.after.crossings<=refine.before.crossings);
 assert.equal(refine.after.errors,0);assert.equal(refine.after.geometryWarnings,0);assert.equal(refine.after.overflow,0);
 if(refine.token)s.applyLayoutPreview(s.newTransaction('refine'),refine.token);
 for(const n of p.nets)assert.equal(s.engine.validateNet(n.id).pin_groups.length,1);
 assert.deepEqual(s.file.project.nets.map(n=>[n.id,n.members]),p.nets.map(n=>[n.id,n.members]));
 assert.deepEqual(s.file.project.sheets[0].instances,before.project.sheets[0].instances);
 assert.deepEqual(s.file.project.sheets[0].graphics,sh.graphics);assert.deepEqual(s.file.project.sheets[0].labels,sh.labels);
 t.diagnostic('TL494_R32G_REFINEMENT '+JSON.stringify({...refine,token:!!refine.token}));
 assert.deepEqual(source,original);
});


test('R32h peer continuation anchors previously placed satellite and aligns its next two-pin neighbor',()=>{
 const {s,b,external}=multiAlignFixture(),doc=s.file,sh=doc.project.sheets[0];
 sh.wires=[];sh.junctions=[];sh.splices=[];
 for(const n of doc.project.nets)n.route_status='unrouted';
 const a=new AuthoringSession(doc);
 assert.throws(()=>a.previewHubPlacement([b,b]),/INVALID_PEER_ANCHORS/);
 const p=a.previewHubPlacement([b]);
 assert.ok(p.token);assert.deepEqual(p.moved,[external]);
 assert.ok(p.afterSpanUm<p.beforeSpanUm);
 assert.deepEqual(a.file,doc);assert.equal(a.revision,0);
 const next=a.layoutPreviewDocument(p.token),ns=next.project.sheets[0];
 assert.deepEqual(ns.instances.filter(i=>i.component_id!==external),sh.instances.filter(i=>i.component_id!==external));
 assert.deepEqual(next.project.nets,doc.project.nets);
 a.applyLayoutPreview(a.newTransaction('peer'),p.token);
 const x=a.beginWire(pin(b,'2')),y=a.beginWire(pin(external,'1'));
 assert.equal(x.at_um[1],y.at_um[1]);assert.ok(y.at_um[0]>x.at_um[0]);
 assert.equal(a.undo(),true);assert.deepEqual(a.file,doc);
});
test('R32h functional routing is atomic, complete and revision-bound even without hub candidates',()=>{
 const {session:s,ids,doc}=batchRouteFixture();
 const p=s.previewFunctionalRouting();
 assert.equal(p.requested,2);assert.equal(p.routed,2);assert.ok(p.token);
 assert.equal(p.variant,'hub');assert.equal(p.quality.bends,0);
 assert.ok(p.attempted<=160);assert.deepEqual(s.file,doc);assert.equal(s.revision,0);
 const next=s.layoutPreviewDocument(p.token);
 s.applyLayoutPreview(s.newTransaction('apply'),p.token);
 for(const id of ids)assert.equal(s.engine.validateNet(id).pin_groups.length,1);
 assert.deepEqual(s.file,next);assert.equal(s.undo(),true);assert.deepEqual(s.file,doc);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,next);
 assert.throws(()=>s.previewFunctionalRouting(),/PREPARE_REQUIRES_UNROUTED_SHEET/);
});
test('R32h actual TL494 compares hub-only with functional peer-chain routing',t=>{
 const source=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const original=structuredClone(source),doc=structuredClone(source),p=doc.project,sh=p.sheets[0];
 p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/TL494-functional-routing',
  expected_counts:{...p.provenance.expected_counts}};
 const s=new AuthoringSession(doc),report=s.previewFunctionalRouting();
 assert.equal(report.requested,15);assert.equal(report.routed,15);assert.ok(report.token);
 assert.ok(report.attempted<=150);
 assert.deepEqual(s.file,doc);assert.equal(s.revision,0);
 assert.ok(report.quality.bends<=report.baseline.bends);
 assert.ok(report.quality.crossings<=report.baseline.crossings);
 assert.ok(report.quality.lengthUm<=report.baseline.lengthUm);
 assert.equal(report.quality.errors,0);assert.equal(report.quality.geometryWarnings,0);assert.equal(report.quality.overflow,0);
 s.applyLayoutPreview(s.newTransaction('apply'),report.token);
 for(const n of p.nets)assert.equal(s.engine.validateNet(n.id).pin_groups.length,1);
 assert.deepEqual(s.file.project.nets.map(n=>[n.id,n.members]),p.nets.map(n=>[n.id,n.members]));
 assert.deepEqual(s.file.project.components,p.components);
 assert.deepEqual(s.file.project.sheets[0].graphics,sh.graphics);assert.deepEqual(s.file.project.sheets[0].labels,sh.labels);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,doc);
 t.diagnostic('TL494_R32H_FUNCTIONAL '+JSON.stringify({...report,token:!!report.token,moved:report.moved.map(id=>p.components.find(c=>c.id===id)?.refdes??id)}));
 assert.deepEqual(source,original);
});


test('R32l synthetic source copy retains canonical DA1 and b inventory through routing edits',()=>{
 const source=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const doc=structuredClone(source),p=doc.project;
 p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/count-parity'};
 const s=new AuthoringSession(doc);
 const counts={components:23,nets:15,memberships:62,da1_pins:16,b_graphics:2};
 assert.deepEqual(s.file.project.provenance.expected_counts,counts);
 s.prepareInitialRouting(s.newTransaction('prepare'));
 assert.deepEqual(s.file.project.provenance.expected_counts,counts);
 const corrupt=structuredClone(s.file);
 corrupt.project.provenance.expected_counts.da1_pins=0;
 corrupt.project.provenance.expected_counts.b_graphics=0;
 assert.throws(()=>new AuthoringSession(corrupt),/SOURCE_COUNT_MISMATCH/);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,doc);
});


test('R35 alternate root and costs preserve original physical terminal indices and deterministic signed leads',async()=>{
 const {planOrthogonalTree}=await import('./orthogonal-tree.ts');
 const frame={minX:0,minY:0,maxX:100000,maxY:100000};
 const ports=[{pin:[20000,50000],tip:[22000,50000]},
  {pin:[70000,60000],tip:[70000,58000]},
  {pin:[80000,30000],tip:[78000,30000]}];
 const original=structuredClone(ports);
 for(const strategy of ['default','crossing-first','bend-first','peripheral-root']){
  const p=planOrthogonalTree(ports,[],frame,[],true,strategy);
  assert.ok(p,strategy);
  assert.deepEqual(planOrthogonalTree(ports,[],frame,[],true,strategy),p);
  const seen=[];
  for(const path of p.paths){
   for(const [index,points] of [[path.startPin,path.points],[path.endPin,[...path.points].reverse()]]){
    if(index===null)continue;
    seen.push(index);
    const port=ports[index],a=points[0],b=points[1],delta=[b[0]-a[0],b[1]-a[1]];
    assert.deepEqual(a,port.pin);
    const lead=[port.tip[0]-port.pin[0],port.tip[1]-port.pin[1]],axis=lead[0]!==0?0:1;
    assert.equal(delta[1-axis],0);
    assert.ok(delta[axis]*Math.sign(lead[axis])>=Math.abs(lead[axis]));
   }
  }
  assert.deepEqual(seen.sort(),[0,1,2]);
 }
 assert.deepEqual(ports,original);
});

test('R35 TL494 extended search preserves R34 baseline, all labels and exact physical membership',t=>{
 const source=JSON.parse(readFileSync(new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'));
 const original=structuredClone(source),doc=structuredClone(source),p=doc.project;
 p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/TL494-R35-alternatives'};
 const s=new AuthoringSession(doc),initial=s.previewFunctionalRouting();
 assert.equal(initial.routed,15);assert.ok(initial.token);
 s.applyLayoutPreview(s.newTransaction('initial'),initial.token);
 const baseline=s.previewRouteRefinement();
 if(baseline.token)s.applyLayoutPreview(s.newTransaction('baseline'),baseline.token);
 const before=s.file,rev=s.revision;
 const next=s.previewRouteRefinement(true);
 assert.ok(next.attempted>=45&&next.attempted<=80);
 assert.equal(next.attempted,next.rejected+next.operations.length);
 assert.deepEqual(s.file,before);assert.equal(s.revision,rev);
 assert.ok(next.after.bends<=baseline.after.bends);
 assert.ok(next.after.crossings<=baseline.after.crossings);
 assert.ok(next.after.lengthUm<=baseline.after.lengthUm);
 assert.equal(next.after.errors,0);assert.equal(next.after.geometryWarnings,0);assert.equal(next.after.overflow,0);
 if(next.token){
  const planned=s.layoutPreviewDocument(next.token);
  s.applyLayoutPreview(s.newTransaction('extended'),next.token);
  assert.deepEqual(s.file,planned);
  assert.equal(s.undo(),true);assert.deepEqual(s.file,before);
  assert.equal(s.redo(),true);assert.deepEqual(s.file,planned);
 }
 for(const n of p.nets)assert.equal(s.engine.validateNet(n.id).pin_groups.length,1);
 assert.deepEqual(s.file.project.nets.map(n=>[n.id,n.members]),p.nets.map(n=>[n.id,n.members]));
 assert.deepEqual(s.file.project.components,p.components);
 assert.deepEqual(s.file.project.sheets[0].instances,before.project.sheets[0].instances);
 assert.deepEqual(s.file.project.sheets[0].graphics,before.project.sheets[0].graphics);
 assert.deepEqual(s.file.project.provenance.expected_counts,{components:23,nets:15,memberships:62,da1_pins:16,b_graphics:2});
 assert.deepEqual(source,original);
 t.diagnostic('TL494_R35_EXTENDED '+JSON.stringify({...next,token:!!next.token}));
});


test('R36 annotated common trunk removes a safe artificial detour without changing pins or other graphics',()=>{
 const {s,net}=railFixture();
 s.buildNetRail(s.newTransaction('baseline'),net);
 const doc=s.file,sh=doc.project.sheets[0];
 const trunk=sh.wires.find(w=>w.vertices.every(v=>v.anchor.kind!=='pin')&&w.vertices.length===2);
 assert.ok(trunk);
 const [first,last]=trunk.vertices,[x,y]=first.at_um,[z,y2]=last.at_um;
 assert.equal(y,y2);assert.ok(z-x>=20000);assert.ok(y-10000>sh.frame.margin_um);
 const points=[[x,y],[x+5000,y],[x+5000,y-10000],[z-5000,y-10000],[z-5000,y],[z,y]];
 trunk.vertices=points.map((at_um,i)=>({id:trunk.id+':v'+i,at_um,anchor:i===0?first.anchor:i===points.length-1?last.anchor:{kind:'bend'}}));
 trunk.segments=trunk.vertices.slice(1).map((v,i)=>({id:trunk.id+':s'+i,from_vertex_id:trunk.vertices[i].id,to_vertex_id:v.id}));
 sh.layers.push({id:'layer-r36-draw',name:'Drawing',kind:'drawing',visible:true,printable:true,locked:false});
 sh.graphics.push({id:'r36-line',layer_id:'layer-r36-draw',kind:'line',points_um:[[300000,240000],[320000,240000]],stroke_um:300});
 sh.labels.push({id:'r36-visual',layer_id:'layer-r36-draw',text:'b',at_um:[325000,240000],role:'visual',net_id:null});
 const a=new AuthoringSession(doc),p=a.previewRailRefinement();
 assert.ok(p.token);assert.equal(p.attempted,1);
 assert.ok(p.after.bends<p.before.bends);assert.ok(p.after.lengthUm<p.before.lengthUm);
 assert.ok(p.after.crossings<=p.before.crossings);
 assert.deepEqual(a.file,doc);assert.equal(a.revision,0);
 const next=a.layoutPreviewDocument(p.token);
 assert.deepEqual(next.project.sheets[0].graphics,sh.graphics);
 assert.deepEqual(next.project.sheets[0].labels,sh.labels);
 assert.deepEqual(next.project.sheets[0].instances,sh.instances);
 assert.deepEqual(next.project.nets.map(n=>[n.id,n.members]),doc.project.nets.map(n=>[n.id,n.members]));
 a.applyLayoutPreview(a.newTransaction('apply'),p.token);
 assert.equal(a.engine.validateNet(net).pin_groups.length,1);
 assert.equal(a.undo(),true);assert.deepEqual(a.file,doc);
 assert.equal(a.redo(),true);assert.deepEqual(a.file,next);
});
test('R36 review-only common trunk refuses unmarked existing geometry atomically',()=>{
 const {s,net}=railFixture(),doc=s.file;
 for(const w of doc.project.sheets[0].wires)w.needs_routing_review=false;
 const a=new AuthoringSession(doc);
 assert.throws(()=>a.buildNetRail(a.newTransaction('manual'),net,true),/REFINE_REVIEW_REQUIRED/);
 assert.equal(a.previewRailRefinement().token,null);
 assert.deepEqual(a.file,doc);assert.equal(a.revision,0);
});


test('R37 compares three complete placement profiles atomically and preserves physical source inventory',()=>{
 const {session:s,ids,doc}=batchRouteFixture();
 const p=s.previewFunctionalAlternatives();
 assert.equal(p.profilesTried,3);assert.equal(p.requested,2);assert.equal(p.routed,2);
 assert.ok(p.token);assert.ok(p.attempted<=450);assert.ok(p.refinementAttempts<=384);
 assert.deepEqual(s.file,doc);assert.equal(s.revision,0);
 for(const k of ['bends','crossings','lengthUm'])assert.ok(p.quality[k]<=p.baseline[k]);
 const next=s.layoutPreviewDocument(p.token);
 s.applyLayoutPreview(s.newTransaction('apply'),p.token);
 for(const id of ids)assert.equal(s.engine.validateNet(id).pin_groups.length,1);
 assert.deepEqual(s.file.project.nets.map(n=>[n.id,n.members]),doc.project.nets.map(n=>[n.id,n.members]));
 assert.deepEqual(s.file.project.components,doc.project.components);
 assert.equal(s.undo(),true);assert.deepEqual(s.file,doc);
 assert.equal(s.redo(),true);assert.deepEqual(s.file,next);
 assert.throws(()=>s.previewFunctionalAlternatives(),/PREPARE_REQUIRES_UNROUTED_SHEET/);
});
test('R37 rejects unknown placement profile without mutation',()=>{
 const {session:s,doc}=batchRouteFixture();
 assert.throws(()=>s.previewFunctionalRouting('invalid'),/INVALID_PLACEMENT_PROFILE/);
 assert.deepEqual(s.file,doc);assert.equal(s.revision,0);
});
