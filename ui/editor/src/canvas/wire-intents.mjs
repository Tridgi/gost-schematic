/** CHAT4 canvas→#123 adapter. The canvas stores stable segment IDs, not positional indices.
 * This boundary is a UI transaction adapter, NOT a second electrical model.
 * `base_revision` must be captured at pointer-down. Source Net ownership stays in ManualWireEngine.
 */
export function captureSegmentDrag(snapshot,wireId,segmentId){
 if(!Number.isSafeInteger(snapshot?.revision)||snapshot.revision<0)throw Error("INVALID_REVISION");
 if(typeof snapshot.project_id!=='string'||!snapshot.project_id.trim()||typeof snapshot.source_topology_hash!=='string'||!snapshot.source_topology_hash.trim())throw Error('INVALID_SNAPSHOT_IDENTITY');
 if(typeof wireId!=='string'||!wireId.trim()||typeof segmentId!=='string'||!segmentId.trim())throw Error('INVALID_ID');
 const candidates=snapshot.wires?.filter(w=>w.id===wireId)||[];
 if(candidates.length!==1)throw Error('UNKNOWN_OR_DUPLICATE_WIRE');
 const wire=candidates[0];
 const index=wire.segments?.findIndex(s=>s.id===segmentId);
 if(index===-1||index===undefined)throw Error('UNKNOWN_SEGMENT');
 if(wire.segments.filter(s=>s.id===segmentId).length!==1)throw Error('DUPLICATE_SEGMENT');
 if(index<1||index>=wire.segments.length-1)throw Error("PIN_ANCHOR_PROTECTED");
 const vertices=new Map(wire.vertices.map(v=>[v.id,v.at_um]));
 const edge=wire.segments[index],a=vertices.get(edge.from_vertex_id),b=vertices.get(edge.to_vertex_id);
 if(!Array.isArray(a)||!Array.isArray(b)||a.length!==2||b.length!==2||!a.every(Number.isSafeInteger)||!b.every(Number.isSafeInteger))throw Error("INVALID_VERTEX");
 if(a[0]===b[0]&&a[1]===b[1])throw Error("ZERO_LENGTH_SEGMENT");
 if(a[0]!==b[0]&&a[1]!==b[1])throw Error("NON_ORTHOGONAL");
 return Object.freeze({wire_id:wireId,segment_id:segmentId,base_revision:snapshot.revision,project_id:snapshot.project_id,source_topology_hash:snapshot.source_topology_hash,axis:a[0]===b[0]?'v':'h'});
}
export function commitSegmentDrag(engine,token,deltaUm,commandId){
 if(!Number.isSafeInteger(deltaUm)||Math.abs(deltaUm)>1e9||deltaUm===0)throw Error("INVALID_DRAG_DELTA");
 if(typeof commandId!=="string"||!commandId.trim())throw Error("INVALID_COMMAND_ID");
 if(!token||!Number.isSafeInteger(token.base_revision))throw Error("INVALID_DRAG_TOKEN");
 // The authoritative engine owns the snapshot and CAS; never mutate it directly.
 const snapshot=engine.snapshot;
 if(snapshot.revision!==token.base_revision)throw Error('STALE_REVISION');
 if(snapshot.project_id!==token.project_id||snapshot.source_topology_hash!==token.source_topology_hash)throw Error('SOURCE_MISMATCH');
 const current=captureSegmentDrag(snapshot,token.wire_id,token.segment_id);
 if(current.axis!==token.axis)throw Error("SEGMENT_CHANGED");
 const tx=engine.newTransaction(commandId);
 if(tx.base_revision!==token.base_revision)throw Error('STALE_REVISION');
 if(tx.project_id!==snapshot.project_id||tx.source_topology_hash!==snapshot.source_topology_hash)throw Error('FOREIGN_TRANSACTION');
 // Domain resolves stable ID under its authoritative CAS transaction.
 return engine.moveSegmentById(tx,token.wire_id,token.segment_id,deltaUm);
}
