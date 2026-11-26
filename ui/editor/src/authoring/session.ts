/** R3 user-authored ProjectV2 transaction boundary.
 *
 * ProjectFileV2 remains the canonical document. ManualWireEngine is the sole
 * validator/mutator of physical route geometry; a full immutable project
 * snapshot is atomically committed with every edit. No visual crossing makes
 * a Net. The revision CAS is monotonic even across Undo/Redo.
 *
 * The in-browser source_guard is the *exact source-inventory serialization*,
 * NOT a SHA-256. The independent Python #122 validator computes canonical
 * SHA-256 when a document crosses the Python IPC boundary.
 */
import type {
  ProjectFileV2, Sheet, PointUm, PinRef, SymbolInstance,
  Component, SymbolDefinition, Net, WireEndpoint, WirePolyline, Junction, Splice
} from '../model/contract';
import {
  ManualWireEngine, WireError, constructWire, routeManhattan, type WiringSnapshot,
  type PointUm as MutablePoint, type PinRef as MutablePin
} from '../wires/manual-wire';
import {loadProjectWires} from '../wires/project-v2-adapter';
import {validateNotes,noteLayout} from '../model/symbol-notes.mjs';
import {planOrthogonalTree,type TreeStrategy} from './orthogonal-tree';
import {assessLayout,improvesLayout,preservesLayoutSafety,type LayoutQuality} from './layout-quality';
import {curveGeometry} from '../model/curves.mjs';
import {planComponentLabels} from '../canvas/component-labels';
import {projectToCanvasScene} from '../canvas/scene-projection.mjs';
import {AUTHORING_PARTS, AUTHORING_SYMBOLS,catalogDefaultValue,catalogAdditions} from './catalog';

export type ComponentClipboard = Readonly<{
  symbol_id:string; value:string; rotation_deg:SymbolInstance['rotation_deg']; mirror_x:boolean;
  origin_um:readonly [number,number];
}>;

/** Detached per-project group template. Original IDs are local mapping keys only. */
export type GroupClipboard = {
  anchor:PointUm;
  components:{key:string;template:ComponentClipboard}[];
  nets:Net[]; wires:WirePolyline[]; junctions:Junction[]; splices:Splice[];
  omittedNetCount:number;
};

export type PlacementHint={origin:MutablePoint;from:MutablePoint;to:MutablePoint;target:PinRef;newPin:string};
export type LayoutPreview={token:string|null;before:LayoutQuality;after:LayoutQuality;operations:string[];attempted:number;rejected:number;limited:boolean};
export type FunctionalRoutingPreview={token:string|null;requested:number;routed:number;variant:'hub'|'functional';moved:string[];baseline:LayoutQuality;quality:LayoutQuality;attempted:number;outcomes:InitialBatchOutcome[]};
export type HubPlacementPreview={token:string|null;moved:string[];beforeSpanUm:number;afterSpanUm:number;attempted:number};
export type InitialBatchOutcome={id:string;name:string;pins:number;rejected?:string};
export type InitialBatchPreview={token:string|null;requested:number;routed:number;attempted:number;order:string;outcomes:InitialBatchOutcome[];quality:LayoutQuality};
type Tx = {project_id:string;revision:number;source_guard:string;command_id:string};
const SOURCE_ZERO='0000000000000000000000000000000000000000';
const clone=<T>(v:T):T=>structuredClone(v);
function reject(code:string):never {throw new WireError(code,code);}
function checkId(value:unknown,code='INVALID_ID'):asserts value is string {
  if(typeof value!=='string'||!value.trim()||value.length>256)reject(code);
}
function xy(value:readonly number[]):MutablePoint {
  if(!Array.isArray(value)||value.length!==2||
    !value.every(n=>Number.isSafeInteger(n)&&Math.abs(n)<=1_000_000_000))
    reject('COORDINATE_RANGE');
  return [value[0],value[1]];
}
function unique(items:readonly {id:string}[],code:string):void {
  const ids=new Set<string>();
  for(const item of items) {checkId(item?.id,code);if(ids.has(item.id))reject(code);ids.add(item.id);}
}
function pinKey(pin:PinRef):string{return JSON.stringify([pin.component_id,pin.physical_pin_number]);}
function newId(prefix:string):string{return prefix+'-'+globalThis.crypto.randomUUID();}
function indexOfSheet(file:ProjectFileV2):number {
  const i=file.project.sheets.findIndex(s=>s.id===file.workspace.active_sheet_id);
  if(i<0)reject('UNKNOWN_SHEET');return i;
}
function sourceGuard(file:ProjectFileV2):string {
  const p=file.project;
  return JSON.stringify({project_id:p.id,provenance:p.provenance.source_sha,
    parts:p.part_definitions,symbols:p.symbol_definitions,
    components:p.components.map(c=>[c.id,c.source_refdes,c.part_id]),
    nets:p.nets.map(n=>[n.id,n.name,n.members])});
}
function nextRefdes(file:ProjectFileV2,prefix:string):string {
  const used=new Set(file.project.components.flatMap(c=>[c.refdes,c.source_refdes]));
  let n=1;while(used.has(prefix+n))n++;
  return prefix+n;
}
type Bounds={minX:number;minY:number;maxX:number;maxY:number};
function symbolBounds(symbol:SymbolDefinition,rotation:SymbolInstance['rotation_deg'],mirror:boolean):Bounds {
  const bounds:Bounds={minX:0,minY:0,maxX:0,maxY:0};
  const include=(at:readonly number[],pad=0)=>{
    const x=mirror?-at[0]:at[0],y=at[1];
    const [u,v]=rotation===0?[x,y]:rotation===90?[-y,x]:rotation===180?[-x,-y]:[y,-x];
    bounds.minX=Math.min(bounds.minX,u-pad);bounds.minY=Math.min(bounds.minY,v-pad);
    bounds.maxX=Math.max(bounds.maxX,u+pad);bounds.maxY=Math.max(bounds.maxY,v+pad);
  };
  for(const pin of symbol.pins)include(pin.at_um);
  for(const g of symbol.graphics){
    const points=g.kind==='circle'||g.kind==='semicircle'?curveGeometry(g.kind,g.points_um).bounds:g.points_um;
    for(const p of points)include(p,g.stroke_um/2);
  }
  for(const n of validateNotes(symbol.constant_annotations)){
    const x=mirror?-n.at_um[0]:n.at_um[0],y=n.at_um[1];
    const at:PointUm=rotation===0?[x,y]:rotation===90?[-y,x]:rotation===180?[-x,-y]:[y,-x];
    for(const p of noteLayout(n,at).bounds){
      bounds.minX=Math.min(bounds.minX,p[0]);bounds.maxX=Math.max(bounds.maxX,p[0]);
      bounds.minY=Math.min(bounds.minY,p[1]);bounds.maxY=Math.max(bounds.maxY,p[1]);
    }
  }
  return bounds;
}
function translateBounds(b:Bounds,p:readonly number[]):Bounds {
  return {minX:b.minX+p[0],minY:b.minY+p[1],maxX:b.maxX+p[0],maxY:b.maxY+p[1]};
}
function separated(a:Bounds,b:Bounds,clearance:number):boolean {
  return a.maxX+clearance<=b.minX||b.maxX+clearance<=a.minX||
    a.maxY+clearance<=b.minY||b.maxY+clearance<=a.minY;
}
/** Sheet-aware bounded orthogonal route. Keep other symbols/wires clear;
 * endpoint symbol boxes may only be traversed by their own outward lead.
 * Ordinary interior X crossings are a fallback, never implicit connections. */
function cleanRoute(file:ProjectFileV2,start:PinRef,end:PinRef,a:WorldPin,b:WorldPin,netId:string,ignoreWire?:string,allowInteriorCrossings=true):MutablePoint[]{
 const sheet=file.project.sheets[indexOfSheet(file)],margin=sheet.frame.margin_um;
 const defs=new Map(file.project.symbol_definitions.map(d=>[d.id,d]));
 const obstacles=sheet.instances.map(i=>{
   const def=defs.get(i.symbol_id);if(!def)reject('UNKNOWN_SYMBOL');
   const box=translateBounds(symbolBounds(def,i.rotation_deg,i.mirror_x),i.origin_um);
   return {id:i.component_id,box};
 });
 const clearance=1000;
 const rect=(p:readonly number[],q:readonly number[]):Bounds=>({minX:Math.min(p[0],q[0]),minY:Math.min(p[1],q[1]),maxX:Math.max(p[0],q[0]),maxY:Math.max(p[1],q[1])});
 const hit=(p:Bounds,q:Bounds)=>p.minX<=q.maxX&&q.minX<=p.maxX&&p.minY<=q.maxY&&q.minY<=p.maxY;
 const eq=(p:readonly number[],q:readonly number[])=>p[0]===q[0]&&p[1]===q[1];
 const channelsX:number[]=[],channelsY:number[]=[];
 const channel=(box:Bounds)=>{
   channelsX.push(Math.floor(box.minX)-clearance,Math.ceil(box.maxX)+clearance);
   channelsY.push(Math.floor(box.minY)-clearance,Math.ceil(box.maxY)+clearance);
 };
 obstacles.forEach(o=>channel(o.box));
 const wires=sheet.wires.filter(w=>w.id!==ignoreWire).flatMap(w=>w.vertices.slice(1).map((v,i)=>({w,a:w.vertices[i],b:v,box:rect(w.vertices[i].at_um,v.at_um)})));
 wires.forEach(w=>channel(w.box));
 const nodePoints=[...sheet.junctions,...sheet.splices].map(n=>n.at_um);
 const isShared=(p:readonly number[],w:typeof wires[number])=>w.w.net_id===netId&&
   [w.a,w.b].some(v=>eq(v.at_um,p)&&v.anchor.kind==='pin'&&
    ((eq(p,a.at_um)&&pinKey(v.anchor)===pinKey(start))||(eq(p,b.at_um)&&pinKey(v.anchor)===pinKey(end))));
 const accept=(path:MutablePoint[],allowCrossing:boolean)=>{
   if(path.some(p=>p[0]<margin||p[1]<margin||p[0]>sheet.frame.size_um[0]-margin||p[1]>sheet.frame.size_um[1]-margin))return false;
   for(let i=1;i<path.length;i++){
     const p=path[i-1],q=path[i],box=rect(p,q);
     for(const o of obstacles){
       if((i===1&&o.id===start.component_id)||(i===path.length-1&&o.id===end.component_id))continue;
       if(!separated(box,o.box,clearance))return false;
     }
     if(nodePoints.some(n=>hit(box,rect(n,n))))return false;
     for(const w of wires){
       if(!hit(box,w.box))continue;
       const overlap= {minX:Math.max(box.minX,w.box.minX),maxX:Math.min(box.maxX,w.box.maxX),minY:Math.max(box.minY,w.box.minY),maxY:Math.min(box.maxY,w.box.maxY)};
       if(overlap.minX!==overlap.maxX||overlap.minY!==overlap.maxY)return false;
       const at=[overlap.minX,overlap.minY];
       if((eq(at,p)||eq(at,q))&&isShared(at,w))continue;
       const cross=(p[0]===q[0])!==(w.a.at_um[0]===w.b.at_um[0]);
       if(!allowCrossing||!cross||eq(at,p)||eq(at,q)||eq(at,w.a.at_um)||eq(at,w.b.at_um))return false;
     }
   }
   return true;
 };
 const opts={channelsX,channelsY};
 try{return routeManhattan(xy(a.at_um),xy(b.at_um),xy(a.normal),xy(b.normal),2000,{...opts,accept:p=>accept(p,false)});}
 catch(e){if(!allowInteriorCrossings||!(e instanceof WireError)||e.code!=='REROUTE_REQUIRED')throw e;}
 return routeManhattan(xy(a.at_um),xy(b.at_um),xy(a.normal),xy(b.normal),2000,{...opts,accept:p=>accept(p,true)});
}
// Match the canonical Python inventory for every provenance status.
function actualCounts(file:ProjectFileV2):ProjectFileV2['project']['provenance']['expected_counts']{
  const p=file.project,parts=new Map(p.part_definitions.map(part=>[part.id,part]));
  return {
    components:p.components.length,nets:p.nets.length,
    memberships:p.nets.reduce((count,n)=>count+n.members.length,0),
    da1_pins:p.components.reduce((count,c)=>count+(c.source_refdes==='DA1'?(parts.get(c.part_id)?.physical_pins.length??0):0),0),
    b_graphics:p.sheets.reduce((count,sh)=>count+sh.graphics.filter(g=>g.kind==='source_b_continuation').length,0)
  };
}
function expectedCounts(file:ProjectFileV2):void {
  file.project.provenance.expected_counts=actualCounts(file);
}
function frameSheet(id:string,index:number,title:string):Sheet {
  return {id,name:title,index,frame:{size_um:[420000,297000],margin_um:10000,paper:'A3 landscape'},
    title_block:{designation:'GSCAD-USER',title,organization:'',revision:'DRAFT',sheet_number:index},
    layers:[{id:index===1?'layer-electric':'layer-electric-'+id,
      name:'Electrical',kind:'electrical',visible:true,printable:true,locked:false}],
    instances:[],wires:[],junctions:[],splices:[],texts:[],labels:[],graphics:[]};
}
export function newBlankProject():ProjectFileV2 {
  const id=newId('project'),sid='sheet-1',title='Новая электрическая схема';
  return {format:'gscad-project',format_version:2,project:{
    id,title,part_definitions:clone(AUTHORING_PARTS),symbol_definitions:clone(AUTHORING_SYMBOLS),
    components:[],nets:[],sheets:[frameSheet(sid,1,title)],
    settings:{units:'um',grid_visible:true,snap_enabled:true,grid_step_um:1000,orthogonal_wires:true},
    provenance:{source_sha:SOURCE_ZERO,source_path:'user-created/'+id,
      status:'synthetic',expected_counts:{components:0,nets:0,memberships:0,da1_pins:0,b_graphics:0}}
  },workspace:{active_sheet_id:sid,camera_center_um:[210000,148500],
    zoom_milli:1000,selected_ids:[],panels_px:{left:280,right:320,bottom:160}}};
}
function scope(file:ProjectFileV2):ProjectFileV2 {
  const focused=clone(file),sheet=focused.project.sheets[indexOfSheet(focused)];
  const present=new Set(sheet.instances.map(i=>i.component_id));
  focused.project.sheets=[sheet];
  focused.project.nets=focused.project.nets.flatMap(n=>{
    const members=n.members.filter(p=>present.has(p.component_id));
    return members.length?[{...n,members}]:[];
  });
  expectedCounts(focused);
  return focused;
}
function validateAuthoring(file:ProjectFileV2):void {
  if(file?.format!=='gscad-project'||file.format_version!==2)reject('SCHEMA_VERSION');
  const p=file.project;
  if(p?.provenance?.status!=='synthetic'||p.provenance.source_sha!==SOURCE_ZERO)
    reject('SOURCE_SHA_MISMATCH');
  checkId(p.id,'INVALID_PROJECT_ID');
  if(!Array.isArray(p.components)||!Array.isArray(p.nets)||!Array.isArray(p.sheets)||
     !p.sheets.length||!Array.isArray(p.symbol_definitions)||!Array.isArray(p.part_definitions))
    reject('INVALID_PROJECT');
  unique(p.components,'DUPLICATE_COMPONENT');
  unique(p.part_definitions,'DUPLICATE_PART');
  unique(p.symbol_definitions,'DUPLICATE_SYMBOL');
  unique(p.nets,'DUPLICATE_NET');
  unique(p.sheets,'DUPLICATE_SHEET');
  // Validate every catalogue part, including definitions not yet placed.
  // Otherwise a malicious imported ProjectV2 can hide duplicate PinRefs
  // until that part is inserted into a real electrical sheet.
  for(const part of p.part_definitions){
    if(!Array.isArray(part.physical_pins))reject('INVALID_PHYSICAL_PINS');
    const numbers=new Set<string>();
    for(const pin of part.physical_pins){
      checkId(pin?.number,'INVALID_PHYSICAL_PIN');
      if(numbers.has(pin.number))reject('DUPLICATE_PHYSICAL_PIN');
      numbers.add(pin.number);
    }
  }
  const parts=new Map(p.part_definitions.map(v=>[v.id,v]));
  const symbols=new Map(p.symbol_definitions.map(v=>[v.id,v]));
  // An unused symbol definition is still persisted and can later become
  // placeable; enforce exact physical pin identities at import time.
  for(const symbol of p.symbol_definitions){
    const part=parts.get(symbol.part_id);
    if(!part)reject('UNKNOWN_PART');
    if(!Array.isArray(symbol.pins))reject('INVALID_SYMBOL_PINS');
    const numbers=new Set<string>();
    validateNotes(symbol.constant_annotations);
    for(const g of symbol.graphics)if(g.kind==='circle'||g.kind==='semicircle')curveGeometry(g.kind,g.points_um);
    for(const pin of symbol.pins){
      checkId(pin?.physical_pin_number,'INVALID_PINREF');
      if(numbers.has(pin.physical_pin_number))reject('DUPLICATE_SYMBOL_PIN');
      numbers.add(pin.physical_pin_number);
      if(!part.physical_pins.some(p=>p.number===pin.physical_pin_number))
        reject('UNKNOWN_PIN');
      xy(pin.at_um);
    }
  }
  const comps=new Map(p.components.map(v=>[v.id,v]));
  const refdes=new Set<string>();
  for(const comp of p.components){
    checkId(comp.refdes,'INVALID_REFDES');
    if(!/^[A-Za-z][A-Za-z0-9_-]{0,31}$/.test(comp.refdes))reject('INVALID_REFDES');
    if(refdes.has(comp.refdes))reject('DUPLICATE_REFDES');refdes.add(comp.refdes);
    if(!parts.has(comp.part_id))reject('UNKNOWN_PART');
  }
  const owned=new Set<string>(),netNames=new Set<string>();
  for(const net of p.nets) {
    checkId(net.name,'INVALID_NET_NAME');
    if(netNames.has(net.name))reject('DUPLICATE_NET_NAME');
    netNames.add(net.name);
    if(!net.members.length)reject('INVALID_NET');
    for(const member of net.members){
      checkId(member.component_id,'INVALID_PINREF');
      checkId(member.physical_pin_number,'INVALID_PINREF');
      const comp=comps.get(member.component_id),part=comp&&parts.get(comp.part_id);
      if(!part?.physical_pins.some(pin=>pin.number===member.physical_pin_number))
        reject('UNKNOWN_PIN');
      const key=pinKey(member);
      if(owned.has(key))reject('DUPLICATE_PIN_OWNERSHIP');owned.add(key);
    }
  }
  const instances=new Set<string>(),placed=new Set<string>(),layers=new Set<string>();
  for(const sh of p.sheets){
    for(const layer of sh.layers){
      checkId(layer.id,'INVALID_LAYER');
      if(layers.has(layer.id))reject('DUPLICATE_LAYER');
      layers.add(layer.id);
    }
    if(!Array.isArray(sh.instances)||!Array.isArray(sh.wires)||!Array.isArray(sh.graphics))
      reject('INVALID_SHEET');
    unique(sh.instances,'DUPLICATE_INSTANCE');
    for(const inst of sh.instances){
      if(instances.has(inst.id)||placed.has(inst.component_id))
        reject('DUPLICATE_INSTANCE');
      instances.add(inst.id);placed.add(inst.component_id);
      const c=comps.get(inst.component_id),sym=symbols.get(inst.symbol_id);
      if(!c||!sym||sym.part_id!==c.part_id)reject('PART_SYMBOL_MISMATCH');
      if(!sh.layers.some(l=>l.id===inst.layer_id))reject('UNKNOWN_LAYER');
      xy(inst.origin_um);
      if(![0,90,180,270].includes(inst.rotation_deg))reject('INVALID_ROTATION');
      const physical=new Set(parts.get(c.part_id)!.physical_pins.map(pin=>pin.number));
      const declared=new Set<string>();
      for(const pin of sym.pins){
        checkId(pin.physical_pin_number,'INVALID_PINREF');
        if(!physical.has(pin.physical_pin_number))reject('UNKNOWN_PIN');
        if(declared.has(pin.physical_pin_number))reject('DUPLICATE_PIN');
        declared.add(pin.physical_pin_number);xy(pin.at_um);
      }
    }
    projectToCanvasScene(file,sh.id);
  }
  if(placed.size!==p.components.length)reject('UNPLACED_COMPONENT');
  const actual=actualCounts(file);
  // Rust serde_json and Python canonicalization reorder JSON object keys when
  // reopening a native file. Counts are a named mapping, not an ordered tuple.
  // Comparing JSON.stringify falsely rejected valid persisted synthetic projects.
  const counts=p.provenance.expected_counts;
  if(!counts||typeof counts!=='object'||Array.isArray(counts)||
     Object.keys(counts).length!==Object.keys(actual).length||
     Object.entries(actual).some(([key,value])=>counts[key as keyof typeof actual]!==value))
    reject('SOURCE_COUNT_MISMATCH');
  indexOfSheet(file);
}
function localSession(file:ProjectFileV2,revision:number){
  const subset=scope(file);
  const sheet=subset.project.sheets[0];
  const session=loadProjectWires(subset,{sheet_id:sheet.id,revision,
    source_topology_hash:sourceGuard(file)});
  return {subset,session};
}
function materialize(file:ProjectFileV2,subset:ProjectFileV2,
  session:ReturnType<typeof loadProjectWires<ProjectFileV2>>):ProjectFileV2 {
  const local=session.materialize(subset),source=local.project.sheets[0];
  const sh=file.project.sheets[indexOfSheet(file)];
  sh.instances=clone(source.instances);
  sh.wires=clone(source.wires);
  sh.junctions=clone(source.junctions);
  sh.splices=clone(source.splices);
  for(const n of file.project.nets){
    const sn=local.project.nets.find(x=>x.id===n.id);
    if(sn&&sn.members.length===n.members.length)n.route_status=sn.route_status;
    else if(sn)n.route_status='partial';
  }
  return file;
}
type WorldPin={at_um:MutablePoint;normal:MutablePoint;net_id:string|null};
function addRouteBends(start:WorldPin,end:WorldPin,bends:readonly PointUm[]):MutablePoint[]{
  const points:MutablePoint[]=[start.at_um];
  const append=(to:MutablePoint)=>{
    const old=points[points.length-1];
    if(old[0]!==to[0]&&old[1]!==to[1]){
      const corner:MutablePoint=[to[0],old[1]];
      if(corner[0]!==old[0]||corner[1]!==old[1])points.push(corner);
    }
    const last=points[points.length-1];
    if(last[0]!==to[0]||last[1]!==to[1])points.push(to);
  };
  append([start.at_um[0]+start.normal[0]*3000,start.at_um[1]+start.normal[1]*3000]);
  for(const b of bends)append(xy(b));
  append([end.at_um[0]+end.normal[0]*3000,end.at_um[1]+end.normal[1]*3000]);
  append(end.at_um);
  return points;
}
export class AuthoringSession {
  private current:ProjectFileV2;
  private layoutPlan:{token:string;revision:number;sheet:string;next:ProjectFileV2}|null=null;
  private clock=0;
  private undoFiles:ProjectFileV2[]=[];
  private redoFiles:ProjectFileV2[]=[];
  engine:ManualWireEngine;
  constructor(document:ProjectFileV2){
    validateAuthoring(document);
    this.current=clone(document);
    this.engine=localSession(this.current,this.clock).session.engine;
  }
  get file():ProjectFileV2{return clone(this.current);}
  get snapshot():WiringSnapshot{return this.engine.snapshot;}
  get revision():number{return this.clock;}
  get canUndo():boolean{return this.undoFiles.length>0;}
  get canRedo():boolean{return this.redoFiles.length>0;}
  newTransaction(command_id:string):Tx{
    checkId(command_id,'INVALID_COMMAND');
    return {command_id,project_id:this.current.project.id,revision:this.clock,
      source_guard:sourceGuard(this.current)};
  }
  private edit(tx:Tx,change:(draft:ProjectFileV2)=>ProjectFileV2):void {
    if(tx.revision!==this.clock)reject('STALE_REVISION');
    if(tx.project_id!==this.current.project.id||tx.source_guard!==sourceGuard(this.current))
      reject('SOURCE_MISMATCH');
    const next=change(clone(this.current));
    validateAuthoring(next);
    const engine=localSession(next,this.clock+1).session.engine;
    this.undoFiles.push(this.current);this.redoFiles=[];
    this.current=clone(next);this.engine=engine;this.clock++;
  }
  private wireEdit(tx:Tx,doWire:(eng:ManualWireEngine)=>void):void {
    this.edit(tx,draft=>{
      const {subset,session}=localSession(draft,this.clock);
      doWire(session.engine);
      return materialize(draft,subset,session);
    });
  }
  upgradeCatalog(tx:Tx):number {
    let added=0;
    this.edit(tx,draft=>{
      const {part_definitions:parts,symbol_definitions:symbols}=draft.project;
      const additions=catalogAdditions(parts,symbols);
      if(!additions.length)reject('NO_CHANGE');
      for(const entry of additions){
        parts.push(clone(entry.part));symbols.push(clone(entry.symbol));added++;
      }
      return draft;
    });
    return added;
  }
  /** Magnetic placement aligns a new physical pin with one facing existing pin.
   * Read-only, no Net creation and no relocation of previously placed symbols.
   * The same proposal is recomputed at commit (revision CAS remains authoritative). */
  suggestAlignedPlacement(symbolId:string,origin:readonly number[]):PlacementHint|null {
    const at=xy(origin),file=this.current,sheet=file.project.sheets[indexOfSheet(file)];
    const defs=new Map(file.project.symbol_definitions.map(d=>[d.id,d]));
    const symbol=defs.get(symbolId);
    if(!symbol||symbol.status==='deprecated')return null;
    if(sheet.instances.length>512||sheet.wires.reduce((n,w)=>n+w.segments.length,0)>8192)return null;
    const dirs={left:[-1,0],right:[1,0],top:[0,-1],bottom:[0,1]} as const;
    const transform=(i:SymbolInstance,p:PointUm,vector=false):MutablePoint=>{
      const x=i.mirror_x?-p[0]:p[0],y=p[1];
      const q=i.rotation_deg===0?[x,y]:i.rotation_deg===90?[-y,x]:i.rotation_deg===180?[-x,-y]:[y,-x];
      return xy([q[0]+(vector?0:i.origin_um[0]),q[1]+(vector?0:i.origin_um[1])]);
    };
    const rect=(p:PointUm,q:PointUm):Bounds=>({minX:Math.min(p[0],q[0]),minY:Math.min(p[1],q[1]),maxX:Math.max(p[0],q[0]),maxY:Math.max(p[1],q[1])});
    const obstacles=sheet.instances.map(i=>{
      const d=defs.get(i.symbol_id);if(!d)reject('UNKNOWN_SYMBOL');
      return {i,d,box:translateBounds(symbolBounds(d,i.rotation_deg,i.mirror_x),i.origin_um)};
    });
    const wireBoxes=sheet.wires.flatMap(w=>w.vertices.slice(1).map((v,i)=>rect(w.vertices[i].at_um,v.at_um)));
    const nodes=[...sheet.junctions,...sheet.splices].map(n=>rect(n.at_um,n.at_um));
    const occupied=[...obstacles.map(o=>o.box),...wireBoxes,...nodes];
    const local=symbolBounds(symbol,0,false),margin=sheet.frame.margin_um;
    const candidates:{hint:PlacementHint;correction:number;gap:number}[]=[];
    for(const target of obstacles)for(const p of target.d.pins){
      const fixed=transform(target.i,p.at_um),normal=transform(target.i,dirs[p.side],true);
      for(const incoming of symbol.pins){
        const n=dirs[incoming.side];
        if(n[0]!==-normal[0]||n[1]!==-normal[1])continue;
        const axis=normal[0]!==0?1:0,along=1-axis;
        const moving:MutablePoint=[at[0]+incoming.at_um[0],at[1]+incoming.at_um[1]];
        const delta=fixed[axis]-moving[axis],gap=(moving[along]-fixed[along])*normal[along];
        if(Math.abs(delta)>5000||gap<4000||gap>80000)continue;
        const position=xy([at[0]+(axis===0?delta:0),at[1]+(axis===1?delta:0)]);
        const box=translateBounds(local,position);
        if(box.minX<margin||box.minY<margin||box.maxX>sheet.frame.size_um[0]-margin||box.maxY>sheet.frame.size_um[1]-margin||
          occupied.some(o=>!separated(box,o,1000)))continue;
        const end:MutablePoint=[position[0]+incoming.at_um[0],position[1]+incoming.at_um[1]],corridor=rect(fixed,end);
        // No suggestion if a direct path would pass through an unrelated symbol, wire or node.
        if(obstacles.some(o=>o.i.id!==target.i.id&&!separated(corridor,o.box,1000))||
          [...wireBoxes,...nodes].some(o=>!separated(corridor,o,1000)))continue;
        candidates.push({correction:Math.abs(delta),gap,hint:{origin:position,from:fixed,to:end,
          target:{component_id:target.i.component_id,physical_pin_number:p.physical_pin_number},
          newPin:incoming.physical_pin_number}});
      }
    }
    candidates.sort((a,b)=>a.correction-b.correction||a.gap-b.gap);
    if(!candidates.length)return null;
    const best=candidates[0];
    // If equally plausible targets imply different poses, leave the requested position alone.
    if(candidates.some(c=>Math.abs(c.correction-best.correction)<=500&&Math.abs(c.gap-best.gap)<=2000&&
      (c.hint.origin[0]!==best.hint.origin[0]||c.hint.origin[1]!==best.hint.origin[1])))return null;
    return best.hint;
  }
  place(tx:Tx,symbolId:string,origin:readonly number[]):string {
    const position=xy(origin);
    let added='';
    this.edit(tx,draft=>{
      const symbol=draft.project.symbol_definitions.find(s=>s.id===symbolId);
      const part=draft.project.part_definitions.find(p=>p.id===symbol?.part_id);
      if(!symbol||!part||symbol.status==='deprecated')reject('UNKNOWN_SYMBOL');
      const refdes=nextRefdes(draft,part.reference_prefix);
      const comp:Component={id:newId('comp'),source_refdes:refdes,refdes,
        part_id:part.id,value:catalogDefaultValue(part.id)};
      const sheet=draft.project.sheets[indexOfSheet(draft)];
      const layer=sheet.layers.find(l=>l.kind==='electrical');
      if(!layer)reject('MISSING_ELECTRICAL_LAYER');
      const instance:SymbolInstance={id:newId('inst'),component_id:comp.id,
        symbol_id:symbolId,origin_um:position,rotation_deg:0,mirror_x:false,
        layer_id:layer.id};
      draft.project.components.push(comp);sheet.instances.push(instance);
      expectedCounts(draft);added=instance.id;return draft;
    });
    return added;
  }
  /** Clipboard is a detached symbol template, never a Net or physical PinRef. */
  copyComponent(instanceId:string):ComponentClipboard {
    const instance=this.current.project.sheets[indexOfSheet(this.current)].instances.find(i=>i.id===instanceId);
    const comp=this.current.project.components.find(c=>c.id===instance?.component_id);
    if(!instance||!comp)reject('UNKNOWN_INSTANCE');
    return {symbol_id:instance.symbol_id,value:comp.value,rotation_deg:instance.rotation_deg,
      mirror_x:instance.mirror_x,origin_um:[...instance.origin_um]};
  }
  /** Suggest a nearby on-paper origin without overlapping another symbol's
   * transformed ink/pin bounds. This is placement assistance, not full DRC:
   * wires, text and labels remain separately checked by the editor. */
  suggestPasteOrigin(template:ComponentClipboard,anchor:readonly number[],snap:boolean):PointUm {
    const at=xy(anchor);
    const file=this.current;
    const sheet=file.project.sheets[indexOfSheet(file)];
    const defs=new Map(file.project.symbol_definitions.map(s=>[s.id,s]));
    const symbol=defs.get(template.symbol_id);
    if(!symbol||symbol.status==='deprecated')reject('UNKNOWN_SYMBOL');
    const grid=snap?file.project.settings.grid_step_um:1;
    if(!Number.isSafeInteger(grid)||grid<=0)reject('INVALID_GRID');
    const stride=Math.ceil(10000/grid)*grid;
    const margin=sheet.frame.margin_um,[width,height]=sheet.frame.size_um;
    const shape=symbolBounds(symbol,template.rotation_deg,template.mirror_x);
    const occupied=sheet.instances.map(i=>{
      const def=defs.get(i.symbol_id);if(!def)reject('UNKNOWN_SYMBOL');
      return translateBounds(symbolBounds(def,i.rotation_deg,i.mirror_x),i.origin_um);
    });
    // Anchor at the nearest valid grid coordinate even after a cross-sheet paste.
    const center:[number,number]=[
      Math.round(Math.max(0,Math.min(width,at[0]))/grid)*grid,
      Math.round(Math.max(0,Math.min(height,at[1]))/grid)*grid
    ];
    const candidate=(dx:number,dy:number):PointUm|null=>{
      const p:PointUm=[center[0]+dx*stride,center[1]+dy*stride];
      const b=translateBounds(shape,p);
      if(b.minX<margin||b.minY<margin||b.maxX>width-margin||b.maxY>height-margin)return null;
      return occupied.every(o=>separated(b,o,1000))?p:null;
    };
    // Bounded expanding rings; prefer the familiar down/right paste offset.
    for(let radius=1;radius<=24;radius++){
      const preferred=candidate(radius,radius);if(preferred)return preferred;
      for(let d=-radius;d<=radius;d++){
        for(const [dx,dy] of [[d,radius],[d,-radius],[radius,d],[-radius,d]]){
          const p=candidate(dx,dy);if(p)return p;
        }
      }
    }
    reject('NO_SAFE_PASTE_ORIGIN');
  }
  pasteComponent(tx:Tx,template:ComponentClipboard,origin:readonly number[]):string {
    const position=xy(origin);
    if(!template||typeof template.value!=='string'||template.value.length>256||
      ![0,90,180,270].includes(template.rotation_deg)||typeof template.mirror_x!=='boolean')
      reject('INVALID_CLIPBOARD');
    let added='';
    this.edit(tx,draft=>{
      const symbol=draft.project.symbol_definitions.find(s=>s.id===template.symbol_id);
      const part=draft.project.part_definitions.find(p=>p.id===symbol?.part_id);
      if(!symbol||!part||symbol.status==='deprecated')reject('UNKNOWN_SYMBOL');
      const sheet=draft.project.sheets[indexOfSheet(draft)];
      const layer=sheet.layers.find(l=>l.kind==='electrical'&&!l.locked);
      if(!layer)reject('MISSING_ELECTRICAL_LAYER');
      const refdes=nextRefdes(draft,part.reference_prefix);
      const comp:Component={id:newId('comp'),refdes,source_refdes:refdes,part_id:part.id,value:template.value};
      const instance:SymbolInstance={id:newId('inst'),component_id:comp.id,symbol_id:symbol.id,
        origin_um:position,rotation_deg:template.rotation_deg,mirror_x:template.mirror_x,layer_id:layer.id};
      draft.project.components.push(comp);sheet.instances.push(instance);
      expectedCounts(draft);added=instance.id;return draft;
    });
    return added;
  }
  /** Copy complete internal Nets only. A Net with any member or geometry
   * outside the selection/sheet is omitted in full, never silently shorted. */
  copyGroup(instanceIds:readonly string[]):GroupClipboard {
    const ids=new Set(instanceIds),file=this.current;
    const sheet=file.project.sheets[indexOfSheet(file)];
    const instances=sheet.instances.filter(i=>ids.has(i.id));
    if(ids.size<2||ids.size!==instanceIds.length||instances.length!==ids.size)reject('INVALID_GROUP');
    const keys=new Set(instances.map(i=>i.component_id));
    const related=file.project.nets.filter(n=>n.members.some(p=>keys.has(p.component_id)));
    const nets=related.filter(n=>n.members.every(p=>keys.has(p.component_id))&&
      !file.project.sheets.some(sh=>sh.id!==sheet.id&&
        [...sh.wires,...sh.junctions,...sh.splices].some(o=>o.net_id===n.id)));
    const included=new Set(nets.map(n=>n.id));
    return clone({
      anchor:[Math.min(...instances.map(i=>i.origin_um[0])),Math.min(...instances.map(i=>i.origin_um[1]))],
      components:instances.map(i=>({key:i.component_id,template:this.copyComponent(i.id)})),
      nets,wires:sheet.wires.filter(w=>included.has(w.net_id)),
      junctions:sheet.junctions.filter(j=>included.has(j.net_id)),
      splices:sheet.splices.filter(j=>included.has(j.net_id)),
      omittedNetCount:related.length-nets.length
    });
  }
  /** Entire group (including route vertices) must fit inside printable margins.
   * Conservative placement uses one bounding box; this is not a full DRC. */
  suggestGroupPasteOrigin(template:GroupClipboard,anchor:readonly number[],snap:boolean):PointUm {
    const at=xy(anchor),file=this.current,sheet=file.project.sheets[indexOfSheet(file)];
    const defs=new Map(file.project.symbol_definitions.map(s=>[s.id,s]));
    const bounds:Bounds={minX:0,minY:0,maxX:0,maxY:0};
    const include=(b:Bounds)=>{
      bounds.minX=Math.min(bounds.minX,b.minX);bounds.minY=Math.min(bounds.minY,b.minY);
      bounds.maxX=Math.max(bounds.maxX,b.maxX);bounds.maxY=Math.max(bounds.maxY,b.maxY);
    };
    const relative=(p:readonly number[])=>[p[0]-template.anchor[0],p[1]-template.anchor[1]];
    for(const {template:t} of template.components){
      const def=defs.get(t.symbol_id);if(!def||def.status==='deprecated')reject('UNKNOWN_SYMBOL');
      include(translateBounds(symbolBounds(def,t.rotation_deg,t.mirror_x),relative(t.origin_um)));
    }
    for(const p of [...template.wires.flatMap(w=>w.vertices.map(v=>v.at_um)),...template.junctions.map(j=>j.at_um),...template.splices.map(j=>j.at_um)]){
      const [x,y]=relative(p);include({minX:x,maxX:x,minY:y,maxY:y});
    }
    const occupied=sheet.instances.map(i=>{
      const def=defs.get(i.symbol_id);if(!def)reject('UNKNOWN_SYMBOL');
      return translateBounds(symbolBounds(def,i.rotation_deg,i.mirror_x),i.origin_um);
    });
    for(const wire of sheet.wires)for(let i=1;i<wire.vertices.length;i++){
      const a=wire.vertices[i-1].at_um,b=wire.vertices[i].at_um;
      occupied.push({minX:Math.min(a[0],b[0]),maxX:Math.max(a[0],b[0]),minY:Math.min(a[1],b[1]),maxY:Math.max(a[1],b[1])});
    }
    const grid=snap?file.project.settings.grid_step_um:1;
    if(!Number.isSafeInteger(grid)||grid<=0)reject('INVALID_GRID');
    const stride=Math.ceil(10000/grid)*grid;
    const [width,height]=sheet.frame.size_um,margin=sheet.frame.margin_um;
    const center=at.map((v,i)=>Math.round(Math.max(0,Math.min(sheet.frame.size_um[i],v))/grid)*grid);
    const candidate=(dx:number,dy:number):PointUm|null=>{
      const p:PointUm=[center[0]+dx*stride,center[1]+dy*stride],b=translateBounds(bounds,p);
      if(b.minX<margin||b.minY<margin||b.maxX>width-margin||b.maxY>height-margin)return null;
      return occupied.every(o=>separated(b,o,1000))?p:null;
    };
    for(let radius=1;radius<=60;radius++){
      const preferred=candidate(radius,radius);if(preferred)return preferred;
      for(let d=-radius;d<=radius;d++)for(const [dx,dy] of [[d,radius],[d,-radius],[radius,d],[-radius,d]]){
        const p=candidate(dx,dy);if(p)return p;
      }
    }
    reject('NO_SAFE_PASTE_ORIGIN');
  }
  pasteGroup(tx:Tx,template:GroupClipboard,origin:readonly number[]):string[] {
    const at=xy(origin),base=xy(template.anchor);
    const shift=(p:readonly number[]):MutablePoint=>xy([p[0]+at[0]-base[0],p[1]+at[1]-base[1]]);
    const added:string[]=[];
    this.edit(tx,draft=>{
      const sheet=draft.project.sheets[indexOfSheet(draft)];
      const layer=sheet.layers.find(l=>l.kind==='electrical'&&!l.locked);
      if(!layer)reject('MISSING_ELECTRICAL_LAYER');
      if(template.components.length<2)reject('INVALID_GROUP');
      const comps=new Map<string,string>(),nets=new Map<string,string>(),junctions=new Map<string,string>(),splices=new Map<string,string>();
      const mapped=(map:Map<string,string>,key:string):string=>{
        const value=map.get(key);if(!value)reject('INVALID_CLIPBOARD');return value;
      };
      const fresh=(map:Map<string,string>,key:string,prefix:string):string=>{
        if(map.has(key))reject('INVALID_CLIPBOARD');
        const id=newId(prefix);map.set(key,id);return id;
      };
      for(const {key,template:t} of template.components){
        const symbol=draft.project.symbol_definitions.find(s=>s.id===t.symbol_id);
        const part=draft.project.part_definitions.find(p=>p.id===symbol?.part_id);
        if(!symbol||!part||symbol.status==='deprecated')reject('UNKNOWN_SYMBOL');
        if(typeof t.value!=='string'||t.value.length>256||![0,90,180,270].includes(t.rotation_deg)||typeof t.mirror_x!=='boolean')reject('INVALID_CLIPBOARD');
        const compId=fresh(comps,key,'comp'),refdes=nextRefdes(draft,part.reference_prefix),id=newId('inst');
        draft.project.components.push({id:compId,refdes,source_refdes:refdes,part_id:part.id,value:t.value});
        sheet.instances.push({id,component_id:compId,symbol_id:symbol.id,origin_um:shift(t.origin_um),rotation_deg:t.rotation_deg,mirror_x:t.mirror_x,layer_id:layer.id});
        added.push(id);
      }
      const names=new Set(draft.project.nets.map(n=>n.name));
      let num=1;
      for(const net of template.nets){
        const id=fresh(nets,net.id,'net');
        while(names.has('N'+num))num++;
        const name='N'+num++;names.add(name);
        draft.project.nets.push({id,name,members:net.members.map(p=>({component_id:mapped(comps,p.component_id),physical_pin_number:p.physical_pin_number})),route_status:'unrouted'});
      }
      for(const j of template.junctions)sheet.junctions.push({id:fresh(junctions,j.id,'junction'),net_id:mapped(nets,j.net_id),layer_id:layer.id,at_um:shift(j.at_um)});
      for(const j of template.splices)sheet.splices.push({id:fresh(splices,j.id,'splice'),net_id:mapped(nets,j.net_id),layer_id:layer.id,at_um:shift(j.at_um)});
      const anchor=(a:WireEndpoint):WireEndpoint=>{
        switch(a.kind){
          case 'pin':return {kind:'pin',component_id:mapped(comps,a.component_id),physical_pin_number:a.physical_pin_number};
          case 'junction':return {kind:'junction',junction_id:mapped(junctions,a.junction_id)};
          case 'splice':return {kind:'splice',splice_id:mapped(splices,a.splice_id)};
          case 'free':return {kind:'free',free_id:newId('free')};
          case 'bend':return {kind:'bend'};
        }
      };
      for(const wire of template.wires){
        const id=newId('wire'),vertices=new Map<string,string>();
        sheet.wires.push({id,net_id:mapped(nets,wire.net_id),layer_id:layer.id,mode:'orthogonal',needs_routing_review:true,
          vertices:wire.vertices.map(v=>({id:fresh(vertices,v.id,'vertex'),at_um:shift(v.at_um),anchor:anchor(v.anchor)})),
          segments:wire.segments.map(s=>({id:newId('segment'),from_vertex_id:mapped(vertices,s.from_vertex_id),to_vertex_id:mapped(vertices,s.to_vertex_id)}))});
      }
      expectedCounts(draft);
      const {session}=localSession(draft,this.clock);
      // Recompute only the copied Nets; never rewrite original route status.
      for(const id of nets.values())draft.project.nets.find(n=>n.id===id)!.route_status=session.engine.validateNet(id).status;
      return draft;
    });
    return added;
  }
  addSheet(tx:Tx):string {
    let added='';
    this.edit(tx,draft=>{
      const index=draft.project.sheets.length+1;
      const sh=frameSheet(newId('sheet'),index,'Лист '+index);
      draft.project.sheets.push(sh);added=sh.id;
      return draft;
    });
    return added;
  }
  /** Paper presets are exact integer micrometres; changing the sheet must
   * never regenerate physical PinRefs, Nets, routes or source provenance.
   */
  setPaper(tx:Tx,paper:'A4'|'A3'|'A2'):void{
    const sizes:{A4:PointUm;A3:PointUm;A2:PointUm}={
      A4:[297000,210000],A3:[420000,297000],A2:[594000,420000]
    };
    if(!Object.hasOwn(sizes,paper))reject('UNKNOWN_PAPER');
    this.edit(tx,draft=>{
      const sheet=draft.project.sheets[indexOfSheet(draft)];
      if(sheet.frame.paper===paper+' landscape'&&
        sheet.frame.size_um[0]===sizes[paper][0]&&
        sheet.frame.size_um[1]===sizes[paper][1])reject('NO_CHANGE');
      sheet.frame={...sheet.frame,paper:paper+' landscape',
        size_um:[...sizes[paper]] as PointUm};
      return draft;
    });
  }
  selectSheet(tx:Tx,id:string):void{
    this.edit(tx,draft=>{
      if(!draft.project.sheets.some(s=>s.id===id))reject('UNKNOWN_SHEET');
      draft.workspace.active_sheet_id=id;return draft;
    });
  }
  updateProperty(tx:Tx,instanceId:string,key:'refdes'|'value',value:string):void{
    this.edit(tx,draft=>{
      const inst=draft.project.sheets.flatMap(s=>s.instances).find(i=>i.id===instanceId);
      const comp=draft.project.components.find(c=>c.id===inst?.component_id);
      if(!comp)reject('UNKNOWN_INSTANCE');
      if(key==='refdes') {
        const next=value.trim();
        if(!/^[A-Za-z][A-Za-z0-9_-]{0,31}$/.test(next))reject('INVALID_REFDES');
        if(draft.project.components.some(c=>c.id!==comp.id&&c.refdes===next))
          reject('DUPLICATE_REFDES');
        comp.refdes=next;
      } else {
        if(typeof value!=='string'||value.length>256)reject('INVALID_VALUE');
        comp.value=value;
      }
      return draft;
    });
  }
  /** Atomic group translation through the real wire engine, with explicit consent
   * for all electrical route changes and exact rollback on any invalid anchor. */
  moveGroup(tx:Tx,instanceIds:readonly string[],delta:readonly number[],permitRebuild=false):void{
    const d=xy(delta);
    if(!d.some(Boolean))reject('NO_CHANGE');
    const ids=new Set(instanceIds);
    if(ids.size<2||ids.size!==instanceIds.length)reject('INVALID_GROUP');
    this.edit(tx,draft=>{
      const sheet=draft.project.sheets[indexOfSheet(draft)];
      const group=sheet.instances.filter(i=>ids.has(i.id));
      if(group.length!==ids.size)reject('UNKNOWN_INSTANCE');
      const componentIds=new Set(group.map(i=>i.component_id));
      if(componentIds.size!==ids.size)reject('INVALID_GROUP');
      for(const inst of group){
        if(sheet.layers.find(l=>l.id===inst.layer_id)?.locked)reject('LAYER_LOCKED');
      }
      const {subset,session}=localSession(draft,this.clock);
      const eng=session.engine;
      const attached=eng.snapshot.wires.filter(w=>[w.vertices[0],w.vertices.at(-1)!].some(
        v=>v.anchor.kind==='pin'&&componentIds.has(v.anchor.component_id)));
      if(attached.length&&!permitRebuild)reject('GROUP_REROUTE_REQUIRED');
      if(attached.some(w=>sheet.layers.find(l=>l.id===w.layer_id)?.locked))reject('LAYER_LOCKED');
      eng.moveComponentsAndReanchor(eng.newTransaction('move-group'),[...componentIds],d,permitRebuild);
      return materialize(draft,subset,session);
    });
  }
  move(tx:Tx,componentId:string,position:readonly number[],permitRebuild=false):void{
    const target=xy(position);
    this.wireEdit(tx,eng=>{
      // Rebuild is an explicit user consent, never enabled for passive drag.
      eng.moveComponentAndReanchor(eng.newTransaction('move-symbol'),componentId,target,permitRebuild);
    });
  }
  rotate(tx:Tx,componentId:string,permitRebuild=false):void{
    this.wireEdit(tx,eng=>{
      const comp=eng.snapshot.components.find(c=>c.id===componentId);
      if(!comp)reject('UNKNOWN_COMPONENT');
      eng.rotateAndReanchor(eng.newTransaction('rotate-symbol'),componentId,
        ((comp.rotation+90)%360) as 0|90|180|270,permitRebuild);
    });
  }
  beginWire(pin:PinRef):WorldPin{
    const comp=this.engine.snapshot.components.find(c=>c.id===pin.component_id);
    const p=comp?.pins.find(p=>p.physical_pin_number===pin.physical_pin_number);
    if(!comp||!p)reject('UNKNOWN_PIN');
    const rotation=comp.rotation,xx=comp.mirror_x?-p.local_at_um[0]:p.local_at_um[0];
    const yy=p.local_at_um[1];
    const local:MutablePoint=rotation===0?[xx,yy]:rotation===90?[-yy,xx]:
      rotation===180?[-xx,-yy]:[yy,-xx];
    const dirs:{[k:string]:MutablePoint}={left:[-1,0],right:[1,0],up:[0,-1],down:[0,1]};
    const outward=dirs[p.outward],a=comp.mirror_x?-outward[0]:outward[0],b=outward[1];
    const normal:MutablePoint=rotation===0?[a,b]:rotation===90?[-b,a]:
      rotation===180?[-a,-b]:[b,-a];
    const net=this.engine.snapshot.nets.find(n=>n.members.some(m=>pinKey(m)===pinKey(pin)));
    return {at_um:[local[0]+comp.origin_um[0],local[1]+comp.origin_um[1]],normal,
      net_id:net?.id??null};
  }
  connect(tx:Tx,start:PinRef,end:PinRef,bends:readonly PointUm[]=[],smart=false):void{
    this.edit(tx,draft=>{
      const a=this.beginWire(start),b=this.beginWire(end);
      if(pinKey(start)===pinKey(end))reject('SAME_PIN');
      if(a.net_id&&b.net_id&&a.net_id!==b.net_id)reject('NET_CONFLICT');
      const netId=a.net_id||b.net_id||newId('net');
      let net=draft.project.nets.find(n=>n.id===netId);
      if(!net){
        // Net IDs are stable UUIDs; display names must also stay unique
        // when an earlier Net is removed and later names survive.
        const used=new Set(draft.project.nets.map(n=>n.name));
        let id=1;
        while(used.has('N'+id))id++;
        net={id:netId,name:'N'+id,members:[],route_status:'unrouted'};
        draft.project.nets.push(net);
      }
      for(const pin of [start,end])if(!net.members.some(m=>pinKey(m)===pinKey(pin)))
        net.members.push(clone(pin));
      expectedCounts(draft);
      const {subset,session}=localSession(draft,this.clock);
      const wpA=session.engine.beginWire(start),wpB=session.engine.beginWire(end);
      const from:WorldPin={...wpA,net_id:netId},to:WorldPin={...wpB,net_id:netId};
      const points=bends.length?addRouteBends(from,to,bends):smart?cleanRoute(draft,start,end,from,to,netId):
        session.engine.previewRoute({kind:'pin',...start},{kind:'pin',...end});
      let num=1;
      while(session.engine.snapshot.wires.some(w=>w.id==='manual-'+num))num++;
      const layer=subset.project.sheets[0].layers.find(l=>l.kind==='electrical');
      if(!layer)reject('MISSING_ELECTRICAL_LAYER');
      const wire=constructWire('manual-'+num,netId,layer.id,points,
        {kind:'pin',...start},{kind:'pin',...end});
      session.engine.commitWire(session.engine.newTransaction('connect-pin'),wire);
      return materialize(draft,subset,session);
    });
  }
  /** Align the actual connected pins, not symbol centers. Move one component
   * only if it has no other attached wire; never rewrite shared junctions.
   * The selected direct wire must become a safe, straight conductor. */
  alignConnectedPair(tx:Tx,instanceIds:readonly string[]):{moved:string;delta:MutablePoint;beforeBends:number}{
    let result:{moved:string;delta:MutablePoint;beforeBends:number}|null=null;
    this.edit(tx,draft=>{
      if(instanceIds.length!==2||new Set(instanceIds).size!==2)reject('INVALID_GROUP');
      const sheet=draft.project.sheets[indexOfSheet(draft)];
      const pair=instanceIds.map(id=>sheet.instances.find(i=>i.id===id));
      if(pair.some(i=>!i))reject('UNKNOWN_INSTANCE');
      const ids=new Set(pair.map(i=>i!.component_id));
      const direct=sheet.wires.filter(w=>{
        const a=w.vertices[0].anchor,b=w.vertices.at(-1)!.anchor;
        return a.kind==='pin'&&b.kind==='pin'&&a.component_id!==b.component_id&&ids.has(a.component_id)&&ids.has(b.component_id);
      });
      if(direct.length!==1)reject('ALIGN_REQUIRES_ONE_DIRECT_WIRE');
      const wire=direct[0],first=wire.vertices[0].anchor,last=wire.vertices.at(-1)!.anchor;
      if(first.kind!=='pin'||last.kind!=='pin')reject('INVALID_PIN');
      if(sheet.layers.find(l=>l.id===wire.layer_id)?.locked)reject('LAYER_LOCKED');
      const a=this.beginWire(first),b=this.beginWire(last);
      if(a.normal[0]!==-b.normal[0]||a.normal[1]!==-b.normal[1])reject('ALIGN_REQUIRES_FACING_PINS');
      const axis=a.normal[0]!==0?1:0;
      if(a.at_um[axis]===b.at_um[axis]&&wire.vertices.length===2)reject('NO_CHANGE');
      const defs=new Map(draft.project.symbol_definitions.map(d=>[d.id,d]));
      const bounds=(i:SymbolInstance)=>{const d=defs.get(i.symbol_id);if(!d)reject('UNKNOWN_SYMBOL');
        return translateBounds(symbolBounds(d,i.rotation_deg,i.mirror_x),i.origin_um)};
      const candidates=[{pin:last,delta:a.at_um[axis]-b.at_um[axis]},{pin:first,delta:b.at_um[axis]-a.at_um[axis]}];
      for(const option of candidates){
        const trial=clone(draft),sh=trial.project.sheets[indexOfSheet(trial)];
        const moving=sh.instances.find(i=>i.component_id===option.pin.component_id)!;
        if(sh.layers.find(l=>l.id===moving.layer_id)?.locked)continue;
        if(trial.project.sheets.some(other=>other.id!==sh.id&&other.instances.some(i=>i.component_id===moving.component_id)))continue;
        if(sh.wires.some(w=>w.id!==wire.id&&w.vertices.some(v=>v.anchor.kind==='pin'&&v.anchor.component_id===moving.component_id)))continue;
        const delta:MutablePoint=axis===0?[option.delta,0]:[0,option.delta];
        moving.origin_um=xy([moving.origin_um[0]+delta[0],moving.origin_um[1]+delta[1]]);
        const box=bounds(moving),margin=sh.frame.margin_um;
        if(box.minX<margin||box.minY<margin||box.maxX>sh.frame.size_um[0]-margin||box.maxY>sh.frame.size_um[1]-margin)continue;
        if(sh.instances.some(i=>i.id!==moving.id&&!separated(box,bounds(i),1000)))continue;
        if(sh.wires.some(w=>w.id!==wire.id&&w.vertices.slice(1).some((v,i)=>{
          const p=w.vertices[i].at_um,q=v.at_um;
          return !separated(box,{minX:Math.min(p[0],q[0]),minY:Math.min(p[1],q[1]),maxX:Math.max(p[0],q[0]),maxY:Math.max(p[1],q[1])},1000);
        })))continue;
        if([...sh.junctions,...sh.splices].some(n=>!separated(box,{minX:n.at_um[0],maxX:n.at_um[0],minY:n.at_um[1],maxY:n.at_um[1]},1000)))continue;
        const shift=(p:WorldPin,ref:PinRef):WorldPin=>ref.component_id===moving.component_id?
          {...p,at_um:xy([p.at_um[0]+delta[0],p.at_um[1]+delta[1]])}:p;
        let points:MutablePoint[];
        try{points=cleanRoute(trial,first,last,shift(a,first),shift(b,last),wire.net_id,wire.id)}
        catch(e){if(e instanceof WireError&&e.code==='REROUTE_REQUIRED')continue;throw e;}
        if(points.length!==2)continue;
        const old=sh.wires.find(w=>w.id===wire.id)!;
        // Preserve both terminal vertex identities, wire ID, Net and layer.
        const vertices=[{...old.vertices[0],at_um:points[0]},{...old.vertices.at(-1)!,at_um:points[1]}];
        const beforeBends=old.vertices.length-2;
        old.vertices=vertices;
        old.segments=[{id:newId('segment'),from_vertex_id:vertices[0].id,to_vertex_id:vertices[1].id}];
        old.needs_routing_review=true;
        const {subset,session}=localSession(trial,this.clock);
        result={moved:moving.id,delta,beforeBends};
        return materialize(trial,subset,session);
      }
      reject('ALIGN_NO_SAFE_STRAIGHT_ROUTE');
    });
    if(!result)reject('ALIGN_NO_SAFE_STRAIGHT_ROUTE');
    return result;
  }
  /** Straighten a selected simple path of facing physical pins.
   * Preserve longitudinal positions, rotations, Net membership and external
   * routes. External connections and locked instances fix transverse poses.
   * Solve relative pin offsets, then choose a median shift (minimum L1 move).
   * Commit only if ALL internal conductors are straight and collision-free. */
  alignSeries(tx:Tx,instanceIds:readonly string[],distribute=false):{moved:number;wires:number;removedBends:number;axis:'horizontal'|'vertical'}{
    let result:{moved:number;wires:number;removedBends:number;axis:'horizontal'|'vertical'}|undefined;
    this.edit(tx,draft=>{
      const sh=draft.project.sheets[indexOfSheet(draft)];
      const selected=new Set(instanceIds);
      if(selected.size<3||selected.size>32||selected.size!==instanceIds.length)reject('INVALID_SERIES_GROUP');
      if(sh.instances.length>256||sh.wires.reduce((n,w)=>n+w.segments.length,0)>2048)reject('LAYOUT_SIZE_LIMIT');
      const group=sh.instances.filter(i=>selected.has(i.id));
      if(group.length!==selected.size)reject('UNKNOWN_INSTANCE');
      const ids=new Set(group.map(i=>i.component_id));
      if(ids.size!==group.length)reject('INVALID_SERIES_GROUP');
      const edges:{wire:WirePolyline;first:PinRef;last:PinRef;a:WorldPin;b:WorldPin}[]=[];
      const adjacency=new Map(group.map(i=>[i.component_id,[] as number[]]));
      const internalIds=new Set<string>(),usedPins=new Set<string>();
      let axis:0|1|undefined;
      for(const wire of sh.wires){
        const first=wire.vertices[0].anchor,last=wire.vertices.at(-1)!.anchor;
        if(first.kind!=='pin'||last.kind!=='pin'||!ids.has(first.component_id)||!ids.has(last.component_id))continue;
        if(first.component_id===last.component_id||usedPins.has(pinKey(first))||usedPins.has(pinKey(last)))reject('SERIES_NOT_SIMPLE_PATH');
        if(sh.layers.find(l=>l.id===wire.layer_id)?.locked)reject('LAYER_LOCKED');
        const a=this.beginWire(first),b=this.beginWire(last);
        if(a.normal[0]!==-b.normal[0]||a.normal[1]!==-b.normal[1])reject('SERIES_REQUIRES_FACING_PINS');
        const transverse:0|1=a.normal[0]!==0?1:0;
        if(axis!==undefined&&axis!==transverse)reject('SERIES_MIXED_AXES');
        axis=transverse;
        const along=1-axis;
        if((b.at_um[along]-a.at_um[along])*a.normal[along]<=0)reject('SERIES_REVERSED_ORDER');
        adjacency.get(first.component_id)!.push(edges.length);adjacency.get(last.component_id)!.push(edges.length);
        usedPins.add(pinKey(first));usedPins.add(pinKey(last));internalIds.add(wire.id);
        edges.push({wire,first,last,a,b});
      }
      if(axis===undefined||edges.length!==group.length-1||[...adjacency.values()].some(v=>v.length<1||v.length>2))reject('SERIES_NOT_SIMPLE_PATH');
      const transverse=axis;
      const endpoint=group.find(i=>adjacency.get(i.component_id)!.length===1);
      if(!endpoint)reject('SERIES_NOT_SIMPLE_PATH');
      const offsets=new Map<string,number>([[endpoint.component_id,0]]);
      let current=endpoint.component_id;
      while(true){
        const edgeIndex=adjacency.get(current)!.find(index=>{
          const e=edges[index];return !offsets.has(e.first.component_id===current?e.last.component_id:e.first.component_id);
        });
        if(edgeIndex===undefined)break;
        const e=edges[edgeIndex],forward=e.first.component_id===current;
        const next=forward?e.last.component_id:e.first.component_id;
        const p=forward?e.a:e.b,q=forward?e.b:e.a;
        offsets.set(next,offsets.get(current)!+p.at_um[transverse]-q.at_um[transverse]);
        current=next;
      }
      if(offsets.size!==group.length)reject('SERIES_NOT_SIMPLE_PATH');
      const outside=sh.wires.filter(w=>!internalIds.has(w.id));
      const fixed=new Set(group.filter(i=>sh.layers.find(l=>l.id===i.layer_id)?.locked||
        draft.project.sheets.some(other=>other.id!==sh.id&&other.instances.some(v=>v.component_id===i.component_id))).map(i=>i.component_id));
      for(const w of outside)for(const v of [w.vertices[0],w.vertices.at(-1)!])if(v.anchor.kind==='pin'&&ids.has(v.anchor.component_id))fixed.add(v.anchor.component_id);
      // Optional equal spacing uses gaps BETWEEN real facing pins, not centers.
      // Retain longitudinal end poses; any fixed intermediate component must
      // already satisfy its proposed coordinate. Integer remainder is exact.
      const along:0|1=transverse===0?1:0;
      const longitudinal=new Map(group.map(i=>[i.component_id,0]));
      if(distribute){
        const ordered=[...offsets.keys()],gaps:number[]=[];
        let direction:number|undefined;
        for(let i=1;i<ordered.length;i++){
          const prev=ordered[i-1],next=ordered[i];
          const edge=edges.find(e=>e.first.component_id===prev&&e.last.component_id===next||
            e.first.component_id===next&&e.last.component_id===prev)!;
          const p=edge.first.component_id===prev?edge.a:edge.b,q=edge.first.component_id===prev?edge.b:edge.a;
          const sign=p.normal[along];
          if(direction!==undefined&&sign!==direction)reject('SERIES_NON_MONOTONIC');
          direction=sign;gaps.push((q.at_um[along]-p.at_um[along])*sign);
        }
        const sum=gaps.reduce((a,b)=>a+b,0),base=Math.floor(sum/gaps.length),remainder=sum%gaps.length;
        if(base<4000)reject('SERIES_GAP_TOO_SMALL');
        let cumulative=0;
        for(let i=1;i<ordered.length;i++){
          cumulative+=(base+(i<=remainder?1:0)-gaps[i-1])*direction!;
          longitudinal.set(ordered[i],cumulative);
        }
        if([...fixed].some(id=>longitudinal.get(id)!==0))reject('SERIES_FIXED_SPACING_CONFLICT');
      }
      const required=[...new Set([...fixed].map(id=>-offsets.get(id)!))];
      if(required.length>1)reject('SERIES_FIXED_CONFLICT');
      const votes=[...offsets.values()].map(n=>-n).sort((a,b)=>a-b);
      const median=votes[Math.floor((votes.length-1)/2)];
      const shifts=required.length?required:[...new Set([median,...votes])].sort((a,b)=>
        votes.reduce((s,v)=>s+Math.abs(v-a)-Math.abs(v-b),0)||a-b);
      const defs=new Map(draft.project.symbol_definitions.map(d=>[d.id,d]));
      const boxFor=(i:SymbolInstance)=>{
        const d=defs.get(i.symbol_id);if(!d)reject('UNKNOWN_SYMBOL');
        return translateBounds(symbolBounds(d,i.rotation_deg,i.mirror_x),i.origin_um);
      };
      const rect=(p:PointUm,q:PointUm):Bounds=>({minX:Math.min(p[0],q[0]),maxX:Math.max(p[0],q[0]),minY:Math.min(p[1],q[1]),maxY:Math.max(p[1],q[1])});
      const wireBoxes=outside.flatMap(w=>w.vertices.slice(1).map((v,i)=>rect(w.vertices[i].at_um,v.at_um)));
      const nodeBoxes=[...sh.junctions,...sh.splices].map(n=>rect(n.at_um,n.at_um));
      for(const common of shifts){
        const trial=clone(draft),sheet=trial.project.sheets[indexOfSheet(trial)];
        const deltas=new Map([...offsets].map(([id,v])=>[id,v+common]));
        const moved=group.filter(i=>(deltas.get(i.component_id)??0)!==0||(longitudinal.get(i.component_id)??0)!==0);
        for(const inst of sheet.instances){
          const delta=deltas.get(inst.component_id)??0,advance=longitudinal.get(inst.component_id)??0;if(!delta&&!advance)continue;
          const position=xy(inst.origin_um);position[transverse]+=delta;position[along]+=advance;inst.origin_um=xy(position);
        }
        const boxes=sheet.instances.map(i=>({i,box:boxFor(i)})),margin=sheet.frame.margin_um;
        if(boxes.some(({i,box})=>(deltas.get(i.component_id)||longitudinal.get(i.component_id))&&(
          box.minX<margin||box.minY<margin||box.maxX>sheet.frame.size_um[0]-margin||box.maxY>sheet.frame.size_um[1]-margin||
          boxes.some(o=>o.i.id!==i.id&&!separated(box,o.box,1000))||
          [...wireBoxes,...nodeBoxes].some(b=>!separated(box,b,1000)))))continue;
        // Temporarily remove ALL internal wires from the planning copy, then
        // validate each new straight route against already accepted routes.
        const originalOrder=sheet.wires.map(w=>w.id);
        sheet.wires=sheet.wires.filter(w=>!internalIds.has(w.id));
        let valid=true,removedBends=0,changed=0;
        for(const edge of edges){
          const shift=(p:WorldPin,ref:PinRef):WorldPin=>{
            const at=xy(p.at_um);at[transverse]+=deltas.get(ref.component_id)!;at[along]+=longitudinal.get(ref.component_id)!;
            return {...p,at_um:xy(at)};
          };
          let points:MutablePoint[];
          try{points=cleanRoute(trial,edge.first,edge.last,shift(edge.a,edge.first),shift(edge.b,edge.last),edge.wire.net_id,undefined,false)}
          catch(e){if(e instanceof WireError&&e.code==='REROUTE_REQUIRED'){valid=false;break}throw e}
          if(points.length!==2){valid=false;break}
          const old=edge.wire,w=clone(old);
          const same=old.vertices.length===2&&old.vertices.every((v,i)=>v.at_um[0]===points[i][0]&&v.at_um[1]===points[i][1]);
          if(!same){
            // Count actual direction changes, not redundant collinear vertices.
            for(let i=1;i<old.vertices.length-1;i++){
              const p=old.vertices[i-1].at_um,c=old.vertices[i].at_um,n=old.vertices[i+1].at_um;
              if(Math.sign(c[0]-p[0])!==Math.sign(n[0]-c[0])||
                 Math.sign(c[1]-p[1])!==Math.sign(n[1]-c[1]))removedBends++;
            }
            changed++;
            w.vertices=[{...old.vertices[0],at_um:points[0]},{...old.vertices.at(-1)!,at_um:points[1]}];
            w.segments=[{id:newId('segment'),from_vertex_id:w.vertices[0].id,to_vertex_id:w.vertices[1].id}];
            w.needs_routing_review=true;
          }
          sheet.wires.push(w);
        }
        if(!valid)continue;
        if(!changed&&!moved.length)reject('NO_CHANGE');
        sheet.wires.sort((a,b)=>originalOrder.indexOf(a.id)-originalOrder.indexOf(b.id));
        const {subset,session}=localSession(trial,this.clock);
        result={moved:moved.length,wires:changed,removedBends,axis:transverse===1?'horizontal':'vertical'};
        return materialize(trial,subset,session);
      }
      reject('SERIES_NO_SAFE_LAYOUT');
    });
    if(!result)reject('SERIES_NO_SAFE_LAYOUT');
    return result;
  }
  /** Rebuild two closed parallel Nets as explicit orthogonal rails.
   * No component moves or inferred membership. All selected two-terminal
   * components must already belong to exactly the same two complete Nets.
   * End taps are invisible degree-2 splices; middle taps are degree-3 dots.
   * Existing route IDs are replaced intentionally; Undo restores them. */
  buildParallelRails(tx:Tx,instanceIds:readonly string[],distribute=false):{branches:number;wires:number;junctions:number;axis:'horizontal'|'vertical'}{
    let result:{branches:number;wires:number;junctions:number;axis:'horizontal'|'vertical'}|undefined;
    this.edit(tx,draft=>{
      const sheet=draft.project.sheets[indexOfSheet(draft)];
      const selection=new Set(instanceIds);
      if(selection.size<3||selection.size>24||selection.size!==instanceIds.length)reject('INVALID_PARALLEL_GROUP');
      if(sheet.instances.length>256||sheet.wires.reduce((n,w)=>n+w.segments.length,0)>2048)reject('LAYOUT_SIZE_LIMIT');
      const group=sheet.instances.filter(i=>selection.has(i.id));
      if(group.length!==selection.size)reject('UNKNOWN_INSTANCE');
      const comps=new Set(group.map(i=>i.component_id));
      const defs=new Map(draft.project.symbol_definitions.map(d=>[d.id,d]));
      const members=draft.project.nets.filter(n=>n.members.some(p=>comps.has(p.component_id)));
      if(members.length!==2||members.some(n=>n.members.length!==group.length||
        new Set(n.members.map(p=>p.component_id)).size!==group.length||n.members.some(p=>!comps.has(p.component_id))))reject('PARALLEL_REQUIRES_CLOSED_NETS');
      const netIds=new Set(members.map(n=>n.id));
      if(draft.project.sheets.some(s=>s.id!==sheet.id&&
        (s.wires.some(w=>netIds.has(w.net_id))||[...s.junctions,...s.splices].some(n=>netIds.has(n.net_id)))))reject('PARALLEL_CROSS_SHEET');
      // Require electrically connected input; don't silently repair an incomplete circuit.
      if(members.some(n=>this.engine.validateNet(n.id).pin_groups.length!==1))reject('PARALLEL_UNCONNECTED_NET');
      const old=sheet.wires.filter(w=>netIds.has(w.net_id));
      if(old.some(w=>[w.vertices[0],w.vertices.at(-1)!].some(v=>v.anchor.kind==='free')))reject('PARALLEL_DANGLING');
      const layers=new Map<string,string>();
      for(const n of members){
        const layerIds=new Set(old.filter(w=>w.net_id===n.id).map(w=>w.layer_id));
        if(layerIds.size!==1)reject('PARALLEL_MIXED_LAYERS');
        const layerId=[...layerIds][0];
        const layer=sheet.layers.find(l=>l.id===layerId);
        if(!layer||layer.locked||layer.kind!=='electrical')reject('LAYER_LOCKED');
        layers.set(n.id,layerId);
      }
      const rails=members.map(n=>({net:n,pins:n.members.map(ref=>({ref,p:this.beginWire(ref)}))}));
      const normal=rails[0].pins[0].p.normal;
      const branchAxis:0|1=normal[0]!==0?0:1,railAxis:0|1=branchAxis===0?1:0;
      for(const i of group){
        const def=defs.get(i.symbol_id);
        if(!def||def.pins.length!==2)reject('PARALLEL_REQUIRES_TWO_TERMINALS');
        const a=rails[0].pins.find(p=>p.ref.component_id===i.component_id)!.p;
        const b=rails[1].pins.find(p=>p.ref.component_id===i.component_id)!.p;
        if(a.normal[0]!==normal[0]||a.normal[1]!==normal[1]||
          b.normal[0]!==-normal[0]||b.normal[1]!==-normal[1]||
          a.at_um[railAxis]!==b.at_um[railAxis]||
          (a.at_um[branchAxis]-b.at_um[branchAxis])*normal[branchAxis]<=0)reject('PARALLEL_REQUIRES_OPPOSED_ALIGNED_PINS');
      }
      // Optional symmetry: preserve the two outer lateral pin coordinates,
      // equalize their intervals, and align both pin rows when spans match.
      // Only fully closed Nets have reached this point; locked UGO cannot move.
      const movedIds=new Set<string>();
      if(distribute){
        const ordered=[...rails[0].pins].sort((a,b)=>a.p.at_um[railAxis]-b.p.at_um[railAxis]);
        const lo=ordered[0].p.at_um[railAxis],hi=ordered.at(-1)!.p.at_um[railAxis];
        const span=hi-lo,intervals=ordered.length-1;
        if(Math.floor(span/intervals)<4000)reject('PARALLEL_GAP_TOO_SMALL');
        const rows=ordered.map(({p})=>p.at_um[branchAxis]).sort((a,b)=>a-b);
        const fixedRows=ordered.filter(({ref})=>{
          const i=group.find(v=>v.component_id===ref.component_id)!;
          return sheet.layers.find(l=>l.id===i.layer_id)?.locked;
        }).map(({p})=>p.at_um[branchAxis]);
        if(new Set(fixedRows).size>1)reject('PARALLEL_FIXED_CONFLICT');
        const row=fixedRows[0]??rows[Math.floor((rows.length-1)/2)];
        const spans=ordered.map(({ref,p})=>p.at_um[branchAxis]-
          rails[1].pins.find(t=>t.ref.component_id===ref.component_id)!.p.at_um[branchAxis]);
        if(new Set(spans).size!==1)reject('PARALLEL_UNEQUAL_PIN_SPAN');
        for(const [k,{ref,p}] of ordered.entries()){
          const lateral=lo+Math.floor(span*k/intervals);
          const delta:MutablePoint=[0,0];
          delta[railAxis]=lateral-p.at_um[railAxis];delta[branchAxis]=row-p.at_um[branchAxis];
          if(!delta[0]&&!delta[1])continue;
          const inst=group.find(i=>i.component_id===ref.component_id)!;
          if(sheet.layers.find(l=>l.id===inst.layer_id)?.locked)reject('PARALLEL_FIXED_CONFLICT');
          if(draft.project.sheets.some(s=>s.id!==sheet.id&&s.instances.some(i=>i.component_id===inst.component_id)))reject('PARALLEL_CROSS_SHEET');
          inst.origin_um=xy([inst.origin_um[0]+delta[0],inst.origin_um[1]+delta[1]]);
          for(const rail of rails){
            const pin=rail.pins.find(t=>t.ref.component_id===ref.component_id)!;
            pin.p.at_um=xy([pin.p.at_um[0]+delta[0],pin.p.at_um[1]+delta[1]]);
          }
          movedIds.add(inst.component_id);
        }
      }
      const positions=rails[0].pins.map(p=>p.p.at_um[railAxis]).sort((a,b)=>a-b);
      if(positions.some((v,i)=>i>0&&v-positions[i-1]<4000))reject('PARALLEL_GAP_TOO_SMALL');
      const boxes=sheet.instances.map(i=>{
        const d=defs.get(i.symbol_id);if(!d)reject('UNKNOWN_SYMBOL');
        return {id:i.component_id,box:translateBounds(symbolBounds(d,i.rotation_deg,i.mirror_x),i.origin_um)};
      });
      const selectedBoxes=boxes.filter(o=>comps.has(o.id));
      if(selectedBoxes.some((o,i)=>selectedBoxes.slice(i+1).some(p=>!separated(o.box,p.box,1000))))reject('PARALLEL_SYMBOL_OVERLAP');
      const rect=(p:PointUm,q:PointUm):Bounds=>({minX:Math.min(p[0],q[0]),maxX:Math.max(p[0],q[0]),minY:Math.min(p[1],q[1]),maxY:Math.max(p[1],q[1])});
      const outside=sheet.wires.filter(w=>!netIds.has(w.net_id));
      const externalBoxes=[...outside.flatMap(w=>w.vertices.slice(1).map((v,i)=>rect(w.vertices[i].at_um,v.at_um))),
        ...[...sheet.junctions,...sheet.splices].filter(n=>!netIds.has(n.net_id)).map(n=>rect(n.at_um,n.at_um)),
        ...sheet.graphics.flatMap(g=>g.points_um.slice(1).map((v,i)=>rect(g.points_um[i],v))),
        ...sheet.labels.map(l=>rect(l.at_um,l.at_um)),...sheet.texts.map(t=>rect(t.at_um,t.at_um))];
      const margin=sheet.frame.margin_um;
      if(boxes.some(({id,box})=>movedIds.has(id)&&(
        box.minX<margin||box.minY<margin||box.maxX>sheet.frame.size_um[0]-margin||box.maxY>sheet.frame.size_um[1]-margin||
        boxes.some(o=>o.id!==id&&!separated(box,o.box,1000))||externalBoxes.some(b=>!separated(box,b,1000)))))reject('PARALLEL_NO_SAFE_LAYOUT');
      const inside=(p:PointUm)=>p.every((v,i)=>v>=margin&&v<=sheet.frame.size_um[i]-margin);
      const plans:{net:string;layer:string;points:MutablePoint[];pins:PinRef[];starts:MutablePoint[]}[]=[];
      for(const rail of rails){
        const sign=rail.pins[0].p.normal[branchAxis];
        const limits=selectedBoxes.map(({box})=>branchAxis===0?(sign<0?box.minX:box.maxX):(sign<0?box.minY:box.maxY));
        const edge=sign<0?Math.floor(Math.min(...limits)):Math.ceil(Math.max(...limits));
        const sorted=[...rail.pins].sort((a,b)=>a.p.at_um[railAxis]-b.p.at_um[railAxis]);
        let plan:typeof plans[number]|undefined;
        for(const gap of [5000,10000,15000,20000,30000]){
          const line=edge+sign*gap;
          const taps=sorted.map(({p})=>{const at=xy(p.at_um);at[branchAxis]=line;return at});
          if(taps.some(p=>!inside(p))||sorted.some(p=>!inside(p.p.at_um)))continue;
          const trunk=rect(taps[0],taps.at(-1)!);
          if(boxes.some(o=>!separated(trunk,o.box,1000))||externalBoxes.some(b=>!separated(trunk,b,1000)))continue;
          if(sorted.some(({p,ref},i)=>{
            const branch=rect(p.at_um,taps[i]);
            return boxes.some(o=>o.id!==ref.component_id&&!separated(branch,o.box,1000))||
              externalBoxes.some(b=>!separated(branch,b,1000));
          }))continue;
          plan={net:rail.net.id,layer:layers.get(rail.net.id)!,points:taps,pins:sorted.map(p=>p.ref),starts:sorted.map(p=>p.p.at_um)};break;
        }
        if(!plan)reject('PARALLEL_NO_SAFE_RAIL');
        plans.push(plan);
      }
      // Validate all geometry together before committing; no visual intersection
      // between the opposite rails, whose taps are outside the selected bounds.
      const newWires:WirePolyline[]=[],newJunctions:Junction[]=[],newSplices:Splice[]=[];
      for(const plan of plans){
        const anchors=plan.points.map((at_um,i)=>{
          const end=i===0||i===plan.points.length-1;
          const id=newId(end?'splice':'junction');
          const node={id,net_id:plan.net,layer_id:plan.layer,at_um};
          if(end){newSplices.push(node);return {kind:'splice' as const,splice_id:id}}
          newJunctions.push(node);return {kind:'junction' as const,junction_id:id};
        });
        const add=(points:MutablePoint[],start:Parameters<typeof constructWire>[4],end:Parameters<typeof constructWire>[5])=>{
          const w=constructWire(newId('wire'),plan.net,plan.layer,points,start,end);
          w.needs_routing_review=true;newWires.push(w);
        };
        for(const [i,ref] of plan.pins.entries()){
          add([plan.starts[i],plan.points[i]],{kind:'pin',...ref},anchors[i]);
          if(i>0)add([plan.points[i-1],plan.points[i]],anchors[i-1],anchors[i]);
        }
      }
      // Compare actual geometry and terminal semantics independent of UUIDs
      // so repeating this command does not churn IDs or add a history entry.
      const signature=(w:WirePolyline)=>{
        const vertices=w.vertices.map(v=>[v.at_um,v.anchor.kind,v.anchor.kind==='pin'?pinKey(v.anchor):null]);
        const forward=JSON.stringify(vertices),backward=JSON.stringify([...vertices].reverse());
        return JSON.stringify([w.net_id,w.layer_id,forward<backward?forward:backward]);
      };
      const nodeSignature=(n:Junction|Splice)=>JSON.stringify([n.net_id,n.layer_id,n.at_um]);
      const sameSet=(a:string[],b:string[])=>JSON.stringify(a.sort())===JSON.stringify(b.sort());
      if(sameSet(old.map(signature),newWires.map(signature))&&
        sameSet(sheet.junctions.filter(n=>netIds.has(n.net_id)).map(nodeSignature),newJunctions.map(nodeSignature))&&
        sameSet(sheet.splices.filter(n=>netIds.has(n.net_id)).map(nodeSignature),newSplices.map(nodeSignature)))reject('NO_CHANGE');
      sheet.wires=[...outside,...newWires];
      sheet.junctions=[...sheet.junctions.filter(n=>!netIds.has(n.net_id)),...newJunctions];
      sheet.splices=[...sheet.splices.filter(n=>!netIds.has(n.net_id)),...newSplices];
      const {subset,session}=localSession(draft,this.clock);
      if(members.some(n=>session.engine.validateNet(n.id).pin_groups.length!==1))reject('PARALLEL_TOPOLOGY_MISMATCH');
      result={branches:group.length,wires:newWires.length,junctions:newJunctions.length,axis:railAxis===0?'horizontal':'vertical'};
      return materialize(draft,subset,session);
    });
    if(!result)reject('PARALLEL_NO_SAFE_RAIL');
    return result;
  }
  /** Reconstruct ONE already connected Net as a straight shared trunk.
   * Accept parallel or antiparallel signed pin normals, with branch leads
   * perpendicular to the trunk. No component moves or inferred membership.
   * A tap may have two opposite-side leads, but no overlapping same-side leads.
   * Fail closed on incomplete topology, annotations, mixed layers or blockage. */
  buildNetRail(tx:Tx,netId:string,refinement=false):{pins:number;wires:number;junctions:number;axis:'horizontal'|'vertical';lengthUm:number}{
    let result:{pins:number;wires:number;junctions:number;axis:'horizontal'|'vertical';lengthUm:number}|undefined;
    this.edit(tx,draft=>{
      const sh=draft.project.sheets[indexOfSheet(draft)];
      if(sh.instances.length>128||sh.wires.reduce((n,w)=>n+w.segments.length,0)>512)reject('LAYOUT_SIZE_LIMIT');
      if(sh.texts.length||(!refinement&&(sh.labels.length||sh.graphics.length))||
        sh.labels.length+sh.graphics.length>32||
        sh.labels.some(l=>l.role!=='visual'||l.net_id!==null||typeof l.text!=='string'||l.text.length>64)||
        sh.graphics.some(g=>!['line','polyline','source_b_continuation'].includes(g.kind)||
          g.points_um.length<2||g.points_um.length>64||!Number.isSafeInteger(g.stroke_um)||g.stroke_um<=0||g.stroke_um>10000))
        reject('LAYOUT_ANNOTATIONS_UNSUPPORTED');
      const net=draft.project.nets.find(n=>n.id===netId);
      if(!net)reject('UNKNOWN_NET');
      if(net.members.length<3||net.members.length>32)reject('RAIL_PIN_COUNT');
      const byComp=new Map(sh.instances.map(i=>[i.component_id,i]));
      if(net.members.some(p=>!byComp.has(p.component_id))||
        draft.project.sheets.some(s=>s.id!==sh.id&&[...s.wires,...s.junctions,...s.splices].some(w=>w.net_id===netId)))reject('RAIL_CROSS_SHEET');
      if(this.engine.validateNet(netId).pin_groups.length!==1)reject('RAIL_UNCONNECTED_NET');
      const prior=assessLayout(draft,this.engine);
      if(!prior.quality.complete)reject('LAYOUT_CHECK_INCOMPLETE');
      const old=sh.wires.filter(w=>w.net_id===netId);
      if(old.some(w=>[w.vertices[0],w.vertices.at(-1)!].some(v=>v.anchor.kind==='free')))reject('RAIL_DANGLING');
      if(refinement&&(!old.length||old.some(w=>!w.needs_routing_review)))reject('REFINE_REVIEW_REQUIRED');
      const labelsBefore=refinement?new Set(planComponentLabels(draft,sh.id).labels.map(l=>l.instanceId)):null;
      const layers=new Set(old.map(w=>w.layer_id));
      if(layers.size!==1||refinement&&[...sh.junctions,...sh.splices].some(n=>n.net_id===netId&&!layers.has(n.layer_id)))reject('RAIL_MIXED_LAYERS');
      const layer=[...layers][0],layerDef=sh.layers.find(l=>l.id===layer);
      if(!layerDef||layerDef.locked||!layerDef.visible||!layerDef.printable||layerDef.kind!=='electrical')reject('LAYER_LOCKED');
      const pins=net.members.map(ref=>({ref,p:this.beginWire(ref)}));
      const mixed=pins.some(({p})=>p.normal[0]!==pins[0].p.normal[0]&&p.normal[0]!==-pins[0].p.normal[0]);
      const defs=new Map(draft.project.symbol_definitions.map(d=>[d.id,d]));
      const boxes=sh.instances.map(i=>{
        const d=defs.get(i.symbol_id);if(!d)reject('UNKNOWN_SYMBOL');
        return {id:i.component_id,box:translateBounds(symbolBounds(d,i.rotation_deg,i.mirror_x),i.origin_um)};
      });
      const rect=(p:PointUm,q:PointUm):Bounds=>({minX:Math.min(p[0],q[0]),minY:Math.min(p[1],q[1]),maxX:Math.max(p[0],q[0]),maxY:Math.max(p[1],q[1])});
      const outside=sh.wires.filter(w=>w.net_id!==netId);
      const foreign=outside.flatMap(w=>w.vertices.slice(1).map((v,i)=>rect(w.vertices[i].at_um,v.at_um)));
      const fixed=[...sh.junctions,...sh.splices].filter(n=>n.net_id!==netId).map(n=>rect(n.at_um,n.at_um));
      if(refinement){
        for(const g of sh.graphics)for(let k=1;k<g.points_um.length;k++){
          const b=rect(g.points_um[k-1],g.points_um[k]),pad=g.stroke_um/2;
          fixed.push({minX:Math.floor(b.minX-pad),minY:Math.floor(b.minY-pad),maxX:Math.ceil(b.maxX+pad),maxY:Math.ceil(b.maxY+pad)});
        }
        for(const l of sh.labels){
          const p=xy(l.at_um),[lo,hi]=noteLayout({key:l.id,text:l.text,at_um:p,height_um:3500,horizontal:'left',vertical:'bottom'},p).bounds;
          fixed.push(rect(lo,hi));
        }
      }
      if(refinement&&fixed.length>640)reject('RAIL_SEARCH_LIMIT');
      const obstacles=[...foreign,...fixed];
      const margin=sh.frame.margin_um;
      const inside=(p:PointUm)=>p.every((v,i)=>v>=margin&&v<=sh.frame.size_um[i]-margin);
      if(pins.some(({p})=>!inside(p.at_um)))reject('RAIL_OUTSIDE_FRAME');
      type Lead={ref:PinRef;points:MutablePoint[];tap:number;approach:number};
      type Plan={branchAxis:0|1;line:number;leads:Lead[];length:number;bends:number;crossings:number};
      let best:Plan|undefined,feasible=false,comparisons=0;
      const budget=()=>{if(++comparisons>500000)reject('RAIL_SEARCH_LIMIT')};
      const clear=(a:Bounds,b:Bounds)=>{budget();return separated(a,b,1000)};
      // Only a perpendicular, strictly interior X crossing is allowed,
      // with more than 1 mm clearance from both segments' endpoints.
      // No overlap, touch, bend, tap, junction or splice may be crossed.
      const properX=(a:Bounds,b:Bounds)=>{
        const ah=a.minY===a.maxY&&a.minX<a.maxX,bh=b.minY===b.maxY&&b.minX<b.maxX;
        const av=a.minX===a.maxX&&a.minY<a.maxY,bv=b.minX===b.maxX&&b.minY<b.maxY;
        const h=ah&&bv?a:bh&&av?b:null,v=ah&&bv?b:bh&&av?a:null;
        return !!h&&!!v&&v.minX>h.minX+1000&&v.minX<h.maxX-1000&&h.minY>v.minY+1000&&h.minY<v.maxY-1000;
      };
      const clearForeign=(a:Bounds)=>fixed.every(o=>clear(a,o))&&
        foreign.every(o=>clear(a,o)||(refinement&&properX(a,o)));
      const crossingCount=(a:Bounds)=>foreign.reduce((n,b)=>{budget();return n+(properX(a,b)?1:0)},0);
      const axes: (0|1)[]=mixed?[0,1]:[pins[0].p.normal[0]!==0?0:1];
      for(const branchAxis of axes){
        const railAxis:0|1=branchAxis===0?1:0;
        const min=(b:Bounds,axis:0|1)=>axis===0?b.minX:b.minY;
        const max=(b:Bounds,axis:0|1)=>axis===0?b.maxX:b.maxY;
        const at=(line:number,tap:number):MutablePoint=>branchAxis===0?[line,tap]:[tap,line];
        const direct=pins.filter(({p})=>p.normal[branchAxis]!==0);
        const indirect=pins.filter(({p})=>p.normal[branchAxis]===0);
        let lo=margin,hi=sh.frame.size_um[branchAxis]-margin;
        for(const {ref,p} of direct){
          const own=boxes.find(b=>b.id===ref.component_id)!.box;
          if(p.normal[branchAxis]>0)lo=Math.max(lo,Math.ceil(max(own,branchAxis))+5000,p.at_um[branchAxis]+5000);
          else hi=Math.min(hi,Math.floor(min(own,branchAxis))-5000,p.at_um[branchAxis]-5000);
        }
        if(lo>hi)continue;
        feasible=true;
        const candidates=new Set([lo,hi,Math.floor((lo+hi)/2)]);
        for(const b of [...boxes.map(v=>v.box),...obstacles]){
          candidates.add(Math.floor(min(b,branchAxis))-1001);candidates.add(Math.ceil(max(b,branchAxis))+1001);
        }
        for(const {p} of pins)for(const offset of [-10000,-5000,5000,10000])candidates.add(p.at_um[branchAxis]+offset);
        const estimate=(line:number)=>pins.reduce((n,{p})=>n+Math.abs(line-p.at_um[branchAxis]),0);
        const lines=[...candidates].filter(v=>v>=lo&&v<=hi).sort((a,b)=>estimate(a)-estimate(b)||a-b).slice(0,mixed?32:64);
        const eq=(a:PointUm,b:PointUm)=>a[0]===b[0]&&a[1]===b[1];
        const collision=(a:Bounds,b:Bounds)=>{budget();return a.minX<=b.maxX&&b.minX<=a.maxX&&a.minY<=b.maxY&&b.minY<=a.maxY};
        const segs=(points:MutablePoint[])=>points.slice(1).map((q,i)=>({a:points[i],b:q,box:rect(points[i],q)}));
        const pathLength=(points:MutablePoint[])=>points.slice(1).reduce((n,q,i)=>n+Math.abs(q[0]-points[i][0])+Math.abs(q[1]-points[i][1]),0);
        for(const line of lines){
          const leads:Lead[]=[];
          const accept=(ref:PinRef,points:MutablePoint[],tap:number,approach:number)=>{
            if(points.some(p=>!inside(p)))return false;
            // Only the shared tap itself may touch another branch; leads
            // approaching it from the same side would overlap.
            if(leads.some(l=>l.tap===tap&&l.approach===approach))return false;
            if(leads.some(l=>l.tap!==tap&&Math.abs(l.tap-tap)<1000))return false;
            const segments=segs(points);
            for(const [i,s] of segments.entries()){
              if(boxes.some(o=>!(i===0&&o.id===ref.component_id)&&!clear(s.box,o.box))||
                !clearForeign(s.box))return false;
              for(const other of leads)for(const t of segs(other.points)){
                if(!collision(s.box,t.box))continue;
                const shared=at(line,tap);
                const intersection:Bounds={minX:Math.max(s.box.minX,t.box.minX),maxX:Math.min(s.box.maxX,t.box.maxX),
                  minY:Math.max(s.box.minY,t.box.minY),maxY:Math.min(s.box.maxY,t.box.maxY)};
                if(other.tap!==tap||intersection.minX!==intersection.maxX||intersection.minY!==intersection.maxY||
                  !eq([intersection.minX,intersection.minY],shared)||
                  !(eq(s.a,shared)||eq(s.b,shared))||!(eq(t.a,shared)||eq(t.b,shared)))return false;
              }
            }
            // Prevent a lead ending on a trunk that would run through ink.
            const positions=[...leads.map(l=>l.tap),tap];
            const trunk=rect(at(line,Math.min(...positions)),at(line,Math.max(...positions)));
            return !boxes.some(o=>!clear(trunk,o.box))&&clearForeign(trunk);
          };
          let valid=true;
          for(const {ref,p} of direct){
            const tap=p.at_um[railAxis],points=[p.at_um,at(line,tap)];
            const approach=Math.sign(p.at_um[branchAxis]-line);
            if(!accept(ref,points,tap,approach)){valid=false;break}
            leads.push({ref,points,tap,approach});
          }
          if(!valid)continue;
          // A pin parallel to the trunk first leaves its own symbol outward,
          // then turns once toward the trunk. Search bounded clear tap offsets.
          for(const {ref,p} of indirect){
            const own=boxes.find(b=>b.id===ref.component_id)!.box,sign=p.normal[railAxis];
            if(p.at_um[branchAxis]===line){valid=false;break}
            const start=p.at_um[railAxis];
            const limit=sign>0?Math.max(start+5000,Math.ceil(max(own,railAxis))+1001):
              Math.min(start-5000,Math.floor(min(own,railAxis))-1001);
            const taps=new Set([limit,limit+sign*5000,limit+sign*10000,limit+sign*20000]);
            for(const l of leads){taps.add(l.tap);taps.add(l.tap-2000);taps.add(l.tap+2000)}
            for(const o of [...boxes.map(v=>v.box),...obstacles]){
              taps.add(Math.floor(min(o,railAxis))-1001);taps.add(Math.ceil(max(o,railAxis))+1001);
            }
            const ordered=[...taps].filter(v=>(v-limit)*sign>=0&&v>=margin&&v<=sh.frame.size_um[railAxis]-margin)
              .sort((a,b)=>Math.abs(a-start)-Math.abs(b-start)||a-b).slice(0,24);
            let lead:Lead|undefined;
            for(const tap of ordered){
              const corner=xy(p.at_um);corner[railAxis]=tap;
              const points=[p.at_um,corner,at(line,tap)],approach=Math.sign(p.at_um[branchAxis]-line);
              if(accept(ref,points,tap,approach)){lead={ref,points,tap,approach};break}
            }
            if(!lead){valid=false;break}
            leads.push(lead);
          }
          if(!valid)continue;
          const positions=[...new Set(leads.map(l=>l.tap))].sort((a,b)=>a-b);
          if(positions.length<2)continue;
          // Recheck EACH final trunk interval, not just its full span:
          // an X at a newly introduced tap is never an ordinary crossing.
          const trunkParts=positions.slice(1).map((tap,k)=>rect(at(line,positions[k]),at(line,tap)));
          if(refinement&&trunkParts.some(b=>!clearForeign(b)))continue;
          const length=leads.reduce((n,l)=>n+pathLength(l.points),positions.at(-1)!-positions[0]);
          const bends=leads.reduce((n,l)=>n+l.points.length-2,0);
          const crossings=refinement?[...trunkParts,...leads.flatMap(l=>segs(l.points).map(s=>s.box))].reduce((n,b)=>n+crossingCount(b),0):0;
          if(!best||crossings<best.crossings||crossings===best.crossings&&(bends<best.bends||bends===best.bends&&length<best.length))
            best={branchAxis,line,leads,length,bends,crossings};
        }
      }
      if(!best)reject(!feasible?'RAIL_NO_COMMON_CHANNEL':'RAIL_NO_SAFE_CHANNEL');
      const {branchAxis,line,leads}=best,railAxis:0|1=branchAxis===0?1:0;
      const at=(tap:number):MutablePoint=>branchAxis===0?[line,tap]:[tap,line];
      const taps=new Map<number,Lead[]>();
      for(const lead of leads){const list=taps.get(lead.tap)??[];list.push(lead);taps.set(lead.tap,list)}
      const sorted=[...taps.keys()].sort((a,b)=>a-b);
      const wires:WirePolyline[]=[],junctions:Junction[]=[],splices:Splice[]=[];
      const anchors=sorted.map((tap,i)=>{
        const degree=taps.get(tap)!.length+(i>0?1:0)+(i<sorted.length-1?1:0);
        const id=newId(degree===2?'splice':'junction');
        const node={id,net_id:netId,layer_id:layer,at_um:at(tap)};
        if(degree===2){splices.push(node);return {kind:'splice' as const,splice_id:id}}
        junctions.push(node);return {kind:'junction' as const,junction_id:id};
      });
      const add=(points:MutablePoint[],start:Parameters<typeof constructWire>[4],end:Parameters<typeof constructWire>[5])=>{
        const w=constructWire(newId('wire'),netId,layer,points,start,end);
        w.needs_routing_review=true;wires.push(w);
      };
      for(const [i,tap] of sorted.entries()){
        for(const lead of taps.get(tap)!)add(lead.points,{kind:'pin',...lead.ref},anchors[i]);
        if(i>0)add([at(sorted[i-1]),at(tap)],anchors[i-1],anchors[i]);
      }
      const signature=(w:WirePolyline)=>{
        const vertices=w.vertices.map(v=>[v.at_um,v.anchor.kind,v.anchor.kind==='pin'?pinKey(v.anchor):null]);
        const a=JSON.stringify(vertices),b=JSON.stringify([...vertices].reverse());
        return JSON.stringify([w.net_id,w.layer_id,a<b?a:b]);
      };
      const nodes=(a:(Junction|Splice)[])=>JSON.stringify(a.map(n=>JSON.stringify([n.net_id,n.layer_id,n.at_um])).sort());
      if(JSON.stringify(old.map(signature).sort())===JSON.stringify(wires.map(signature).sort())&&
        nodes(sh.junctions.filter(n=>n.net_id===netId))===nodes(junctions)&&
        nodes(sh.splices.filter(n=>n.net_id===netId))===nodes(splices))reject('NO_CHANGE');
      sh.wires=[...outside,...wires];sh.junctions=[...sh.junctions.filter(n=>n.net_id!==netId),...junctions];
      sh.splices=[...sh.splices.filter(n=>n.net_id!==netId),...splices];
      const {subset,session}=localSession(draft,this.clock);
      if(session.engine.validateNet(netId).pin_groups.length!==1)reject('RAIL_TOPOLOGY_MISMATCH');
      result={pins:pins.length,wires:wires.length,junctions:junctions.length,axis:railAxis===0?'horizontal':'vertical',lengthUm:best.length};
      const otherStatuses=new Map(draft.project.nets.filter(n=>n.id!==netId).map(n=>[n.id,n.route_status]));
      const next=materialize(draft,subset,session);
      if(refinement)for(const n of next.project.nets)if(otherStatuses.has(n.id))n.route_status=otherStatuses.get(n.id)!;
      const after=assessLayout(next,session.engine);
      if(!preservesLayoutSafety(prior,after))reject('RAIL_UNSAFE_DIAGNOSTICS');
      if(refinement){
        if(!improvesLayout(prior,after))reject('REFINE_NO_IMPROVEMENT');
        const ns=next.project.sheets[indexOfSheet(next)];
        if(JSON.stringify(ns.wires.filter(w=>w.net_id!==netId))!==JSON.stringify(outside)||
          JSON.stringify(ns.junctions.filter(n=>n.net_id!==netId))!==JSON.stringify(sh.junctions.filter(n=>n.net_id!==netId))||
          JSON.stringify(ns.splices.filter(n=>n.net_id!==netId))!==JSON.stringify(sh.splices.filter(n=>n.net_id!==netId)))reject('REFINE_FOREIGN_GEOMETRY');
        const nextLabels=new Set(planComponentLabels(next,ns.id).labels.map(l=>l.instanceId));
        if([...labelsBefore!].some(id=>!nextLabels.has(id)))reject('REFINE_LABEL_LOSS');
      }
      return next;
    });
    if(!result)reject('RAIL_NO_SAFE_CHANNEL');
    return result;
  }
  /** Reconstruct a connected Net as a bounded obstacle-aware rectilinear
   * tree. Signed pin membership, component poses and other Nets are fixed. */
  buildNetTree(tx:Tx,netId:string,initial=false,controlled=false,strategy:TreeStrategy='default'):{pins:number;wires:number;junctions:number;lengthUm:number;bends:number}{
    let result:{pins:number;wires:number;junctions:number;lengthUm:number;bends:number}|undefined;
    this.edit(tx,draft=>{
      const sh=draft.project.sheets[indexOfSheet(draft)];
      if(sh.instances.length>128||sh.wires.reduce((n,w)=>n+w.segments.length,0)>512)reject('LAYOUT_SIZE_LIMIT');
      const refinement=!initial&&controlled;
      if(strategy!=='default'&&(!refinement||!['crossing-first','bend-first','peripheral-root'].includes(strategy)))reject('TREE_STRATEGY_UNSUPPORTED');
      // Explicit controlled refinement can protect the same bounded visual
      // annotations as initial routing. Ordinary geometry edits fail closed.
      if(sh.texts.length||(!initial&&!refinement&&(sh.labels.length||sh.graphics.length))||
        sh.labels.length+sh.graphics.length>32||
        sh.labels.some(l=>l.role!=='visual'||l.net_id!==null||typeof l.text!=='string'||l.text.length>64)||
        sh.graphics.some(g=>!['line','polyline','source_b_continuation'].includes(g.kind)||
          g.points_um.length<2||g.points_um.length>64||!Number.isSafeInteger(g.stroke_um)||g.stroke_um<=0||g.stroke_um>10000))
        reject('LAYOUT_ANNOTATIONS_UNSUPPORTED');
      const net=draft.project.nets.find(n=>n.id===netId);
      if(!net)reject('UNKNOWN_NET');
      if(net.members.length<(initial||refinement?2:3)||net.members.length>32)reject('TREE_PIN_COUNT');
      const byComp=new Map(sh.instances.map(i=>[i.component_id,i]));
      if(net.members.some(p=>!byComp.has(p.component_id))||
        draft.project.sheets.some(s=>s.id!==sh.id&&[...s.wires,...s.junctions,...s.splices].some(w=>w.net_id===netId)))reject('RAIL_CROSS_SHEET');
      const validation=this.engine.validateNet(netId);
      if(initial){
        // Only completely untouched declared Nets. Never erase partial/manual geometry.
        if(validation.status!=='unrouted'||draft.project.sheets.some(s=>[...s.wires,...s.junctions,...s.splices].some(w=>w.net_id===netId)))reject('TREE_ALREADY_ROUTED');
      }else if(validation.pin_groups.length!==1)reject('RAIL_UNCONNECTED_NET');
      const prior=assessLayout(draft,this.engine,initial?netId:undefined);
      if(!prior.quality.complete)reject('LAYOUT_CHECK_INCOMPLETE');
      const old=sh.wires.filter(w=>w.net_id===netId);
      if(old.some(w=>[w.vertices[0],w.vertices.at(-1)!].some(v=>v.anchor.kind==='free')))reject('RAIL_DANGLING');
      // Review flags are not proof of generated provenance. This explicit
      // operation is restricted to routes already marked for review.
      if(refinement&&(!old.length||old.some(w=>!w.needs_routing_review)))reject('REFINE_REVIEW_REQUIRED');
      const layers=new Set(old.map(w=>w.layer_id));
      if(!initial&&layers.size!==1)reject('RAIL_MIXED_LAYERS');
      const eligible=sh.layers.filter(l=>l.kind==='electrical'&&!l.locked&&l.visible&&l.printable);
      if(initial&&eligible.length!==1)reject('TREE_ELECTRICAL_LAYER_AMBIGUOUS');
      if(refinement&&[...sh.junctions,...sh.splices].some(n=>n.net_id===netId&&!layers.has(n.layer_id)))reject('RAIL_MIXED_LAYERS');
      const layer=initial?eligible[0].id:[...layers][0],layerDef=sh.layers.find(l=>l.id===layer);
      if(!layerDef||layerDef.locked||!layerDef.visible||!layerDef.printable||layerDef.kind!=='electrical')reject('LAYER_LOCKED');
      const defs=new Map(draft.project.symbol_definitions.map(d=>[d.id,d]));
      const inflate=(b:Bounds):Bounds=>({minX:Math.floor(b.minX)-1000,minY:Math.floor(b.minY)-1000,
        maxX:Math.ceil(b.maxX)+1000,maxY:Math.ceil(b.maxY)+1000});
      const rect=(p:PointUm,q:PointUm):Bounds=>({minX:Math.min(p[0],q[0]),minY:Math.min(p[1],q[1]),maxX:Math.max(p[0],q[0]),maxY:Math.max(p[1],q[1])});
      const boxes=sh.instances.map(i=>{
        const d=defs.get(i.symbol_id);if(!d)reject('UNKNOWN_SYMBOL');
        return {id:i.component_id,box:inflate(translateBounds(symbolBounds(d,i.rotation_deg,i.mirror_x),i.origin_um))};
      });
      const annotations:Bounds[]=[];
      for(const g of sh.graphics)for(let i=1;i<g.points_um.length;i++){
        const b=rect(xy(g.points_um[i-1]),xy(g.points_um[i])),pad=g.stroke_um/2;
        annotations.push(inflate({minX:b.minX-pad,minY:b.minY-pad,maxX:b.maxX+pad,maxY:b.maxY+pad}));
      }
      for(const l of sh.labels){
        const p=xy(l.at_um),[lo,hi]=noteLayout({key:l.id,text:l.text,at_um:p,height_um:3500,horizontal:'left',vertical:'bottom'},p).bounds;
        annotations.push(inflate(rect(lo,hi)));
      }
      if(annotations.length>128)reject('LAYOUT_ANNOTATIONS_UNSUPPORTED');
      const outside=sh.wires.filter(w=>w.net_id!==netId);
      const crossingMode=controlled;
      const foreignSegments=outside.flatMap(w=>w.vertices.slice(1).map((v,i)=>({a:xy(w.vertices[i].at_um),b:xy(v.at_um),clearance:1000})));
      const wireBoxes=foreignSegments.map(w=>inflate(rect(w.a,w.b)));
      const fixed=[...annotations,
        ...[...sh.junctions,...sh.splices].filter(n=>n.net_id!==netId).map(n=>inflate(rect(n.at_um,n.at_um)))];
      const pins=net.members.map(ref=>({ref,p:this.beginWire(ref)}));
      const makePort=({ref,p}:{ref:PinRef;p:WorldPin})=>{
        const own=boxes.find(b=>b.id===ref.component_id)!.box;
        const axis:0|1=p.normal[0]!==0?0:1,sign=p.normal[axis],tip=xy(p.at_um);
        const edge=axis===0?(sign>0?own.maxX:own.minX):(sign>0?own.maxY:own.minY);
        tip[axis]=sign>0?Math.max(edge+1,tip[axis]+2000):Math.min(edge-1,tip[axis]-2000);
        const m=sh.frame.margin_um,[w,h]=sh.frame.size_um;
        if([p.at_um,tip].some(v=>v[0]<m||v[1]<m||v[0]>w-m||v[1]>h-m))reject('TREE_PIN_LEAD_OUTSIDE_FRAME');
        return {pin:p.at_um,tip};
      };
      // Reserve the outward leads of future local declared terminals.
      // No routing path may use their space, even in crossing mode.
      const reservations:Bounds[]=[];
      if(crossingMode)for(const n of draft.project.nets){
        if(n.id===netId||!n.members.every(p=>byComp.has(p.component_id))||
          this.engine.validateNet(n.id).status!=='unrouted')continue;
        for(const ref of n.members){
          try{
            const port=makePort({ref,p:this.beginWire(ref)});
            reservations.push(inflate(rect(port.pin,port.tip)));
          }catch(e){
            if(!(e instanceof WireError)||e.code!=='TREE_PIN_LEAD_OUTSIDE_FRAME')throw e;
          }
        }
      }
      const foreign=[...fixed,...reservations,...wireBoxes];
      const ports=pins.map(({ref,p})=>{
        const port=makePort({ref,p}),lead=rect(port.pin,port.tip);
        if(boxes.some(o=>o.id!==ref.component_id&&!separated(lead,o.box,0))||
          foreign.some(o=>!separated(lead,o,0)))reject('TREE_BLOCKED_PIN_LEAD');
        return port;
      });
      const m=sh.frame.margin_um,frame={minX:m,minY:m,maxX:sh.frame.size_um[0]-m,maxY:sh.frame.size_um[1]-m};
      let plan:ReturnType<typeof planOrthogonalTree>;
      try{
        // For a route already connected, compare the weighted crossing-aware
        // path against actual existing geometry via the full Pareto gate.
        if(refinement)
          plan=planOrthogonalTree(ports,[...boxes.map(o=>o.box),...fixed,...reservations],frame,foreignSegments,true,strategy);
        else{
          plan=planOrthogonalTree(ports,[...boxes.map(o=>o.box),...foreign],frame,[],crossingMode);
          if(!plan&&crossingMode&&foreignSegments.length)
            plan=planOrthogonalTree(ports,[...boxes.map(o=>o.box),...fixed,...reservations],frame,foreignSegments,true);
        }
      }
      catch(e){if(e instanceof Error&&['TREE_SEARCH_LIMIT','TREE_GRID_LIMIT'].includes(e.message))reject(e.message);throw e}
      if(!plan)reject('TREE_NO_SAFE_ROUTE');
      const junctions:Junction[]=plan.nodes.map(at_um=>({id:newId('junction'),net_id:netId,layer_id:layer,at_um}));
      const nodeByPoint=new Map(junctions.map(j=>[j.at_um.join(','),j.id]));
      const anchor=(pin:number|null,point:PointUm):Parameters<typeof constructWire>[4]=>{
        if(pin!==null)return {kind:'pin',...pins[pin].ref};
        const id=nodeByPoint.get(point.join(','));if(!id)reject('TREE_NODE_MISMATCH');
        return {kind:'junction',junction_id:id};
      };
      const wires=plan.paths.map(p=>{
        const w=constructWire(newId('wire'),netId,layer,p.points,anchor(p.startPin,p.points[0]),anchor(p.endPin,p.points.at(-1)!));
        w.needs_routing_review=true;return w;
      });
      const signature=(w:WirePolyline)=>{
        const v=w.vertices.map(v=>[v.at_um,v.anchor.kind,v.anchor.kind==='pin'?pinKey(v.anchor):null]);
        const a=JSON.stringify(v),b=JSON.stringify([...v].reverse());
        return JSON.stringify([w.net_id,w.layer_id,a<b?a:b]);
      };
      const nodes=(v:Junction[])=>JSON.stringify(v.map(n=>n.at_um.join(',')).sort());
      if(JSON.stringify(old.map(signature).sort())===JSON.stringify(wires.map(signature).sort())&&
        nodes(sh.junctions.filter(n=>n.net_id===netId))===nodes(junctions)&&!sh.splices.some(n=>n.net_id===netId))reject('NO_CHANGE');
      sh.wires=[...outside,...wires];sh.junctions=[...sh.junctions.filter(n=>n.net_id!==netId),...junctions];
      sh.splices=sh.splices.filter(n=>n.net_id!==netId);
      const {subset,session}=localSession(draft,this.clock);
      if(session.engine.validateNet(netId).pin_groups.length!==1)reject('RAIL_TOPOLOGY_MISMATCH');
      const otherStatuses=new Map(draft.project.nets.filter(n=>n.id!==netId).map(n=>[n.id,n.route_status]));
      const next=materialize(draft,subset,session);
      if(initial||refinement)for(const n of next.project.nets)if(otherStatuses.has(n.id))n.route_status=otherStatuses.get(n.id)!;
      const after=assessLayout(next,session.engine,initial?netId:undefined);
      if(!preservesLayoutSafety(prior,after,crossingMode?netId:undefined))reject('TREE_UNSAFE_DIAGNOSTICS');
      if(refinement){
        // No trade-off: fewer crossings, bends or length, with no increase
        // in any of those metrics; signed groups and hazards remain fixed.
        if(!improvesLayout(prior,after))reject('REFINE_NO_IMPROVEMENT');
        const ns=next.project.sheets[indexOfSheet(next)];
        if(JSON.stringify(ns.wires.filter(w=>w.net_id!==netId))!==JSON.stringify(outside)||
          JSON.stringify(ns.junctions.filter(n=>n.net_id!==netId))!==JSON.stringify(sh.junctions.filter(n=>n.net_id!==netId))||
          JSON.stringify(ns.splices.filter(n=>n.net_id!==netId))!==JSON.stringify(sh.splices.filter(n=>n.net_id!==netId)))reject('REFINE_FOREIGN_GEOMETRY');
      }
      result={pins:pins.length,wires:wires.length,junctions:junctions.length,lengthUm:plan.lengthUm,bends:plan.bends};
      return next;
    });
    if(!result)reject('TREE_NO_SAFE_ROUTE');return result;
  }
  /** Explicit pre-routing placement repair: reserve space for signed
   * outward leads without weakening the printable frame or moving wired UGO. */
  prepareInitialRouting(tx:Tx):{moved:number;maxShiftUm:number}{
    let moved=0,maxShiftUm=0;
    this.edit(tx,draft=>{
      const sh=draft.project.sheets[indexOfSheet(draft)];
      if(sh.instances.length>128)reject('LAYOUT_SIZE_LIMIT');
      if(sh.wires.length||sh.junctions.length||sh.splices.length)reject('PREPARE_REQUIRES_UNROUTED_SHEET');
      if(sh.texts.length||sh.labels.length+sh.graphics.length>32||
        sh.labels.some(l=>l.role!=='visual'||l.net_id!==null||typeof l.text!=='string'||l.text.length>64)||
        sh.graphics.some(g=>!['line','polyline','source_b_continuation'].includes(g.kind)||
          g.points_um.length<2||g.points_um.length>64||!Number.isSafeInteger(g.stroke_um)||g.stroke_um<=0||g.stroke_um>10000))
        reject('LAYOUT_ANNOTATIONS_UNSUPPORTED');
      const defs=new Map(draft.project.symbol_definitions.map(d=>[d.id,d]));
      const bounds=(i:SymbolInstance)=>translateBounds(symbolBounds(defs.get(i.symbol_id)!,i.rotation_deg,i.mirror_x),i.origin_um);
      const rect=(a:PointUm,b:PointUm,pad=0):Bounds=>({minX:Math.min(a[0],b[0])-pad,minY:Math.min(a[1],b[1])-pad,maxX:Math.max(a[0],b[0])+pad,maxY:Math.max(a[1],b[1])+pad});
      const ink:Bounds[]=[];
      for(const g of sh.graphics)for(let k=1;k<g.points_um.length;k++)ink.push(rect(xy(g.points_um[k-1]),xy(g.points_um[k]),g.stroke_um/2));
      for(const l of sh.labels){
        const p=xy(l.at_um),[a,b]=noteLayout({key:l.id,text:l.text,at_um:p,height_um:3500,horizontal:'left',vertical:'bottom'},p).bounds;
        ink.push(rect(a,b));
      }
      if(ink.length>128)reject('LAYOUT_ANNOTATIONS_UNSUPPORTED');
      const before=assessLayout(draft,this.engine);
      if(!before.quality.complete)reject('LAYOUT_CHECK_INCOMPLETE');
      // 2 mm minimum signed lead plus 1 mm free channel; bounds
      // already include symbol ink, text and physical terminals.
      const m=sh.frame.margin_um+3000,[w,h]=sh.frame.size_um;
      const shift=(lo:number,hi:number,size:number)=>{
        const min=Math.ceil(m-lo),max=Math.floor(size-m-hi);
        if(min>max)reject('PREPARE_FRAME_TOO_SMALL');
        return Math.max(min,Math.min(0,max));
      };
      const changed=new Set<string>();
      for(const i of sh.instances){
        const b=bounds(i),dx=shift(b.minX,b.maxX,w),dy=shift(b.minY,b.maxY,h);
        if(!dx&&!dy)continue;
        if(!sh.layers.some(l=>l.id===i.layer_id&&l.kind==='electrical'&&l.visible&&l.printable&&!l.locked))reject('LAYER_LOCKED');
        if(draft.project.nets.some(n=>n.members.some(p=>p.component_id===i.component_id)&&
          n.members.some(p=>!sh.instances.some(j=>j.component_id===p.component_id))))reject('RAIL_CROSS_SHEET');
        i.origin_um=xy([i.origin_um[0]+dx,i.origin_um[1]+dy]);
        changed.add(i.id);moved++;maxShiftUm=Math.max(maxShiftUm,Math.abs(dx)+Math.abs(dy));
      }
      if(!moved)reject('NO_CHANGE');
      for(const i of sh.instances.filter(i=>changed.has(i.id))){
        const b=bounds(i);
        if(sh.instances.some(j=>j.id!==i.id&&!separated(b,bounds(j),1000))||
          ink.some(k=>!separated(b,k,1000)))reject('PREPARE_NO_SAFE_PLACEMENT');
      }
      const {session}=localSession(draft,this.clock);
      if(!preservesLayoutSafety(before,assessLayout(draft,session.engine)))reject('PREPARE_UNSAFE_DIAGNOSTICS');
      return draft;
    });
    return {moved,maxShiftUm};
  }
  /** Read-only pre-placement of two-terminal satellites beside signed hub
   * pins on a wholly unrouted sheet. Span is a lower-bound proxy, not a
   * claim about actual routed length. No electrical membership changes. */
  previewHubPlacement(peerAnchorIds:readonly string[]=[]):HubPlacementPreview{
    this.layoutPlan=null;
    const base=this.file,sh=base.project.sheets[indexOfSheet(base)];
    if(sh.instances.length>128)reject('LAYOUT_SIZE_LIMIT');
    if(sh.wires.length||sh.junctions.length||sh.splices.length)reject('PREPARE_REQUIRES_UNROUTED_SHEET');
    if(sh.texts.length||sh.labels.length+sh.graphics.length>32||
      sh.labels.some(l=>l.role!=='visual'||l.net_id!==null||typeof l.text!=='string'||l.text.length>64)||
      sh.graphics.some(g=>!['line','polyline','source_b_continuation'].includes(g.kind)||
        g.points_um.length<2||g.points_um.length>64||!Number.isSafeInteger(g.stroke_um)||g.stroke_um<=0||g.stroke_um>10000))
      reject('LAYOUT_ANNOTATIONS_UNSUPPORTED');
    const defs=new Map(base.project.symbol_definitions.map(d=>[d.id,d]));
    const byComp=new Map(sh.instances.map(i=>[i.component_id,i]));
    const peerAnchors=new Set(peerAnchorIds);
    if(peerAnchors.size!==peerAnchorIds.length||peerAnchorIds.some(id=>!byComp.has(id)||
      defs.get(byComp.get(id)!.symbol_id)?.pins.length!==2))reject('INVALID_PEER_ANCHORS');
    const localNets=base.project.nets.filter(n=>n.members.every(p=>byComp.has(p.component_id)));
    const rect=(a:PointUm,b:PointUm,pad=0):Bounds=>({minX:Math.min(a[0],b[0])-pad,minY:Math.min(a[1],b[1])-pad,maxX:Math.max(a[0],b[0])+pad,maxY:Math.max(a[1],b[1])+pad});
    const ink:Bounds[]=[];
    for(const g of sh.graphics)for(let k=1;k<g.points_um.length;k++)ink.push(rect(xy(g.points_um[k-1]),xy(g.points_um[k]),g.stroke_um/2));
    for(const l of sh.labels){
      const p=xy(l.at_um),[a,b]=noteLayout({key:l.id,text:l.text,at_um:p,height_um:3500,horizontal:'left',vertical:'bottom'},p).bounds;
      ink.push(rect(a,b));
    }
    if(ink.length>128)reject('LAYOUT_ANNOTATIONS_UNSUPPORTED');
    const bounds=(i:SymbolInstance)=>translateBounds(symbolBounds(defs.get(i.symbol_id)!,i.rotation_deg,i.mirror_x),i.origin_um);
    const span=(s:AuthoringSession,nets:readonly Net[]=localNets)=>nets.reduce((sum,n)=>{
      const p=n.members.map(m=>s.beginWire(m).at_um);
      return p.length?sum+Math.max(...p.map(v=>v[0]))-Math.min(...p.map(v=>v[0]))+Math.max(...p.map(v=>v[1]))-Math.min(...p.map(v=>v[1])):sum;
    },0);
    const beforeSpanUm=span(this),before=assessLayout(base,this.engine);
    if(!before.quality.complete)reject('LAYOUT_CHECK_INCOMPLETE');
    let best=new AuthoringSession(base),bestSpan=beforeSpanUm,attempted=0;
    const moved:string[]=[];
    const pairs:{leaf:PinRef;hub:PinRef;net:Net}[]=[];
    for(const net of localNets){
      if(net.members.length!==2)continue;
      for(const [leaf,hub] of [[net.members[0],net.members[1]],[net.members[1],net.members[0]]]){
        if(leaf.component_id===hub.component_id)continue;
        const a=byComp.get(leaf.component_id)!,b=byComp.get(hub.component_id)!;
        if(defs.get(a.symbol_id)?.pins.length!==2)continue;
        if(peerAnchors.size){
          if(!peerAnchors.has(hub.component_id)||peerAnchors.has(leaf.component_id))continue;
        }else if((defs.get(b.symbol_id)?.pins.length??0)<4)continue;
        if(!sh.layers.some(l=>l.id===a.layer_id&&l.kind==='electrical'&&l.visible&&l.printable&&!l.locked))continue;
        if(base.project.nets.some(n=>n.members.some(p=>p.component_id===leaf.component_id)&&!localNets.includes(n)))continue;
        if(base.project.sheets.some(s=>s.id!==sh.id&&s.instances.some(i=>i.component_id===leaf.component_id)))continue;
        pairs.push({leaf,hub,net});
      }
    }
    pairs.sort((a,b)=>span(this,[b.net])-span(this,[a.net])||a.net.id.localeCompare(b.net.id));
    const transform=(i:SymbolInstance,p:PointUm):MutablePoint=>{
      const x=i.mirror_x?-p[0]:p[0],y=p[1];
      return i.rotation_deg===0?[x,y]:i.rotation_deg===90?[-y,x]:i.rotation_deg===180?[-x,-y]:[y,-x];
    };
    const margin=sh.frame.margin_um,[w,h]=sh.frame.size_um;
    const inside=(p:PointUm)=>p[0]>=margin&&p[1]>=margin&&p[0]<=w-margin&&p[1]<=h-margin;
    for(const {leaf,hub,net} of pairs){
      if(attempted>=48)break;
      if(moved.includes(leaf.component_id))continue;
      const anchor=best.beginWire(hub),current=best.file;
      const original=current.project.sheets[indexOfSheet(current)].instances.find(i=>i.component_id===leaf.component_id)!;
      const pin=defs.get(original.symbol_id)!.pins.find(p=>p.physical_pin_number===leaf.physical_pin_number)!;
      const dirs={left:[-1,0],right:[1,0],top:[0,-1],bottom:[0,1]} as const;
      let winner:AuthoringSession|undefined,winnerSpan=bestSpan;
      const oldPairSpan=span(best,[net]);
      for(const rotation of [0,90,180,270] as const){
        const pose={...original,rotation_deg:rotation};
        const normal=transform(pose,xy(dirs[pin.side]));
        if(normal[0]!==-anchor.normal[0]||normal[1]!==-anchor.normal[1])continue;
        const offset=transform(pose,pin.at_um);
        for(const gap of [12000,20000,30000,40000]){
          if(attempted>=48)break;
          attempted++;
          if(gap>=oldPairSpan)continue;
          const doc=clone(current),sheet=doc.project.sheets[indexOfSheet(doc)];
          const inst=sheet.instances.find(i=>i.id===original.id)!;
          inst.rotation_deg=rotation;inst.origin_um=xy([anchor.at_um[0]+anchor.normal[0]*gap-offset[0],anchor.at_um[1]+anchor.normal[1]*gap-offset[1]]);
          const box=bounds(inst),m=margin+3000;
          if(box.minX<m||box.minY<m||box.maxX>w-m||box.maxY>h-m)continue;
          const others=sheet.instances.filter(i=>i.id!==inst.id);
          if(others.some(i=>!separated(box,bounds(i),1000))||ink.some(b=>!separated(box,b,1000)))continue;
          const trial=new AuthoringSession(doc),score=span(trial);
          if(score>=winnerSpan)continue;
          // Protect the future signed exit corridors of both the moved
          // component and all other declared local physical terminals.
          const allPins=localNets.flatMap(n=>n.members);
          const envelopes=new Map(sheet.instances.map(i=>[i.component_id,bounds(i)]));
          const leads=allPins.map(ref=>{
            const p=trial.beginWire(ref),b=envelopes.get(ref.component_id)!;
            const axis=p.normal[0]!==0?0:1,sign=p.normal[axis],tip=xy(p.at_um);
            const edge=axis===0?(sign>0?b.maxX:b.minX):(sign>0?b.maxY:b.minY);
            tip[axis]=sign>0?Math.max(Math.ceil(edge)+1001,tip[axis]+2000):Math.min(Math.floor(edge)-1001,tip[axis]-2000);
            return {ref,p,tip,box:rect(p.at_um,tip,1000)};
          });
          const own=leads.filter(l=>l.ref.component_id===leaf.component_id),foreign=leads.filter(l=>l.ref.component_id!==leaf.component_id);
          if(own.some(l=>!inside(l.p.at_um)||!inside(l.tip)||others.some(i=>!separated(l.box,bounds(i),0))||ink.some(b=>!separated(l.box,b,0)))||
            foreign.some(l=>!separated(l.box,box,0))||
            own.some(l=>foreign.some(k=>!separated(l.box,k.box,0))))continue;
          // The dedicated pair must also have a clear straight corridor.
          const target=trial.beginWire(leaf),corridor=rect(anchor.at_um,target.at_um,1000);
          if(others.some(i=>i.component_id!==hub.component_id&&!separated(corridor,bounds(i),0))||
            ink.some(b=>!separated(corridor,b,0))||foreign.some(l=>pinKey(l.ref)!==pinKey(hub)&&!separated(corridor,l.box,0)))continue;
          if(!preservesLayoutSafety(before,assessLayout(doc,trial.engine)))continue;
          winner=trial;winnerSpan=score;
        }
      }
      if(winner){best=winner;bestSpan=winnerSpan;moved.push(leaf.component_id)}
    }
    const token=moved.length?newId('hub-placement'):null;
    if(token){
      const next=best.file;
      if(sourceGuard(next)!==sourceGuard(base))reject('LAYOUT_TOPOLOGY_MISMATCH');
      this.layoutPlan={token,revision:this.clock,sheet:sh.id,next};
    }
    return {token,moved,beforeSpanUm,afterSpanUm:bestSpan,attempted};
  }
  /** Compare actual simultaneous routing with hub-only placement and a
   * bounded continuation along dedicated two-member peer connections.
   * The expanded placement wins only if the full routed candidate
   * Pareto-dominates the full hub-only baseline (or connects more Nets).
   * No intermediate placement or partial route is committed. */
  previewFunctionalRouting():FunctionalRoutingPreview{
    this.layoutPlan=null;
    const base=this.file,sh=base.project.sheets[indexOfSheet(base)];
    if(sh.wires.length||sh.junctions.length||sh.splices.length)reject('PREPARE_REQUIRES_UNROUTED_SHEET');
    const local=new Set(sh.instances.map(i=>i.component_id));
    const nets=base.project.nets.filter(n=>n.members.length>0&&n.members.some(p=>local.has(p.component_id)));
    if(nets.some(n=>!n.members.every(p=>local.has(p.component_id))))reject('RAIL_CROSS_SHEET');
    if(nets.length<1||nets.length>16)reject('BATCH_NET_COUNT');
    const ids=nets.map(n=>n.id),prepared=new AuthoringSession(base);
    try{prepared.prepareInitialRouting(prepared.newTransaction('functional-inset'))}
    catch(e){if(!(e instanceof WireError)||e.code!=='NO_CHANGE')throw e}
    const hub=prepared.previewHubPlacement();
    if(hub.token)prepared.applyLayoutPreview(prepared.newTransaction('functional-hub'),hub.token);
    const hubDoc=prepared.file;
    const baseline=new AuthoringSession(hubDoc),first=baseline.previewInitialBatch(ids,true);
    let attempted=first.attempted;
    let chosen=baseline,report=first,variant:'hub'|'functional'='hub';
    let moved=[...hub.moved];
    // Two bounded layers extend the chains while freezing every previous
    // anchor. Each pass remains subject to the same placement safety checks.
    if(hub.moved.length){
      const expanded=new AuthoringSession(hubDoc),anchors=[...hub.moved];
      for(let pass=0;pass<2;pass++){
        const next=expanded.previewHubPlacement(anchors);
        if(!next.token)break;
        expanded.applyLayoutPreview(expanded.newTransaction('functional-peer'),next.token);
        anchors.push(...next.moved);
      }
      if(anchors.length>hub.moved.length){
        const second=expanded.previewInitialBatch(ids,true);
        attempted+=second.attempted;
        const a=first.quality,b=second.quality;
        const dominates=b.crossings<=a.crossings&&b.bends<=a.bends&&b.lengthUm<=a.lengthUm&&
          (b.crossings<a.crossings||b.bends<a.bends||b.lengthUm<a.lengthUm);
        if(second.routed>first.routed||(second.routed===first.routed&&dominates)){
          chosen=expanded;report=second;variant='functional';moved=anchors;
        }
      }
    }
    const token=report.token?newId('functional-routing'):null;
    if(token){
      const next=chosen.layoutPreviewDocument(report.token!);
      const trial=new AuthoringSession(next);
      const before=assessLayout(base,this.engine),after=assessLayout(next,trial.engine);
      if(sourceGuard(next)!==sourceGuard(base)||ids.some(id=>trial.engine.validateNet(id).pin_groups.length!==1)||
        !before.quality.complete||!after.quality.complete||
        after.overflowIds.some(id=>!before.overflowIds.includes(id))||
        Object.keys(after.hazards).some(k=>after.hazards[k]>(before.hazards[k]??0)))reject('BATCH_TOPOLOGY_MISMATCH');
      this.layoutPlan={token,revision:this.clock,sheet:sh.id,next};
    }
    return {token,requested:ids.length,routed:report.routed,variant,moved,baseline:first.quality,quality:report.quality,attempted,outcomes:report.outcomes};
  }
  /** Route an explicit batch of untouched Nets on an isolated draft.
   * All selected Nets must succeed; no intermediate edits/history are published.
   * Try larger Nets first, then the reverse order if the first pass is blocked.
   * At most 8 Nets and 16 individual planning attempts per command. */
  routeInitialNets(tx:Tx,netIds:readonly string[]):{nets:number;wires:number;junctions:number;bends:number;lengthUm:number;attempts:number}{
    let result:{nets:number;wires:number;junctions:number;bends:number;lengthUm:number;attempts:number}|undefined;
    this.edit(tx,draft=>{
      if(netIds.length<1||netIds.length>8)reject('BATCH_NET_COUNT');
      if(new Set(netIds).size!==netIds.length)reject('BATCH_DUPLICATE_NET');
      const byId=new Map(draft.project.nets.map(n=>[n.id,n]));
      if(netIds.some(id=>!byId.has(id)))reject('UNKNOWN_NET');
      const ordered=[...netIds].sort((a,b)=>byId.get(b)!.members.length-byId.get(a)!.members.length);
      const orders=ordered.length>1?[ordered,[...ordered].reverse()]:[ordered];
      let attempts=0,lastFailure='';
      for(const order of orders){
        const trial=new AuthoringSession(draft);
        const totals={nets:0,wires:0,junctions:0,bends:0,lengthUm:0};
        let failed=false;
        for(const id of order){
          attempts++;
          try{
            const route=trial.buildNetTree(trial.newTransaction('batch-initial-route'),id,true);
            totals.nets++;totals.wires+=route.wires;totals.junctions+=route.junctions;
            totals.bends+=route.bends;totals.lengthUm+=route.lengthUm;
          }catch(e){
            if(!(e instanceof WireError))throw e;
            lastFailure=byId.get(id)!.name+': '+e.code;failed=true;break;
          }
        }
        if(failed)continue;
        const next=trial.file;
        if(sourceGuard(next)!==sourceGuard(draft)||netIds.some(id=>trial.engine.validateNet(id).pin_groups.length!==1))
          reject('BATCH_TOPOLOGY_MISMATCH');
        result={...totals,attempts};return next;
      }
      throw new WireError('BATCH_NO_SAFE_ROUTE','BATCH_NO_SAFE_ROUTE: '+lastFailure);
    });
    if(!result)reject('BATCH_NO_SAFE_ROUTE');return result;
  }
  /** Evaluate bounded whole-sheet initial routing orders on detached copies.
   * Failed Nets are skipped for diagnosis, never partially committed. Only
   * a candidate connecting every requested Net receives an Apply token. */
  previewInitialBatch(netIds:readonly string[],controlled=false):InitialBatchPreview{
    this.layoutPlan=null;
    const base=this.file,sh=base.project.sheets[indexOfSheet(base)];
    if(netIds.length<1||netIds.length>16)reject('BATCH_NET_COUNT');
    if(new Set(netIds).size!==netIds.length)reject('BATCH_DUPLICATE_NET');
    const byId=new Map(base.project.nets.map(n=>[n.id,n]));
    if(netIds.some(id=>!byId.has(id)))reject('UNKNOWN_NET');
    const local=new Set(sh.instances.map(i=>i.component_id));
    for(const id of netIds){
      const n=byId.get(id)!;
      if(n.members.length<2||n.members.length>32)reject('TREE_PIN_COUNT');
      if(n.members.some(p=>!local.has(p.component_id)))reject('RAIL_CROSS_SHEET');
      if(this.engine.validateNet(id).status!=='unrouted'||
        base.project.sheets.some(s=>[...s.wires,...s.junctions,...s.splices].some(w=>w.net_id===id)))reject('TREE_ALREADY_ROUTED');
    }
    const span=new Map(netIds.map(id=>{
      const p=byId.get(id)!.members.map(m=>this.beginWire(m).at_um);
      return [id,Math.max(...p.map(v=>v[0]))-Math.min(...p.map(v=>v[0]))+
        Math.max(...p.map(v=>v[1]))-Math.min(...p.map(v=>v[1]))] as const;
    }));
    const byCount=(a:string,b:string)=>byId.get(b)!.members.length-byId.get(a)!.members.length;
    const orders=[
      {name:'large-first',ids:[...netIds].sort((a,b)=>byCount(a,b)||a.localeCompare(b))},
      {name:'small-first',ids:[...netIds].sort((a,b)=>byCount(b,a)||a.localeCompare(b))},
      {name:'short-span-first',ids:[...netIds].sort((a,b)=>span.get(a)!-span.get(b)!||a.localeCompare(b))}
    ];
    const tried=new Set<string>();
    let attempted=0,best:{session:AuthoringSession;order:string;routed:number;outcomes:InitialBatchOutcome[];quality:LayoutQuality}|undefined;
    // Controlled mode retries the difficult Nets first on fresh copies.
    // Strict mode retains its original three orders and attempt bound.
    for(let k=0;k<5;k++){
      if(k===3){
        if(!controlled||!best||best.routed===netIds.length)break;
        const failed=best.outcomes.filter(o=>o.rejected).map(o=>o.id);
        const done=best.outcomes.filter(o=>!o.rejected).map(o=>o.id);
        orders.push({name:'blocked-first',ids:[...failed,...done]});
        orders.push({name:'blocked-first-short-span',ids:[...failed].sort((a,b)=>span.get(a)!-span.get(b)!||a.localeCompare(b)).concat(done)});
      }
      const order=orders[k];
      if(!order)break;
      const signature=JSON.stringify(order.ids);if(tried.has(signature))continue;tried.add(signature);
      const session=new AuthoringSession(base),outcomes:InitialBatchOutcome[]=[];
      let routed=0;
      for(const id of order.ids){
        attempted++;
        const n=byId.get(id)!;
        const item:InitialBatchOutcome={id,name:n.name,pins:n.members.length};
        try{session.buildNetTree(session.newTransaction('preview-batch-net'),id,true,controlled);routed++}
        catch(e){if(!(e instanceof WireError))throw e;item.rejected=e.code}
        outcomes.push(item);
      }
      const quality=assessLayout(session.file,session.engine).quality;
      if(!quality.complete||sourceGuard(session.file)!==sourceGuard(base)||
        outcomes.some(o=>!o.rejected&&session.engine.validateNet(o.id).pin_groups.length!==1))reject('BATCH_TOPOLOGY_MISMATCH');
      if(!best||routed>best.routed||(routed===best.routed&&
        (quality.crossings<best.quality.crossings||(quality.crossings===best.quality.crossings&&(quality.bends<best.quality.bends||(quality.bends===best.quality.bends&&quality.lengthUm<best.quality.lengthUm))))))
        best={session,order:order.name,routed,outcomes,quality};
      if(controlled&&best?.routed===netIds.length&&best.quality.crossings===0)break;
    }
    if(!best)reject('BATCH_NO_SAFE_ROUTE');
    const token=best.routed===netIds.length?newId('initial-batch'):null;
    if(token)this.layoutPlan={token,revision:this.clock,sheet:sh.id,next:best.session.file};
    return {token,requested:netIds.length,routed:best.routed,attempted,order:best.order,outcomes:best.outcomes,quality:best.quality};
  }
  /** Bounded read-only refinement of connected routes marked for review.
   * The entire accepted sequence is a single revision-bound proposal. */
  previewRouteRefinement(extended=false):LayoutPreview{
    this.layoutPlan=null;
    const base=this.file,sh=base.project.sheets[indexOfSheet(base)];
    if(sh.instances.length>128||sh.wires.reduce((n,w)=>n+w.segments.length,0)>512)reject('LAYOUT_SIZE_LIMIT');
    const before=assessLayout(base,this.engine);
    if(!before.quality.complete)reject('LAYOUT_CHECK_INCOMPLETE');
    let best=new AuthoringSession(base),assessment=before,attempted=0,rejected=0;
    const operations:string[]=[];
    let visibleLabels=new Set(planComponentLabels(base,sh.id).labels.map(l=>l.instanceId));
    const local=new Set(sh.instances.map(i=>i.component_id));
    const eligible=base.project.nets.filter(n=>{
      const wires=sh.wires.filter(w=>w.net_id===n.id);
      return n.members.length>=2&&n.members.length<=32&&n.members.every(p=>local.has(p.component_id))&&
        wires.length>0&&wires.every(w=>w.needs_routing_review)&&this.engine.validateNet(n.id).pin_groups.length===1;
    });
    const rank=()=>{
      const counts=new Map<string,number>();
      for(const k of assessment.crossingKeys??[]){
        const [a,b]=JSON.parse(k) as [string,string,number,number];
        counts.set(a,(counts.get(a)??0)+1);if(a!==b)counts.set(b,(counts.get(b)??0)+1);
      }
      const doc=best.file,current=doc.project.sheets[indexOfSheet(doc)];
      const length=(id:string)=>current.wires.filter(w=>w.net_id===id).reduce((sum,w)=>
        sum+w.vertices.slice(1).reduce((n,v,i)=>n+Math.abs(v.at_um[0]-w.vertices[i].at_um[0])+Math.abs(v.at_um[1]-w.vertices[i].at_um[1]),0),0);
      return [...eligible].sort((a,b)=>(counts.get(b.id)??0)-(counts.get(a.id)??0)||length(b.id)-length(a.id)||a.id.localeCompare(b.id));
    };
    type Candidate={session:AuthoringSession;after:ReturnType<typeof assessLayout>;labels:Set<string>;strategy:TreeStrategy};
    const evaluate=(n:Net,strategy:TreeStrategy):Candidate|undefined=>{
      attempted++;
      const trial=new AuthoringSession(best.file);
      try{trial.buildNetTree(trial.newTransaction('refine-review-net'),n.id,false,true,strategy)}
      catch(e){if(!(e instanceof WireError))throw e;rejected++;return}
      const file=trial.file,after=assessLayout(file,trial.engine);
      if(sourceGuard(file)!==sourceGuard(base)||!improvesLayout(assessment,after)){rejected++;return}
      const labels=new Set(planComponentLabels(file,sh.id).labels.map(l=>l.instanceId));
      if([...visibleLabels].some(id=>!labels.has(id))){rejected++;return}
      return {session:trial,after,labels,strategy};
    };
    const accept=(n:Net,candidate:Candidate)=>{
      best=candidate.session;assessment=candidate.after;visibleLabels=candidate.labels;
      operations.push('Перестроение '+n.name+(candidate.strategy==='default'?'':' ('+candidate.strategy+')'));
    };
    // Preserve the established two-pass baseline and its acceptance order.
    for(let pass=0;pass<2&&attempted<32;pass++){
      let changed=0;
      for(const n of rank()){
        if(attempted>=32)break;
        const candidate=evaluate(n,'default');
        if(candidate){accept(n,candidate);changed++}
      }
      if(!changed)break;
    }
    const baselineLimited=attempted>=32;
    let alternatives=0;
    if(extended){
      // Try different route objectives and root terminals against the same
      // current snapshot. Never apply a merely weighted-score improvement.
      const strategies:TreeStrategy[]=['crossing-first','bend-first','peripheral-root'];
      const compare=(a:Candidate,b:Candidate)=>a.after.quality.crossings-b.after.quality.crossings||
        a.after.quality.bends-b.after.quality.bends||a.after.quality.lengthUm-b.after.quality.lengthUm;
      for(const n of rank()){
        if(alternatives>=48)break;
        let winner:Candidate|undefined;
        for(const strategy of strategies){
          if(alternatives>=48)break;
          alternatives++;
          const candidate=evaluate(n,strategy);
          if(!candidate)continue;
          if(!winner||compare(candidate,winner)<0){if(winner)rejected++;winner=candidate}
          else rejected++;
        }
        if(winner)accept(n,winner);
      }
    }
    const token=operations.length?newId('route-refinement'):null;
    if(token)this.layoutPlan={token,revision:this.clock,sheet:sh.id,next:best.file};
    return {token,before:before.quality,after:assessment.quality,operations,attempted,rejected,limited:baselineLimited||alternatives>=48};
  }
  /** Align a two-pin component with multiple direct signed neighbors,
   * rebuilding all its incident routes on one detached candidate. */
  alignMultiConnected(tx:Tx,instanceId:string,scopeIds:readonly string[]=[]):{moved:string;delta:MutablePoint;wires:number}{
    let result:{moved:string;delta:MutablePoint;wires:number}|undefined;
    this.edit(tx,draft=>{
      const sh=draft.project.sheets[indexOfSheet(draft)];
      if(sh.instances.length>128||sh.wires.reduce((n,w)=>n+w.segments.length,0)>512)reject('LAYOUT_SIZE_LIMIT');
      if(sh.texts.length||sh.labels.length||sh.graphics.length)reject('LAYOUT_ANNOTATIONS_UNSUPPORTED');
      const inst=sh.instances.find(i=>i.id===instanceId);
      if(!inst)reject('UNKNOWN_INSTANCE');
      const defs=new Map(draft.project.symbol_definitions.map(d=>[d.id,d]));
      if(defs.get(inst.symbol_id)?.pins.length!==2)reject('MULTI_REQUIRES_TWO_PIN_SYMBOL');
      const layerOK=(id:string)=>sh.layers.some(l=>l.id===id&&!l.locked&&l.visible&&l.printable&&l.kind==='electrical');
      if(!layerOK(inst.layer_id))reject('LAYER_LOCKED');
      const scopeSet=new Set(scopeIds);
      if(scopeSet.size!==scopeIds.length||scopeIds.some(id=>!sh.instances.some(i=>i.id===id))||
        (scopeSet.size&&!scopeSet.has(instanceId)))reject('INVALID_GROUP');
      const allowed=new Set(sh.instances.filter(i=>!scopeSet.size||scopeSet.has(i.id)).map(i=>i.component_id));
      const incident=sh.wires.filter(w=>[w.vertices[0],w.vertices.at(-1)!].some(v=>v.anchor.kind==='pin'&&v.anchor.component_id===inst.component_id));
      if(incident.length<2||incident.length>8)reject('MULTI_WIRE_COUNT');
      const xs=new Set<number>(),ys=new Set<number>();
      const edges=incident.map(w=>{
        const a=w.vertices[0].anchor,b=w.vertices.at(-1)!.anchor;
        if(a.kind!=='pin'||b.kind!=='pin'||a.component_id===b.component_id||
          !allowed.has(a.component_id)||!allowed.has(b.component_id))reject('MULTI_EXTERNAL_OR_BRANCH');
        if(!layerOK(w.layer_id))reject('LAYER_LOCKED');
        const net=draft.project.nets.find(n=>n.id===w.net_id)!;
        if(net.members.some(p=>!allowed.has(p.component_id))||this.engine.validateNet(net.id).pin_groups.length!==1)
          reject('MULTI_EXTERNAL_OR_BRANCH');
        const moving=a.component_id===inst.component_id?a:b,other=moving===a?b:a;
        const p=this.beginWire(moving),q=this.beginWire(other);
        if(p.normal[0]===-q.normal[0]&&p.normal[1]===-q.normal[1]){
          const axis=p.normal[0]!==0?0:1,t=1-axis;
          if((q.at_um[axis]-p.at_um[axis])*p.normal[axis]>0){
            const delta=q.at_um[t]-p.at_um[t];if(delta)(t===0?xs:ys).add(delta);
          }
        }
        return {w,a,b};
      });
      const shifts:MutablePoint[]=[...[...xs].map(x=>[x,0] as MutablePoint),...[...ys].map(y=>[0,y] as MutablePoint)];
      for(const x of xs)for(const y of ys)shifts.push([x,y]);
      shifts.sort((a,b)=>Math.abs(a[0])+Math.abs(a[1])-Math.abs(b[0])-Math.abs(b[1])||a[0]-b[0]||a[1]-b[1]);
      const before=assessLayout(draft,this.engine);
      if(!before.quality.complete)reject('LAYOUT_CHECK_INCOMPLETE');
      let best:ProjectFileV2|null=null,bestAssessment=before;
      const incidentIds=new Set(incident.map(w=>w.id));
      const bounds=(i:SymbolInstance)=>translateBounds(symbolBounds(defs.get(i.symbol_id)!,i.rotation_deg,i.mirror_x),i.origin_um);
      for(const delta of shifts.slice(0,8)){
        const trial=clone(draft),ts=trial.project.sheets[indexOfSheet(trial)],m=ts.instances.find(i=>i.id===instanceId)!;
        m.origin_um=xy([m.origin_um[0]+delta[0],m.origin_um[1]+delta[1]]);
        const box=bounds(m),margin=ts.frame.margin_um;
        if(box.minX<margin||box.minY<margin||box.maxX>ts.frame.size_um[0]-margin||box.maxY>ts.frame.size_um[1]-margin)continue;
        if(ts.instances.some(i=>i.id!==m.id&&!separated(box,bounds(i),1000)))continue;
        ts.wires=ts.wires.filter(w=>!incidentIds.has(w.id));
        const rect=(p:PointUm,q:PointUm):Bounds=>({minX:Math.min(p[0],q[0]),minY:Math.min(p[1],q[1]),maxX:Math.max(p[0],q[0]),maxY:Math.max(p[1],q[1])});
        if(ts.wires.some(w=>w.vertices.slice(1).some((v,i)=>!separated(box,rect(w.vertices[i].at_um,v.at_um),1000)))||
          [...ts.junctions,...ts.splices].some(n=>!separated(box,rect(n.at_um,n.at_um),1000)))continue;
        const shift=(ref:PinRef):WorldPin=>{
          const p=this.beginWire(ref);
          return ref.component_id===m.component_id?{...p,at_um:xy([p.at_um[0]+delta[0],p.at_um[1]+delta[1]])}:p;
        };
        try{
          for(const {w,a,b} of edges){
            const points=cleanRoute(trial,a,b,shift(a),shift(b),w.net_id,undefined,false);
            const vertices=points.map((p,i)=>i===0?{...w.vertices[0],at_um:p}:i===points.length-1?{...w.vertices.at(-1)!,at_um:p}:
              {id:newId('vertex'),at_um:p,anchor:{kind:'bend' as const}});
            ts.wires.push({...w,vertices,segments:vertices.slice(1).map((v,i)=>({id:newId('segment'),from_vertex_id:vertices[i].id,to_vertex_id:v.id})),needs_routing_review:true});
          }
          const order=new Map(sh.wires.map((w,i)=>[w.id,i]));
          ts.wires.sort((a,b)=>order.get(a.id)!-order.get(b.id)!);
          const {subset,session}=localSession(trial,this.clock);
          const next=materialize(trial,subset,session);
          const affectedNets=new Set(incident.map(w=>w.net_id));
          for(const n of next.project.nets)if(!affectedNets.has(n.id))
            n.route_status=draft.project.nets.find(v=>v.id===n.id)!.route_status;
          const assessment=assessLayout(next,session.engine);
          if(!improvesLayout(before,assessment)||!improvesLayout(bestAssessment,assessment))continue;
          best=next;bestAssessment=assessment;result={moved:instanceId,delta,wires:incident.length};
        }catch(e){if(!(e instanceof WireError))throw e}
      }
      if(!best)reject('MULTI_NO_SAFE_IMPROVEMENT');return best;
    });
    if(!result)reject('MULTI_NO_SAFE_IMPROVEMENT');return result;
  }
  /** Read-only plan, using isolated AuthoringSessions and strict non-regression.
   * No edits or Undo history until applyLayoutPreview consumes the opaque token.
   * Bounded to 12 trials. Never infer an electrical connection from placement. */
  previewLayout(instanceIds:readonly string[]=[]):LayoutPreview{
    this.layoutPlan=null;
    const base=this.file,sh=base.project.sheets[indexOfSheet(base)];
    const ids=new Set(instanceIds);
    if(ids.size!==instanceIds.length||instanceIds.some(id=>!sh.instances.some(i=>i.id===id)))reject('INVALID_GROUP');
    if(sh.instances.length>128||sh.wires.reduce((n,w)=>n+w.segments.length,0)>512)reject('LAYOUT_SIZE_LIMIT');
    // Sheet-level annotation collision envelopes are not yet certified.
    // Fail closed instead of automatically moving through text or graphics.
    if(sh.texts.length||sh.labels.length||sh.graphics.length)reject('LAYOUT_ANNOTATIONS_UNSUPPORTED');
    const layerIds=new Set([...sh.instances,...sh.wires,...sh.junctions,...sh.splices].map(o=>o.layer_id));
    if(sh.layers.some(l=>layerIds.has(l.id)&&(!l.visible||!l.printable)))reject('LAYOUT_HIDDEN_LAYER_UNSUPPORTED');
    const before=assessLayout(base,this.engine);
    if(!before.quality.complete)reject('LAYOUT_CHECK_INCOMPLETE');
    let best=new AuthoringSession(base),assessment=before,attempted=0,rejected=0,limited=false;
    const operations:string[]=[];
    const group=sh.instances.filter(i=>!ids.size||ids.has(i.id));
    const byComp=new Map(group.map(i=>[i.component_id,i.id]));
    const tryEdit=(name:string,edit:(trial:AuthoringSession)=>void)=>{
      if(attempted>=12){limited=true;return}
      attempted++;
      const trial=new AuthoringSession(best.file);
      try{edit(trial)}
      catch(e){if(e instanceof WireError){rejected++;return}throw e}
      const next=trial.file;
      if(sourceGuard(next)!==sourceGuard(base))reject('LAYOUT_TOPOLOGY_MISMATCH');
      const nextAssessment=assessLayout(next,trial.engine);
      if(!improvesLayout(assessment,nextAssessment)){rejected++;return}
      best=trial;assessment=nextAssessment;operations.push(name);
    };
    // Closed parallel groups are discovered by actual two-Net membership.
    // A Net with any external physical member is deliberately not a candidate.
    const defs=new Map(base.project.symbol_definitions.map(d=>[d.id,d]));
    const netByPin=new Map(base.project.nets.flatMap(n=>n.members.map(p=>[pinKey(p),n.id] as const)));
    const buckets=new Map<string,string[]>();
    for(const i of group){
      const d=defs.get(i.symbol_id);if(!d||d.pins.length!==2)continue;
      const nets=d.pins.map(p=>netByPin.get(pinKey({component_id:i.component_id,physical_pin_number:p.physical_pin_number})));
      if(!nets[0]||!nets[1]||nets[0]===nets[1])continue;
      const key=JSON.stringify(nets.sort()),b=buckets.get(key)??[];b.push(i.id);buckets.set(key,b);
    }
    for(const g of buckets.values())if(g.length>=3&&g.length<=24){
      tryEdit('Параллельные ветви: '+g.length,s=>s.buildParallelRails(s.newTransaction('auto-parallel'),g,true));
      tryEdit('Общие магистрали: '+g.length,s=>s.buildParallelRails(s.newTransaction('auto-rails'),g));
    }
    // Multi-terminal anchors: keep the hub absolutely fixed, and straighten
    // individual two-terminal satellites attached by exactly one signed wire.
    // This does not infer the electrical function of any component or Net.
    const hubSheet=best.file.project.sheets[indexOfSheet(best.file)];
    const attached=new Map<string,Set<string>>();
    for(const w of hubSheet.wires)for(const v of [w.vertices[0],w.vertices.at(-1)!]){
      if(v.anchor.kind!=='pin')continue;
      const key=v.anchor.component_id,list=attached.get(key)??new Set<string>();
      list.add(w.id);attached.set(key,list);
    }
    const hubs=new Set(group.filter(i=>(defs.get(i.symbol_id)?.pins.length??0)>=4&&
      (attached.get(i.component_id)?.size??0)>=2).map(i=>i.component_id));
    const satellites:{hub:string;leaf:string;wire:string;distance:number;ref:string}[]=[];
    for(const w of hubSheet.wires){
      const a=w.vertices[0].anchor,b=w.vertices.at(-1)!.anchor;
      if(a.kind!=='pin'||b.kind!=='pin')continue;
      const hub=hubs.has(a.component_id)?a:hubs.has(b.component_id)?b:null;
      if(!hub)continue;
      const leaf=hub===a?b:a,inst=group.find(i=>i.component_id===leaf.component_id);
      if(!inst||defs.get(inst.symbol_id)?.pins.length!==2||attached.get(leaf.component_id)?.size!==1)continue;
      const h=best.beginWire(hub),l=best.beginWire(leaf);
      if(h.normal[0]!==-l.normal[0]||h.normal[1]!==-l.normal[1])continue;
      const axis=h.normal[0]!==0?0:1;
      if((l.at_um[axis]-h.at_um[axis])*h.normal[axis]<=0)continue;
      const transverse=1-axis;
      if(h.at_um[transverse]===l.at_um[transverse]&&w.vertices.length===2)continue;
      const ref=base.project.components.find(c=>c.id===hub.component_id)?.refdes??hub.component_id;
      satellites.push({hub:byComp.get(hub.component_id)!,leaf:inst.id,wire:w.id,
        distance:Math.abs(l.at_um[transverse]-h.at_um[transverse]),ref});
    }
    satellites.sort((a,b)=>a.distance-b.distance||a.wire.localeCompare(b.wire));
    for(const pair of satellites)tryEdit('Выводы '+pair.ref+': соседний компонент',s=>{
      const initial=s.file,anchor=initial.project.sheets[indexOfSheet(initial)].instances.find(i=>i.id===pair.hub)!;
      const result=s.alignConnectedPair(s.newTransaction('auto-hub-satellite'),[pair.hub,pair.leaf]);
      const after=s.file,stationary=after.project.sheets[indexOfSheet(after)].instances.find(i=>i.id===pair.hub);
      if(result.moved!==pair.leaf||JSON.stringify(anchor)!==JSON.stringify(stationary))reject('HUB_MUST_STAY_FIXED');
    });
    // Discover direct-wire connected components of the current trial.
    // Chain solver rejects cycles, branches, mixed axes and fixed conflicts.
    const adj=new Map(group.map(i=>[i.id,new Set<string>()]));
    const current=best.file.project.sheets[indexOfSheet(best.file)];
    for(const w of current.wires){
      const a=w.vertices[0].anchor,b=w.vertices.at(-1)!.anchor;
      if(a.kind!=='pin'||b.kind!=='pin')continue;
      const x=byComp.get(a.component_id),y=byComp.get(b.component_id);
      if(x&&y&&x!==y){adj.get(x)!.add(y);adj.get(y)!.add(x)}
    }
    const visited=new Set<string>();
    for(const id of adj.keys()){
      if(visited.has(id))continue;
      const pending=[id],connected:string[]=[];visited.add(id);
      while(pending.length){
        const v=pending.pop()!;connected.push(v);
        for(const n of adj.get(v)!)if(!visited.has(n)){visited.add(n);pending.push(n)}
      }
      if(connected.length===2)tryEdit('Выравнивание пары',s=>s.alignConnectedPair(s.newTransaction('auto-pair'),connected));
      else if(connected.length>=3&&connected.length<=32)tryEdit('Выравнивание цепочки: '+connected.length,s=>s.alignSeries(s.newTransaction('auto-series'),connected));
    }
    // R30: a two-pin device with several incident wires can be shifted
    // as a unit, even if the connected graph is not a simple series path.
    const multiSheet=best.file.project.sheets[indexOfSheet(best.file)];
    const degree=new Map<string,number>();
    for(const w of multiSheet.wires)for(const v of [w.vertices[0],w.vertices.at(-1)!]){
      if(v.anchor.kind==='pin')degree.set(v.anchor.component_id,(degree.get(v.anchor.component_id)??0)+1);
    }
    let multiAttempts=0;
    for(const i of group){
      if(attempted>=9||multiAttempts>=3)break;
      if(defs.get(i.symbol_id)?.pins.length!==2||(degree.get(i.component_id)??0)<2)continue;
      multiAttempts++;
      tryEdit('Совместное выравнивание '+(base.project.components.find(c=>c.id===i.component_id)?.refdes??i.id),
        s=>s.alignMultiConnected(s.newTransaction('auto-multi-align'),i.id,instanceIds));
    }
    // Try shared single-Net trunks only when every physical member belongs
    // to the selected scope. The quality gate may reject longer rail routes.
    const netCandidates=base.project.nets.filter(n=>n.members.length>=3&&n.members.length<=32&&
      n.members.every(p=>byComp.has(p.component_id))).sort((a,b)=>b.members.length-a.members.length||a.id.localeCompare(b.id));
    for(const n of netCandidates){
      if(attempted>=11){limited=true;break}
      tryEdit('Магистраль '+n.name,s=>s.buildNetRail(s.newTransaction('auto-net-rail'),n.id));
      if(attempted<11)tryEdit('Дерево '+n.name,s=>s.buildNetTree(s.newTransaction('auto-net-tree'),n.id));
    }
    tryEdit('Упрощение проводников',s=>s.simplifyRoutes(s.newTransaction('auto-cleanup'),instanceIds));
    const token=operations.length?newId('layout'):null;
    if(token)this.layoutPlan={token,revision:this.clock,sheet:sh.id,next:best.file};
    return {token,before:before.quality,after:assessment.quality,operations,attempted,rejected,limited};
  }
  layoutPreviewDocument(token:string):ProjectFileV2{
    const plan=this.layoutPlan;
    if(!plan||plan.token!==token)reject('LAYOUT_PLAN_UNKNOWN');
    if(plan.revision!==this.clock||plan.sheet!==this.current.workspace.active_sheet_id)reject('STALE_REVISION');
    return clone(plan.next);
  }
  applyLayoutPreview(tx:Tx,token:string):void{
    const plan=this.layoutPlan;
    if(!plan||plan.token!==token)reject('LAYOUT_PLAN_UNKNOWN');
    if(plan.revision!==this.clock||plan.sheet!==this.current.workspace.active_sheet_id)reject('STALE_REVISION');
    this.edit(tx,draft=>{
      if(sourceGuard(draft)!==sourceGuard(plan.next))reject('LAYOUT_TOPOLOGY_MISMATCH');
      return clone(plan.next);
    });
    this.layoutPlan=null;
  }
  discardLayoutPreview(token:string):void{
    if(this.layoutPlan?.token===token)this.layoutPlan=null;
  }
  /** Explicit post-processing: only existing signed pin-to-pin wires.
   * Never increase length or turns, never introduce wire intersections, never
   * change any component pose, Net membership, wire ID or terminal vertex ID.
   * One transaction for the whole bounded scope, Undo restores the exact file. */
  simplifyRoutes(tx:Tx,instanceIds:readonly string[]=[]):{checked:number;changed:number;removedBends:number;removedLengthUm:number}{
    const stats={checked:0,changed:0,removedBends:0,removedLengthUm:0};
    this.edit(tx,draft=>{
      const sh=draft.project.sheets[indexOfSheet(draft)];
      const selected=new Set(instanceIds);
      if(selected.size!==instanceIds.length||instanceIds.some(id=>!sh.instances.some(i=>i.id===id)))reject('INVALID_GROUP');
      if(sh.instances.length>256||sh.wires.reduce((n,w)=>n+w.segments.length,0)>2048)reject('LAYOUT_SIZE_LIMIT');
      const comps=new Set(sh.instances.filter(i=>selected.has(i.id)).map(i=>i.component_id));
      const eligible=sh.wires.filter(w=>{
        const a=w.vertices[0].anchor,b=w.vertices.at(-1)!.anchor;
        return a.kind==='pin'&&b.kind==='pin'&&(!selected.size||(comps.has(a.component_id)&&comps.has(b.component_id)))&&
          !sh.layers.find(l=>l.id===w.layer_id)?.locked;
      });
      if(eligible.length>64)reject('LAYOUT_SIZE_LIMIT');
      const metric=(points:readonly PointUm[])=>{
        let turns=0,length=0;
        let prior:MutablePoint|null=null;
        const lens:number[]=[];
        for(let i=1;i<points.length;i++){
          const p=points[i-1],q=points[i];
          const dx=q[0]-p[0],dy=q[1]-p[1],n:MutablePoint=[Math.sign(dx),Math.sign(dy)];
          const l=Math.abs(dx)+Math.abs(dy);length+=l;
          if(prior&&(n[0]!==prior[0]||n[1]!==prior[1]))turns++;
          prior=n;lens.push(l);
        }
        const imbalance=turns===2&&points.length===4?Math.abs(lens[0]-lens[2]):0;
        return {turns,length,imbalance};
      };
      // Re-evaluate obstacles after each accepted route, preserving deterministic order.
      for(const w of eligible){
        stats.checked++;
        const start=w.vertices[0].anchor,end=w.vertices.at(-1)!.anchor;
        if(start.kind!=='pin'||end.kind!=='pin')continue;
        const a=this.beginWire(start),b=this.beginWire(end);
        let points:MutablePoint[];
        try{points=cleanRoute(draft,start,end,a,b,w.net_id,w.id,false);}
        catch(e){if(e instanceof WireError&&e.code==='REROUTE_REQUIRED')continue;throw e;}
        const oldPoints=w.vertices.map(v=>v.at_um),old=metric(oldPoints),next=metric(points);
        if(next.turns>old.turns||next.length>old.length)continue;
        const improved=next.turns<old.turns||next.length<old.length||points.length<oldPoints.length||
          (next.turns===old.turns&&next.length===old.length&&points.length===oldPoints.length&&next.imbalance<old.imbalance);
        if(!improved)continue;
        const vertices:WirePolyline['vertices']=[
          {...w.vertices[0],at_um:points[0]},
          ...points.slice(1,-1).map(at_um=>({id:newId('vertex'),at_um,anchor:{kind:'bend'} as const})),
          {...w.vertices.at(-1)!,at_um:points.at(-1)!}];
        w.vertices=vertices;
        w.segments=vertices.slice(1).map((v,i)=>({id:newId('segment'),from_vertex_id:vertices[i].id,to_vertex_id:v.id}));
        w.needs_routing_review=true;
        stats.changed++;stats.removedBends+=old.turns-next.turns;stats.removedLengthUm+=old.length-next.length;
      }
      if(!stats.changed)reject('NO_CHANGE');
      const {subset,session}=localSession(draft,this.clock);
      return materialize(draft,subset,session);
    });
    return stats;
  }
  moveSegment(tx:Tx,wireId:string,segmentId:string,deltaUm:number):void{
    this.wireEdit(tx,eng=>eng.moveSegmentById(eng.newTransaction('move-segment'),
      wireId,segmentId,deltaUm));
  }
  createJunction(tx:Tx,segments:readonly {wire_id:string;segment_id:string}[]):void{
    this.wireEdit(tx,eng=>{
      let n=1;
      while(eng.snapshot.junctions.some(j=>j.id==='manual-junction-'+n))n++;
      eng.connectCrossingSegmentsById(eng.newTransaction('junction'),segments,
        'manual-junction-'+n);
    });
  }
  deleteWire(tx:Tx,wireId:string):void{
    this.wireEdit(tx,eng=>eng.deleteWire(eng.newTransaction('delete-wire'),wireId));
  }
  deleteComponent(tx:Tx,componentId:string):void{
    this.edit(tx,draft=>{
      if(!draft.project.components.some(c=>c.id===componentId))
        reject('UNKNOWN_COMPONENT');
      if(draft.project.sheets.some(s=>s.wires.some(w=>w.vertices.some(v=>
        v.anchor.kind==='pin'&&v.anchor.component_id===componentId))))
        reject('REROUTE_REQUIRED');
      draft.project.components=draft.project.components.filter(c=>c.id!==componentId);
      for(const sh of draft.project.sheets)
        sh.instances=sh.instances.filter(i=>i.component_id!==componentId);
      draft.project.nets=draft.project.nets.flatMap(n=>{
        const members=n.members.filter(p=>p.component_id!==componentId);
        return members.length?[{...n,members,route_status:'unrouted' as const}]:[];
      });
      expectedCounts(draft);return draft;
    });
  }
  undo():boolean {
    if(!this.undoFiles.length)return false;
    const prior=this.undoFiles[this.undoFiles.length-1];
    const engine=localSession(prior,this.clock+1).session.engine;
    this.redoFiles.push(this.current);
    this.current=this.undoFiles.pop()!;this.engine=engine;this.clock++;
    return true;
  }
  redo():boolean {
    if(!this.redoFiles.length)return false;
    const next=this.redoFiles[this.redoFiles.length-1];
    const engine=localSession(next,this.clock+1).session.engine;
    this.undoFiles.push(this.current);
    this.current=this.redoFiles.pop()!;this.engine=engine;this.clock++;
    return true;
  }
}
