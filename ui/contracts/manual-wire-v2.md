# Manual wire ↔ project file v2 contract (R1, normative for UI integration)

**Owners:** #122 data architect + #123 wire architect; integration authority #125. This reconciles their R0 proposals in GitHub Issue #122/#123. No change to existing engine's `gse-project` v1 until a tested adapter exists.

## Identity/geometry

- Use `int` JSON numbers, signed µm, magnitude ≤1e9. JS must enforce `Number.isSafeInteger` before any arithmetic/persistence.
- `PinRef = {component_id:string, physical_pin_number:string}`, never a refdes or canvas handle. A stable component ID is not changed by renaming the reference designator.
- `PartDefinition` owns manufacturer physical pins; `SymbolDefinition` maps those same physical numbers to local graphic endpoints. `SymbolInstance` has origin, rotation 0/90/180/270 and mirror. `worldPin(PinRef)` must be computed exactly, with y-down clockwise transforms.
- `Net{id, literal_source_name, members:PinRef[]}` is a declaration, **not** inferred from `WirePolyline` or a point intersection; source `Net.members` remains locked even when the route is partial.

## Tagged anchor contract (authoritative)

```ts
type PointUm = [number, number];
type PinRef = { component_id: string; physical_pin_number: string };
type WireAnchor =
  | { kind: 'pin'; component_id: string; physical_pin_number: string }
  | { kind: 'junction'; junction_id: string }
  | { kind: 'splice'; splice_id: string }
  | { kind: 'free'; free_id: string };
type WireVertex = {
  id: string;
  at_um: PointUm;
  anchor: WireAnchor | { kind: 'bend' };
};
type WireSegment = { id: string; from_vertex_id: string; to_vertex_id: string };
type WirePolyline = {
  id: string;
  net_id: string;
  layer_id: string;
  vertices: WireVertex[];
  segments: WireSegment[];
  mode: 'orthogonal';
};
type Junction = { id: string; net_id: string; at_um: PointUm; layer_id: string };
type Splice = { id: string; net_id: string; at_um: PointUm; layer_id: string };
```

**Terminal anchors** are only `pin|junction|splice|free`; `bend` is internal geometry only. `WireSegment` stores stable adjacent vertex IDs. Segment endpoints are never duplicated as floating-point coordinates. Both `Junction` and `Splice` require explicit editor actions and same-Net links. Junction draws a dot; splice remains invisible and degree-2 electrical continuity. Free `free_id` is a stable, endpoint-unique identity; two coincident free endpoints do NOT connect.

A pin anchor must exactly resolve to a manufacturer physical pin, belong to the wire's declared Net, and coincide after transform with the endpoint `at_um`; if mismatched by even 1µm the operation **fails closed** with `PIN_ANCHOR_MISMATCH`. A source Net may contain isolated routed islands and only gets `verified` when reachability validates all declared members; otherwise `unrouted`/`partial`.

Source `b` continuation marks are `GraphicLine(kind='source_b_continuation')` and MUST NOT appear as `WirePolyline`, `PinRef` or `Net` members.

## Transactions and invalid cases

Transaction input `{schema_version, project_id, base_revision, source_topology_hash, command_id, kind, payload}`; command must validate all affected model invariants and commit atomically on revision match. Upon error it returns structured error and **does not** alter project, history or source data. Snapshot-level Undo/Redo must restore topology and geometry with stable IDs; file saves include canonical engineering data, not ephemeral canvas state as part of engineering digest.

Suggested command service: `beginWire`, `previewRoute`, `commitWire`, `moveSegment`, `splitWire`, `toggleJunction`, `rotateAndReanchor`, `validateNet`. GUI must keep hover/preview state transient and never commit wires solely because pixels overlap.

A visual X crossing does NOT connect even when lines share same Net; one selected T branch joins only on an explicit junction transaction that splits/anchors the eligible segments. Cross-Net connections reject `NET_CONFLICT`; wrong Net, unknown pin, malformed unknown schema, wrong physical normal and 1µm mismatch all reject; editing with snap disabled still resolves an accepted pin to exact physical contact.

For export, canonical `project.gscad.json` v2 source scene is consumed, not canvas DOM. Preserve immutable `source_sha=e695c415fdced164b0e0c39c5249d030795a0aa6` provenance on the 23/15/62/16 fixture. Opening it initially with **0 wires** is valid, but all 15 routes must be `unrouted`, never `verified`.

## Mandatory tests

1. Same Net pin→pin, orthogonal route, physical endpoints and normals exactly retained.
2. Drag vertical interior segment by +3000µm; inverse Undo/Redo byte-identical model hash.
3. Unmarked X with different nets (and with the same net) remains graph-disconnected; no false dots.
4. Explicit T split + visible junction joins; separate hidden splice remains degree 2 with no dot.
5. Wrong-Net junction, malformed source PinRef, anchored pin 1µm drift and stale revision roll back.
6. Symbol rotation moves real pin exactly, never changes `PinRef`; no silent detachment.
7. Save/reopen preserves net names, members, anchors, segments and stable IDs; UI grid/snap independent.
8. Full E695 fixture exactly 23 components/15 source Net names/62 memberships/16 DA1 physical pins + 2 non-electric b graphics; negative historical route not imported as valid.

**Implementation note:** #122 R0 archive used 3 terminal anchors; #123 used an additional hidden splice and per-free endpoint identity. Their R0 JSON is a *draft*; this document resolves the proposed combined representation for initial shared v2 before it becomes a released format. Define JSON Schema and Python/TS conformance tests before accepting imported files.
