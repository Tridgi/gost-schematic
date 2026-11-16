import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {renderProjectPreviewSVG,setPng300Dpi} from './browser-export.ts';

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
 const pinrefs=source.project.nets.flatMap(n=>n.members);
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
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlSmKkAAAAASUVORK5CYII=','base64'));
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
