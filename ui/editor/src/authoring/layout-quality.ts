import type {ProjectFileV2,PointUm} from '../model/contract';
import type {ManualWireEngine} from '../wires/manual-wire';
import {projectToCanvasScene} from '../canvas/scene-projection.mjs';
import {analyzeDiagnostics} from './diagnostics.mjs';
import {detectPaperOverflow} from '../canvas/paper-bounds.mjs';

export type LayoutQuality={
  bends:number;lengthUm:number;crossings:number;wireCount:number;straightWires:number;
  errors:number;geometryWarnings:number;overflow:number;complete:boolean;
};
export type LayoutAssessment={quality:LayoutQuality;hazards:Record<string,number>;connectivity:string;overflowIds:string[]};
const direction=(a:PointUm,b:PointUm)=>[Math.sign(b[0]-a[0]),Math.sign(b[1]-a[1])];
const pinKey=(p:{component_id:string;physical_pin_number:string})=>JSON.stringify([p.component_id,p.physical_pin_number]);
export function assessLayout(file:ProjectFileV2,engine:ManualWireEngine):LayoutAssessment{
 const sh=file.project.sheets.find(s=>s.id===file.workspace.active_sheet_id)!;
 const scene=projectToCanvasScene(file,sh.id),snapshot=engine.snapshot;
 let bends=0,lengthUm=0,straightWires=0;
 const segments:{id:string;net:string;a:PointUm;b:PointUm}[]=[];
 const spliceDirections=new Map<string,number[][]>();
 for(const w of sh.wires){
  let turns=0;
  for(let i=1;i<w.vertices.length;i++){
   const a=w.vertices[i-1].at_um,b=w.vertices[i].at_um;
   lengthUm+=Math.abs(b[0]-a[0])+Math.abs(b[1]-a[1]);
   segments.push({id:w.id,net:w.net_id,a,b});
   if(i>1){
    const p=direction(w.vertices[i-2].at_um,a),q=direction(a,b);
    if(p[0]!==q[0]||p[1]!==q[1])turns++;
   }
  }
  bends+=turns;if(turns===0)straightWires++;
  for(const [v,near] of [[w.vertices[0],w.vertices[1]],[w.vertices.at(-1)!,w.vertices.at(-2)!]]){
   if(v.anchor.kind!=='splice')continue;
   const arr=spliceDirections.get(v.anchor.splice_id)??[];
   arr.push(direction(v.at_um,near.at_um));spliceDirections.set(v.anchor.splice_id,arr);
  }
 }
 for(const dirs of spliceDirections.values())if(dirs.length===2&&(dirs[0][0]!==-dirs[1][0]||dirs[0][1]!==-dirs[1][1]))bends++;
 // Count strict interior perpendicular crossings, not endpoint contacts or
 // shared explicit nodes. A crossing never establishes electrical membership.
 const intersections=new Set<string>();
 let complete=segments.length<=512;
 if(complete)for(let i=0;i<segments.length;i++)for(let j=i+1;j<segments.length;j++){
  const a=segments[i],b=segments[j];
  const horizontal=a.a[1]===a.b[1],other=b.a[1]===b.b[1];
  if(horizontal===other)continue;
  const h=horizontal?a:b,v=horizontal?b:a,x=v.a[0],y=h.a[1];
  if(x>Math.min(h.a[0],h.b[0])&&x<Math.max(h.a[0],h.b[0])&&
     y>Math.min(v.a[1],v.b[1])&&y<Math.max(v.a[1],v.b[1]))
   intersections.add(JSON.stringify([...[a.net,b.net].sort(),x,y]));
 }
 const statuses:Record<string,string>={},groups:string[]=[];
 for(const n of snapshot.nets){
  const result=engine.validateNet(n.id);statuses[n.id]=result.status;
  groups.push(JSON.stringify([n.id,result.pin_groups.map(g=>JSON.stringify(g.map(pinKey).sort())).sort()]));
 }
 const report=analyzeDiagnostics(file,scene,snapshot,statuses,{maxItems:10000,maxComparisons:500000});
 complete=complete&&!report.incomplete&&report.omitted===0;
 const hazards:Record<string,number>={};let geometryWarnings=0;
 for(const d of report.items){
  if(d.severity!=='error'&&(!d.code.startsWith('DRC_')||d.code==='DRC_ROUTE_REVIEW'))continue;
  // Stable diagnostic messages include net names / reference designators;
  // preserve multiplicity rather than allowing one new fault to offset another.
  const k=JSON.stringify([d.code,d.message]);hazards[k]=(hazards[k]??0)+1;
  if(d.severity==='warning')geometryWarnings++;
 }
 const overflow=detectPaperOverflow(scene,snapshot,sh.frame.size_um);
 const overflowIds=[...overflow.symbols.map(x=>'symbol:'+x),...overflow.wires.map(x=>'wire:'+x),
  ...overflow.graphics.map(x=>'graphic:'+x),...overflow.junctions.map(x=>'junction:'+x),...overflow.splices.map(x=>'splice:'+x)].sort();
 return {quality:{bends,lengthUm,crossings:intersections.size,wireCount:sh.wires.length,straightWires,
  errors:report.counts.error,geometryWarnings,overflow:overflow.total,complete},
  hazards,connectivity:JSON.stringify(groups.sort()),overflowIds};
}
/** Common safety gate for automatic and explicitly requested geometry edits. */
export function preservesLayoutSafety(a:LayoutAssessment,b:LayoutAssessment):boolean{
 return a.quality.complete&&b.quality.complete&&a.connectivity===b.connectivity&&
  !b.overflowIds.some(id=>!a.overflowIds.includes(id))&&
  !Object.keys(b.hazards).some(k=>b.hazards[k]>(a.hazards[k]??0))&&
  b.quality.crossings<=a.quality.crossings;
}
/** Strict Pareto improvement: no extra length, turns or ordinary crossings.
 * Explicit review warnings are intentionally excluded from geometry hazards. */
export function improvesLayout(a:LayoutAssessment,b:LayoutAssessment):boolean{
 const x=a.quality,y=b.quality;
 if(!preservesLayoutSafety(a,b))return false;
 return y.bends<=x.bends&&y.lengthUm<=x.lengthUm&&
  (y.bends<x.bends||y.lengthUm<x.lengthUm||y.crossings<x.crossings||y.geometryWarnings<x.geometryWarnings||y.errors<x.errors);
}
