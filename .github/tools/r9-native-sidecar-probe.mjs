/** CI-only: replay user-authored ProjectV2 through the exact installed Python EXE.
 * Distinguishes a synthetic-model/PyInstaller defect from Rust/Tauri pipe lifecycle.
 */
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const require=createRequire(new URL('../../ui/editor/package.json',import.meta.url));
const {build}=require('esbuild');
const executable=process.argv[2];
assert(process.env.GITHUB_ACTIONS==='true'&&executable&&process.env.RUNNER_TEMP);
const dir=mkdtempSync(join(tmpdir(),'gscad-r9-sidecar-probe-'));
try{
  const outfile=join(dir,'authoring.mjs');
  await build({entryPoints:[fileURLToPath(new URL('../../ui/editor/src/authoring/session.ts',import.meta.url))],
    outfile,bundle:true,platform:'node',format:'esm',target:'node22',logLevel:'silent'});
  const {AuthoringSession,newBlankProject}=await import(pathToFileURL(outfile).href);
  const s=new AuthoringSession(newBlankProject());
  s.place(s.newTransaction('r1'),'symbol/resistor.fixed',[100000,100000]);
  s.place(s.newTransaction('c1'),'symbol/capacitor.fixed',[155000,100000]);
  const c1=s.file.project.components.find(c=>c.refdes==='C1');
  const inst=s.file.project.sheets[0].instances.find(i=>i.component_id===c1.id);
  s.updateProperty(s.newTransaction('rename'),inst.id,'refdes','C9');
  s.updateProperty(s.newTransaction('value'),inst.id,'value','220н');
  s.place(s.newTransaction('r2'),'symbol/resistor.fixed',[220000,150000]);
  const r1=s.file.project.components.find(c=>c.refdes==='R1');
  const c9=s.file.project.components.find(c=>c.refdes==='C9');
  s.connect(s.newTransaction('route'),{component_id:r1.id,physical_pin_number:'2'},
    {component_id:c9.id,physical_pin_number:'1'});
  const document=s.file;
  assert.equal(document.project.nets.length,1);
  assert.equal(document.project.sheets[0].wires.length,1);
  const request=JSON.stringify({v:1,id:'r9_synthetic_sidecar',op:'parse_document_blob',
    args:{blob:JSON.stringify(document)}})+'\n';
  const result=spawnSync(executable,[],{input:request,encoding:'utf8',timeout:30000,windowsHide:true});
  console.log('R9_SYNTHETIC_DIRECT_EXIT='+result.status+' SIGNAL='+result.signal);
  if(result.stderr)console.log('R9_SYNTHETIC_DIRECT_STDERR='+result.stderr.slice(-1100));
  const reply=JSON.parse(result.stdout.trim());
  assert.equal(result.status,0,'direct packed Python process exit');
  assert.equal(reply.ok,true,'same strict synthetic ProjectFileV2 parser');
  assert.equal(reply.id,'r9_synthetic_sidecar');
  assert.deepEqual(reply.result.document,document);
  assert.match(reply.result.project_sha256,/^[0-9a-f]{64}$/);
  console.log('R9_DIRECT_SYNTHETIC_PARSE_PASS sha='+reply.result.project_sha256);
}finally{rmSync(dir,{force:true,recursive:true});}
