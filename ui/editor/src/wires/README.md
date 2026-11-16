# CHAT 7 — typed Manual Wire engine (gscad-project v2 interface)

**Scope:** independent integer-µm wiring domain service; not the canvas, not a full CAD app.
**Owner:** GitHub Issue #123; upstream integration contract: `ui/contracts/manual-wire-v2.md`; consumer: MASTER #125.
**License:** MIT (original implementation; no GPL source copied).

## Run locally

```bash
cd ui/editor/src/wires
npm run typecheck  # requires installed tsc 5.8+ on PATH; no project npm dependencies
npm run build
npm test           # node 22, built-in node:test
```

The package has no external runtime dependencies. `npm test` consumes `dist/manual-wire.js`, so build first.
No `npm ci` is necessary for this isolated spike; the future MASTER-owned React/Vite root will supply its own pinned TS toolchain.

## Architecture and invariants

- Wire schema follows `manual-wire-v2`: `PinRef{component_id,physical_pin_number}`, `Net` declarations, `WirePolyline(vertices,segments,mode='orthogonal')`, terminal `pin|junction|splice|free`, interior `bend`. This file uses a **wire submodel snapshot**, not the entire #122 `ProjectFileV2`; adapter remains unimplemented.
- Signed integer micrometres (`Number.isSafeInteger` and ±1e9), transformed exact physical pin positions and normals, immutable declared Nets during route commands. Canvas pixels and visible crossing geometry are never electrical truth.
- T/X: unmarked cross remains disconnected; selected explicit same-Net junction splits backbones and draws one dot; foreign-Net wire **or physical pin** contact at a visible junction is rejected. Hidden splice is electrically conductive exactly degree 2, no dot; free IDs unique per wire-side even at identical coordinates.
- Commands validate a cloned snapshot, then commit atomically on matching `(project_id,source_topology_hash,base_revision)`. Error leaves prior document, history, generation unmodified.
- Undo/Redo revisions are deliberately **monotonic** to protect CAS from ABA replay. Compare only engineering model content (excluding `revision`) for Undo/Redo topology equality.
- For pin move/rotate with wires, no silent detachment: `REROUTE_REQUIRED` without explicit consent; consent creates a Manhattan local suggestion tagged `needs_routing_review` pending collision/ERC review.
- `validateNet()` uses DSU from **typed endpoint identities**, requires actual source physical-pin membership and rejects `verified` whenever any wire is dangling or marked for DRC review. `danglingEndpoints(netId)` returns explicit per-wire-side diagnostics.

## Status and gates

**PASS (local):** strict TypeScript typecheck and 42 `node:test` cases (physical pin→pin, T/X, distinct Net, foreign dot, split/merge, interior +3000 µm, corner move, exact 1µm, symbol R90, stale/ABA CAS, rollback, save/parse, source membership preservation, explicit dangling endpoint diagnostics).
**BLOCKED:** #122 canonical `ProjectFileV2` adapter/fixture committed to GitHub; #120 interactive canvas + #119 independent mouse hit tests; #124 real clean SVG/PNG300; #125 integration app root and Windows browser/CI. No E695 23/15/62/16+2 source import done here; 15/15 autorouter never claimed.

**CI caution:** green Python workflow runs on PR #126 do not execute this TypeScript suite. MASTER must install Node/TS and add explicit wire tests on its integration CI before declaring R3 accepted. This branch is review-only; do not merge absent user approval.
