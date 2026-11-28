/** VISUAL CAD CHAT 6 — prospective editor domain contract, v2.
 *  Integers are micrometres; runtime must validate Number.isSafeInteger at IPC.
 *  Electrical Net membership NEVER derives from Canvas/ReactFlow/tldraw edges.
 *  The full JSON Schema + semantic validator are authoritative.
 */
export type ID = string;
export type PointUm = readonly [x: number, y: number];
export type Rotation = 0 | 90 | 180 | 270;
export type ElectricalType = 'passive' | 'input' | 'output' | 'bidirectional' |
  'power_input' | 'power_output' | 'open_collector' | 'unspecified';
export interface PhysicalPin { number: string; name: string; electrical_type: ElectricalType }
export interface PartDefinition { id: ID; reference_prefix: string; symbol_ids: ID[]; physical_pins: PhysicalPin[] }
export interface SymbolPin { physical_pin_number: string; at_um: PointUm; side: 'left'|'right'|'top'|'bottom' }
export interface Primitive { kind: 'line'|'rect'|'polyline'|'circle'; points_um: PointUm[]; stroke_um: number }
export interface SymbolDefinition { id: ID; part_id: ID; revision: number; status:'draft'|'approved'|'deprecated'; pins:SymbolPin[]; graphics:Primitive[]; standard_refs:string[] }
export interface Component { id: ID; source_refdes: string; refdes: string; part_id: ID; value: string }
export interface PinRef { component_id: ID; physical_pin_number: string }
export interface Net { id: ID; name: string; members: PinRef[]; route_status:'unrouted'|'partial'|'verified' }
export interface SymbolInstance { id: ID; component_id: ID; symbol_id: ID; origin_um: PointUm; rotation_deg: Rotation; mirror_x:boolean; layer_id: ID }
export type WireEndpoint =
  | {kind:'pin'; component_id:ID; physical_pin_number:string}
  | {kind:'junction'; junction_id:ID}
  | {kind:'splice'; splice_id:ID}
  | {kind:'free'; free_id:ID}
  | {kind:'bend'};
export interface WireVertex {id:ID; at_um:PointUm; anchor:WireEndpoint}
export interface WireSegment {id:ID; from_vertex_id:ID; to_vertex_id:ID}
export interface WirePolyline {id:ID; net_id:ID; layer_id:ID; vertices:WireVertex[]; segments:WireSegment[]; mode:'orthogonal'; needs_routing_review?:boolean}
export interface Splice { id:ID; net_id:ID; at_um:PointUm; layer_id:ID }
export interface Junction {id:ID; net_id:ID; at_um:PointUm; layer_id:ID}
export interface Layer {id:ID; name:string; kind:'electrical'|'annotation'|'drawing'|'diagnostics'; visible:boolean; printable:boolean; locked:boolean}
export interface SheetFrame {size_um:PointUm; margin_um:number; paper:string}
export interface TitleBlock {designation:string; title:string; organization:string; revision:string; sheet_number:number}
export interface SheetText {id:ID; layer_id:ID; text:string; at_um:PointUm; rotation_deg:Rotation; height_um:number}
export interface Label {id:ID; layer_id:ID; text:string; at_um:PointUm; role:'visual'|'net_annotation'; net_id:ID|null}
export interface Graphic {id:ID; layer_id:ID; kind:'line'|'polyline'|'source_b_continuation'; points_um:PointUm[]; stroke_um:number}
export interface Sheet {id:ID; name:string; index:number; frame:SheetFrame; title_block:TitleBlock; layers:Layer[]; instances:SymbolInstance[]; wires:WirePolyline[]; junctions:Junction[]; splices:Splice[]; texts:SheetText[]; labels:Label[]; graphics:Graphic[]}
export interface Provenance {source_sha:string; source_path:string; status:'source_traced_unapproved'|'source_excerpt_unapproved'|'synthetic'; expected_counts:{components:number; nets:number; memberships:number; da1_pins:number; b_graphics:number}}
export interface ProjectSettings {units:'um'; grid_visible:boolean; snap_enabled:boolean; grid_step_um:number; orthogonal_wires:boolean}
export interface Project {id:ID; title:string; part_definitions:PartDefinition[]; symbol_definitions:SymbolDefinition[]; components:Component[]; nets:Net[]; sheets:Sheet[]; settings:ProjectSettings; provenance:Provenance}
export interface Workspace {active_sheet_id:ID; camera_center_um:PointUm; zoom_milli:number; selected_ids:ID[]; panels_px:{left:number; right:number; bottom:number}}
export interface ProjectFileV2 {format:'gscad-project'; format_version:2; project:Project; workspace:Workspace}
export interface HistoryCommand {kind:'replace_entity'|'add_entity'|'remove_entity'; entity_type:'component'|'instance'|'wire'|'junction'|'splice'|'text'|'label'|'graphic'|'net'; entity_id:ID; before:Record<string,unknown>|null; after:Record<string,unknown>|null}
export interface HistoryTransaction {id:ID; base_sha256:string; generation:number; source_topology_hash:string; commands:HistoryCommand[]}
export type IPCMethod = 'validate_document'|'commit_transaction'|'render_svg'|'render_png';
export interface IPCRequest {protocol:'gscad-ipc'; protocol_version:1; request_id:ID; method:IPCMethod; expected_project_sha256:string|null; generation:number; params:Record<string,unknown>}
export type IPCResponse = {protocol:'gscad-ipc'; protocol_version:1; request_id:ID; ok:true; result:unknown; project_sha256:string; generation:number} | {protocol:'gscad-ipc'; protocol_version:1; request_id:ID; ok:false; error:{code:string; message:string; details?:unknown}; project_sha256:string; generation:number};

export function assertSafePoint(p: PointUm): void {
  if (p.length !== 2 || p.some(x => !Number.isSafeInteger(x) || Math.abs(x)>1_000_000_000))
    throw new Error('COORDINATE_NOT_SAFE_INTEGER');
}
/** Mirror X then clockwise y-down discrete rotation, as Python Transform.apply. */
export function worldPin(instance:SymbolInstance, local:PointUm):PointUm {
  let [x,y]=local;
  if(instance.mirror_x)x=-x;
  switch(instance.rotation_deg) {
    case 0:break;
    case 90:[x,y]=[-y,x];break;
    case 180:[x,y]=[-x,-y];break;
    case 270:[x,y]=[y,-x];break;
  }
  const answer:[number,number]=[instance.origin_um[0]+x,instance.origin_um[1]+y];
  assertSafePoint(answer);
  return answer;
}
