# ADR-0010 — Visual schematic CAD MVP architecture

- **Status:** ACCEPTED FOR R1 IMPLEMENTATION, **not** product/release acceptance
- **Date:** 2026-11-15
- **Owner:** MAIN 4 (coordinator), #125 (sole integration owner)
- **Baseline:** `integration/stage0-12` at `9ae2561562c2b6e41069e8343d0e682bd37ab3d4`
- **Epic:** https://github.com/Tridgi/gost-schematic/issues/116
- **Inputs:** #117–#124, MASTER #125 comment 6900801841, successor audit #116 comment 6900895063
- **Original source fixture:** `e695c415fdced164b0e0c39c5249d030795a0aa6` (immutable)

## Decision

Use **Tauri 2 + React/TypeScript + custom SVG scene + Mantine + supervised existing Python engine**.

React/TypeScript owns command interaction and UI presentation; domain commands operate on the independent, validated, versioned integer-µm CAD project. A bespoke SVG canvas paints/manipulates geometry as a **projection** of engineering data; SVG paths, handles and visual X crossings never assign electrical connectivity.

Rust/Tauri owns file permissions and atomic persistence, subprocess lifecycle, versioned strict IPC, export and safe packaging. Python remains the existing MIT ESKD/UGO/layout/validation/render authority. The existing `gse-project` v1 contract is not the new editor `gscad-project` v2; interoperability is an explicit adapter, not a silent direct interchange. **No pre-existing write ApplyTransaction API is assumed**.

Use `ui/contracts/manual-wire-v2.md` as the R1 integration contract. In particular, #122's three endpoint kinds need #123's invisible splice and uniquely anchored free ends before production data import. Both source Net membership and physical PinRef identity are immutable across presentation edits.

## Evidence and alternatives

The scoring below is **provisional architectural judgment**, not FPS or Windows benchmark evidence. Weighting: physical CAD editing 30%, MVP time 20%, performance 15%, Python integration/export 15%, license/security 10%, UX 10%; reported by MASTER #125.

| Stack | MASTER weighted score / 5 | Decision |
| --- | ---: | --- |
| Tauri + React Flow + Python | 3.50 | Rejected as the sole wire/canvas semantics; conditional view adapter only |
| Tauri + tldraw + Python | 3.60 | Rejected for production MVP: license conditions and additional electrical bindings |
| **Tauri + custom SVG + Python** | **4.05** | **Selected for integrated R1** |
| Rust native egui/Slint | 3.50 | Rejected for MVP time/porting cost; Slint distribution licensing needs separate review |
| Qt / PySide6 + Python | 3.70 | Contingency when Tauri/Windows packaging fails |

Versions quoted in R0 reports (Tauri 2.12.x, Mantine 9.8.1, resvg 0.50.0, ReactFlow 12.x) are **candidate versions only**, not installed dependency locks. Before R2, package lockfiles and full licenses/security audit are mandatory. tldraw SDK is not MIT; production requires an appropriate license. Tauri on Windows requires WebView2, C++ Build Tools and Rust.

## Non-negotiable invariants

1. Signed **integer micrometres** (JSON safe integer within ±1,000,000,000); mm/pixels for display only. 1µm roundtrip exact.
2. `PartDefinition` (physical pins) distinct from `SymbolDefinition` (graphic pins, primitive strokes). `PinRef={component_id, physical_pin_number}`, never refdes/DOM handle ID/XY.
3. Source-declared `Net(id, members[PinRef])` cannot be rewritten by geometry or inferred from intersections. Segments are independent realized graph edges and a Net may remain partially routed.
4. `WirePolyline` orthogonal segment/vertex IDs, tagged `pin|junction|splice|free` terminal anchors. Only explicit Junction joins T/4-way; plain X is not joined; splice is electrically continuous but never draws a dot. Free endpoints have unique stable IDs, no coordinate-equality joins.
5. Atomic validated command transactions + compare-and-swap `base_revision`/`source_topology_hash`, Undo/Redo, reject bad PinRef, wrong Net, 1µm pin drift without mutating snapshot.
6. Independent `grid_visible` and `snap_enabled`; snapping off never detaches a stored real pin.
7. Original graphical `b` continuations remain NON-electrical `GraphicLine`, not `WirePolyline`.
8. Native `gscad-project` format v2 + strict schema/version validation, canonical deterministic source hash excluding workspace, provenance and immutable source lock.
9. True clean canonical SVG in physical millimetres, PNG generated from same clean SVG (300 DPI) with exact image dimensions and tagged pHYs; never save UI screenshot as electrical drawing.
10. All UGO remain DRAFT until independently ESKD/QA approved; no fonts redistributed without license audit.

## Frozen acceptance fixture

Read source commit `e695c415fdced164b0e0c39c5249d030795a0aa6`: **23 components / 15 original literal Nets / 62 member PinRefs / all 16 manufacturer physical DA1 pins / 2 graphical non-electrical 'b' continuations**. Old 91 wire segments, 37 junctions, 9 DRC errors + 32 warnings form a **negative fixture**, not a complete schematic. The current automatic router is partial (~9/15 latest layout; earlier ~10/15 elsewhere). Manual editing MUST NOT wait for auto-router 15/15.

## Development ownership (one shared UI branch, one integrator)

- **#125 MASTER:** owns branch/worktrees, app entrypoint, dependency locks, CI, E2E and integrated PR; no parallel root edits by specialists.
- **#117 UX:** acceptance journeys, hotkeys/accessibility and user-facing smoke scripts; no shared app root writes.
- **#118 desktop:** `ui/desktop/`, `ui/bridge/transport/`; OS shell, strict IPC, Python distribution and Windows build.
- **#119 React Flow:** independent review/test of interaction adapter and pin hit-testing; no production React Flow dependency without a second decision.
- **#120 SVG canvas:** `ui/editor/src/canvas/`; custom SVG viewport, pointer-to-world, bounds/hits/segment grips.
- **#121 design:** `ui/editor/src/components/`, `ui/editor/src/theme/`; Mantine AppShell, tree/inspector, accessible responsive themes.
- **#122 model:** `ui/editor/src/model/`, `ui/contracts/`, `ui/fixtures/`; v2 schema, genuine TL494 source import, validation, migrations/revisions.
- **#123 wires:** `ui/editor/src/wires/`; typed pin/junction/splice/free route transactions + Undo/Redo.
- **#124 export:** `ui/editor/src/export/`, `ui/bridge/export/`; canonical SVG and true PNG300, font/metrology tests.

Workstreams use independent Git worktrees or separate working copies. No changes to `main`, `integration/stage0-12`, frozen source or legacy owner branches; no merge without user permission.

## Release gates

- **R1:** one branch and ADR, actual source artifacts recovered and SHA checked, shared tagged anchor schema and branch ownership frozen. Documentation alone is NOT a runnable CAD.
- **R2:** reproducible `npm ci && npm run build`, `npm run dev`, real Windows browser open, place/move/rotate authentic R/C, mm canvas, tree/inspector, independent grid/snap, typecheck/lint/tests.
- **R3:** real pin-to-pin wire, segment dragging, T/X/splice/free safety, valid Undo/Redo, safe save/reopen, canonical SVG and PNG300. Playwright gestures verify outcomes, not merely DOM presence.
- **R4:** frozen 23/15/62/16+2 non-electric source imported with truthful partial route-status and negative gates, Windows Tauri package actually installed/launched, smoke and 23/1000 component benchmark measured. Full 15/15 automatic routing is a separate engine track.

Required CI: TypeScript typecheck, lint, JS/TS unit, Python 3.12/3.13 pytest+ruff, Rust cargo check/test when present, browser Playwright, Windows native smoke, exact µm/source invariants, graphics/PNG DPI and font verification. 60 FPS is a target **only after measurements**.

## Risk register

- **R0 source ZIP not in GitHub:** MASTER's isolated archive `gost-visual-cad-r0-20261115.zip` SHA256 claimed `72d67151168dc9c9af9b596366b312cb54c3ac28aab3cc2f733681d583327d6b`. Source bytes must be explicitly transferred and independently verified. Never fabricate a ZIP path or assert it has been integrated.
- Independent #122/#123 model/graph contract mismatch; block unvalidated source import until aligned.
- Existing engine lacks a general desktop write IPC; any implemented adapter must be explicit and strictly validated.
- Windows Rust/toolchain and gesture E2E unverified in reported R0; pending.
- GOST fonts/provenance and official 36 DRAFT catalogue remain unapproved.
- Legacy NET/DRC auto-router incompleteness must not block manual editor.

**Decision authority:** this ADR authorizes isolated R1/R2 engineering in `ui/visual-cad-mvp` only. It does NOT accept a Windows release or authorize merging to main/integration.
