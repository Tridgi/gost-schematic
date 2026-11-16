/** CHAT4 pointer-independent interaction state machine (one owner pointer).
 * Emits typed intentions; only #123 ManualWireEngine can mutate electrical topology.
 */
import {screen,world,hitTest,snap,point} from './precision.mjs';
import {captureSegmentDrag} from './wire-intents.mjs';
const same=(a,b)=>a[0]===b[0]&&a[1]===b[1];
function orthogonal(from,to){point(from);point(to);if(same(from,to))return [from];const corner=[to[0],from[1]];return [from,corner,to].filter((p,i,a)=>i===0||!same(p,a[i-1]))}
export function createCanvasController(initial){
 let context=initial,active=null,draft=null,hover=null;
 const emit=i=>{if(typeof context.onIntent!=='function')throw Error('MISSING_COMMAND_DISPATCH');return context.onIntent(i)};
 const toWorld=p=>snap(world(p,context.camera),context.gridUm,context.snapEnabled);
 const owner=p=>!active||active.pointerId===p.pointerId;
 const getState=()=>({camera:{...context.camera},draft:draft?{...draft,bends_um:draft.bends_um.map(p=>[...p])}:null,drag:active?{kind:active.kind,pointerId:active.pointerId}:null,hover});
 return {
  getState,
  setContext(next){context={...context,...next}},
  down(p){
   if(!owner(p)||active)return false;
   const hit=hitTest(context.scene,context.camera,p);
   hover=hit;
   if(context.tool==='wire'&&p.button===0){
    if(!draft){
     if(hit?.pin?.component_id&&hit.pin.physical_pin_number!==undefined){
      emit({kind:'beginWire',pin:hit.pin});draft={source:hit.pin,from_um:hit.at_um,bends_um:[],cursor_um:hit.at_um};
      return true;
     }
     return false;
    }
    if(hit?.pin){
     if(hit.pin.component_id===draft.source.component_id&&hit.pin.physical_pin_number===draft.source.physical_pin_number)return false;
     // If source/target are different declared Nets, the service must throw;
     // draft is deliberately retained when a transaction fails.
     emit({kind:'commitWire',source:draft.source,target:{kind:'pin',pin:hit.pin},bend_points_um:draft.bends_um});
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
   if(context.tool==='select'&&p.button===0){emit({kind:'select',target:hit});return true}
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
   if(k==='Escape'){if(draft)emit({kind:'cancelWire',source:draft.source});draft=null;active=null;return true}
   if(k==='Enter'&&draft){
    const prev=draft.bends_um.at(-1)||draft.from_um;
    if(same(prev,draft.cursor_um))return false;
    emit({kind:'commitWire',source:draft.source,target:{kind:'free',at_um:draft.cursor_um},bend_points_um:draft.bends_um});
    draft=null;return true;
   }
   return false;
  },
  preview(){if(!draft)return [];const from=draft.bends_um.at(-1)||draft.from_um;return [draft.from_um,...draft.bends_um,...orthogonal(from,draft.cursor_um).slice(1)]}
 };
}
