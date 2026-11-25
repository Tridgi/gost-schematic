/** GOST Schematic visual CAD: manual wiring domain, isolated from the canvas.
 * MIT; original implementation. Exact signed integer micrometres, never pixels.
 * For integration with gscad-project v2 (Issue #122) via a validated adapter.
 */
export type PointUm = [number, number];
export type PinRef = { component_id: string; physical_pin_number: string };
export type Direction = 'left' | 'right' | 'up' | 'down';
export type TerminalAnchor =
  | ({ kind: 'pin' } & PinRef)
  | { kind: 'junction'; junction_id: string }
  | { kind: 'splice'; splice_id: string }
  | { kind: 'free'; free_id: string };
export type WireAnchor = TerminalAnchor | { kind: 'bend' };
export type WireVertex = { id: string; at_um: PointUm; anchor: WireAnchor };
export type WireSegment = { id: string; from_vertex_id: string; to_vertex_id: string };
export type WirePolyline = {
  id: string; net_id: string; layer_id: string; vertices: WireVertex[];
  segments: WireSegment[]; mode: 'orthogonal'; needs_routing_review?: boolean;
};
export type Junction = { id: string; net_id: string; layer_id: string; at_um: PointUm };
export type Splice = { id: string; net_id: string; layer_id: string; at_um: PointUm };
export type PhysicalPin = PinRef & { local_at_um: PointUm; outward: Direction };
export type Component = { id: string; origin_um: PointUm; rotation: 0 | 90 | 180 | 270; mirror_x: boolean; pins: PhysicalPin[] };
export type Net = { id: string; literal_source_name: string; members: PinRef[] };
export type WiringSnapshot = {
  schema_version: 2; project_id: string; revision: number; source_topology_hash: string;
  components: Component[]; nets: Net[]; wires: WirePolyline[];
  junctions: Junction[]; splices: Splice[];
};
export type Transaction = { schema_version: 2; project_id: string; base_revision: number; source_topology_hash: string; command_id: string };
export class WireError extends Error {
  constructor(public readonly code: string, message: string) { super(message); this.name = 'WireError'; }
}
function fail(code: string, message: string): never { throw new WireError(code, message); }
const copy = <T>(value: T): T => structuredClone(value);
function id(value: unknown, field: string): asserts value is string {
  if (typeof value !== 'string' || !value.trim()) fail('INVALID_ID', `${field} must be nonempty`);
}
function int(value: unknown): asserts value is number {
  if (!Number.isSafeInteger(value) || Math.abs(value as number) > 1_000_000_000)
    fail('COORDINATE_RANGE', 'Coordinates must be safe integer micrometres within ±1e9');
}
function point(value: unknown): asserts value is PointUm {
  if (!Array.isArray(value) || value.length !== 2) fail('INVALID_POINT', 'Expected [xUm,yUm]');
  int(value[0]); int(value[1]);
}
function same(a: PointUm, b: PointUm): boolean { return a[0] === b[0] && a[1] === b[1]; }
function axis(a: PointUm, b: PointUm): boolean { return !same(a,b) && (a[0] === b[0] || a[1] === b[1]); }
function onSegment(p: PointUm, a: PointUm, b: PointUm): boolean {
  return axis(a,b) && (a[0] === b[0] && p[0] === a[0] && p[1] >= Math.min(a[1],b[1]) && p[1] <= Math.max(a[1],b[1]) ||
    a[1] === b[1] && p[1] === a[1] && p[0] >= Math.min(a[0],b[0]) && p[0] <= Math.max(a[0],b[0]));
}
function pinKey(ref: PinRef): string { return `${JSON.stringify(ref.component_id)}:${JSON.stringify(ref.physical_pin_number)}`; }
function anchorKey(a: TerminalAnchor): string {
  switch(a.kind) {
    case 'pin': return `p:${pinKey(a)}`;
    case 'junction': return `j:${a.junction_id}`;
    case 'splice': return `s:${a.splice_id}`;
    case 'free': return `f:${a.free_id}`;
  }
}
export function transform(local: PointUm, c: Component): PointUm {
  point(local); point(c.origin_um);
  const x = c.mirror_x ? -local[0] : local[0], y = local[1];
  const p: PointUm = c.rotation === 0 ? [x,y] : c.rotation === 90 ? [-y,x] :
    c.rotation === 180 ? [-x,-y] : [y,-x];
  const result: PointUm = [c.origin_um[0] + p[0], c.origin_um[1] + p[1]];
  point(result); return result;
}
const normals: Record<Direction,PointUm> = { left:[-1,0], right:[1,0], up:[0,-1], down:[0,1] };
function pinNormal(pin: PhysicalPin, c: Component): PointUm {
  const zero: Component = { ...c, origin_um: [0,0] };
  return transform(normals[pin.outward], zero);
}
function physicalPin(doc: WiringSnapshot, ref: PinRef): { at:PointUm; normal:PointUm } {
  const comp = doc.components.find(c => c.id === ref.component_id);
  const pin = comp?.pins.find(p => p.physical_pin_number === ref.physical_pin_number);
  if (!comp || !pin) fail('UNKNOWN_PIN', `Unknown physical pin ${pinKey(ref)}`);
  return { at:transform(pin.local_at_um,comp), normal:pinNormal(pin,comp) };
}
function segmentOutward(from: PointUm, toward: PointUm, normal: PointUm): boolean {
  const dx = toward[0]-from[0], dy = toward[1]-from[1];
  return (normal[0] === 0 ? dx === 0 && dy * normal[1] > 0 : dy === 0 && dx * normal[0] > 0);
}
function terminal(v:WireVertex): TerminalAnchor {
  if (v.anchor.kind === 'bend') fail('INVALID_ANCHOR', 'Wire endpoint cannot be bend');
  return v.anchor;
}
function checkedWire(doc: WiringSnapshot, w: WirePolyline, net:Net): void {
  id(w.id,'Wire ID'); id(w.layer_id,'Layer ID');
  if(w.mode !== 'orthogonal' || w.vertices.length < 2 || w.segments.length !== w.vertices.length-1)
    fail('WIRE_GEOMETRY', 'Polyline must have adjacent H/V segments');
  const seen = new Set<string>(), sids = new Set<string>();
  for (const v of w.vertices) { id(v.id,'Vertex ID'); point(v.at_um); if(seen.has(v.id)) fail('DUPLICATE_ID','Vertex IDs must be unique'); seen.add(v.id); }
  w.segments.forEach((seg,i) => {
    id(seg.id,'Segment ID'); if(sids.has(seg.id)) fail('DUPLICATE_ID','Segment IDs must be unique'); sids.add(seg.id);
    if (seg.from_vertex_id !== w.vertices[i].id || seg.to_vertex_id !== w.vertices[i+1].id ||
      !axis(w.vertices[i].at_um, w.vertices[i+1].at_um)) fail('WIRE_GEOMETRY','Invalid H/V segment or adjacency');
  });
  for (const v of w.vertices.slice(1,-1)) if (v.anchor.kind !== 'bend') fail('INVALID_ANCHOR','Internal vertex must be bend');
  for (const [side,idx,neighbor] of [['start',0,1],['end',w.vertices.length-1,w.vertices.length-2]] as const) {
    const v = w.vertices[idx], a = terminal(v);
    if(a.kind === 'pin') {
      if(!net.members.some(p=>pinKey(p)===pinKey(a))) fail('NET_CONFLICT','Pin is not a member of wire Net');
      const actual=physicalPin(doc,a);
      if(!same(actual.at,v.at_um)) fail('PIN_ANCHOR_MISMATCH','Pin coordinate differs by ≥1µm');
      if(!segmentOutward(v.at_um,w.vertices[neighbor].at_um,actual.normal))
        fail('PIN_NORMAL','First/last segment must leave pin outward');
    } else if(a.kind === 'junction' || a.kind === 'splice') {
      const obj=(a.kind==='junction'?doc.junctions:doc.splices).find(j=>j.id===(a.kind==='junction'?a.junction_id:a.splice_id));
      if(!obj || obj.net_id!==w.net_id || obj.layer_id!==w.layer_id || !same(obj.at_um,v.at_um))
        fail('ANCHOR_MISMATCH','Junction/splice must match explicit Net/layer/contact');
    } else {
      id(a.free_id,'Free endpoint ID');
    }
  }
}
export function validateDocument(doc: WiringSnapshot): void {
  if(doc.schema_version!==2 || !Array.isArray(doc.wires) || !Array.isArray(doc.nets) ||
      !Array.isArray(doc.components) || !Array.isArray(doc.junctions) || !Array.isArray(doc.splices))
    fail('SCHEMA_VERSION','Unsupported or malformed gscad wire document');
  id(doc.project_id,'Project ID'); id(doc.source_topology_hash,'Source topology hash');
  if(!Number.isSafeInteger(doc.revision) || doc.revision<0) fail('REVISION','Invalid revision');
  const ids=new Set<string>(), pinIds=new Set<string>(), netMembers=new Set<string>();
  for(const c of doc.components) {
    id(c.id,'Component ID'); if(ids.has(c.id)) fail('DUPLICATE_ID','Duplicate component'); ids.add(c.id);
    point(c.origin_um); if(![0,90,180,270].includes(c.rotation) || typeof c.mirror_x!=='boolean') fail('TRANSFORM','Invalid rotation/mirror');
    for(const p of c.pins) {
      if(p.component_id!==c.id || !Object.hasOwn(normals,p.outward)) fail('INVALID_PIN','Pin definition does not belong to component');
      id(p.physical_pin_number,'Physical pin number'); point(p.local_at_um);
      const key=pinKey(p); if(pinIds.has(key)) fail('DUPLICATE_ID','Physical pin reused'); pinIds.add(key);
      transform(p.local_at_um,c);
    }
  }
  const nets=new Map<string,Net>();
  for(const net of doc.nets) {
    id(net.id,'Net ID'); id(net.literal_source_name,'Original Net name');
    if(!Array.isArray(net.members) || net.members.length===0) fail('INVALID_NET','Declared source Net needs at least one physical PinRef');
    if(nets.has(net.id)) fail('DUPLICATE_ID','Duplicate Net'); nets.set(net.id,net);
    for(const pin of net.members) {
      const key=pinKey(pin); if(!pinIds.has(key)) fail('UNKNOWN_PIN','Declared Net includes missing pin');
      if(netMembers.has(key)) fail('NET_CONFLICT','Physical PinRef appears in multiple Nets'); netMembers.add(key);
    }
  }
  const allAnchors=new Set<string>();
  for(const [kind,nodes] of [['j',doc.junctions],['s',doc.splices]] as const) {
    for(const node of nodes) {
      id(node.id,'Conductor node ID'); point(node.at_um); id(node.layer_id,'Node layer');
      if(!nets.has(node.net_id) || allAnchors.has(`${kind}:${node.id}`)) fail('NODE_CONFLICT','Invalid or duplicate conductor node');
      allAnchors.add(`${kind}:${node.id}`);
    }
  }
  const wireIds=new Set<string>(), degrees=new Map<string,number>(), freeIds=new Set<string>();
  for(const w of doc.wires) {
    if(wireIds.has(w.id)) fail('DUPLICATE_ID','Duplicate wire'); wireIds.add(w.id);
    const net=nets.get(w.net_id); if(!net) fail('UNKNOWN_NET','Wire uses unknown Net');
    checkedWire(doc,w,net);
    for(const end of [terminal(w.vertices[0]),terminal(w.vertices.at(-1)!)]) {
      if(end.kind==='free') {
        if(freeIds.has(end.free_id)) fail('FREE_ALIAS','Free endpoint IDs must be unique across the sheet');
        freeIds.add(end.free_id);
      }
      const key=anchorKey(end); degrees.set(key,(degrees.get(key)??0)+1);
    }
  }
  for(const j of doc.junctions) {
    const key=`j:${j.id}`; if((degrees.get(key)??0)<2) fail('JUNCTION_DEGREE','Visible junction must join >=2 wire ends');
    // A deliberately visible conducting dot must not sit on a foreign physical contact.
    for(const net of doc.nets) if(net.id!==j.net_id) for(const pin of net.members)
      if(same(physicalPin(doc,pin).at,j.at_um)) fail('NET_CONFLICT','Junction overlaps foreign-Net physical pin');
    for(const w of doc.wires) if(w.layer_id===j.layer_id && w.net_id!==j.net_id &&
      w.segments.some((_,i)=>onSegment(j.at_um,w.vertices[i].at_um,w.vertices[i+1].at_um)))
      fail('NET_CONFLICT','Junction touches foreign Net wire');
  }
  for(const s of doc.splices) if((degrees.get(`s:${s.id}`)??0)!==2)
    fail('SPLICE_DEGREE','Invisible splice must join exactly two wire ends');
}
/** Allocate a distinct dangling endpoint identity without renaming surviving source Free IDs.
 * Splitting a wire can retain an old Free ID on a newly renamed wire part, so
 * `wireId:start/end` is a suggestion, not an identity guarantee.
 */
function freshFreeId(doc:WiringSnapshot, wireId:string, side:string):string {
  const used=new Set<string>();
  for(const w of doc.wires)
    for(const v of [w.vertices[0],w.vertices.at(-1)!])
      if(v.anchor.kind==='free') used.add(v.anchor.free_id);
  const base=`${wireId}:${side}`;
  let candidate=base, i=1;
  while(used.has(candidate)) candidate=`${base}#${i++}`;
  return candidate;
}
function serialId(prefix:string, doc:WiringSnapshot): string {
  const all=new Set([...doc.wires,...doc.junctions,...doc.splices].map(v=>v.id));
  let i=1; while(all.has(`${prefix}${i}`)) i++; return `${prefix}${i}`;
}
function wireFromPoints(idValue:string, net_id:string,layer_id:string, points:PointUm[],start:TerminalAnchor,end:TerminalAnchor):WirePolyline {
  const vertices=points.map((p,i):WireVertex=>({id:`${idValue}:v${i}`,at_um:copy(p),anchor:i===0?copy(start):i===points.length-1?copy(end):{kind:'bend'}}));
  return {id:idValue,net_id,layer_id,mode:'orthogonal',vertices,
    segments:vertices.slice(1).map((v,i)=>({id:`${idValue}:s${i}`,from_vertex_id:vertices[i].id,to_vertex_id:v.id}))};
}
function splitPoints(w:WirePolyline, at:PointUm):[PointUm[],PointUm[]] {
  const pts=w.vertices.map(v=>v.at_um);
  let idx=-1;
  for(let i=0;i<pts.length-1;i++) if(onSegment(at,pts[i],pts[i+1])) {idx=i;break;}
  if(idx<0 || same(at,pts[0]) || same(at,pts.at(-1)!)) fail('SPLIT_POINT','Split must lie strictly inside wire');
  return [[...pts.slice(0,idx+1),...(!same(at,pts[idx])?[at]:[])],
          [at,...pts.slice(idx+1).filter((p,i)=>i!==0 || !same(p,at))]];
}
/** Prefer straight, L and Z/U routes; never reverse along a conductor.
 * Optional acceptance predicate is supplied by the sheet-level obstacle planner.
 * This bounded candidate search is not a complete global maze router. */
export function routeManhattan(start:PointUm,end:PointUm,startNormal?:PointUm,endNormal?:PointUm,lead=2000,
  options?:{accept?:(path:PointUm[])=>boolean;channelsX?:readonly number[];channelsY?:readonly number[]}):PointUm[] {
  point(start);point(end);int(lead);
  if(lead<=0) fail('LEAD_LENGTH','Lead must be >0 µm');
  if(same(start,end)) fail('WIRE_GEOMETRY','Coincident wire terminals');
  for(const n of [startNormal,endNormal])if(n&&(!Number.isInteger(n[0])||!Number.isInteger(n[1])||Math.abs(n[0])+Math.abs(n[1])!==1))
    fail('PIN_NORMAL','Expected cardinal pin normal');
  const extend=(p:PointUm,n?:PointUm):PointUm=>n?[p[0]+n[0]*lead,p[1]+n[1]*lead]:copy(p);
  const a=extend(start,startNormal),b=extend(end,endNormal);
  const candidates:PointUm[][]=[];
  const keys=new Set<string>();
  const add=(raw:PointUm[])=>{
    const compact:PointUm[]=[];
    for(const p of raw){
      if(!p.every(v=>Number.isSafeInteger(v)&&Math.abs(v)<=1e9))return;
      if(compact.length&&same(p,compact.at(-1)!))continue;
      compact.push(p);
      while(compact.length>=3){
        const [x,y,z]=compact.slice(-3);
        if(onSegment(y,x,z))compact.splice(compact.length-2,1);else break;
      }
    }
    if(compact.length<2||compact.some((p,i)=>i>0&&!axis(compact[i-1],p)))return;
    if(startNormal&&!segmentOutward(start,compact[1],startNormal)||endNormal&&!segmentOutward(end,compact.at(-2)!,endNormal))return;
    for(let i=1;i<compact.length-1;i++){
      const [x,y,z]=compact.slice(i-1,i+2);
      if(x[0]===y[0]&&y[0]===z[0]||x[1]===y[1]&&y[1]===z[1])return;
    }
    // No self intersections, including nonadjacent endpoint touches.
    for(let i=0;i<compact.length-1;i++)for(let j=i+2;j<compact.length-1;j++){
      const [p,q,r,t]=[compact[i],compact[i+1],compact[j],compact[j+1]];
      if(Math.max(Math.min(p[0],q[0]),Math.min(r[0],t[0]))<=Math.min(Math.max(p[0],q[0]),Math.max(r[0],t[0]))&&
         Math.max(Math.min(p[1],q[1]),Math.min(r[1],t[1]))<=Math.min(Math.max(p[1],q[1]),Math.max(r[1],t[1])))return;
    }
    const key=JSON.stringify(compact);if(!keys.has(key)){keys.add(key);candidates.push(compact)}
  };
  // Direct candidates allow shorter terminal leads when geometrically legal.
  add([start,end]);add([start,[end[0],start[1]],end]);add([start,[start[0],end[1]],end]);
  const channels=(i:0|1,extra:readonly number[]=[])=>{
    const lo=Math.min(start[i],end[i],a[i],b[i]),hi=Math.max(start[i],end[i],a[i],b[i]);
    const mid=Math.round((start[i]+end[i])/2);
    const base=[mid,a[i],b[i],lo-lead,hi+lead,start[i],end[i],lo-2*lead,hi+2*lead];
    const more=[...new Set(extra)].filter(v=>Number.isSafeInteger(v)&&Math.abs(v)<=1e9)
      .sort((x,y)=>Math.abs(x-mid)-Math.abs(y-mid)||x-y).slice(0,48);
    return [...new Set([...base,...more])];
  };
  const xs=channels(0,options?.channelsX),ys=channels(1,options?.channelsY);
  for(const x of xs){add([start,[x,start[1]],[x,end[1]],end]);add([start,a,[x,a[1]],[x,b[1]],b,end])}
  for(const y of ys){add([start,[start[0],y],[end[0],y],end]);add([start,a,[a[0],y],[b[0],y],b,end])}
  add([start,a,[b[0],a[1]],b,end]);add([start,a,[a[0],b[1]],b,end]);
  const length=(p:PointUm[])=>p.slice(1).reduce((sum,q,i)=>sum+Math.abs(q[0]-p[i][0])+Math.abs(q[1]-p[i][1]),0);
  const balance=(p:PointUm[])=>p.length===4?Math.abs((Math.abs(p[1][0]-p[0][0])+Math.abs(p[1][1]-p[0][1]))-
    (Math.abs(p[3][0]-p[2][0])+Math.abs(p[3][1]-p[2][1]))):0;
  candidates.sort((p,q)=>p.length-q.length||length(p)-length(q)||balance(p)-balance(q));
  const best=candidates.find(p=>!options?.accept||options.accept(p));
  if(!best)fail('REROUTE_REQUIRED','No safe simple orthogonal route found');
  return best;
}

export class ManualWireEngine {
  private doc:WiringSnapshot;
  private undoStack:WiringSnapshot[]=[];
  private redoStack:WiringSnapshot[]=[];
  private clock:number;
  constructor(initial:WiringSnapshot) { validateDocument(initial); this.doc=copy(initial); this.clock=initial.revision; }
  get snapshot():WiringSnapshot { return copy(this.doc); }
  private transaction(tx:Transaction,edit:(draft:WiringSnapshot)=>void):WiringSnapshot {
    if(tx.schema_version!==2 || tx.project_id!==this.doc.project_id || tx.source_topology_hash!==this.doc.source_topology_hash)
      fail('SOURCE_MISMATCH','Transaction must match project identity and locked source topology');
    id(tx.command_id,'Command ID');
    if(!Number.isSafeInteger(tx.base_revision) || tx.base_revision!==this.doc.revision)
      fail('STALE_REVISION','Revision check failed; nothing mutated');
    const draft=copy(this.doc); edit(draft); draft.revision=this.clock+1;
    validateDocument(draft);
    this.undoStack.push(this.doc); this.redoStack=[]; this.doc=draft;this.clock++;
    return this.snapshot;
  }
  newTransaction(command_id:string):Transaction {
    return {schema_version:2,project_id:this.doc.project_id,base_revision:this.doc.revision,
      source_topology_hash:this.doc.source_topology_hash,command_id};
  }
  beginWire(pin:PinRef):{at_um:PointUm;normal:PointUm;net_id:string} {
    const {at,normal}=physicalPin(this.doc,pin);
    const net=this.doc.nets.find(n=>n.members.some(p=>pinKey(p)===pinKey(pin)));
    if(!net) fail('UNKNOWN_NET','Pin is not in source Net');
    return {at_um:at,normal,net_id:net.id};
  }
  previewRoute(from:TerminalAnchor,to:TerminalAnchor):PointUm[] {
    const resolved=(a:TerminalAnchor):{at:PointUm;normal?:PointUm}=>{
      if(a.kind==='pin') return physicalPin(this.doc,a);
      if(a.kind==='free') fail('UNBOUND_FREE','Free route preview needs explicit cursor position');
      const n=(a.kind==='junction'?this.doc.junctions:this.doc.splices).find(n=>n.id===(a.kind==='junction'?a.junction_id:a.splice_id));
      if(!n) fail('ANCHOR_MISMATCH','Unknown anchor'); return {at:n.at_um};
    };
    const a=resolved(from),b=resolved(to);
    return routeManhattan(a.at,b.at,a.normal,b.normal);
  }
  commitWire(tx:Transaction, wire:WirePolyline):WiringSnapshot {
    return this.transaction(tx,d=>{if(d.wires.some(w=>w.id===wire.id)) fail('DUPLICATE_ID','Wire already exists');d.wires.push(copy(wire));});
  }
  moveSegment(tx:Transaction,wireId:string,segmentIndex:number,offsetUm:number):WiringSnapshot {
    int(offsetUm); if(offsetUm===0) fail('NO_CHANGE','Cannot move segment by 0');
    return this.transaction(tx,d=>{
      const w=d.wires.find(w=>w.id===wireId);if(!w) fail('UNKNOWN_WIRE','Unknown wire');
      if(!Number.isInteger(segmentIndex) || segmentIndex<=0 || segmentIndex>=w.segments.length-1)
        fail('PIN_ANCHOR_PROTECTED','Move only a middle segment');
      const a=w.vertices[segmentIndex].at_um,b=w.vertices[segmentIndex+1].at_um;
      if(a[0]===b[0]) {a[0]+=offsetUm;b[0]+=offsetUm;} else {a[1]+=offsetUm;b[1]+=offsetUm;}
    });
  }
  /** Canvas hit-testing returns a persistent segment ID, not an array offset.
   * Resolve that ID on the same monotonic CAS revision before editing.
   * A stale/removed handle must not silently drag a different segment.
   */
  moveSegmentById(tx:Transaction,wireId:string,segmentId:string,offsetUm:number):WiringSnapshot {
    id(segmentId,'Segment ID');
    const w=this.doc.wires.find(w=>w.id===wireId);
    if(!w) fail('UNKNOWN_WIRE','Unknown wire');
    const idx=w.segments.findIndex(seg=>seg.id===segmentId);
    if(idx<0) fail('UNKNOWN_SEGMENT','Selected segment ID no longer belongs to this wire');
    return this.moveSegment(tx,wireId,idx,offsetUm);
  }
  /** Physical component placement is a CAS-guarded model edit.
   * Existing attached conductors cannot be silently detached or stretched.
   * A follow-up explicit reanchor workflow must handle that separately.
   */
  moveComponent(tx:Transaction,componentId:string,originUm:PointUm):WiringSnapshot {
    id(componentId,'Component ID');point(originUm);
    return this.transaction(tx,d=>{
      const component=d.components.find(c=>c.id===componentId);
      if(!component)fail('UNKNOWN_COMPONENT','No physical component for placement');
      if(same(component.origin_um,originUm))fail('NO_CHANGE','Component position unchanged');
      if(d.wires.some(w=>w.vertices.some(v=>v.anchor.kind==='pin'&&v.anchor.component_id===componentId)))
        fail('REROUTE_REQUIRED','Cannot move symbol with physically anchored conductors');
      component.origin_um=copy(originUm);
    });
  }
  private cutWire(d:WiringSnapshot,w:WirePolyline,at:PointUm,newAnchor:TerminalAnchor):[string,string] {
    const [left,right]=splitPoints(w,at);
    const newId=serialId(`${w.id}:part`,d);
    const a=wireFromPoints(w.id,w.net_id,w.layer_id,left,terminal(w.vertices[0]),newAnchor);
    const oldEnd=terminal(w.vertices.at(-1)!);
    const secondEnd:TerminalAnchor=oldEnd; // Preserve canonical free endpoint identity on split.
    const b=wireFromPoints(newId,w.net_id,w.layer_id,right,newAnchor,secondEnd);
    d.wires.splice(d.wires.indexOf(w),1,a,b);
    return [a.id,b.id];
  }
  splitWire(tx:Transaction,wireId:string,at:PointUm,spliceId:string):WiringSnapshot {
    return this.transaction(tx,d=>{
      point(at);id(spliceId,'Splice ID');
      const w=d.wires.find(w=>w.id===wireId);if(!w) fail('UNKNOWN_WIRE','Unknown wire');
      if(d.splices.some(n=>n.id===spliceId)||d.junctions.some(n=>n.id===spliceId)) fail('DUPLICATE_ID','Conductor anchor ID already exists');
      d.splices.push({id:spliceId,net_id:w.net_id,layer_id:w.layer_id,at_um:copy(at)});
      this.cutWire(d,w,at,{kind:'splice',splice_id:spliceId});
    });
  }
  toggleJunction(tx:Transaction,j:Junction,wireIds:string[]):WiringSnapshot {
    return this.transaction(tx,d=>{
      id(j.id,'Junction ID');point(j.at_um);
      if(d.junctions.some(n=>n.id===j.id)||d.splices.some(n=>n.id===j.id)) fail('DUPLICATE_ID','Node ID already exists');
      if(wireIds.length<2 || new Set(wireIds).size!==wireIds.length) fail('JUNCTION_DEGREE','Select >=2 distinct conductor paths');
      d.junctions.push(copy(j));
      for(const wid of wireIds) {
        const w=d.wires.find(w=>w.id===wid);
        if(!w || w.net_id!==j.net_id || w.layer_id!==j.layer_id) fail('NET_CONFLICT','Selected wires must be same Net and layer');
        const start=w.vertices[0],end=w.vertices.at(-1)!;
        if(same(start.at_um,j.at_um)) {
          if(start.anchor.kind!=='free') fail('ALREADY_CONNECTED','Can only join free endpoint');
          start.anchor={kind:'junction',junction_id:j.id};
        } else if(same(end.at_um,j.at_um)) {
          if(end.anchor.kind!=='free') fail('ALREADY_CONNECTED','Can only join free endpoint');
          end.anchor={kind:'junction',junction_id:j.id};
        } else this.cutWire(d,w,j.at_um,{kind:'junction',junction_id:j.id});
      }
    });
  }
  /** Explicit user action at a true H/V intersection, never SVG overlap inference.
   * All segment handles are resolved by immutable IDs under a monotonic CAS revision.
   */
  connectCrossingSegmentsById(
    tx:Transaction,
    selections:ReadonlyArray<{wire_id:string;segment_id:string}>,
    junctionId:string
  ):WiringSnapshot {
    id(junctionId,'Junction ID');
    if(tx.base_revision!==this.doc.revision)fail('STALE_REVISION','Junction selection is stale');
    if(selections.length<2)fail('JUNCTION_DEGREE','Choose at least two independent conductors');
    const chosen=selections.map(selection=>{
      id(selection.wire_id,'Wire ID');id(selection.segment_id,'Segment ID');
      const wire=this.doc.wires.find(w=>w.id===selection.wire_id);
      if(!wire)fail('UNKNOWN_WIRE','Selected conductor does not exist');
      const index=wire.segments.findIndex(s=>s.id===selection.segment_id);
      if(index<0)fail('UNKNOWN_SEGMENT','Selected segment does not exist');
      const a=wire.vertices[index].at_um,b=wire.vertices[index+1].at_um;
      return {wire,a,b};
    });
    if(new Set(chosen.map(v=>v.wire.id)).size!==chosen.length)
      fail('JUNCTION_DEGREE','Select distinct conductor paths');
    const first=chosen[0].wire;
    if(chosen.some(c=>c.wire.net_id!==first.net_id||c.wire.layer_id!==first.layer_id))
      fail('NET_CONFLICT','Only conductors on same signed Net and layer can join');
    const h=chosen.find(c=>c.a[1]===c.b[1]);
    const v=chosen.find(c=>c.a[0]===c.b[0]);
    if(!h||!v)fail('AMBIGUOUS_JUNCTION','Parallel coincident geometry has no unique H/V intersection');
    const at:PointUm=[v.a[0],h.a[1]];
    point(at);
    if(chosen.some(c=>!onSegment(at,c.a,c.b)))
      fail('INVALID_JUNCTION_POINT','Selected segments do not meet at the same physical location');
    if(this.doc.junctions.some(j=>same(j.at_um,at)&&j.layer_id===first.layer_id))
      fail('ALREADY_CONNECTED','The physical intersection already has an explicit Junction');
    let netId=first.net_id,layerId=first.layer_id;
    return this.toggleJunction(tx,{
      id:junctionId,net_id:netId,layer_id:layerId,at_um:at
    },chosen.map(c=>c.wire.id));
  }
  mergeSplice(tx:Transaction,spliceId:string):WiringSnapshot {
    return this.transaction(tx,d=>{
      const splice=d.splices.find(s=>s.id===spliceId);
      if(!splice) fail('UNKNOWN_NODE','Unknown hidden splice');
      const linked=d.wires.filter(w=>[w.vertices[0],w.vertices.at(-1)!].some(v=>v.anchor.kind==='splice'&&v.anchor.splice_id===spliceId));
      if(linked.length!==2) fail('SPLICE_DEGREE','Merge requires exactly 2 incident wires');
      const [wA,wB]=linked;
      if(wA.net_id!==wB.net_id || wA.layer_id!==wB.layer_id) fail('NET_CONFLICT','Splice routes must share Net/layer');
      const oriented=(w:WirePolyline,spliceAtEnd:boolean)=>{
        const first=terminal(w.vertices[0]),last=terminal(w.vertices.at(-1)!);
        const endHas=last.kind==='splice'&&last.splice_id===spliceId;
        const pts=w.vertices.map(v=>v.at_um);
        const forward=spliceAtEnd?endHas:!endHas;
        return {pts:forward?pts:pts.reverse(),start:forward?first:last,end:forward?last:first};
      };
      const a=oriented(wA,true),b=oriented(wB,false);
      const pts=[...a.pts,...b.pts.slice(1)];
      const merged=wireFromPoints(wA.id,wA.net_id,wA.layer_id,pts,a.start,b.end); // Keep stable external free IDs.
      merged.needs_routing_review=!!(wA.needs_routing_review||wB.needs_routing_review);
      d.wires=d.wires.filter(w=>w!==wA&&w!==wB);d.wires.push(merged);
      d.splices=d.splices.filter(s=>s.id!==spliceId);
    });
  }
  moveVertex(tx:Transaction,wireId:string,index:number,target:PointUm):WiringSnapshot {
    return this.transaction(tx,d=>{
      point(target);const w=d.wires.find(w=>w.id===wireId);
      if(!w) fail('UNKNOWN_WIRE','Unknown wire');
      if(!Number.isInteger(index)||index<=0||index>=w.vertices.length-1)
        fail('PIN_ANCHOR_PROTECTED','Only internal bend vertex can be moved');
      const pts=w.vertices.map(v=>v.at_um);const prev=pts[index-1],next=pts[index+1];
      const expanded=[...pts.slice(0,index),[target[0],prev[1]] as PointUm,target,
        [next[0],target[1]] as PointUm,...pts.slice(index+1)];
      const dedup:PointUm[]=[];for(const p of expanded) if(!dedup.length||!same(dedup.at(-1)!,p))dedup.push(p);
      for(let i=1;i<dedup.length-1;) {if(onSegment(dedup[i],dedup[i-1],dedup[i+1]))dedup.splice(i,1);else i++;}
      const updated=wireFromPoints(w.id,w.net_id,w.layer_id,dedup,terminal(w.vertices[0]),terminal(w.vertices.at(-1)!));
      updated.needs_routing_review=true;d.wires[d.wires.indexOf(w)]=updated;
    });
  }
  removeJunction(tx:Transaction,junctionId:string):WiringSnapshot {
    return this.transaction(tx,d=>{
      if(!d.junctions.some(n=>n.id===junctionId)) fail('UNKNOWN_NODE','Unknown junction');
      for(const w of d.wires) for(const [i,side] of [[0,'start'],[w.vertices.length-1,'end']] as const) {
        const v=w.vertices[i]; if(v.anchor.kind==='junction'&&v.anchor.junction_id===junctionId) v.anchor={kind:'free',free_id:freshFreeId(d,w.id,side)};
      }
      d.junctions=d.junctions.filter(j=>j.id!==junctionId);
    });
  }
  deleteWire(tx:Transaction,wireId:string):WiringSnapshot {
    return this.transaction(tx,d=>{
      if(!d.wires.some(w=>w.id===wireId)) fail('UNKNOWN_WIRE','Unknown wire');
      d.wires=d.wires.filter(w=>w.id!==wireId);
      for(const node of [...d.splices]) {
        const refs=d.wires.flatMap(w=>[w.vertices[0],w.vertices.at(-1)!].map((v,i)=>({w,v,side:i===0?'start':'end'})))
          .filter(x=>x.v.anchor.kind==='splice'&&x.v.anchor.splice_id===node.id);
        if(refs.length<2) {
          for(const ref of refs) ref.v.anchor={kind:'free',free_id:freshFreeId(d,ref.w.id,ref.side)};
          d.splices=d.splices.filter(s=>s.id!==node.id);
        }
      }
      // A junction that lost a branch must be explicitly removed or rewired: no silent topology change.
    });
  }
  /** User-consented movement of a physically connected component.
   * Signed endpoint PinRefs, Net IDs and wire IDs are invariant. The route
   * is regenerated only inside a validated CAS transaction. An unsatisfiable
   * lead/obstacle arrangement aborts the entire edit with no state mutation.
   * Rebuilt segments are marked for routing review, NEVER auto-verified.
   */
  moveComponentAndReanchor(tx:Transaction,componentId:string,originUm:PointUm,permitRebuild=false):WiringSnapshot {
    id(componentId,'Component ID');point(originUm);
    return this.transaction(tx,d=>{
      const component=d.components.find(c=>c.id===componentId);
      if(!component)fail('UNKNOWN_COMPONENT','Unknown connected component');
      if(same(component.origin_um,originUm))fail('NO_CHANGE','Component position unchanged');
      const attached=d.wires.filter(w=>[w.vertices[0],w.vertices.at(-1)!].some(
        v=>v.anchor.kind==='pin'&&v.anchor.component_id===componentId));
      if(attached.length&&!permitRebuild)
        fail('REROUTE_REQUIRED','Moving wired component requires explicit user consent');
      component.origin_um=copy(originUm);
      for(const wire of attached){
        const start=terminal(wire.vertices[0]),end=terminal(wire.vertices.at(-1)!);
        const resolve=(anchor:TerminalAnchor,original:PointUm):{at:PointUm;normal?:PointUm}=>{
          if(anchor.kind==='pin')return physicalPin(d,anchor);
          if(anchor.kind==='junction'){
            const node=d.junctions.find(j=>j.id===anchor.junction_id);
            if(!node)fail('ANCHOR_MISMATCH','Missing signed Junction');
            return {at:node.at_um};
          }
          if(anchor.kind==='splice'){
            const node=d.splices.find(j=>j.id===anchor.splice_id);
            if(!node)fail('ANCHOR_MISMATCH','Missing signed Splice');
            return {at:node.at_um};
          }
          return {at:original};
        };
        const a=resolve(start,wire.vertices[0].at_um);
        const b=resolve(end,wire.vertices.at(-1)!.at_um);
        const points=routeManhattan(a.at,b.at,a.normal,b.normal);
        const updated=wireFromPoints(wire.id,wire.net_id,wire.layer_id,points,start,end);
        updated.needs_routing_review=true;
        d.wires[d.wires.indexOf(wire)]=updated;
      }
    });
  }
  /** One CAS transaction for a physical group. Internal routes translate exactly;
   * external terminal routes are rebuilt once after all component positions change.
   * Explicit junctions/splices stay fixed, and no Net membership is inferred. */
  moveComponentsAndReanchor(tx:Transaction,componentIds:readonly string[],delta:PointUm,permitRebuild=false):WiringSnapshot {
    point(delta);
    if(!delta.some(Boolean))fail('NO_CHANGE','Group displacement is zero');
    const ids=new Set(componentIds);
    if(ids.size<2||ids.size!==componentIds.length)fail('INVALID_GROUP','Expected distinct component IDs');
    return this.transaction(tx,d=>{
      const group=d.components.filter(c=>ids.has(c.id));
      if(group.length!==ids.size)fail('UNKNOWN_COMPONENT','Unknown group component');
      const moved=(a:TerminalAnchor)=>a.kind==='pin'&&ids.has(a.component_id);
      const attached=d.wires.filter(w=>moved(terminal(w.vertices[0]))||moved(terminal(w.vertices.at(-1)!)));
      if(attached.length&&!permitRebuild)fail('GROUP_REROUTE_REQUIRED','Group wire changes require explicit consent');
      const shift=(p:PointUm):PointUm=>{
        const next:PointUm=[p[0]+delta[0],p[1]+delta[1]];point(next);return next;
      };
      for(const c of group)c.origin_um=shift(c.origin_um);
      const resolve=(anchor:TerminalAnchor,original:PointUm):{at:PointUm;normal?:PointUm}=>{
        if(anchor.kind==='pin')return physicalPin(d,anchor);
        if(anchor.kind==='junction'||anchor.kind==='splice'){
          const node=(anchor.kind==='junction'?d.junctions:d.splices).find(n=>n.id===(anchor.kind==='junction'?anchor.junction_id:anchor.splice_id));
          if(!node)fail('ANCHOR_MISMATCH','Missing signed conductor node');
          return {at:node.at_um};
        }
        return {at:original};
      };
      for(const wire of attached){
        const first=wire.vertices[0],last=wire.vertices.at(-1)!;
        const a=terminal(first),b=terminal(last);
        if(moved(a)&&moved(b)){
          for(const vertex of wire.vertices)vertex.at_um=shift(vertex.at_um);
          wire.needs_routing_review=true;
        }else{
          const start=resolve(a,first.at_um),end=resolve(b,last.at_um);
          const points=routeManhattan(start.at,end.at,start.normal,end.normal);
          const updated=wireFromPoints(wire.id,wire.net_id,wire.layer_id,points,a,b);
          updated.needs_routing_review=true;
          d.wires[d.wires.indexOf(wire)]=updated;
        }
      }
    });
  }
  rotateAndReanchor(tx:Transaction,componentId:string,rotation:0|90|180|270,permitRebuild=false):WiringSnapshot {
    return this.transaction(tx,d=>{
      const c=d.components.find(c=>c.id===componentId);if(!c) fail('UNKNOWN_COMPONENT','Unknown component');
      const attached=d.wires.filter(w=>[w.vertices[0],w.vertices.at(-1)!].some(v=>v.anchor.kind==='pin'&&v.anchor.component_id===componentId));
      if(attached.length&&!permitRebuild) fail('REROUTE_REQUIRED','Pin has attached wires; explicit reroute consent required');
      c.rotation=rotation;
      for(const w of attached) {
        const a=terminal(w.vertices[0]),b=terminal(w.vertices.at(-1)!);
        const resolve=(anchor:TerminalAnchor,original:PointUm):{at:PointUm;normal?:PointUm}=>{
          if(anchor.kind==='pin') return physicalPin(d,anchor);
          if(anchor.kind==='junction') return {at:d.junctions.find(n=>n.id===anchor.junction_id)!.at_um};
          if(anchor.kind==='splice') return {at:d.splices.find(n=>n.id===anchor.splice_id)!.at_um};
          return {at:original};
        };
        const s=resolve(a,w.vertices[0].at_um),e=resolve(b,w.vertices.at(-1)!.at_um);
        const route=routeManhattan(s.at,e.at,s.normal,e.normal);
        const updated=wireFromPoints(w.id,w.net_id,w.layer_id,route,a,b);
        updated.needs_routing_review=true;
        d.wires[d.wires.indexOf(w)]=updated;
      }
    });
  }
  validateNet(netId:string):{status:'unrouted'|'partial'|'verified'; pin_groups:PinRef[][]} {
    const net=this.doc.nets.find(n=>n.id===netId);if(!net) fail('UNKNOWN_NET','Unknown Net');
    const parents=new Map<string,string>();
    const find=(s:string):string=>{if(!parents.has(s)) parents.set(s,s);const p=parents.get(s)!;if(p!==s) parents.set(s,find(p));return parents.get(s)!;};
    const union=(a:string,b:string):void=>{parents.set(find(a),find(b));};
    for(const p of net.members) find(`p:${pinKey(p)}`);
    const wires=this.doc.wires.filter(w=>w.net_id===netId);
    for(const w of wires) union(anchorKey(terminal(w.vertices[0])),anchorKey(terminal(w.vertices.at(-1)!)));
    const groups=new Map<string,PinRef[]>();
    for(const p of net.members) {const k=find(`p:${pinKey(p)}`);groups.set(k,[...(groups.get(k)??[]),copy(p)]);}
    const touched=new Set(wires.flatMap(w=>[terminal(w.vertices[0]),terminal(w.vertices.at(-1)!)]
      .filter((a):a is Extract<TerminalAnchor,{kind:'pin'}>=>a.kind==='pin').map(pinKey)));
    const allPinsTouched=net.members.every(p=>touched.has(pinKey(p)));
    const noDanglingOrUnreviewed=wires.every(w=>!w.needs_routing_review&&
      [terminal(w.vertices[0]),terminal(w.vertices.at(-1)!)].every(a=>a.kind!=='free'));
    return {status:wires.length===0?'unrouted':groups.size===1&&allPinsTouched&&noDanglingOrUnreviewed?'verified':'partial',
      pin_groups:[...groups.values()]};
  }
  danglingEndpoints(netId?:string):string[] {
    if(netId!==undefined&&!this.doc.nets.some(n=>n.id===netId))fail('UNKNOWN_NET','Unknown Net');
    return this.doc.wires.filter(w=>netId===undefined||w.net_id===netId).flatMap(w=>
      ([{v:w.vertices[0],side:'start'},{v:w.vertices.at(-1)!,side:'end'}] as const)
        .filter(x=>x.v.anchor.kind==='free').map(x=>`${w.id}:${x.side}`)).sort();
  }
  highlightNet(netId:string):{wire_ids:string[];junction_ids:string[];splice_ids:string[];pin_groups:PinRef[][]} {
    const {pin_groups}=this.validateNet(netId);
    return {pin_groups,wire_ids:this.doc.wires.filter(w=>w.net_id===netId).map(w=>w.id),
      junction_ids:this.doc.junctions.filter(j=>j.net_id===netId).map(j=>j.id),
      splice_ids:this.doc.splices.filter(s=>s.net_id===netId).map(s=>s.id)};
  }
  // Revision is monotonic even across history: prevents ABA stale-CAS replay.
  // Engineering-model hash excludes the revision/undo bookkeeping, not coordinates or topology.
  undo():boolean {
    if(!this.undoStack.length)return false;this.redoStack.push(this.doc);
    this.doc={...this.undoStack.pop()!,revision:++this.clock};return true;
  }
  redo():boolean {
    if(!this.redoStack.length)return false;this.undoStack.push(this.doc);
    this.doc={...this.redoStack.pop()!,revision:++this.clock};return true;
  }
  serialize():string {return JSON.stringify(this.doc);}
  static parse(raw:string):ManualWireEngine {
    let data:unknown;try {data=JSON.parse(raw);}catch{fail('INVALID_JSON','Not valid JSON');}
    return new ManualWireEngine(data as WiringSnapshot);
  }
}
export function constructWire(idValue:string,netId:string,layerId:string,points:PointUm[],start:TerminalAnchor,end:TerminalAnchor):WirePolyline {
  return wireFromPoints(idValue,netId,layerId,points,start,end);
}
