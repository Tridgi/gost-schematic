/** CHAT4 pointer-independent interaction state machine (one owner pointer).
 * Emits typed intentions; only #123 ManualWireEngine can mutate electrical topology.
 */
import {screen,world,hitTest,snap,point} from './precision.mjs';
import {captureSegmentDrag} from './wire-intents.mjs';
const same=(a,b)=>a[0]===b[0]&&a[1]===b[1];
/** Geometry is only for selecting a symbol, never for making an electrical connection. */
function symbolHit(scene,camera,p){
 const hits=[];
 const dist=(pt,a,b)=>{
  const dx=b.x-a.x,dy=b.y-a.y,len=dx*dx+dy*dy;
  const t=len?Math.max(0,Math.min(1,((pt.x-a.x)*dx+(pt.y-a.y)*dy)/len)):0;
  return Math.hypot(pt.x-(a.x+t*dx),pt.y-(a.y+t*dy));
 };
 for(const s of scene.symbols||[]){
  const transform=(at)=>{
   point(at);
   const x=s.mirror_x?-at[0]:at[0],y=at[1];
   const t=s.rotation_deg===0?[x,y]:s.rotation_deg===90?[-y,x]:
     s.rotation_deg===180?[-x,-y]:s.rotation_deg===270?[y,-x]:null;
   if(!t)throw Error('INVALID_ROTATION');
   return screen(point([s.origin_um[0]+t[0],s.origin_um[1]+t[1]]),camera);
  };
  let minimum=Infinity;
  for(const stroke of s.strokes||[]){
   minimum=Math.min(minimum,dist(p,transform(stroke.from_um),transform(stroke.to_um)));
  }
  if(minimum<=8)hits.push({kind:'symbol',instance_id:s.instance_id,
    component_id:s.component_id,distance_px:minimum});
 }
 hits.sort((a,b)=>a.distance_px-b.distance_px);
 if(!hits.length)return null;
 const sameDistance=hits.filter(a=>a.distance_px-hits[0].distance_px<=.75);
 return sameDistance.length===1?hits[0]:{kind:'ambiguous-symbol',candidates:sameDistance.map(a=>a.instance_id)};
}

function orthogonal(from,to){point(from);point(to);if(same(from,to))return [from];const corner=[to[0],from[1]];return [from,corner,to].filter((p,i,a)=>i===0||!same(p,a[i-1]))}
export function createCanvasController(initial){
 let context=initial,active=null,draft=null,hover=null,selected=null;
 const emit=i=>{if(typeof context.onIntent!=='function')throw Error('MISSING_COMMAND_DISPATCH');return context.onIntent(i)};
 const toWorld=p=>snap(world(p,context.camera),context.gridUm,context.snapEnabled);
 const owner=p=>!active||active.pointerId===p.pointerId;
 const getState=()=>({camera:{...context.camera},draft:draft?{...draft,bends_um:draft.bends_um.map(p=>[...p])}:null,drag:active?{kind:active.kind,pointerId:active.pointerId}:null,hover,selected});
 return {
  getState,
  setContext(next){
    if(next.tool!==undefined&&next.tool!==context.tool&&next.tool!=='wire')draft=null;
    context={...context,...next};
  },
  down(p){
   if(!owner(p)||active)return false;
   const exact=hitTest(context.scene,context.camera,p);
   const hit=context.tool==='select'&&!exact?symbolHit(context.scene,context.camera,p):exact;
   hover=hit;
   if(context.tool==='place'&&p.button===0){
    return emit({kind:'placeSymbol',at_um:toWorld(p),
      base_revision:context.wireSnapshot.revision})!==false;
   }
   if(context.tool==='junction'&&p.button===0){
    if(hit?.kind!=='ambiguous-segment'||hit.candidates.length<2){
      emit({kind:'rejectJunction',reason:'JUNCTION_SELECTION_REQUIRED'});
      return true;
    }
    return emit({kind:'createJunction',
      selected_segments:hit.candidates.map(c=>({wire_id:c.wire_id,segment_id:c.segment_id})),
      base_revision:context.wireSnapshot.revision})!==false;
   }
   if(context.tool==='wire'&&p.button===0){
    if(!draft){
     if(hit?.pin?.component_id&&hit.pin.physical_pin_number!==undefined){
      if(emit({kind:'beginWire',pin:hit.pin})===false)return false;
      draft={source:hit.pin,from_um:hit.at_um,bends_um:[],cursor_um:hit.at_um};
      return true;
     }
     return false;
    }
    if(hit?.pin){
     if(hit.pin.component_id===draft.source.component_id&&hit.pin.physical_pin_number===draft.source.physical_pin_number)return false;
     // If source/target are different declared Nets, the service must throw;
     // draft is deliberately retained when a transaction fails.
     // Host false is a rejected CAS/Net/route transaction. Keep the signed
     // source and authored bends: the user can choose another target or Escape.
     if(emit({kind:'commitWire',source:draft.source,target:{kind:'pin',pin:hit.pin},bend_points_um:draft.bends_um})===false)
      return false;
     draft=null;return true;
    }
    if(hit?.kind==='ambiguous-pin'||hit?.kind==='ambiguous-segment')return false;
    const at=toWorld(p),prev=draft.bends_um.at(-1)||draft.from_um;
    if(!same(at,prev))draft={...draft,bends_um:[...draft.bends_um,at],cursor_um:at};
    return true;
   }
   if((context.tool==='pan'||p.button===1)&&p.button!==2){
    active={kind:'pan',pointerId:p.pointerId,point:{x:p.x,y:p.y}};return true;
   }
   if(context.tool==='select'&&p.button===0&&hit?.kind==='segment'&&hit.movable){
    const token=captureSegmentDrag(context.wireSnapshot,hit.wire_id,hit.segment_id);
    active={kind:'segment',pointerId:p.pointerId,point:{x:p.x,y:p.y},token};
    emit({kind:'select',target:hit});return true;
   }
   if(context.tool==='select'&&p.button===0&&hit?.kind==='symbol'){
    selected=hit;
    active={kind:'symbol',pointerId:p.pointerId,point:{x:p.x,y:p.y},
      instanceId:hit.instance_id,componentId:hit.component_id,
      baseRevision:context.wireSnapshot.revision};
    emit({kind:'select',target:hit});return true;
   }
   if(context.tool==='select'&&p.button===0){
    selected=hit?.kind==='symbol'?hit:null;
    emit({kind:'select',target:hit});return true;
   }
   return false;
  },
  move(p){
   if(!owner(p))return false;
   if(active?.kind==='pan'){
    const dx=p.x-active.point.x,dy=p.y-active.point.y;
    const c=context.camera;
    context={...context,camera:{...c,x:c.x+dx,y:c.y+dy}};
    active.point={x:p.x,y:p.y};return true;
   }
   if(draft){draft={...draft,cursor_um:toWorld(p)};return true}
   hover=hitTest(context.scene,context.camera,p);return false;
  },
  up(p){
   if(!active||!owner(p))return false;
   const drag=active;
   if(drag.kind==='symbol'){
    const a=world(drag.point,context.camera),b=world(p,context.camera);
    const delta=point([b[0]-a[0],b[1]-a[1]]);
    const snapped=context.snapEnabled?
      point(delta.map(v=>Math.round(v/context.gridUm)*context.gridUm)):delta;
    if(snapped[0]||snapped[1])emit({kind:'moveInstance',component_id:drag.componentId,
      instance_id:drag.instanceId,delta_um:snapped,base_revision:drag.baseRevision});
   }
   if(drag.kind==='segment'){
    const a=world(drag.point,context.camera),b=world(p,context.camera);
    const axis=drag.token.axis;
    const delta=axis==='v'?b[0]-a[0]:b[1]-a[1];
    const n=context.snapEnabled?Math.round(delta/context.gridUm)*context.gridUm:delta;
    point([n,0]);
    if(n!==0)emit({kind:'moveSegment',token:drag.token,delta_um:n});
   }
   active=null;return true;
  },
  key(k){
   if((k==='r'||k==='R')&&selected?.kind==='symbol'){
    emit({kind:'rotateInstance',component_id:selected.component_id,
      instance_id:selected.instance_id,base_revision:context.wireSnapshot.revision});
    return true;
   }
   if(k==='Escape'){if(draft)emit({kind:'cancelWire',source:draft.source});draft=null;active=null;return true}
   if(k==='Enter'&&draft){
    const prev=draft.bends_um.at(-1)||draft.from_um;
    if(same(prev,draft.cursor_um))return false;
    if(emit({kind:'commitWire',source:draft.source,target:{kind:'free',at_um:draft.cursor_um},bend_points_um:draft.bends_um})===false)
      return false;
    draft=null;return true;
   }
   return false;
  },
  preview(){if(!draft)return [];const from=draft.bends_um.at(-1)||draft.from_um;return [draft.from_um,...draft.bends_um,...orthogonal(from,draft.cursor_um).slice(1)]}
 };
}
