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
  ManualWireEngine, WireError, constructWire, type WiringSnapshot,
  type PointUm as MutablePoint, type PinRef as MutablePin
} from '../wires/manual-wire';
import {loadProjectWires} from '../wires/project-v2-adapter';
import {projectToCanvasScene} from '../canvas/scene-projection.mjs';
import {AUTHORING_PARTS, AUTHORING_SYMBOLS,catalogDefaultValue} from './catalog';

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
  for(const g of symbol.graphics)for(const p of g.points_um)include(p,g.stroke_um/2);
  return bounds;
}
function translateBounds(b:Bounds,p:readonly number[]):Bounds {
  return {minX:b.minX+p[0],minY:b.minY+p[1],maxX:b.maxX+p[0],maxY:b.maxY+p[1]};
}
function separated(a:Bounds,b:Bounds,clearance:number):boolean {
  return a.maxX+clearance<=b.minX||b.maxX+clearance<=a.minX||
    a.maxY+clearance<=b.minY||b.maxY+clearance<=a.minY;
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
  connect(tx:Tx,start:PinRef,end:PinRef,bends:readonly PointUm[]=[]):void{
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
      const points=bends.length?addRouteBends(from,to,bends):
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
