import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {renderProjectPreviewSVG,setPng300Dpi} from './browser-export.ts';
import {planComponentLabels} from '../canvas/component-labels.ts';

const source=JSON.parse(readFileSync(
  new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url),'utf8'
));
test('frozen E695 physical A3 SVG preserves 23 component instances, source Nets, 62 PinRefs and b ink',()=>{
 const svg=renderProjectPreviewSVG(source,'sheet-1');
 assert.match(svg,/width="420mm" height="297mm" viewBox="0 0 420 297"/);
 assert.match(svg,/data-font-status="unverified-preview"/);
 assert.match(svg,/data-source-net-count="15"/);
 assert.match(svg,/data-authored-wire-count="0"/);
 assert.match(svg,/e695c415fdced164b0e0c39c5249d030795a0aa6/);
 assert.equal((svg.match(/data-layer="symbols"/g)||[]).length,23);
 assert.equal((svg.match(/data-kind="source_b_continuation"/g)||[]).length,2);
 assert.equal((svg.match(/data-layer="wires"/g)||[]).length,0);
 assert.equal((svg.match(/data-layer="explicit-junctions"/g)||[]).length,0);
 const pinrefs=source.project.nets.flatMap((n:{members:unknown[]})=>n.members);
 assert.equal(pinrefs.length,62);
 assert.ok(svg.includes('data-electrical="declared-not-geometry-inferred"'));
});
test('XML metacharacters in source labels are escaped and cannot create a script element',()=>{
 const doc=structuredClone(source);
 doc.project.sheets[0].labels[0].text='<svg onload="alert(1)">& bad';
 const svg=renderProjectPreviewSVG(doc,'sheet-1');
 assert.ok(!svg.includes('<svg onload='));
 assert.ok(svg.includes('&lt;svg onload=&quot;alert(1)&quot;&gt;&amp; bad'));
});
test('unknown version and malformed graphic fail closed',()=>{
 const bad=structuredClone(source);
 bad.format_version=99;
 assert.throws(()=>renderProjectPreviewSVG(bad,'sheet-1'),/INVALID_PROJECT_V2/);
 const badGraph=structuredClone(source);
 badGraph.project.sheets[0].graphics[0].points_um=[[0,0],[0,0]];
 assert.throws(()=>renderProjectPreviewSVG(badGraph,'sheet-1'),/ZERO_LENGTH_GRAPHIC/);
});
test('PNG pHYs is physically 300 DPI and preserves original PNG bytes/chunk order',()=>{
 const raw=new Uint8Array(Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9RYVFHYAAAAASUVORK5CYII=','base64'));
 const out=setPng300Dpi(raw);
 assert.deepEqual([...out.slice(0,8)],[137,80,78,71,13,10,26,10]);
 assert.equal(Buffer.from(out.slice(12,16)).toString(),'IHDR');
 assert.equal(Buffer.from(out.slice(37,41)).toString(),'pHYs');
 assert.equal(Buffer.from(out.slice(41,45)).readUInt32BE(0),11811);
 assert.equal(Buffer.from(out.slice(45,49)).readUInt32BE(0),11811);
 assert.equal(out[49],1);
 assert.match(Buffer.from(out).toString('latin1'),/IEND/);
 assert.deepEqual(setPng300Dpi(out),out);
 assert.throws(()=>setPng300Dpi(new Uint8Array([1,2,3])),/NOT_PNG/);
});


test('PNG300 encoder rejects invalid chunk CRC, missing IDAT and trailing garbage',()=>{
 const valid=new Uint8Array(Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9RYVFHYAAAAASUVORK5CYII=','base64'));
 const badIdat=valid.slice();
 badIdat[43]^=1; // corrupt IDAT compressed data without correcting CRC
 assert.throws(()=>setPng300Dpi(badIdat),/INVALID_PNG_CRC/);
 const noIdat=Uint8Array.from([...valid.slice(0,33),...valid.slice(-12)]);
 assert.throws(()=>setPng300Dpi(noIdat),/INVALID_PNG_STRUCTURE/);
 const trailing=Uint8Array.from([...valid,0x61]);
 assert.throws(()=>setPng300Dpi(trailing),/INVALID_PNG_STRUCTURE/);
});

test('R17c exact circle and semicircle under all D4 transforms, invalid curves rejected',()=>{
 const doc=structuredClone(source);
 const inst=doc.project.sheets[0].instances[0];
 const sym=doc.project.symbol_definitions.find((s:{id:string})=>s.id===inst.symbol_id);
 sym.graphics=[{kind:'circle',points_um:[[0,0],[2000,0]],stroke_um:300},
  {kind:'semicircle',points_um:[[-2000,0],[0,-2000],[2000,0]],stroke_um:300}];
 for(const rotation of [0,90,180,270])for(const mirror of [false,true]){
  inst.rotation_deg=rotation;inst.mirror_x=mirror;
  const svg=renderProjectPreviewSVG(doc,'sheet-1');
  assert.match(svg,/<circle[^>]* r="2"[^>]*stroke-width="0.300"/);
  assert.match(svg,new RegExp(' A 2 2 0 0 '+(mirror?0:1)+' '));
 }
 sym.graphics[1].points_um[1]=[0,-1999];
 assert.throws(()=>renderProjectPreviewSVG(doc,'sheet-1'),/INVALID_CURVE/);
});


test('R32j frozen source component labels are upright, deterministic and do not invent missing values',()=>{
 const original=structuredClone(source),p=planComponentLabels(source,'sheet-1');
 assert.equal(p.labels.length+p.unplaced.length,23);
 assert.ok(p.labels.length>0);
 assert.ok(p.labels.every(l=>!l.value));
 assert.deepEqual(planComponentLabels(source,'sheet-1'),p);
 assert.deepEqual(source,original);
 const svg=renderProjectPreviewSVG(source,'sheet-1');
 assert.equal((svg.match(/data-label-role="reference"/g)??[]).length,p.labels.length);
 assert.equal((svg.match(/data-label-role="value"/g)??[]).length,0);
 assert.ok(svg.includes('data-unplaced-label-count="'+p.unplaced.length+'"'));
 for(const a of p.labels)for(const b of p.labels.filter(x=>x!==a)){
  assert.ok(a.bounds.x1<b.bounds.x0||a.bounds.x0>b.bounds.x1||a.bounds.y1<b.bounds.y0||a.bounds.y0>b.bounds.y1);
 }
});
test('R32j nonempty values escape XML and unresolved placement is explicit',()=>{
 const doc=structuredClone(source);
 doc.project.components[0].value='10 < 20 & "V"';
 const labels=planComponentLabels(doc,'sheet-1');
 assert.ok(labels.labels.some(l=>l.refdes==='C1'&&l.value===doc.project.components[0].value));
 const svg=renderProjectPreviewSVG(doc,'sheet-1');
 assert.ok(svg.includes('10 &lt; 20 &amp; &quot;V&quot;'));
 assert.ok(svg.includes('data-label-role="value"'));
 const bad=structuredClone(doc);
 bad.project.components[0].value='x'.repeat(65);
 const p=planComponentLabels(bad,'sheet-1');
 assert.ok(p.unplaced.some(l=>l.refdes==='C1'&&l.reason==='LABEL_TEXT_UNSUPPORTED'));
 assert.ok(renderProjectPreviewSVG(bad,'sheet-1').includes('LABEL_TEXT_UNSUPPORTED'));
});


test('R32k extended nearby channels place a label beyond blocked original slots without reducing clearance',async()=>{
 const {projectToCanvasScene}=await import('../canvas/scene-projection.mjs');
 const doc=structuredClone(source);
 const sh=doc.project.sheets[0];
 sh.texts=[];sh.labels=[];sh.graphics=[];sh.wires=[];sh.junctions=[];sh.splices=[];
 const scene=projectToCanvasScene(doc,'sheet-1');
 const symbol=scene.symbols[0];
 // A synthetic projected symbol with exact 10 x 6 mm ink envelope.
 // Four conservative ink bands obstruct every original nearby slot.
 const only={...symbol,origin_um:[100000,100000] as [number,number],
  rotation_deg:0 as const,mirror_x:false,pins:[],curves:[],notes:[],
  strokes:[],inkStrokes:[{from_um:[-5000,-3000] as [number,number],
    to_um:[5000,3000] as [number,number],stroke_um:0}]};
 const bands=[
  {from_um:[80000,90000],to_um:[120000,90000],stroke_um:9000},
  {from_um:[80000,110000],to_um:[120000,110000],stroke_um:9000},
  {from_um:[85000,80000],to_um:[85000,120000],stroke_um:10000},
  {from_um:[115000,80000],to_um:[115000,120000],stroke_um:10000}
 ] as const;
 const projected={...scene,symbols:[only],graphics:bands.map((b,i)=>({
  id:'band-'+i,layer_id:only.layer_id,kind:'line' as const,source_role:'none',electrical:false as const,
  strokes:[{from_um:[...b.from_um] as [number,number],to_um:[...b.to_um] as [number,number],stroke_um:b.stroke_um}]
 }))};
 const before=structuredClone(projected),p=planComponentLabels(doc,'sheet-1',projected);
 assert.equal(p.labels.length,1);assert.equal(p.unplaced.length,0);
 assert.equal(p.labels[0].heightUm,2500);
 const b=p.labels[0].bounds;
 for(const s of bands){
  const x0=Math.min(s.from_um[0],s.to_um[0])-s.stroke_um/2;
  const x1=Math.max(s.from_um[0],s.to_um[0])+s.stroke_um/2;
  const y0=Math.min(s.from_um[1],s.to_um[1])-s.stroke_um/2;
  const y1=Math.max(s.from_um[1],s.to_um[1])+s.stroke_um/2;
  assert.ok(b.x1<x0||b.x0>x1||b.y1<y0||b.y0>y1);
 }
 assert.deepEqual(planComponentLabels(doc,'sheet-1',projected),p);
 assert.deepEqual(projected,before);
});
