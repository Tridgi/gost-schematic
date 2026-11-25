/** Derived upright, non-electrical component labels shared by canvas and SVG.
 * Conservative font envelopes, not measured GOST glyph metrics.
 * Never invent values, modify the document or hide a failed placement. */
import type {ProjectFileV2,PointUm} from '../model/contract';
import type {CanvasScene,CanvasSymbol} from './scene-projection.d.mts';
import {projectToCanvasScene} from './scene-projection.mjs';
import {noteLayout} from '../model/symbol-notes.mjs';
import {pinWorld} from './precision.mjs';

type Box={x0:number;y0:number;x1:number;y1:number};
export type ComponentLabel={instanceId:string;componentId:string;refdes:string;value:string;
  x:number;y:number;heightUm:number;lineStepUm:number;bounds:Box};
export type ComponentLabelPlan={labels:ComponentLabel[];unplaced:{instanceId:string;refdes:string;reason:string}[]};
const H=2500,STEP=3500,PAD=500;
const box=(a:PointUm,b:PointUm,p=0):Box=>({x0:Math.floor(Math.min(a[0],b[0])-p),y0:Math.floor(Math.min(a[1],b[1])-p),x1:Math.ceil(Math.max(a[0],b[0])+p),y1:Math.ceil(Math.max(a[1],b[1])+p)});
const union=(a:Box,b:Box):Box=>({x0:Math.min(a.x0,b.x0),y0:Math.min(a.y0,b.y0),x1:Math.max(a.x1,b.x1),y1:Math.max(a.y1,b.y1)});
const hits=(a:Box,b:Box)=>a.x0<=b.x1&&a.x1>=b.x0&&a.y0<=b.y1&&a.y1>=b.y0;
function world(s:CanvasSymbol,p:PointUm):[number,number]{
 const x=s.mirror_x?-p[0]:p[0],y=p[1];
 const [a,b]=s.rotation_deg===0?[x,y]:s.rotation_deg===90?[-y,x]:s.rotation_deg===180?[-x,-y]:[y,-x];
 return [a+s.origin_um[0],b+s.origin_um[1]];
}
function symbolBox(s:CanvasSymbol):Box{
 let b=box(s.origin_um,s.origin_um);
 const add=(p:PointUm,q:PointUm,pad=0)=>{b=union(b,box(p,q,pad))};
 for(const pin of s.pins){const p=pinWorld(s,pin.physical_pin_number).at_um;add(p,p)}
 for(const k of s.inkStrokes)add(world(s,k.from_um),world(s,k.to_um),k.stroke_um/2);
 for(const c of s.curves)for(const p of c.bounds){const q=world(s,p);add(q,q,c.stroke_um/2)}
 for(const n of s.notes){const [a,z]=noteLayout(n,world(s,n.at_um)).bounds;add(a,z)}
 return b;
}
export function planComponentLabels(file:ProjectFileV2,sheetId:string,scene:CanvasScene=projectToCanvasScene(file,sheetId)):ComponentLabelPlan{
 const sh=file.project.sheets.find(s=>s.id===sheetId);
 if(!sh)throw Error('UNKNOWN_SHEET');
 // Same conservative arrangement for visible and hidden layer objects:
 // a temporary visibility change must not shift the printed label.
 const components=new Map(file.project.components.map(c=>[c.id,c]));
 const labels:ComponentLabel[]=[],unplaced:ComponentLabelPlan['unplaced']=[];
 const visible=new Set(sh.layers.filter(l=>l.visible&&l.printable&&l.kind!=='diagnostics').map(l=>l.id));
 const symbols=scene.symbols.filter(s=>visible.has(s.layer_id));
 if(symbols.length>128||scene.wires.reduce((n,w)=>n+w.segments.length,0)>512||scene.graphics.reduce((n,g)=>n+g.strokes.length,0)>512||
   scene.junctions.length+scene.splices.length>512||sh.texts.length+sh.labels.length>128){
  return {labels,unplaced:symbols.map(s=>({instanceId:s.instance_id,refdes:components.get(s.component_id)?.refdes??s.component_id,reason:'LABEL_SIZE_LIMIT'}))};
 }
 const bounds=new Map(scene.symbols.map(s=>[s.instance_id,symbolBox(s)]));
 const obstacles:Box[]=[...bounds.values()];
 for(const w of scene.wires)for(let k=1;k<w.vertices.length;k++)obstacles.push(box(w.vertices[k-1].at_um,w.vertices[k].at_um,150));
 for(const g of scene.graphics)for(const s of g.strokes)obstacles.push(box(s.from_um,s.to_um,(s.stroke_um??0)/2));
 for(const n of scene.junctions)obstacles.push(box(n.at_um,n.at_um,550));
 for(const n of scene.splices)obstacles.push(box(n.at_um,n.at_um));
 // Existing sheet annotations reserve conservative envelopes.
 for(const n of [...sh.texts,...sh.labels]){
  if(!n.text)continue;
  const h='height_um' in n?n.height_um:3500;
  const [a,b]=noteLayout({key:n.id,text:n.text,at_um:n.at_um,height_um:h,horizontal:'left',vertical:'bottom'},n.at_um).bounds;
  obstacles.push(box(a,b));
 }
 const m=sh.frame.margin_um,[w,h]=sh.frame.size_um;
 const inside=(b:Box)=>b.x0>=m&&b.y0>=m&&b.x1<=w-m&&b.y1<=h-m;
 for(const s of symbols){
  const c=components.get(s.component_id)!;
  const fail=(reason:string)=>unplaced.push({instanceId:s.instance_id,refdes:c.refdes,reason});
  const text=[c.refdes,c.value].filter(v=>v.length>0);
  if(!c.refdes||text.some(v=>Array.from(v).length>64||/[\u0000-\u001f\u007f]/.test(v))){fail('LABEL_TEXT_UNSUPPORTED');continue}
  // Monospace preview with deliberately overestimated width, plus padding.
  const width=(Math.max(...text.map(v=>Array.from(v).length))+1)*H;
  const height=3*H+(text.length-1)*STEP;
  const b=bounds.get(s.instance_id)!;
  const cx=Math.round((b.x0+b.x1)/2),cy=Math.round((b.y0+b.y1)/2);
  let found:ComponentLabel|undefined;
  for(const gap of [1000,2500,5000,8000]){
   const candidates:[number,number][]=[
    [cx,b.y0-gap-height/2],[cx,b.y1+gap+height/2],
    [b.x1+gap+width/2,cy],[b.x0-gap-width/2,cy],
    [b.x0+width/2,b.y0-gap-height/2],[b.x1-width/2,b.y0-gap-height/2],
    [b.x0+width/2,b.y1+gap+height/2],[b.x1-width/2,b.y1+gap+height/2]
   ];
   for(const [x,y] of candidates){
    const left=Math.floor(x-width/2),top=Math.floor(y-height/2),right=left+width,bottom=top+height;
    const envelope={x0:left-PAD,y0:top-PAD,x1:right+PAD,y1:bottom+PAD};
    if(!inside(envelope)||obstacles.some(o=>hits(o,envelope)))continue;
    found={instanceId:s.instance_id,componentId:s.component_id,refdes:c.refdes,value:c.value,x:Math.round(x),y:top+2*H,heightUm:H,lineStepUm:STEP,bounds:envelope};break;
   }
   if(found)break;
  }
  if(found){labels.push(found);obstacles.push(found.bounds)}
  else fail('LABEL_NO_SAFE_POSITION');
 }
 return {labels,unplaced};
}
