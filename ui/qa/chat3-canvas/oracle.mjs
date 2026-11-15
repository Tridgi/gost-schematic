/**
 * Independent canvas-contract QA oracle for GOST Schematic R1.
 * NOT production wire/model code, NOT a React Flow or browser implementation.
 * Reference definitions follow ui/contracts/manual-wire-v2.md at 030ec942... .
 * No dependencies; Node.js 20+ (tested 22.16.0).
 */
export const MAX_UM = 1_000_000_000;

export function integerUm(value) {
  if (!Number.isSafeInteger(value) || Math.abs(value) > MAX_UM) {
    throw new RangeError(`INVALID_UM: ${String(value)}`);
  }
  return value;
}
export function pointUm(p) {
  if (!Array.isArray(p) || p.length !== 2) throw new TypeError('POINT_FORMAT');
  return [integerUm(p[0]), integerUm(p[1])];
}

/** y-down, mirror local X before clockwise rotation. */
export function localToWorld(local, instance) {
  const [px, py] = pointUm(local);
  const [ox, oy] = pointUm(instance.origin_um);
  const x = instance.mirror_x ? -px : px;
  const y = py;
  let dx, dy;
  switch (instance.rotation_deg) {
    case 0: [dx, dy] = [x, y]; break;
    case 90: [dx, dy] = [-y, x]; break;
    case 180: [dx, dy] = [-x, -y]; break;
    case 270: [dx, dy] = [y, -x]; break;
    default: throw new RangeError('ROTATION_NOT_QUARTER_TURN');
  }
  return pointUm([ox + dx, oy + dy]);
}

/**
 * Transform is for view only. Pixel tolerance cannot be substituted for
 * exact electrical equality; 1 world unit is 1 micrometre.
 */
export function viewport({zoom, pan_px = [0, 0], px_per_mm = 4}) {
  if (!(Number.isFinite(zoom) && zoom > 0) ||
      !(Number.isFinite(px_per_mm) && px_per_mm > 0) ||
      !Array.isArray(pan_px) || pan_px.length !== 2 ||
      !pan_px.every(Number.isFinite)) throw new RangeError('BAD_VIEWPORT');
  const scale = zoom * px_per_mm / 1000;
  return {
    worldToLocal: p => {
      const [x, y] = pointUm(p);
      return [x * scale + pan_px[0], y * scale + pan_px[1]];
    },
    localToWorld: p => {
      if (!Array.isArray(p) || !p.every(Number.isFinite)) throw new TypeError('BAD_POINTER');
      return pointUm([Math.round((p[0] - pan_px[0]) / scale),
                      Math.round((p[1] - pan_px[1]) / scale)]);
    },
    clientToWorld: (client, rect) => {
      if (![client?.[0], client?.[1], rect?.left, rect?.top].every(Number.isFinite)) throw new TypeError('BAD_RECT');
      return pointUm([Math.round((client[0] - rect.left - pan_px[0]) / scale),
                      Math.round((client[1] - rect.top - pan_px[1]) / scale)]);
    },
    scale,
  };
}

/** Return unambiguous physical PinRef only; keep DOM IDs and labels out. */
export function hitPin(localPointer, physicalPins, view, tolerancePx = 7) {
  if (!(Number.isFinite(tolerancePx) && tolerancePx >= 0)) throw new RangeError('BAD_HIT_RADIUS');
  const candidates = physicalPins.map(p => {
    const [x, y] = view.worldToLocal(p.at_um);
    const distance = Math.hypot(localPointer[0] - x, localPointer[1] - y);
    return {...p, distance};
  }).filter(p => p.distance <= tolerancePx).sort((a,b) => a.distance - b.distance);
  if (!candidates.length) return {kind: 'none'};
  if (candidates.length > 1 && Math.abs(candidates[0].distance - candidates[1].distance) < 1e-7) {
    return {kind:'ambiguous', candidates:candidates.filter(c => Math.abs(c.distance - candidates[0].distance) < 1e-7).map(c => c.pin)};
  }
  return {kind:'pin', pin:candidates[0].pin, distance_px:candidates[0].distance};
}

/** Hit-tests ACTUAL H/V segment at CSS-pixel tolerance under zoom/pan. */
export function hitSegment(localPointer, segments, view, tolerancePx = 5) {
  const hits = [];
  for (const seg of segments) {
    const [x1,y1] = view.worldToLocal(seg.from_um);
    const [x2,y2] = view.worldToLocal(seg.to_um);
    if (x1 !== x2 && y1 !== y2) throw new Error('NON_ORTHOGONAL');
    if (x1 === x2 && y1 === y2) throw new Error('ZERO_LENGTH');
    const qx = Math.max(Math.min(x1,x2),Math.min(Math.max(x1,x2),localPointer[0]));
    const qy = Math.max(Math.min(y1,y2),Math.min(Math.max(y1,y2),localPointer[1]));
    const distance = Math.hypot(localPointer[0]-qx,localPointer[1]-qy);
    if (distance <= tolerancePx) hits.push({id:seg.id, distance_px:distance});
  }
  hits.sort((a,b) => a.distance_px-b.distance_px);
  if (!hits.length) return {kind:'none'};
  if (hits.length > 1 && Math.abs(hits[0].distance_px-hits[1].distance_px) < 1e-7) {
    return {kind:'ambiguous', ids:hits.filter(h => Math.abs(h.distance_px-hits[0].distance_px) < 1e-7).map(h=>h.id)};
  }
  return {kind:'segment', ...hits[0]};
}

/** Electrical conductivity oracle: only explicit stable anchors connect wire paths. */
export function connected(wires, a, b) {
  const parent = new Map();
  const key = (wire, vertex) => `${wire.id}/${vertex.id}`;
  function root(v) { if(!parent.has(v)) parent.set(v,v); const p=parent.get(v);if(p!==v)parent.set(v,root(p));return parent.get(v); }
  function unite(x,y) { const rx=root(x),ry=root(y);if(rx!==ry)parent.set(rx,ry); }
  const anchors = new Map();
  for (const wire of wires) {
    const nodes = new Map(wire.vertices.map(v=>[v.id,v]));
    for (const seg of wire.segments) {
      if (!nodes.has(seg.from_vertex_id)||!nodes.has(seg.to_vertex_id)) throw new Error('MISSING_VERTEX');
      unite(key(wire,nodes.get(seg.from_vertex_id)),key(wire,nodes.get(seg.to_vertex_id)));
    }
    for (const v of wire.vertices) {
      const anc=v.anchor;
      let identity;
      if(anc.kind==='pin') identity = `pin:${anc.component_id}/${anc.physical_pin_number}`;
      if(anc.kind==='junction') identity = `junction:${anc.junction_id}`;
      if(anc.kind==='splice') identity = `splice:${anc.splice_id}`;
      // Free is not joined even when its coordinate or FREE ID is duplicated.
      if(!identity) continue;
      const grouped = `${wire.net_id}/${identity}`;
      const prev=anchors.get(grouped);
      if (prev) unite(prev,key(wire,v));
      else anchors.set(grouped,key(wire,v));
    }
  }
  return root(a) === root(b);
}

function pointOnAxisSegment(p, a, b) {
  return (a[0]===b[0] && p[0]===a[0] && p[1]>=Math.min(a[1],b[1]) && p[1]<=Math.max(a[1],b[1])) ||
         (a[1]===b[1] && p[1]===a[1] && p[0]>=Math.min(a[0],b[0]) && p[0]<=Math.max(a[0],b[0]));
}

/**
 * Read-only negative validator for the v2 contract; NEVER writes to the input.
 * Component and pin lookup supplied by owner #122 when integrated.
 */
export function validateWire(wire, {net_members, pin_positions, junctions = [], splices = [], other_wires = []}) {
  const errors = [];
  const byVertex = new Map();
  for(const vertex of wire.vertices) {
    if (byVertex.has(vertex.id)) errors.push('DUPLICATE_VERTEX');
    byVertex.set(vertex.id,vertex);
    try {pointUm(vertex.at_um);} catch {errors.push('INVALID_POINT');}
  }
  for(let i=0;i<wire.segments.length;i++){
    const s=wire.segments[i], a=byVertex.get(s.from_vertex_id),b=byVertex.get(s.to_vertex_id);
    if(!a || !b){errors.push('MISSING_VERTEX');continue;}
    const [ax,ay]=a.at_um,[bx,by]=b.at_um;
    if(ax!==bx && ay!==by) errors.push('NON_ORTHOGONAL');
    if(ax===bx && ay===by) errors.push('ZERO_LENGTH');
    if (i && wire.segments[i-1].to_vertex_id!==s.from_vertex_id) errors.push('NON_CONTIGUOUS');
  }
  const first=wire.segments[0],last=wire.segments.at(-1);
  const terminalIds=new Set([first?.from_vertex_id,last?.to_vertex_id]);
  for(const v of wire.vertices){
    const anc=v.anchor;
    if(!anc||!['pin','junction','splice','free','bend'].includes(anc.kind)){errors.push('BAD_ANCHOR');continue;}
    const terminal=terminalIds.has(v.id);
    if(terminal && anc.kind==='bend' || !terminal && anc.kind!=='bend') errors.push('ANCHOR_POSITION');
    if(anc.kind==='pin'){
      const id=`${anc.component_id}/${anc.physical_pin_number}`;
      if(!net_members.includes(id)) errors.push('PIN_NET_MISMATCH');
      const real=pin_positions[id];
      if(!real) errors.push('UNKNOWN_PIN');
      else if(real[0]!==v.at_um[0] || real[1]!==v.at_um[1]) errors.push('PIN_ANCHOR_MISMATCH');
    }
    if(anc.kind==='free' && (!anc.free_id || typeof anc.free_id!=='string')) errors.push('INVALID_FREE_ID');
    const table=anc.kind==='junction'?junctions:anc.kind==='splice'?splices:null;
    if(table){
      const id=anc.kind==='junction'?anc.junction_id:anc.splice_id;
      const elem=table.find(e=>e.id===id);
      if(!elem || elem.net_id!==wire.net_id || elem.at_um[0]!==v.at_um[0] || elem.at_um[1]!==v.at_um[1]) errors.push('ANCHOR_REFERENCE_MISMATCH');
    }
  }
  for(const j of junctions.filter(j=>j.net_id===wire.net_id)) {
    for(const foreign of other_wires.filter(w=>w.net_id!==j.net_id)){
      const fverts=new Map(foreign.vertices.map(v=>[v.id,v]));
      for(const seg of foreign.segments){
        const a=fverts.get(seg.from_vertex_id)?.at_um, b=fverts.get(seg.to_vertex_id)?.at_um;
        if(a && b && pointOnAxisSegment(j.at_um,a,b)) errors.push('JUNCTION_CROSSES_FOREIGN_NET');
      }
    }
  }
  return [...new Set(errors)];
}