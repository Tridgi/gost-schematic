/** Live, read-only first-pass ERC/DRC. Geometry never creates electrical edges.
 * Not a normative GOST clearance or circuit-simulation certificate.
 */
import {pinWorld} from '../canvas/precision.mjs';
import {noteLayout} from '../model/symbol-notes.mjs';
const key=p=>JSON.stringify([p.component_id,p.physical_pin_number]);
const same=(a,b)=>a[0]===b[0]&&a[1]===b[1];
const endpointKey=a=>a?.kind==='pin'?'pin:'+key(a):a?.kind==='junction'?'j:'+a.junction_id:a?.kind==='splice'?'s:'+a.splice_id:null;
const bbox=(a,b)=>({x0:Math.min(a[0],b[0]),x1:Math.max(a[0],b[0]),y0:Math.min(a[1],b[1]),y1:Math.max(a[1],b[1])});
const within=(p,b)=>p[0]>=b.x0&&p[0]<=b.x1&&p[1]>=b.y0&&p[1]<=b.y1;
const overlap=(a,b)=>a.x0<=b.x1&&b.x0<=a.x1&&a.y0<=b.y1&&b.y0<=a.y1;
const world=(s,p)=>{
 const x=s.mirror_x?-p[0]:p[0],y=p[1],r=s.rotation_deg;
 const q=r===0?[x,y]:r===90?[-y,x]:r===180?[-x,-y]:[y,-x];
 return [s.origin_um[0]+q[0],s.origin_um[1]+q[1]];
};
function symbolBounds(s){
 const b={x0:s.origin_um[0],x1:s.origin_um[0],y0:s.origin_um[1],y1:s.origin_um[1]};
 const add=(p,pad=0)=>{b.x0=Math.min(b.x0,p[0]-pad);b.y0=Math.min(b.y0,p[1]-pad);b.x1=Math.max(b.x1,p[0]+pad);b.y1=Math.max(b.y1,p[1]+pad)};
 for(const p of s.pins)add(world(s,p.at_um));
 for(const l of s.inkStrokes??s.strokes){const w=(l.stroke_um??0)/2;add(world(s,l.from_um),w);add(world(s,l.to_um),w)}
 for(const c of s.curves??[])for(const p of c.bounds)add(world(s,p),c.stroke_um/2);
 for(const n of s.notes??[])for(const p of noteLayout(n,world(s,n.at_um)).bounds)add(p);
 return b;
}
function contact(a,b){
 if(!overlap(a.box,b.box))return null;
 if(a.horizontal===b.horizontal){
  if(a.horizontal&&a.a.at_um[1]!==b.a.at_um[1]||!a.horizontal&&a.a.at_um[0]!==b.a.at_um[0])return null;
  const lo=a.horizontal?Math.max(a.box.x0,b.box.x0):Math.max(a.box.y0,b.box.y0);
  const hi=a.horizontal?Math.min(a.box.x1,b.box.x1):Math.min(a.box.y1,b.box.y1);
  if(hi>lo)return {kind:'overlap'};
  return {kind:'touch',at:a.horizontal?[lo,a.a.at_um[1]]:[a.a.at_um[0],lo]};
 }
 const h=a.horizontal?a:b,v=a.horizontal?b:a;
 const at=[v.a.at_um[0],h.a.at_um[1]];
 if(!within(at,a.box)||!within(at,b.box))return null;
 return {kind:'touch',at};
}
/** Exact straight stroke versus H/V wire centerline. Rational arithmetic avoids
 * floating rounding of signed µm coordinates, even for steep diagonals. */
function straightContact(segment,a,b){
 const fixed=segment.horizontal?1:0,variable=1-fixed,q=segment.a.at_um[fixed];
 const lo=BigInt(Math.min(segment.a.at_um[variable],segment.b.at_um[variable]));
 const hi=BigInt(Math.max(segment.a.at_um[variable],segment.b.at_um[variable]));
 if(q<Math.min(a[fixed],b[fixed])||q>Math.max(a[fixed],b[fixed]))return [];
 const at=v=>segment.horizontal?[v,q]:[q,v];
 if(a[fixed]===b[fixed]){
  const left=lo>BigInt(Math.min(a[variable],b[variable]))?lo:BigInt(Math.min(a[variable],b[variable]));
  const right=hi<BigInt(Math.max(a[variable],b[variable]))?hi:BigInt(Math.max(a[variable],b[variable]));
  if(left>right)return [];
  return left===right?[{at:at(Number(left))}]:[{overlap:true}];
 }
 let denominator=BigInt(b[fixed])-BigInt(a[fixed]);
 let numerator=BigInt(a[variable])*denominator+(BigInt(b[variable])-BigInt(a[variable]))*(BigInt(q)-BigInt(a[fixed]));
 if(denominator<0n){denominator=-denominator;numerator=-numerator}
 if(numerator<lo*denominator||numerator>hi*denominator)return [];
 return numerator%denominator===0n?[{at:at(Number(numerator/denominator))}]:[{nonInteger:true}];
}
/** Distance between disjoint closed straight segments. Stroke clearance
 * is a visual warning only; it cannot create connectivity. */
function pointSegmentDistance2(p,a,b){
 const dx=b[0]-a[0],dy=b[1]-a[1],d=dx*dx+dy*dy;
 const t=d===0?0:Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d));
 return (p[0]-a[0]-t*dx)**2+(p[1]-a[1]-t*dy)**2;
}
function strokeNear(segment,a,b,radius){
 if(!(radius>0))return false;
 const p=segment.a.at_um,q=segment.b.at_um;
 return Math.min(pointSegmentDistance2(p,a,b),pointSegmentDistance2(q,a,b),
  pointSegmentDistance2(a,p,q),pointSegmentDistance2(b,p,q))<=radius*radius;
}
/** Analytic H/V-circle intersection, clipped to the semicircle's visible half.
 * Square-root values are used only for a visual warning, never connectivity. */
function curvedContact(segment,symbol,curve){
 const center=world(symbol,curve.center),r=curve.radius;
 const fixed=segment.horizontal?1:0,variable=1-fixed,q=segment.a.at_um[fixed];
 const d=q-center[fixed];if(Math.abs(d)>r)return [];
 const t=Math.sqrt((r-Math.abs(d))*(r+Math.abs(d)));
 const lo=Math.min(segment.a.at_um[variable],segment.b.at_um[variable]),hi=Math.max(segment.a.at_um[variable],segment.b.at_um[variable]);
 const apex=curve.kind==='semicircle'?world(symbol,curve.points_um[1]):null;
 const result=[];
 for(const v of new Set([center[variable]-t,center[variable]+t])){
  if(v<lo-1e-6||v>hi+1e-6)continue;
  const at=segment.horizontal?[v,q]:[q,v];
  if(apex&&(at[0]-center[0])*(apex[0]-center[0])+(at[1]-center[1])*(apex[1]-center[1])< -1e-6)continue;
  result.push({at});
 }
 return result;
}
/** Minimum distance for a disjoint axis-aligned conductor and a cardinal
 * circular arc: endpoints, radial projections and normal extrema suffice.
 * Uses the visible semicircle only, never the invisible complementary half. */
function curvedNear(segment,symbol,curve){
 const pad=curve.stroke_um/2;if(!(pad>0))return false;
 const c=world(symbol,curve.center),r=curve.radius;
 const p=segment.a.at_um,q=segment.b.at_um;
 const apex=curve.kind==='semicircle'?world(symbol,curve.points_um[1]):null;
 const visible=v=>!apex||(v[0]-c[0])*(apex[0]-c[0])+(v[1]-c[1])*(apex[1]-c[1])>=0;
 let distance2=Infinity;
 for(const v of [p,q]){
  const dx=v[0]-c[0],dy=v[1]-c[1],d=Math.hypot(dx,dy);
  if(visible(v))distance2=Math.min(distance2,(d-r)**2);
 }
 const extrema=[[c[0]-r,c[1]],[c[0]+r,c[1]],[c[0],c[1]-r],[c[0],c[1]+r]];
 for(const v of extrema)if(visible(v))distance2=Math.min(distance2,pointSegmentDistance2(v,p,q));
 return distance2<=pad*pad;
}
export function analyzeDiagnostics(file,scene,snapshot,routeStatuses={},options={}){
 const maxItems=options.maxItems??200,maxComparisons=options.maxComparisons??150000;
 const buckets={error:[],warning:[],info:[]},seen=new Set(),counts={error:0,warning:0,info:0};
 let comparisons=0,incomplete=false;
 const add=(code,severity,message,identities=[],instanceId)=>{
  const id=JSON.stringify([code,...identities]);
  if(seen.has(id))return;
  // Electrical counts are exact for the scanned entities; only geometry comparisons
  // and rendered rows are capped. Do not silently drop known issue counts.
  seen.add(id);counts[severity]++;
  if(buckets[severity].length<maxItems)buckets[severity].push({id,code,severity,message,...(instanceId?{instanceId}:{})});
 };
 const budget=()=>{if(comparisons>=maxComparisons){incomplete=true;return false}comparisons++;return true};
 const project=file.project,byComp=new Map(project.components.map(c=>[c.id,c]));
 const byPart=new Map(project.part_definitions.map(p=>[p.id,p]));
 const byNet=new Map(project.nets.map(n=>[n.id,n]));
 const pinNet=new Map(project.nets.flatMap(n=>n.members.map(p=>[key(p),n.id])));
 const ref=id=>byComp.get(id)?.refdes??id,netName=id=>byNet.get(id)?.name??id;
 for(const s of scene.symbols){
  const missing=s.pins.filter(p=>!pinNet.has(key({component_id:s.component_id,physical_pin_number:p.physical_pin_number})));
  if(missing.length)add('ERC_UNASSIGNED_PIN','warning',ref(s.component_id)+': выводы без назначенной цепи: '+missing.map(p=>p.physical_pin_number).join(', '),[s.component_id],s.instance_id);
 }
 for(const n of snapshot.nets){
  const status=routeStatuses[n.id];
  if(status==='unrouted'||status==='partial')add(status==='unrouted'?'ERC_UNROUTED_NET':'ERC_PARTIAL_NET','warning',
   netName(n.id)+(status==='unrouted'?': отсутствует маршрут на активном листе.':': маршрут неполный или требует проверки.'),[n.id]);
  const global=byNet.get(n.id);
  const drivers=(global?.members??[]).filter(p=>{
   const part=byPart.get(byComp.get(p.component_id)?.part_id);
   const type=part?.physical_pins.find(v=>v.number===p.physical_pin_number)?.electrical_type;
   return type==='output'||type==='power_output';
  });
  if(drivers.length>1)add('ERC_MULTIPLE_OUTPUTS','warning',netName(n.id)+': несколько активных выходов ('+drivers.map(p=>ref(p.component_id)+'.'+p.physical_pin_number).join(', ')+'). Проверьте совместимость.',[n.id]);
 }
 const segments=[];
 for(const w of snapshot.wires){
  const last=w.vertices.length-1;
  const free=[w.vertices[0],w.vertices[last]].filter(v=>v.anchor.kind==='free');
  if(free.length)add('ERC_FREE_ENDPOINT','warning',netName(w.net_id)+': незакреплённых концов проводника: '+free.length,[w.id]);
  if(w.needs_routing_review)add('DRC_ROUTE_REVIEW','warning',netName(w.net_id)+': проводник требует проверки трассировки.',[w.id]);
  const byId=new Map(w.vertices.map((v,i)=>[v.id,{...v,index:i}]));
  for(const seg of w.segments){
   const a=byId.get(seg.from_vertex_id),b=byId.get(seg.to_vertex_id);
   if(!a||!b)continue;
   segments.push({wire:w,seg,a,b,box:bbox(a.at_um,b.at_um),horizontal:a.at_um[1]===b.at_um[1]});
  }
 }
 const sorted=segments.sort((a,b)=>a.box.x0-b.box.x0);
 outer:for(let i=0;i<sorted.length;i++)for(let j=i+1;j<sorted.length;j++){
  const a=sorted[i],b=sorted[j];
  if(b.box.x0>a.box.x1)break;
  if(!budget())break outer;
  const c=contact(a,b);if(!c)continue;
  const sameWire=a.wire.id===b.wire.id,foreign=a.wire.net_id!==b.wire.net_id;
  if(c.kind==='overlap'){
   const ids=[a.wire.id,b.wire.id].sort();
   add(foreign?'DRC_FOREIGN_WIRE_OVERLAP':'DRC_WIRE_OVERLAP',foreign?'error':'warning',
    'Графическое наложение проводников: '+netName(a.wire.net_id)+' / '+netName(b.wire.net_id)+'. Соединение не добавлено.',ids);
   continue;
  }
  const va=[a.a,a.b].find(v=>same(v.at_um,c.at)),vb=[b.a,b.b].find(v=>same(v.at_um,c.at));
  if(!va&&!vb)continue; // ordinary X crossing is not an electrical fault
  if(sameWire&&va&&vb&&va.id===vb.id)continue;
  if(va&&vb&&endpointKey(va.anchor)&&endpointKey(va.anchor)===endpointKey(vb.anchor))continue;
  add(foreign?'DRC_FOREIGN_WIRE_TOUCH':'DRC_UNMARKED_TOUCH',foreign?'error':'warning',
   'Неоднозначное касание проводников '+netName(a.wire.net_id)+' / '+netName(b.wire.net_id)+'. Требуется явное соединение или разнос.',[...([a.wire.id,b.wire.id].sort()),...c.at]);
 }
 const boxes=scene.symbols.map(s=>({s,box:symbolBounds(s)})).sort((a,b)=>a.box.x0-b.box.x0);
 outer:for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
  const a=boxes[i],b=boxes[j];
  if(b.box.x0>=a.box.x1)break;
  if(!budget())break outer;
  if(a.box.y0<b.box.y1&&b.box.y0<a.box.y1)
   add('DRC_SYMBOL_BOUNDS','warning','Пересекаются габариты УГО '+ref(a.s.component_id)+' и '+ref(b.s.component_id)+'. Проверьте визуальный зазор.',[...([a.s.component_id,b.s.component_id].sort())],a.s.instance_id);
 }
 outer:for(const s of scene.symbols)for(const p of s.pins){
  const signed=pinWorld(s,p.physical_pin_number),at=signed.at_um,pinId=key(signed.pin),assigned=pinNet.get(pinId);
  for(const seg of sorted){
   if(seg.box.x0>at[0])break;
   if(!budget())break outer;
   if(!within(at,seg.box))continue;
   if([seg.a,seg.b].some(v=>same(v.at_um,at)&&v.anchor.kind==='pin'&&key(v.anchor)===pinId))continue;
   // Other segments of an explicitly attached wire may share its terminal at the same coordinate.
   if([seg.wire.vertices[0],seg.wire.vertices.at(-1)].some(v=>same(v.at_um,at)&&v.anchor.kind==='pin'&&key(v.anchor)===pinId))continue;
   const foreign=assigned!==undefined&&assigned!==seg.wire.net_id;
   add(foreign?'DRC_FOREIGN_PIN_CONTACT':'DRC_UNSIGNED_PIN_CONTACT',foreign?'error':'warning',
    'Проводник '+netName(seg.wire.net_id)+' касается '+ref(s.component_id)+'.'+p.physical_pin_number+' без соответствующего PinRef.',[seg.wire.id,pinId],s.instance_id);
  }
 }
 // Visual wire-to-symbol ink checks: real straight segments and analytic arcs.
 // A genuine signed pin contact is exempt only at its exact terminal.
 outer:for(const {s,box} of boxes){
  for(const seg of sorted){
   if(seg.box.x0>box.x1)break;
   if(!budget())break outer;
   if(!overlap(seg.box,box))continue;
   const allowed=hit=>hit.at&&[seg.a,seg.b].some(v=>
     v.anchor.kind==='pin'&&v.anchor.component_id===s.component_id&&same(v.at_um,hit.at)&&
     s.pins.some(p=>p.physical_pin_number===v.anchor.physical_pin_number&&same(pinWorld(s,p.physical_pin_number).at_um,hit.at)));
   let collision=false;
   for(const stroke of s.inkStrokes??s.strokes){
    if(!budget())break outer;
    const a=world(s,stroke.from_um),b=world(s,stroke.to_um);
    const radius=(stroke.stroke_um??0)/2,extent=bbox(a,b);
    if(!overlap(seg.box,{x0:extent.x0-radius,x1:extent.x1+radius,y0:extent.y0-radius,y1:extent.y1+radius}))continue;
    const hits=straightContact(seg,a,b);
    if(hits.some(hit=>!allowed(hit))||(!hits.length&&strokeNear(seg,a,b,radius))){collision=true;break}
   }
   if(!collision)for(const curve of s.curves??[]){
    if(!budget())break outer;
    const hits=curvedContact(seg,s,curve);
    if(hits.some(hit=>!allowed(hit))||(!hits.length&&curvedNear(seg,s,curve))){collision=true;break}
   }
   // Text is upright sheet ink; use the same conservative envelope as
   // the placement/print geometry rather than treating it as a conductor.
   for(const note of s.notes??[]){
    if(!budget())break outer;
    const [a,b]=noteLayout(note,world(s,note.at_um)).bounds;
    if(overlap(seg.box,bbox(a,b)))add('DRC_WIRE_SYMBOL_TEXT','warning',
     'Проводник '+netName(seg.wire.net_id)+' пересекает область надписи '+ref(s.component_id)+' ('+note.key+'). Проверьте читаемость.',
     [seg.wire.id,s.component_id,note.key],s.instance_id);
   }
   if(collision)add('DRC_WIRE_SYMBOL_INK','warning',
    'Проводник '+netName(seg.wire.net_id)+' пересекает графику УГО '+ref(s.component_id)+' вне подписанного вывода. Проверьте разводку.',[seg.wire.id,s.component_id],s.instance_id);
  }
 }
 // A large number of disconnected pins must never hide critical DRC errors.
 const items=[...buckets.error,...buckets.warning,...buckets.info].slice(0,maxItems);
 const omitted=counts.error+counts.warning+counts.info-items.length;
 if(incomplete||omitted>0)items.push({id:'diagnostics-limit',code:'CHECK_LIMIT',severity:'info',message:'Диагностика ограничена: '+omitted+' сообщений скрыто'+(incomplete?'; геометрическая проверка неполная.':'.')});
 return {items,counts,comparisons,incomplete,omitted};
}
