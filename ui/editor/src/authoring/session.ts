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
  Component, SymbolDefinition, Net
} from '../model/contract';
import {
  ManualWireEngine, WireError, constructWire, type WiringSnapshot,
  type PointUm as MutablePoint, type PinRef as MutablePin
} from '../wires/manual-wire';
import {loadProjectWires} from '../wires/project-v2-adapter';
import {projectToCanvasScene} from '../canvas/scene-projection.mjs';
import {AUTHORING_PARTS, AUTHORING_SYMBOLS} from './catalog';

type Tx = {project_id:string;revision:number;source_guard:string;command_id:string};
const SOURCE_ZERO='0000000000000000000000000000000000000000';
const clone=<T>(v:T):T=>structuredClone(v);
const reject=(code:string):never=>{throw new WireError(code,code)};
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
    layers:[{id:'layer-electric',name:'Electrical',kind:'electrical',visible:true,printable:true,locked:false}],
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
  const parts=new Map(p.part_definitions.map(v=>[v.id,v]));
  const symbols=new Map(p.symbol_definitions.map(v=>[v.id,v]));
  const comps=new Map(p.components.map(v=>[v.id,v]));
  const refdes=new Set<string>();
  for(const comp of p.components){
    checkId(comp.refdes,'INVALID_REFDES');
    if(!/^[A-Za-z][A-Za-z0-9_-]{0,31}$/.test(comp.refdes))reject('INVALID_REFDES');
    if(refdes.has(comp.refdes))reject('DUPLICATE_REFDES');refdes.add(comp.refdes);
    if(!parts.has(comp.part_id))reject('UNKNOWN_PART');
  }
  const owned=new Set<string>();
  for(const net of p.nets) {
    checkId(net.name,'INVALID_NET_NAME');
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
  const instances=new Set<string>(),placed=new Set<string>();
  for(const sh of p.sheets){
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
  if(JSON.stringify(actual)!==JSON.stringify(p.provenance.expected_counts))
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
    if(tx.project_id!==this.current.project.id||tx.source_guard!==sourceGuard(this.current))
      reject('SOURCE_MISMATCH');
    if(tx.revision!==this.clock)reject('STALE_REVISION');
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
      let n=1;
      while(draft.project.components.some(c=>c.refdes===part.reference_prefix+n))n++;
      const refdes=part.reference_prefix+n;
      const comp:Component={id:newId('comp'),source_refdes:refdes,refdes,
        part_id:part.id,value:part.reference_prefix==='R'?'1к':'100н'};
      const instance:SymbolInstance={id:newId('inst'),component_id:comp.id,
        symbol_id:symbolId,origin_um:position,rotation_deg:0,mirror_x:false,
        layer_id:'layer-electric'};
      const sheet=draft.project.sheets[indexOfSheet(draft)];
      draft.project.components.push(comp);sheet.instances.push(instance);
      expectedCounts(draft);added=instance.id;return draft;
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
  move(tx:Tx,componentId:string,position:readonly number[]):void{
    const target=xy(position);
    this.wireEdit(tx,eng=>{eng.moveComponent(eng.newTransaction('move-symbol'),componentId,target);});
  }
  rotate(tx:Tx,componentId:string):void{
    this.wireEdit(tx,eng=>{
      const comp=eng.snapshot.components.find(c=>c.id===componentId);
      if(!comp)reject('UNKNOWN_COMPONENT');
      eng.rotateAndReanchor(eng.newTransaction('rotate-symbol'),componentId,
        ((comp.rotation+90)%360) as 0|90|180|270,false);
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
        const id=1+draft.project.nets.length;
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
