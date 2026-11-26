/** Generate a detached full routed test project using the production editor.
 * CI-only; no Chromium needed for the model generation step. */
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdtempSync,rmSync} from 'node:fs';
import {resolve,join,sep} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';

const editor=fileURLToPath(new URL('../../ui/editor/',import.meta.url));
const require=createRequire(new URL('../../ui/editor/package.json',import.meta.url));
const {build}=require('esbuild');
const root=process.env.RUNNER_TEMP;
const output=process.argv[2];
if(process.env.GITHUB_ACTIONS!=='true'||!root||!output||
 !resolve(output).toLowerCase().startsWith(resolve(root).toLowerCase()+sep))throw Error('R33_CI_PATH_INVALID');
const sourcePath=resolve(editor,'../fixtures/tl494-source-e695-v2.gscad.json');
const raw=readFileSync(sourcePath),source=JSON.parse(raw.toString('utf8')),doc=structuredClone(source);
const p=doc.project;
assert.equal(p.components.length,23);assert.equal(p.nets.length,15);
assert.equal(p.nets.reduce((n,v)=>n+v.members.length,0),62);
p.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),
 source_path:'test-only/TL494-R33-native',expected_counts:{...p.provenance.expected_counts}};
const temp=mkdtempSync(join(tmpdir(),'r33-model-'));
try{
 const module=join(temp,'model.mjs');
 await build({stdin:{contents:"export {AuthoringSession} from './src/authoring/session.ts'; export {assessLayout} from './src/authoring/layout-quality.ts'; export {planComponentLabels} from './src/canvas/component-labels.ts';",resolveDir:editor,sourcefile:'r33-entry.ts'},
  outfile:module,bundle:true,platform:'node',format:'esm',target:'node22',logLevel:'silent'});
 const {AuthoringSession,assessLayout,planComponentLabels}=await import(pathToFileURL(module).href);
 let s=new AuthoringSession(doc);
 const proposal=s.previewFunctionalRouting();
 assert.equal(proposal.routed,15);assert.ok(proposal.token);
 s.applyLayoutPreview(s.newTransaction('functional'),proposal.token);
 const refinement=s.previewRouteRefinement();
 if(refinement.token)s.applyLayoutPreview(s.newTransaction('refinement'),refinement.token);
 const baseline=assessLayout(s.file,s.engine).quality;
 if(process.env.GSCAD_R35_EXTENDED==='1'){
  const extended=s.previewRouteRefinement(true);
  assert.ok(extended.attempted<=80);
  if(extended.token)s.applyLayoutPreview(s.newTransaction('extended'),extended.token);
  console.log('R35_NATIVE_EXTENDED '+JSON.stringify({...extended,token:!!extended.token}));
 }
 const beforeTrunks=assessLayout(s.file,s.engine).quality;
 if(process.env.GSCAD_R36_TRUNKS==='1'){
  const rails=s.previewRailRefinement();
  assert.ok(rails.attempted<=16);
  if(rails.token)s.applyLayoutPreview(s.newTransaction('trunks'),rails.token);
  console.log('R36_NATIVE_TRUNKS '+JSON.stringify({...rails,token:!!rails.token}));
 }
 const beforePlacement=assessLayout(s.file,s.engine).quality;
 if(process.env.GSCAD_R37_PLACEMENT==='1'){
  const alternate=new AuthoringSession(doc),p=alternate.previewFunctionalAlternatives();
  assert.equal(p.routed,15);assert.ok(p.token);
  alternate.applyLayoutPreview(alternate.newTransaction('placement-profiles'),p.token);
  s=alternate;
  console.log('R37_NATIVE_PLACEMENT '+JSON.stringify({...p,token:!!p.token}));
 }
 const next=s.file,sh=next.project.sheets[0],quality=assessLayout(next,s.engine).quality;
 for(const k of ['bends','crossings','lengthUm'])assert.ok(quality[k]<=beforePlacement[k],k);
 for(const k of ['bends','crossings','lengthUm'])assert.ok(quality[k]<=beforeTrunks[k],k);
 for(const k of ['bends','crossings','lengthUm'])assert.ok(quality[k]<=baseline[k],k);
 for(const [key,limit] of Object.entries({bends:81,crossings:38,lengthUm:5340345}))assert.ok(quality[key]<=limit,key);
 assert.ok(quality.complete);assert.equal(quality.errors,0);assert.equal(quality.geometryWarnings,0);assert.equal(quality.overflow,0);
 for(const n of p.nets)assert.equal(s.engine.validateNet(n.id).pin_groups.length,1);
 assert.deepEqual(next.project.nets.map(n=>[n.id,n.members]),source.project.nets.map(n=>[n.id,n.members]));
 assert.deepEqual(next.project.components,source.project.components);
 assert.deepEqual(sh.graphics,source.project.sheets[0].graphics);
 const labels=planComponentLabels(next,sh.id);
 assert.equal(labels.labels.length,23);assert.equal(labels.unplaced.length,0);
 assert.deepEqual(readFileSync(sourcePath),raw);
 writeFileSync(output,JSON.stringify(next,null,2)+'\n',{flag:'wx'});
 console.log('R33_FULL_TL494_GENERATED '+JSON.stringify({quality,labels:23,nets:15,pinrefs:62}));
}finally{rmSync(temp,{recursive:true,force:true});}
