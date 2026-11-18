import {performance} from 'node:perf_hooks';
import {hitPin,hitSegment,viewport} from './oracle.mjs';
const vp=viewport({zoom:1.25,pan_px:[12,-9],px_per_mm:4});
const pins=Array.from({length:1000},(_,i)=>({at_um:[(i%40)*20_000,Math.floor(i/40)*20_000],pin:{component_id:`C${i}`,physical_pin_number:'1'}}));
const segments=Array.from({length:2000},(_,i)=>({id:`S${i}`,from_um:[(i%50)*10_000,Math.floor(i/50)*10_000],to_um:[(i%50)*10_000,Math.floor(i/50)*10_000+8000]}));
const samples=400;
for (let warm=0;warm<2;warm++) for(let i=0;i<samples;i++){hitPin(vp.worldToLocal(pins[i].at_um),pins,vp);hitSegment(vp.worldToLocal(segments[i].from_um),segments,vp);}
const t0=performance.now();
for (let i=0;i<samples;i++) hitPin(vp.worldToLocal(pins[i].at_um),pins,vp);
const t1=performance.now();
for (let i=0;i<samples;i++) hitSegment(vp.worldToLocal(segments[i].from_um),segments,vp);
const t2=performance.now();
console.log(JSON.stringify({node:process.version,symbols:1000,pins:1000,wire_segments:2000,samples,mean_hitpin_ms:(t1-t0)/samples,mean_hitsegment_ms:(t2-t1)/samples,elapsed_ms:t2-t0,qualification:'standalone reference linear scan, NOT DOM/render/FPS production benchmark'},null,2));