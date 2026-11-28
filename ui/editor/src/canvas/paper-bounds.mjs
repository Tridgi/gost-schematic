/** R10: non-mutating paper overflow diagnostics. A projected symbol's ink and
 * physical contacts count, not just its origin. Nets are never inferred from
 * geometric overlaps or the paper guide.
 */
import {noteLayout} from '../model/symbol-notes.mjs';
const at=(symbol,p)=>{
 const x=symbol.mirror_x?-p[0]:p[0],y=p[1];
 const r=symbol.rotation_deg;
 if(![0,90,180,270].includes(r))throw Error('INVALID_ROTATION');
 const q=r===0?[x,y]:r===90?[-y,x]:r===180?[-x,-y]:[y,-x];
 return [symbol.origin_um[0]+q[0],symbol.origin_um[1]+q[1]];
};
/** Return source identities only; no changes to the authoritative document. */
export function detectPaperOverflow(scene,snapshot,sizeUm,annotations=[]){
 if(!Array.isArray(sizeUm)||sizeUm.length!==2||
   !sizeUm.every(n=>Number.isSafeInteger(n)&&n>0))throw Error('INVALID_FRAME');
 const outside=(p,pad=0)=>p[0]-pad<0||p[1]-pad<0||p[0]+pad>sizeUm[0]||p[1]+pad>sizeUm[1];
 const symbols=scene.symbols.filter(s=>outside(s.origin_um)||
   s.pins.some(p=>outside(at(s,p.at_um)))||
   (s.inkStrokes??s.strokes).some(k=>outside(at(s,k.from_um),(k.stroke_um??0)/2)||outside(at(s,k.to_um),(k.stroke_um??0)/2))||
   (s.curves??[]).some(c=>c.bounds.some(p=>outside(at(s,p),c.stroke_um/2)))||
   (s.notes||[]).some(n=>noteLayout(n,at(s,n.at_um)).bounds.some(p=>outside(p))))
   .map(s=>s.component_id);
 const graphics=scene.graphics.filter(g=>g.strokes.some(k=>
   outside(k.from_um,(k.stroke_um??0)/2)||outside(k.to_um,(k.stroke_um??0)/2))).map(g=>g.id);
 // Canonical browser print uses 300 µm butt-capped orthogonal wires
 // and 550 µm radius junction dots. Invisible splices remain point checks.
 const wires=snapshot.wires.filter(w=>w.vertices.some(v=>outside(v.at_um))||
   w.vertices.slice(1).some((v,i)=>{
    const a=w.vertices[i].at_um,b=v.at_um;
    const t=a[0]===b[0]?0:1;
    return [a,b].some(p=>p[t]-150<0||p[t]+150>sizeUm[t]);
   })).map(w=>w.id);
 const junctions=snapshot.junctions.filter(j=>outside(j.at_um,550)).map(j=>j.id);
 const splices=snapshot.splices.filter(s=>outside(s.at_um)).map(s=>s.id);
 // Match the canonical Python export envelope (not certified font ink).
 // Python len counts Unicode code points; Array.from has the same semantics.
 const texts=annotations.filter(t=>{
   if(!t.text)return false;
   const h=t.height_um??3500,r=t.rotation_deg??0,n=Array.from(t.text).length;
   if(!Number.isSafeInteger(h)||h<=0||![0,90,180,270].includes(r))throw Error('INVALID_ANNOTATION_GEOMETRY');
   return [[-h,-2*h],[(n+1)*h,-2*h],[-h,h],[(n+1)*h,h]].some(([x,y])=>{
     const [u,v]=r===0?[x,y]:r===90?[-y,x]:r===180?[-x,-y]:[y,-x];
     return outside([t.at_um[0]+u,t.at_um[1]+v]);
   });
 }).map(t=>t.id);
 return {symbols,graphics,wires,junctions,splices,texts,
   total:symbols.length+graphics.length+wires.length+junctions.length+splices.length+texts.length};
}
