/** CHAT3 R2 proof of the SVG selection -> Manual Wire Engine command boundary.
 * Non-authoritative QA adapter. The graph/Net mutation remains in #123 WireEngine.
 * This avoids stale array-index mistakes: UI always stores stable segment_id.
 */
function integer(value) {
  if (!Number.isSafeInteger(value) || Math.abs(value) > 1_000_000_000)
    throw Error('INVALID_UM');
  return value;
}
function identifier(id) {
  if (typeof id !== 'string' || !id.trim()) throw Error('INVALID_ID');
  return id;
}
/** Convert a verified, unambiguous hit result into a stable UI selection. */
export function selectMovableSegment(hit) {
  if (!hit || hit.kind !== 'segment' || hit.movable !== true)
    throw Error('NOT_MOVABLE_SEGMENT');
  return {wire_id: identifier(hit.wire_id),segment_id: identifier(hit.segment_id)};
}
/**
 * Execute the segment move only if selection belongs to the SAME immutable
 * revision that generated the hit. Map segment_id -> index within CAS window.
 */
export function moveSelectedSegment(engine,selection,normal_delta_um,expected_revision,command_id) {
  identifier(command_id);
  integer(normal_delta_um);
  if (normal_delta_um === 0) throw Error('NO_CHANGE');
  if (!Number.isSafeInteger(expected_revision) || expected_revision < 0)
    throw Error('INVALID_REVISION');
  if (!engine || typeof engine.newTransaction !== 'function' ||
      typeof engine.moveSegment !== 'function') throw Error('INVALID_ENGINE');
  const snapshot = engine.snapshot;
  if (snapshot.revision !== expected_revision) throw Error('STALE_REVISION');
  const wire_id = identifier(selection?.wire_id),segment_id = identifier(selection?.segment_id);
  const matches = snapshot.wires.filter(w => w.id === wire_id);
  if (matches.length !== 1) throw Error('UNKNOWN_OR_DUPLICATE_WIRE');
  const segments = matches[0].segments;
  const segmentIndex = segments.findIndex(seg => seg.id === segment_id);
  if (segmentIndex < 0) throw Error('UNKNOWN_SEGMENT');
  if (segments.filter(seg => seg.id === segment_id).length !== 1)
    throw Error('DUPLICATE_SEGMENT');
  if (segmentIndex === 0 || segmentIndex === segments.length - 1)
    throw Error('PIN_ANCHOR_PROTECTED');
  const tx = engine.newTransaction(command_id);
  if (tx.base_revision !== expected_revision ||
      tx.project_id !== snapshot.project_id ||
      tx.source_topology_hash !== snapshot.source_topology_hash)
    throw Error('STALE_OR_FOREIGN_TRANSACTION');
  return engine.moveSegment(tx,wire_id,segmentIndex,normal_delta_um);
}