/** R10: non-mutating paper overflow diagnostics. A projected symbol's ink and
 * physical contacts count, not just its origin. Nets are never inferred from
 * geometric overlaps or the paper guide.
 */
const at=(symbol,p)=>{
 const x=symbol.mirror_x?-p[0]:p[0],y=p[1];
 const r=symbol.rotation_deg;
 if(![0,90,180,270].includes(r))throw Error('INVALID_ROTATION');
 const q=r===0?[x,y]:r===90?[-y,x]:r===180?[-x,-y]:[y,-x];
 return [symbol.origin_um[0]+q[0],symbol.origin_um[1]+q[1]];
};
/** Return source identities only; no changes to the authoritative document. */
export function detectPaperOverflow(scene,snapshot,sizeUm){
 if(!Array.isArray(sizeUm)||sizeUm.length!==2||
   !sizeUm.every(n=>Number.isSafeInteger(n)&&n>0))throw Error('INVALID_FRAME');
 const outside=p=>p[0]<0||p[1]<0||p[0]>sizeUm[0]||p[1]>sizeUm[1];
 const symbols=scene.symbols.filter(s=>outside(s.origin_um)||
   s.pins.some(p=>outside(at(s,p.at_um)))||
   s.strokes.some(k=>outside(at(s,k.from_um))||outside(at(s,k.to_um))))
   .map(s=>s.component_id);
 const graphics=scene.graphics.filter(g=>g.strokes.some(k=>
   outside(k.from_um)||outside(k.to_um))).map(g=>g.id);
 const wires=snapshot.wires.filter(w=>w.vertices.some(v=>outside(v.at_um))).map(w=>w.id);
 const junctions=snapshot.junctions.filter(j=>outside(j.at_um)).map(j=>j.id);
 const splices=snapshot.splices.filter(s=>outside(s.at_um)).map(s=>s.id);
 return {symbols,graphics,wires,junctions,splices,
   total:symbols.length+graphics.length+wires.length+junctions.length+splices.length};
}
