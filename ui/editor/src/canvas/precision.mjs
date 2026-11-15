/** CHAT 4 isolated precision geometry — no implied electrical topology.
 * Prototype adapter awaiting #122 model & #123 commands. Source values are integer µm.
 * DOM/SVG hit testing is visual; only signed PinRefs and explicit Junctions connect.
 */
function assertUm(n){if(!Number.isSafeInteger(n)||Math.abs(n)>1e9)throw Error("INVALID_UM");return n}

function point(p){if(!Array.isArray(p)||p.length!==2)throw Error("INVALID_POINT");return [assertUm(p[0]),assertUm(p[1])]}

function screen(p,c){point(p);if(!(c.s>0&&Number.isFinite(c.s)))throw Error("INVALID_ZOOM");return {x:p[0]*c.s+c.x,y:p[1]*c.s+c.y}}

function world(p,c){if(!(c.s>0&&Number.isFinite(c.s)))throw Error("INVALID_ZOOM");return point([Math.round((p.x-c.x)/c.s),Math.round((p.y-c.y)/c.s)])}

function zoom(c,p,factor){if(!(factor>0&&Number.isFinite(factor)))throw Error("INVALID_ZOOM_FACTOR");const s=Math.min(.2,Math.max(.002,c.s*factor));const u=(p.x-c.x)/c.s,v=(p.y-c.y)/c.s;return {s,x:p.x-u*s,y:p.y-v*s}}

function snap(p,grid,enabled){point(p);if(!Number.isSafeInteger(grid)||grid<=0)throw Error("INVALID_GRID");return enabled?point(p.map(v=>Math.round(v/grid)*grid)):p}

function pinWorld(symbol,physical_pin_number){
 const pin=symbol.pins.find(p=>p.physical_pin_number===physical_pin_number);if(!pin)throw Error("UNKNOWN_PIN");
 const [ox,oy]=point(symbol.origin_um),[px,py]=point(pin.at_um),x=symbol.mirror_x?-px:px,y=py;
 const n={up:[0,-1],down:[0,1],left:[-1,0],right:[1,0]}[pin.normal];if(!n)throw Error("INVALID_PIN_NORMAL");
 const rot=([a,b])=>{switch(symbol.rotation_deg){case 0:return [a,b];case 90:return [-b,a];case 180:return [-a,-b];case 270:return [b,-a];default:throw Error("INVALID_ROTATION")}};
 const d=rot([x,y]),nv=rot([symbol.mirror_x?-n[0]:n[0],n[1]]);
 const normal=Object.entries({up:[0,-1],down:[0,1],left:[-1,0],right:[1,0]}).find(([,v])=>v[0]===nv[0]&&v[1]===nv[1])?.[0];
 return {at_um:point([ox+d[0],oy+d[1]]),normal,pin:{component_id:symbol.component_id,physical_pin_number}};
}

function segmentDistance(p,a,b){const dx=b.x-a.x,dy=b.y-a.y,m=dx*dx+dy*dy;const t=m?Math.max(0,Math.min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/m)):0;return Math.hypot(p.x-(a.x+dx*t),p.y-(a.y+dy*t))}

function hitTest(scene,c,p,tolerance=8){
 if(!Number.isFinite(tolerance)||tolerance<=0)throw Error('INVALID_HIT_TOLERANCE');
 const pinBandPx=Math.min(tolerance,7),wireBandPx=Math.min(tolerance,5);
 const pins=[];for(const s of scene.symbols)for(const pin of s.pins){
  const q=pinWorld(s,pin.physical_pin_number);const d=Math.hypot(p.x-screen(q.at_um,c).x,p.y-screen(q.at_um,c).y);
  if(d<=pinBandPx)pins.push({...q,distance_px:d});
 }
 pins.sort((a,b)=>a.distance_px-b.distance_px);
 if(pins.length){const choices=pins.filter(x=>x.distance_px-pins[0].distance_px<=.75);return choices.length>1?{kind:"ambiguous-pin",candidates:choices.map(x=>x.pin)}:{kind:"pin",...pins[0]}}
 for(const j of scene.junctions||[]){const xy=screen(j.at_um,c);if(Math.hypot(p.x-xy.x,p.y-xy.y)<=tolerance)return {kind:"junction",junction_id:j.id}}
 const hits=[];for(const w of scene.wires)for(let i=0;i<w.segments.length;i++){
  const segment=w.segments[i],a=w.vertices.find(v=>v.id===segment.from_vertex_id),b=w.vertices.find(v=>v.id===segment.to_vertex_id);
  if(!a||!b)throw Error("MISSING_VERTEX");
  point(a.at_um);point(b.at_um);if(a.at_um[0]!==b.at_um[0]&&a.at_um[1]!==b.at_um[1])throw Error("NON_ORTHOGONAL");
  const d=segmentDistance(p,screen(a.at_um,c),screen(b.at_um,c));
  if(d<=wireBandPx)hits.push({kind:"segment",wire_id:w.id,segment_id:segment.id,distance_px:d,movable:i>0&&i<w.segments.length-1,axis:a.at_um[0]===b.at_um[0]?"v":"h"});
 }
 hits.sort((a,b)=>a.distance_px-b.distance_px);if(hits.length){const near=hits.filter(x=>x.distance_px-hits[0].distance_px<=.75);return near.length>1?{kind:"ambiguous-segment",candidates:near.map(x=>({wire_id:x.wire_id,segment_id:x.segment_id}))}:near[0]}
 return null;
}
export {assertUm,point,screen,world,zoom,snap,pinWorld,hitTest};
