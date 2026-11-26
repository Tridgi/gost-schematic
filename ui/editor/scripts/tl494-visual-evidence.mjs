/** Reproducible evidence from the real authoring and preview-export modules.
 * Not a source unlock, canonical print approval or Windows acceptance. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,mkdirSync,mkdtempSync,rmSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {build} from 'esbuild';
import {chromium} from '@playwright/test';

const editor=fileURLToPath(new URL('../',import.meta.url));
const sourcePath=resolve(editor,'../fixtures/tl494-source-e695-v2.gscad.json');
const output=resolve(process.argv[2]??join(editor,'test-results/tl494-evidence'));
const temp=mkdtempSync(join(tmpdir(),'tl494-evidence-'));
const hash=value=>createHash('sha256').update(value).digest('hex');
const raw=readFileSync(sourcePath);
const source=JSON.parse(raw.toString('utf8')),original=structuredClone(source);
const p=source.project,sh=p.sheets[0];
const ids=p.nets.map(n=>n.id),membership=p.nets.map(n=>[n.id,n.name,n.members]);
assert.equal(p.components.length,23);assert.equal(ids.length,15);
assert.equal(p.nets.reduce((a,n)=>a+n.members.length,0),62);
const da=p.components.find(c=>c.source_refdes==='DA1');
assert.equal(new Set(p.nets.flatMap(n=>n.members.filter(m=>m.component_id===da.id).map(m=>m.physical_pin_number))).size,16);
assert.equal(sh.graphics.filter(g=>g.kind==='source_b_continuation').length,2);
let browser;
try{
 const module=join(temp,'evidence.mjs');
 await build({stdin:{contents:"export {AuthoringSession} from './src/authoring/session.ts'; export {assessLayout} from './src/authoring/layout-quality.ts'; export {renderProjectPreviewSVG} from './src/export/browser-export.ts'; export {planComponentLabels} from './src/canvas/component-labels.ts';",resolveDir:editor,sourcefile:'evidence-entry.ts'},outfile:module,bundle:true,platform:'node',format:'esm',target:'node22',logLevel:'silent'});
 const {AuthoringSession,assessLayout,renderProjectPreviewSVG,planComponentLabels}=await import(pathToFileURL(module).href);
 assert.throws(()=>new AuthoringSession(source),/SOURCE_SHA_MISMATCH/);
 const doc=structuredClone(source);
 doc.project.provenance={...p.provenance,status:'synthetic',source_sha:'0'.repeat(40),source_path:'test-only/TL494-visual-evidence',expected_counts:{...p.provenance.expected_counts}};
 const baseline=new AuthoringSession(doc);
 baseline.prepareInitialRouting(baseline.newTransaction('inset'));
 const initial=baseline.previewInitialBatch(ids,true);
 assert.equal(initial.routed,15);assert.ok(initial.token);
 baseline.applyLayoutPreview(baseline.newTransaction('initial'),initial.token);
 const stages=[{name:'01-inset-routing',file:baseline.file,quality:assessLayout(baseline.file,baseline.engine).quality}];
 const optimized=new AuthoringSession(doc);
 const functional=optimized.previewFunctionalRouting();
 assert.equal(functional.routed,15);assert.ok(functional.token);
 optimized.applyLayoutPreview(optimized.newTransaction('functional'),functional.token);
 stages.push({name:'02-functional-routing',file:optimized.file,quality:assessLayout(optimized.file,optimized.engine).quality});
 const refinement=optimized.previewRouteRefinement();
 if(refinement.token)optimized.applyLayoutPreview(optimized.newTransaction('refine'),refinement.token);
 stages.push({name:'03-refined-routing',file:optimized.file,quality:assessLayout(optimized.file,optimized.engine).quality});
 for(const k of ['bends','lengthUm','crossings'])assert.ok(stages[2].quality[k]<=stages[1].quality[k],k);
 // R33 verified reference baseline: never trade readability for a new route.
 for(const [key,limit] of Object.entries({bends:81,crossings:38,lengthUm:5340345}))
  assert.ok(stages[2].quality[key]<=limit,`R34 baseline regression: ${key}`);
 for(const stage of stages)assert.equal(planComponentLabels(stage.file,stage.file.project.sheets[0].id).labels.length,23);
 // Export through the same browser raster function used in the editor.
 const raster=await build({entryPoints:[join(editor,'src/export/browser-export.ts')],bundle:true,platform:'browser',format:'iife',globalName:'GSCADPreview',write:false,logLevel:'silent'});
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage();
 await page.addScriptTag({content:raster.outputFiles[0].text});
 mkdirSync(output,{recursive:true});
 const report={schema:1,sourceFile:'ui/fixtures/tl494-source-e695-v2.gscad.json',sourceFileSha256:hash(raw),sourceRevision:p.provenance.source_sha,sourceApproval:'unchanged; detached synthetic test-only copies',fontStatus:'unverified-preview',scope:'browser preview SVG/PNG300, not normative print or native Windows acceptance',counts:{components:23,nets:15,pinrefs:62,da1Pins:16,bGraphics:2},variant:functional.variant,refinementOperations:refinement.operations,stages:[]};
 for(const stage of stages){
  const {file,quality,name}=stage;
  const session=new AuthoringSession(file),sheet=file.project.sheets[0];
  assert.deepEqual(file.project.nets.map(n=>[n.id,n.name,n.members]),membership);
  assert.deepEqual(file.project.components,p.components);
  assert.deepEqual(file.project.symbol_definitions,p.symbol_definitions);
  assert.deepEqual(sheet.graphics,sh.graphics);assert.deepEqual(sheet.labels,sh.labels);
  assert.ok(quality.complete);assert.equal(quality.errors,0);assert.equal(quality.geometryWarnings,0);assert.equal(quality.overflow,0);
  for(const id of ids)assert.equal(session.engine.validateNet(id).pin_groups.length,1);
  const svg=renderProjectPreviewSVG(file,sheet.id);
  assert.equal((svg.match(/data-layer="symbols"/g)??[]).length,23);
  assert.equal((svg.match(/data-layer="wires"/g)??[]).length,sheet.wires.length);
  assert.equal((svg.match(/data-kind="source_b_continuation"/g)??[]).length,2);
  assert.equal((svg.match(/data-layer="explicit-junctions"/g)??[]).length,sheet.junctions.length);
  const placedLabels=Number(svg.match(/data-component-label-count="(\d+)"/)?.[1]);
  const unplacedLabels=Number(svg.match(/data-unplaced-label-count="(\d+)"/)?.[1]);
  assert.equal(placedLabels+unplacedLabels,23);
  const labels=planComponentLabels(file,sheet.id);
  assert.equal(labels.labels.length,placedLabels);
  assert.equal(labels.unplaced.length,unplacedLabels);
  const expectedRefs=file.project.components.map(c=>c.refdes).sort();
  assert.deepEqual([...labels.labels,...labels.unplaced].map(l=>l.refdes).sort(),expectedRefs);
  assert.equal((svg.match(/data-label-role="reference"/g)??[]).length,placedLabels);
  assert.equal((svg.match(/data-label-role="value"/g)??[]).length,0);
  const pngBytes=await page.evaluate(async({svg,size})=>{
   const blob=await globalThis.GSCADPreview.renderPreviewPng300(svg,size);
   return Array.from(new Uint8Array(await blob.arrayBuffer()));
  },{svg,size:sheet.frame.size_um});
  const png=Buffer.from(pngBytes),width=png.readUInt32BE(16),height=png.readUInt32BE(20);
  assert.equal(width,Math.round(sheet.frame.size_um[0]/25400*300));
  assert.equal(height,Math.round(sheet.frame.size_um[1]/25400*300));
  const json=JSON.stringify(file,null,2)+'\n';
  writeFileSync(join(output,name+'.gscad.json'),json);writeFileSync(join(output,name+'.svg'),svg);writeFileSync(join(output,name+'.png'),png);
  report.stages.push({name,quality,connectedNets:15,pinRefs:62,componentLabels:{placed:placedLabels,unplaced:unplacedLabels,missing:labels.unplaced.map(l=>({refdes:l.refdes,reason:l.reason}))},png:{width,height,dpi:300},sha256:{project:hash(json),svg:hash(svg),png:hash(png)}});
 }
 assert.deepEqual(source,original);assert.deepEqual(readFileSync(sourcePath),raw);
 writeFileSync(join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
 console.log('TL494_R32I_EVIDENCE '+JSON.stringify(report));
}finally{
 await browser?.close();rmSync(temp,{recursive:true,force:true});
}
