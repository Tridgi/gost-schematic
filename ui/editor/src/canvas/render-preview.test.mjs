import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {renderViewportSVG} from './render-preview.mjs';
import {projectToCanvasScene} from './scene-projection.mjs';
const url=new URL('../../../fixtures/tl494-source-e695-v2.gscad.json',import.meta.url);
const camera={s:.003,x:0,y:0};
test('actual E695 23/15/62/16+2b source renders ink without fake routed wire or junction dot',()=>{
 const file=JSON.parse(readFileSync(url,'utf8')),p=file.project,scene=projectToCanvasScene(file,p.sheets[0].id);
 const before=JSON.stringify(file);
 const svg=renderViewportSVG(scene,camera,{width:1200,height:900,pins:true});
 assert.equal(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"'),true);
 assert.equal((svg.match(/class="source-b"/g)||[]).length,2);
 assert.equal((svg.match(/class="electric-wires"/g)||[]).length,1);
 assert.equal((svg.match(/<circle/g)||[]).length,scene.symbols.reduce((n,s)=>n+s.pins.length,0));
 assert.equal(svg.includes('NaN'),false);
 assert.equal(JSON.stringify(file),before);
 assert.equal(scene.wires.length,0);assert.equal(scene.junctions.length,0);
});
test('render view changes on zoom but signed electrical graph does not',()=>{
 const file=JSON.parse(readFileSync(url,'utf8')),p=file.project,scene=projectToCanvasScene(file,p.sheets[0].id);
 const before=JSON.stringify({nets:p.nets,wires:scene.wires,graphics:p.sheets[0].graphics});
 const a=renderViewportSVG(scene,{...camera,s:.004},{width:1200,height:900,pins:false});
 const b=renderViewportSVG(scene,{...camera,s:.008},{width:1200,height:900,pins:false});
 assert.notEqual(a,b);
 assert.equal(JSON.stringify({nets:p.nets,wires:scene.wires,graphics:p.sheets[0].graphics}),before);
});
test('bare X produces only strokes; explicit junction produces one dot; splice no dot',()=>{
 const base={symbols:[],graphics:[],wires:[
 {id:'w1',vertices:[{id:'a',at_um:[0,10000]},{id:'b',at_um:[20000,10000]}],segments:[{from_vertex_id:'a',to_vertex_id:'b'}]},
 {id:'w2',vertices:[{id:'c',at_um:[10000,0]},{id:'d',at_um:[10000,20000]}],segments:[{from_vertex_id:'c',to_vertex_id:'d'}]}],junctions:[],splices:[{id:'hidden',at_um:[10000,10000]}]};
 const a=renderViewportSVG(base,camera);
 assert.equal((a.match(/<circle/g)||[]).length,0);
 const b=renderViewportSVG({...base,junctions:[{id:'J',at_um:[10000,10000]}]},camera);
 assert.equal((b.match(/<circle/g)||[]).length,1);
});
test('reject zero-length, diagonal and unbounded viewport; do not expose user text attributes',()=>{
 const wire={id:'w',vertices:[{id:'a',at_um:[0,0]},{id:'b',at_um:[0,0]}],segments:[{from_vertex_id:'a',to_vertex_id:'b'}]};
 const scene={symbols:[],graphics:[],wires:[wire],junctions:[]};
 assert.throws(()=>renderViewportSVG(scene,camera),/ZERO_LENGTH_SEGMENT/);
 wire.vertices[1].at_um=[100,100];assert.throws(()=>renderViewportSVG(scene,camera),/NON_ORTHOGONAL/);
 assert.throws(()=>renderViewportSVG({...scene,wires:[]},camera,{width:Infinity}),/INVALID_VIEWPORT/);
 const fake={...scene,wires:[],graphics:[{kind:'line',id:'"><script>alert(1)</script>',strokes:[{from_um:[0,0],to_um:[1000,0]}]}]};
 assert.equal(renderViewportSVG(fake,camera).includes('<script>'),false);
});
