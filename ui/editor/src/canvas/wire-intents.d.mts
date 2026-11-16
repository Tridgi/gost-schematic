/** Type-safe Canvas→ManualWireEngine boundary, generated from reviewed wire contract.
 * Keep runtime `wire-intents.mjs` and this declaration in sync.
 */
import type { ManualWireEngine, WiringSnapshot } from '../wires/manual-wire';

export type SegmentDragToken = Readonly<{
  wire_id: string;
  segment_id: string;
  base_revision: number;
  project_id: string;
  source_topology_hash: string;
  axis: 'h' | 'v';
}>;

/** Capture selection against authoritative signed source and CURRENT revision. */
export declare function captureSegmentDrag(
  snapshot: WiringSnapshot, wireId: string, segmentId: string
): SegmentDragToken;

/** Runs exactly one #123 validated transaction. Throws before mutation on stale or foreign input. */
export declare function commitSegmentDrag(
  engine: ManualWireEngine, token: SegmentDragToken,
  deltaUm: number, commandId: string
): WiringSnapshot;
