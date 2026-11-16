/** CHAT 7 — fail-closed single-sheet ProjectFileV2 ↔ manual wire graph adapter.
 * Only route geometry, status and explicitly approved symbol transforms are written.
 * Full ProjectFileV2 must also pass CHAT6 Python schema+semantic validation at IPC.
 * No source Nets, manufacturer pins, UGO, provenance, b graphics or workspace rewrites.
 */
import {
  ManualWireEngine, WireError, type WiringSnapshot, type Component, type PinRef,
  type PointUm, type WirePolyline, type Junction, type Splice
} from './manual-wire.js';

type Rotation = 0|90|180|270;
type SymbolPinV2 = { physical_pin_number: string; at_um: readonly [number,number]; side:'left'|'right'|'top'|'bottom' };
type InstanceV2 = {id:string;component_id:string;symbol_id:string;origin_um:readonly [number,number];rotation_deg:Rotation;mirror_x:boolean;layer_id:string};
type NetV2 = {id:string;name:string;members:PinRef[];route_status:'unrouted'|'partial'|'verified'};

/** Structural subset of CHAT6 contract.ts ProjectFileV2, without duplicating its entire schema.
 * All additional fields are retained by generic T and checked by the canonical validator.
 */
export type WireProjectV2 = {
  format:'gscad-project'; format_version:2;
  project: {
    id:string;
    part_definitions:Array<{id:string;physical_pins:Array<{number:string}>}>;
    symbol_definitions:Array<{id:string;part_id:string;pins:SymbolPinV2[]}>;
    components:Array<{id:string;part_id:string}>;
    nets:NetV2[];
    sheets:Array<{
      id:string; layers:Array<{id:string;kind:string}>;
      instances:InstanceV2[]; wires:WirePolyline[]; junctions:Junction[]; splices:Splice[];
    }>;
  };
};
export type WireImportOptions = { sheet_id:string; revision:number; source_topology_hash:string };

function reject(code:string, message:string):never { throw new WireError(code,message); }
function at(p:readonly [number,number]):PointUm {
  if(!Array.isArray(p)||p.length!==2||!p.every(x=>Number.isSafeInteger(x)&&Math.abs(x)<=1_000_000_000))
    reject('COORDINATE_RANGE','Expected exact safe integer micrometre tuple');
  return [p[0],p[1]];
}
function key(p:PinRef):string { return JSON.stringify([p.component_id,p.physical_pin_number]); }
function freezeSource(project:WireProjectV2['project']) {
  return JSON.stringify({
    id:project.id,
    parts:project.part_definitions,
    symbols:project.symbol_definitions,
    components:project.components,
    nets:project.nets.map(n=>({id:n.id,name:n.name,members:n.members}))
  });
}
function routeGuard(file:WireProjectV2, sheetId:string):string {
  const sheet=file.project.sheets.find(s=>s.id===sheetId);
  if(!sheet)reject('UNKNOWN_SHEET','Selected sheet no longer exists');
  return JSON.stringify({
    source:freezeSource(file.project),
    nets:file.project.nets,
    instances:sheet.instances,
    wires:sheet.wires,junctions:sheet.junctions,splices:sheet.splices
  });
}
function resolveSnapshot(file:WireProjectV2, opt:WireImportOptions):WiringSnapshot {
  if(file?.format!=='gscad-project'||file.format_version!==2)
    reject('SCHEMA_VERSION','Expected validated gscad-project v2 document');
  if(file.project.sheets.length!==1)
    reject('MULTISHEET_UNSUPPORTED','ManualWireEngine is scoped to one electrical sheet; no cross-sheet net joining');
  if(!opt.sheet_id||typeof opt.source_topology_hash!=='string'||!opt.source_topology_hash)
    reject('MISSING_SOURCE_GUARD','Canonical source topology hash and sheet_id are required');
  if(!Number.isSafeInteger(opt.revision)||opt.revision<0)
    reject('REVISION','Nonnegative canonical command revision required');
  const sheet=file.project.sheets.find(s=>s.id===opt.sheet_id);
  if(!sheet)reject('UNKNOWN_SHEET',opt.sheet_id);
  const componentsById=new Map(file.project.components.map(c=>[c.id,c]));
  const parts=new Map(file.project.part_definitions.map(p=>[p.id,p]));
  const symbols=new Map(file.project.symbol_definitions.map(s=>[s.id,s]));
  const seenComponents=new Set<string>();
  const flattened:Component[]=[];
  for(const inst of sheet.instances){
    if(seenComponents.has(inst.component_id))
      reject('MULTI_UNIT_UNSUPPORTED','Multiple symbol instances for same component require explicit sheet/unit adapter');
    seenComponents.add(inst.component_id);
    const comp=componentsById.get(inst.component_id);
    const symbol=symbols.get(inst.symbol_id);
    const part=comp&&parts.get(comp.part_id);
    if(!comp||!symbol||!part||symbol.part_id!==comp.part_id)
      reject('PART_SYMBOL_MISMATCH','Instanced symbol must belong to installed manufacturer part');
    const physical=new Set(part.physical_pins.map(p=>p.number));
    const pins=symbol.pins.map(p=>{
      if(!physical.has(p.physical_pin_number))
        reject('SYMBOL_UNKNOWN_PIN','Graphic terminal is not a manufacturer physical pin');
      return {
        component_id:inst.component_id,physical_pin_number:p.physical_pin_number,
        local_at_um:at(p.at_um),outward:p.side==='top'?'up':p.side==='bottom'?'down':p.side
      } as Component['pins'][number];
    });
    flattened.push({
      id:inst.component_id,origin_um:at(inst.origin_um),rotation:inst.rotation_deg,
      mirror_x:inst.mirror_x,pins
    });
  }
  const displayed=new Set(flattened.flatMap(c=>c.pins.map(key)));
  for(const n of file.project.nets)for(const pref of n.members)
    if(!displayed.has(key(pref)))
      reject('UNPLACED_NET_PIN','Source Net references a physical pin with no placed symbol contact on this sheet');
  const electrical=new Set(sheet.layers.filter(l=>l.kind==='electrical').map(l=>l.id));
  for(const obj of [...sheet.wires,...sheet.junctions,...sheet.splices])
    if(!electrical.has(obj.layer_id))
      reject('NON_ELECTRICAL_LAYER','Wire graph node belongs to a non-electrical or missing layer');
  return {
    schema_version:2,project_id:file.project.id,revision:opt.revision,
    source_topology_hash:opt.source_topology_hash,components:flattened,
    nets:file.project.nets.map(n=>({id:n.id,literal_source_name:n.name,members:structuredClone(n.members)})),
    wires:structuredClone(sheet.wires),junctions:structuredClone(sheet.junctions),
    splices:structuredClone(sheet.splices)
  };
}

/** Owns the CAS boundary for one editor-local document snapshot. Do not cache across
 * concurrent IPC edits: the caller must still compare canonical document SHA/generation.
 */
export class ProjectV2WireSession<T extends WireProjectV2> {
  readonly engine:ManualWireEngine;
  readonly sheet_id:string;
  readonly source_topology_hash:string;
  private baseline:string;
  private readonly immutableSource:string;
  private readonly originalPinDefs:string;
  constructor(file:T, options:WireImportOptions) {
    const snapshot=resolveSnapshot(file,options);
    this.engine=new ManualWireEngine(snapshot); // rejects 1µm drift/wrong-Net/normal/dots
    this.sheet_id=options.sheet_id;
    this.source_topology_hash=options.source_topology_hash;
    this.baseline=routeGuard(file,this.sheet_id);
    this.immutableSource=freezeSource(file.project);
    this.originalPinDefs=JSON.stringify(snapshot.components.map(c=>({id:c.id,pins:c.pins})));
  }

  /** Emits a NEW project object; the supplied document is never mutated.
   * Requires a source topology lock and a locally unchanged route/instance baseline.
   */
  materialize(file:T):T {
    if(file.project.id!==this.engine.snapshot.project_id ||
       routeGuard(file,this.sheet_id)!==this.baseline)
      reject('STALE_PROJECT','Document routing/instances/source changed after wire session loaded');
    const snapshot=this.engine.snapshot;
    if(snapshot.source_topology_hash!==this.source_topology_hash||
       freezeSource(file.project)!==this.immutableSource)
      reject('SOURCE_TOPOLOGY_MISMATCH','Source names and PinRef membership must remain immutable');
    if(JSON.stringify(snapshot.nets)!==JSON.stringify(file.project.nets.map(n=>({
      id:n.id,literal_source_name:n.name,members:n.members
    })))||JSON.stringify(snapshot.components.map(c=>({id:c.id,pins:c.pins})))!==this.originalPinDefs)
      reject('SOURCE_TOPOLOGY_MISMATCH','Wire commands cannot redefine source pins or Nets');
    const out=structuredClone(file);
    const sheet=out.project.sheets.find(s=>s.id===this.sheet_id)!;
    const byId=new Map(snapshot.components.map(c=>[c.id,c]));
    for(const inst of sheet.instances) {
      const c=byId.get(inst.component_id);
      if(!c)reject('UNPLACED_NET_PIN','Missing component from wiring session');
      inst.origin_um=at(c.origin_um);
      inst.rotation_deg=c.rotation;
      inst.mirror_x=c.mirror_x;
    }
    sheet.wires=structuredClone(snapshot.wires);
    sheet.junctions=structuredClone(snapshot.junctions);
    sheet.splices=structuredClone(snapshot.splices);
    for(const net of out.project.nets)net.route_status=this.engine.validateNet(net.id).status;
    this.baseline=routeGuard(out,this.sheet_id);
    return out;
  }
}

export function loadProjectWires<T extends WireProjectV2>(
  file:T, options:WireImportOptions
):ProjectV2WireSession<T> {
  return new ProjectV2WireSession(file,options);
}
