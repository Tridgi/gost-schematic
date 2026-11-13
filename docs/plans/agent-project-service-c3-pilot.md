# Issue #74 — Minimal P1 implementation plan and C3 acceptance exercise

**Status:** DESIGN / NOT IMPLEMENTED. Companion to
`docs/architecture/agent-project-service-rfc74.md`.
Target: independent future implementation PRs, **not** PR #73.

## Scope and ownership

This document describes a **later connected-C3 editing acceptance gate**, not
the next P1.1 implementation. The first independent implementation PR must
follow the [read-only persisted six-part roundtrip](agent-project-service-readonly-roundtrip.md)
first. That PR saves and cold-opens real Circuit/ExternalWireGraph and renders
revision-bound SVG/PNG; no arbitrary editing is enabled. The connected-C3
pilot requires later explicitly authorized safe multi-member branch routing. The in-process ProjectService owns every
command, controls revisions and produces snapshots. P0's existing PNG
renderer remains read-only. It must not be extended with write-on-render.

Owners for approval: ELEKTRIK handles authorized net/PinRef and safe routing;
PAINT handles symbol viewport/keepout/text geometry; YGO handles catalog
revision and DRAFT locking; QA checks frozen archive and independent regressions.

## Milestone plan

| Milestone | Delivery | Blocker / acceptance |
| --- | --- | --- |
| P1.1 | Controlled import, typed immutable `.gseproj`, store/open, model re-projection, real SVG/PNG/diagnostics | Fresh process reopens 6 components, 5 nets, 3 junctions, 16 authored wires; **no MCP writes** |
| P1.2 | Isolated transactional add/nominal/transform and fail-closed connected moves | CAS, replay, rollback, store journal/HEAD atomicity tests; no C3 routing claim |
| P1.3 | Typed add/nominal/transform/move with transactional write scopes | Isolated component move works; moved connected C3 must reject without corresponding route fix |
| P1.4 | Reviewed multi-member net branch repair | Current safe router accepts only 2-member nets; branch adapter requires ELEKTRIK+QA sign-off, no silent junction |
| P1.5 | Revision-bound SVG/PNG before/after + diff + MCP commands | Agent sees real ImageContent for both revisions, matched diagnostics and read-after-write hash |
| P1.6 | Codex CLI end-to-end agent test + docs | Model uses actual images to decide second inspect; no manual direct JSON editing |

## Exact eight-stage pilot protocol

**Baseline:** fixed import uses six current catalog parts: R1, R2, C1,
C2, C3 and L1. C3 is the **specialized** `capacitor.electrolytic`, origin
(100000,80000) µm, physical PLUS 1 at (91000,80000), MINUS 2 at
(109000,80000). Five semantic networks, sixteen wire segments and three
explicit junctions are the *initial* checksums. The older 18-wire archive
is not the migration source. TOP has four member pins, RIGHT three;
`route_circuit_two_pins` does not support them.

1. **Open:** `schematic_open_project(project_id)` loads a saved
   `.gseproj` from approved workspace, validates its catalog lock,
   projects to `Circuit` and `ExternalWireGraph` and returns
   `S0.revision_sha` and `S0.generation`.
2. **View:** `schematic_render_overview(project_id,revision=S0.sha)`
   returns genuine `ImageContent image/png`, exact SVG hash,
   `bbox_mm`, DPI, font warning and `S0.sha`.
3. **Prepare move:** desired delta `{x:0,y:+5000}` µm moves C3 to
   (100000,85000), with new physical pins (91000,85000) and
   (109000,85000). Agent gets a semantic/geometry **preview**, not a
   committed C3 with dangling old wires.
4. **Update two physical branches:** authorize precise branch IDs for
   TOP→C3.1 and RIGHT→C3.2; replace their terminal portions using an
   approved branch-aware safe adapter, preserving existing junction
   declarations and every other circuit net membership. If no safe
   complete route is found, reject with `ROUTE_UNSUPPORTED_MULTIPIN_NET`
   or `ROUTE_GEOMETRY_BLOCKED`. Do **not** fall back to geometry-only
   `route_two_pins`.
5. **Validate atomically:** submit `MoveComponent` and the approved
   branch updates in one `ProjectService.apply_transaction`, with
   expected `S0.sha`/generation and idempotency UUID. Validate electrical
   nets/polarity, exact contact endpoints, all junction/intersections,
   clearance/keepouts and draft provenance before commit. On failure,
   `S0.sha` stays head; no partial move, stale wires or new junctions.
6. **Render both versions:** after successful commit `S1`, request
   `schematic_render_overview(...revision=S1.sha)` and
   `schematic_inspect_component(...revision=S1.sha,reference=C3)`;
   get `S0/S1` image hashes and diagnostics each bearing the correct
   snapshot SHA. Request S0 images by exact revision for comparison.
7. **Diff:** output typed changes: `C3.origin_um y:80000→85000`;
   physical contact positions before/after; changed route/segment IDs,
   lengths and bends; immutable net member-set hashes and junction IDs;
   before/after ERC codes and screenshots. Assert no accidental net
   additions, swaps, merger or false crossing short. Do not assert
   the post-route segment count remains 16.
8. **Save/reopen:** `schematic_save_project(project_id,expected_revision=S1.sha)`
   writes atomically. Restart the service and
   `schematic_open_project(project_id, revision=S1.sha)`.
   Exact canonical bytes, revision hash, five nets, explicit junctions,
   physical pin polarity, symbol lock and deterministic SVG must match S1.

Each phase is a reproducible service call with a stored command ID,
request/response JSON trace and result hashes. The test must never
overwrite the authored Python review specimen or modify the frozen
historical C3 fixture.

## Additional negative / edge assertions

- Stale `S0` caller after `S1` commit → `REVISION_CONFLICT`, no changes.
- Retry identical key → identical S1; changed payload under same key →
  `IDEMPOTENCY_CONFLICT`, no duplicate component/wire.
- `C3.9` (invalid physical pin) → `PHYSICAL_PIN_INVALID`.
- Attempt to map C3.1 to RIGHT or flip physical polarity →
  `VALIDATION_REJECTED`.
- T or X intersection that would join TOP and RIGHT →
  `WIRE_NET_SHORT` / `JUNCTION_REQUIRED`, no auto-invented junction.
- Text/UGO footprint collision or clipping → explicit geometry diagnostic.
- Font unavailable → explicit warning (no fake ESKD approved image).
- Route adapter not ready → **BLOCKED**, no partial transaction;
  the test must not be marked as complete.
- Path outside configured workspace and symlink escape → `WORKSPACE_DENIED`.
- Interrupted write, concurrent transaction, partial serialization →
  no corrupt reachable HEAD; reopen last valid revision.
- Save/open/render repeated on both Python 3.12 and 3.13 →
  byte-identical canonical model SHA and deterministic SVG.
- All 21 catalog symbols remain DRAFT; wheel contains required data;
  no core public API drift.

## Program/QA completion criteria

The actual C3 move and re-route is **not implemented** by this RFC.
Do not mark the pilot green until a branch-capable safe route adapter
is explicitly approved, a real persisted project is edited via
MCP/ProjectService, the model returns two different revision hashes
and two real ImageContent blocks, and a cold reopen proves zero drift.

Suggested developer commands for later implementation:

```powershell
python -m pytest tests/agent_project_service -q
python -m pytest -q
ruff check .
python scripts/audit_symbol_catalog.py
python -m build --wheel
python scripts/verify_wheel_payload.py dist
```

All file names and commands in this section are target acceptance
procedures, not assertions that the proposed test suite exists today.
