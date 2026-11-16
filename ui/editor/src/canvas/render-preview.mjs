/** Read-only SVG viewport painter for canonical v2 scene projection.
 * NOT the canonical engineering exporter. No UI stroke can create electrical topology.
 * Numeric-only SVG attributes: source IDs/refdes cannot become injected DOM text.
 */
import {screen,pinWorld,camera as validateCamera,point} from './precision.mjs';
const num=n=>{if(!Number.isFinite(n))throw Error('NONFINITE_VIEW');return String(Math.round(n*1000)/1000)};
const line=(a,b,style)=>'<line x1="'+num(a.x)+'" y1="'+num(a.y)+'" x2="'+num(b.x)+'" y2="'+num(b.y)+'" '+style+'/>';
function transform(s,p){
 point(p);
 const [x,y]=[s.mirror_x?-p[0]:p[0],p[1]];
 const d=s.rotation_deg===0?[x,y]:s.rotation_deg===90?[-y,x]:s.rotation_deg===180?[-x,-y]:s.rotation_deg===270?[y,-x]:null;
 if(!d)throw Error('INVALID_ROTATION');
 return point([s.origin_um[0]+d[0],s.origin_um[1]+d[1]]);
}
export function renderViewportSVG(scene,c,{width=900,height=600,pins=true,gridVisible=false,gridUm=1000}={}){
 validateCamera(c);
 if(!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0||width>20000||height>20000)throw Error('INVALID_VIEWPORT');
 const out=['<svg xmlns="http://www.w3.org/2000/svg" width="'+num(width)+'" height="'+num(height)+'" viewBox="0 0 '+num(width)+' '+num(height)+'" role="img" aria-label="GOST visual canvas preview">'];
 out.push('<rect width="100%" height="100%" fill="#141b25"/>');
 if(gridVisible){
  if(!Number.isSafeInteger(gridUm)||gridUm<=0)throw Error('INVALID_GRID');
  const grid=[],topX=Math.ceil(-c.x/c.s/gridUm),bottomX=Math.floor((width-c.x)/c.s/gridUm),topY=Math.ceil(-c.y/c.s/gridUm),bottomY=Math.floor((height-c.y)/c.s/gridUm);
  if(bottomX-topX+bottomY-topY<300&&bottomX-topX>=0&&bottomY-topY>=0){
   for(let i=topX;i<=bottomX;i++){const x=i*gridUm;if(Math.abs(x)>1e9)continue;const p=screen([x,0],c);grid.push(line({x:p.x,y:0},{x:p.x,y:height},'stroke="#293444" stroke-width=".55"'))}
   for(let i=topY;i<=bottomY;i++){const y=i*gridUm;if(Math.abs(y)>1e9)continue;const p=screen([0,y],c);grid.push(line({x:0,y:p.y},{x:width,y:p.y},'stroke="#293444" stroke-width=".55"'))}
  }
  out.push('<g class="viewport-grid">'+grid.join('')+'</g>');
 }
 out.push('<g class="symbol-strokes" fill="none" stroke="#d5e2ee" stroke-width="1.5">');
 for(const s of scene.symbols||[])for(const st of s.strokes||[])out.push(line(screen(transform(s,st.from_um),c),screen(transform(s,st.to_um),c),''));
 out.push('</g>');
 out.push('<g class="electric-wires" stroke="#79c6e8" stroke-width="1.75" fill="none">');
 for(const w of scene.wires||[]){
  const vertices=new Map(w.vertices.map(v=>[v.id,v.at_um]));
  for(const seg of w.segments){
   const a=vertices.get(seg.from_vertex_id),b=vertices.get(seg.to_vertex_id);
   if(!a||!b)throw Error('MISSING_VERTEX');
   point(a);point(b);
   if(a[0]===b[0]&&a[1]===b[1])throw Error('ZERO_LENGTH_SEGMENT');
   if(a[0]!==b[0]&&a[1]!==b[1])throw Error('NON_ORTHOGONAL');
   out.push(line(screen(a,c),screen(b,c),''));
  }
 }
 out.push('</g>');
 out.push('<g class="source-graphics" fill="none" stroke="#aaa9a4" stroke-width="1.2">');
 for(const g of scene.graphics||[])for(const st of g.strokes||[]){
  // These graphics are never wires, regardless of coincidence with a physical pin.
  out.push('<g class="'+(g.kind==='source_b_continuation'?'source-b':'annotation-ink')+'">'+line(screen(st.from_um,c),screen(st.to_um,c),'')+'</g>');
 }
 out.push('</g>');
 out.push('<g class="junction-dots" fill="#79c6e8">');
 for(const j of scene.junctions||[]){const p=screen(j.at_um,c);out.push('<circle cx="'+num(p.x)+'" cy="'+num(p.y)+'" r="3.2"/>')}
 out.push('</g>');
 // A hidden Splice is conductive in the authoritative domain but has no dot here.
 if(pins){
  out.push('<g class="pin-markers" fill="#141b25" stroke="#8dd0b2" stroke-width="1.25">');
  for(const s of scene.symbols||[])for(const p of s.pins||[]){const v=screen(pinWorld(s,p.physical_pin_number).at_um,c);out.push('<circle cx="'+num(v.x)+'" cy="'+num(v.y)+'" r="2.8"/>')}
  out.push('</g>');
 }
 out.push('</svg>');
 return out.join('');
}
