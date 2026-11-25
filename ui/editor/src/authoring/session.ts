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
import {curveGeometry} from '../model/curves.mjs';
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
function cleanRoute(file:ProjectFileV2,start:PinRef,end:PinRef,a:WorldPin,b:WorldPin,netId:string,ignoreWire?:string):MutablePoint[]{
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
 catch(e){if(!(e instanceof WireError)||e.code!=='REROUTE_REQUIRED')throw e;}
 return routeManhattan(xy(a.at_um),xy(b.at_um),xy(a.normal),xy(b.normal),2000,{...opts,accept:p=>accept(p,true)});
}
function expectedCounts(file:ProjectFileV2):void {
  const p=file.project;
  p.provenance.expected_counts={
    components:p.components.length,nets:p.nets.length,
    memberships:p.nets.reduce((count,n)=>count+n.members.length,0),
    da1_pins:0,b_graphics:0
  };
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
  const actual={components:p.components.length,nets:p.nets.length,
    memberships:p.nets.reduce((n,net)=>n+net.members.length,0),
    da1_pins:0,b_graphics:0};
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
