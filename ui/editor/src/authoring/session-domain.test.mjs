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
   'import json,sys;sys.path.insert(0,"../..");from ui.editor.src.model.contract import validate,digest;d=json.load(sys.stdin);validate(d);print(digest(d))'
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
