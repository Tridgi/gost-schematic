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
 await build({stdin:{contents:"export {AuthoringSession} from './src/authoring/session.ts'; export {assessLayout} from './src/authoring/layout-quality.ts'; export {parallelSpacingQuality} from './src/authoring/detour-shortcuts.ts'; export {renderProjectPreviewSVG} from './src/export/browser-export.ts'; export {planComponentLabels} from './src/canvas/component-labels.ts';",resolveDir:editor,sourcefile:'evidence-entry.ts'},outfile:module,bundle:true,platform:'node',format:'esm',target:'node22',logLevel:'silent'});
 const {AuthoringSession,assessLayout,parallelSpacingQuality,renderProjectPreviewSVG,planComponentLabels}=await import(pathToFileURL(module).href);
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
 const extended=optimized.previewRouteRefinement(true);
 assert.ok(extended.attempted<=80);
 if(extended.token)optimized.applyLayoutPreview(optimized.newTransaction('extended'),extended.token);
 stages.push({name:'04-extended-routing',file:optimized.file,quality:assessLayout(optimized.file,optimized.engine).quality});
 for(const k of ['bends','lengthUm','crossings'])assert.ok(stages[3].quality[k]<=stages[2].quality[k],k);
 assert.deepEqual(stages[3].file.project.sheets[0].instances,stages[2].file.project.sheets[0].instances);
 const rails=optimized.previewRailRefinement();
 assert.ok(rails.attempted<=16);
 if(rails.token)optimized.applyLayoutPreview(optimized.newTransaction('trunks'),rails.token);
 stages.push({name:'05-common-trunks',file:optimized.file,quality:assessLayout(optimized.file,optimized.engine).quality});
 for(const k of ['bends','lengthUm','crossings'])assert.ok(stages[4].quality[k]<=stages[3].quality[k],k);
 assert.deepEqual(stages[4].file.project.sheets[0].instances,stages[3].file.project.sheets[0].instances);
 console.log('TL494_R36_TRUNKS '+JSON.stringify({...rails,token:!!rails.token}));
 const placementSearch=new AuthoringSession(doc);
 const placement=placementSearch.previewFunctionalAlternatives();
 assert.equal(placement.routed,15);assert.ok(placement.token);
 assert.equal(placement.profilesTried,3);assert.ok(placement.refinementAttempts<=384);
 placementSearch.applyLayoutPreview(placementSearch.newTransaction('placement-profiles'),placement.token);
 stages.push({name:'06-placement-profiles',file:placementSearch.file,quality:assessLayout(placementSearch.file,placementSearch.engine).quality});
 for(const k of ['bends','lengthUm','crossings'])assert.ok(stages[5].quality[k]<=stages[4].quality[k],k);
 console.log('TL494_R37_PLACEMENT '+JSON.stringify({...placement,token:!!placement.token}));
 const detours=placementSearch.previewDetourRefinement();
 assert.ok(detours.attempted<=64);
 if(detours.token)placementSearch.applyLayoutPreview(placementSearch.newTransaction('detours'),detours.token);
 stages.push({name:'07-local-detours',file:placementSearch.file,quality:assessLayout(placementSearch.file,placementSearch.engine).quality});
 for(const k of ['bends','lengthUm','crossings'])assert.ok(stages[6].quality[k]<=stages[5].quality[k],k);
 for(const k of ['instances','junctions','splices'])assert.deepEqual(stages[6].file.project.sheets[0][k],stages[5].file.project.sheets[0][k]);
 console.log('TL494_R38_DETOURS '+JSON.stringify({...detours,token:!!detours.token}));
 for(const [key,limit] of Object.entries({bends:77,crossings:38,lengthUm:5282207}))
  assert.ok(stages[6].quality[key]<=limit,`R38 baseline regression: ${key}`);
 const crossingChannels=placementSearch.previewDetourRefinement(true);
 assert.ok(crossingChannels.attempted<=96);
 if(crossingChannels.token)placementSearch.applyLayoutPreview(placementSearch.newTransaction('crossing-channels'),crossingChannels.token);
 stages.push({name:'08-crossing-channels',file:placementSearch.file,quality:assessLayout(placementSearch.file,placementSearch.engine).quality});
 for(const k of ['bends','lengthUm','crossings'])assert.ok(stages[7].quality[k]<=stages[6].quality[k],k);
 if(crossingChannels.token)assert.ok(stages[7].quality.crossings<stages[6].quality.crossings);
 for(const k of ['instances','junctions','splices'])assert.deepEqual(stages[7].file.project.sheets[0][k],stages[6].file.project.sheets[0][k]);
 console.log('TL494_R39_CROSSINGS '+JSON.stringify({...crossingChannels,token:!!crossingChannels.token}));
 const spacingOf=file=>parallelSpacingQuality(file.project.sheets[0].wires.flatMap(w=>
  w.vertices.slice(1).map((v,i)=>({a:w.vertices[i].at_um,b:v.at_um,net:w.net_id}))));
 const spacingBase=placementSearch.file,spacingRevision=placementSearch.revision;
 const spacing=placementSearch.previewParallelSpacing();
 assert.ok(spacing.attempted<=32);
 assert.deepEqual(placementSearch.file,spacingBase);assert.equal(placementSearch.revision,spacingRevision);
 assert.deepEqual(spacing.spacing.before,spacingOf(spacingBase));assert.equal(spacing.spacing.before.complete,true);
 if(spacing.token)placementSearch.applyLayoutPreview(placementSearch.newTransaction('parallel-spacing'),spacing.token);
 else assert.deepEqual(placementSearch.file,spacingBase);
 const spacingFinal=placementSearch.file;
 assert.deepEqual(spacing.spacing.after,spacingOf(spacingFinal));assert.equal(spacing.spacing.after.complete,true);
 assert.ok(spacing.spacing.after.coverageUm>=spacing.spacing.before.coverageUm);
 if(spacing.token)assert.ok(spacing.spacing.after.imbalanceUm2<spacing.spacing.before.imbalanceUm2);
 else assert.deepEqual(spacing.spacing.after,spacing.spacing.before);
 stages.push({name:'09-parallel-spacing',file:spacingFinal,quality:assessLayout(spacingFinal,placementSearch.engine).quality});
 for(const k of ['bends','lengthUm','crossings','errors','geometryWarnings','overflow'])assert.ok(stages[8].quality[k]<=stages[7].quality[k],k);
 for(const k of ['instances','junctions','splices','labels','graphics'])assert.deepEqual(stages[8].file.project.sheets[0][k],stages[7].file.project.sheets[0][k]);
 const terminals=file=>file.project.sheets[0].wires.map(w=>[w.id,w.net_id,w.layer_id,w.vertices[0],w.vertices.at(-1)]);
 assert.deepEqual(terminals(spacingFinal),terminals(spacingBase));
 if(spacing.token){
  assert.equal(placementSearch.undo(),true);assert.deepEqual(placementSearch.file,spacingBase);
  assert.equal(placementSearch.redo(),true);assert.deepEqual(placementSearch.file,spacingFinal);
 }
 console.log('TL494_R63_SPACING '+JSON.stringify({...spacing,token:!!spacing.token}));
 for(const stage of stages)assert.equal(planComponentLabels(stage.file,stage.file.project.sheets[0].id).labels.length,23);
 // Export through the same browser raster function used in the editor.
 const raster=await build({entryPoints:[join(editor,'src/export/browser-export.ts')],bundle:true,platform:'browser',format:'iife',globalName:'GSCADPreview',write:false,logLevel:'silent'});
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage();
 await page.addScriptTag({content:raster.outputFiles[0].text});
 mkdirSync(output,{recursive:true});
 const report={schema:1,sourceFile:'ui/fixtures/tl494-source-e695-v2.gscad.json',sourceFileSha256:hash(raw),sourceRevision:p.provenance.source_sha,sourceApproval:'unchanged; detached synthetic test-only copies',fontStatus:'unverified-preview',scope:'browser preview SVG/PNG300, not normative print or native Windows acceptance',counts:{components:23,nets:15,pinrefs:62,da1Pins:16,bGraphics:2},variant:functional.variant,refinementOperations:refinement.operations,extendedOperations:extended.operations,extendedAttempts:extended.attempted,trunkOperations:rails.operations,trunkAttempts:rails.attempted,placementProfile:placement.profile,placementProfilesTried:placement.profilesTried,detourOperations:detours.operations,detourAttempts:detours.attempted,crossingOperations:crossingChannels.operations,crossingAttempts:crossingChannels.attempted,spacingOperations:spacing.operations,spacingAttempts:spacing.attempted,spacing:spacing.spacing,stages:[]};
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
