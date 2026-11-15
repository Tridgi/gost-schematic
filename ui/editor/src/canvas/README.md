# CHAT 4 — SVG viewport geometry review candidate (R2)

**Role:** #120 canvas owner. **Base:** `ui/visual-cad-mvp` @ `9d2d8c1c683efba29338addc86631f8a6b68a6e6`. **Source scope:** this directory only; **target:** MASTER #125 Draft PR #126. Branch is independent; no merge to main/integration or to PR #126.

## Actually committed
- `precision.mjs`: dependency-free exact micrometre/pixel transforms, cursor-centered zoom, snap independent of physical PinRef, y-down exact quarter-turn+mirror terminal position/normal, physical pin hit-testing with **7 CSS px band**, wire segment hit band **5 CSS px** matching #119 QA, fail-closed ambiguous pin/segment hits, no inferred junction from X, explicit Junction prioritized over wire geometry. This never writes electrical Net membership.
- `precision.test.mjs`: reproducible Node 22+ tests for 50/100/200% zoom, 1µm precision, unsafe coordinates, signed pins, 6.99/7.01 CSS px pin and 4.99/5.01 CSS px wire hit bands, mirror/rotation, bare X vs intentional junction, ambiguous overlap and malformed diagonal route.
- `scene-projection.mjs` and `scene-projection.test.mjs`: **read-only** #122 ProjectFileV2 `PartDefinition` + `SymbolDefinition` + `SymbolInstance` adapter; verifies physical pin numbers, maps `top/bottom` → `up/down`, expands source graphical `line`, `rect`, `polyline` primitives into strokes, keeps `source_b_continuation` only in a *non-electrical graphics collection*. Authoritative Nets and wire IDs are unchanged.

```powershell
git fetch origin
git switch agent/chat4-canvas-r2-20261116
node --check ui/editor/src/canvas/precision.mjs
node --test ui/editor/src/canvas/*.test.mjs
```

**Observed independently during this active session:** 18 initial synchronous geometry checks and 10 read-only scene-projection checks executed against the exact function source before committing; the canvas JS boundary was aligned to 7/5px hit bands and corresponding committed Node tests were added. A separate richer local TypeScript/React canvas candidate + **31/31 PASS** Node geometry/controller tests (Node 22.16, TypeScript 5.8.3) was built and is available as an archived source artifact in CHAT 4's conversation, **not committed to this branch**. The independent committed Node test file should be rerun by CI/MASTER; **we do not claim that GitHub already ran it**. No React JSX pointer E2E, no Vite/npm, no 1000-symbol FPS, no source-locked TL494 importer, no Python IPC or Tauri build.

## How to integrate without changing the Net graph
- #122 supplies `CanvasScene` with approved symbol strokes, symbol origins and the actual `(component_id,physical_pin_number)` terminal anchors; do not derive a contact ID from refdes, coordinates, React handle or shape ID.
- #123 supplies `beginWire`, `commitWire`, `moveSegment`, `toggleJunction`, reanchor+undo transactions and rejects wrong Net, unknown physical pin, stale revision, 1µm drift. Canvas only emits user intentions; it cannot mutate `Net.members`, create free IDs or infer junctions from X.
- #125 supplies React/Vite root, browser and Windows test harness; #121 supplies controls and theme. The larger staged TSX `CanvasView` source has these interfaces but needs complete canonical v2 model and command API before integration.
- #119 should independently rerun 50/100/200% pin hit, ambiguous X, move interior H/V segment tests; #117 should verify keyboard/pointer capture and accessibility.

## Pending blocks
`REVIEW_REQUIRED #122`: the `gscad-project v2` model and E695 fixture arrived in independent Draft PR #134; `scene-projection.mjs` is the initial canvas-facing adapter, but the model/validator PR must pass CI and be integrated at a reviewed SHA before source-backed UI acceptance.
`REVIEW_REQUIRED #123`: signed-wire command implementation now exists in independent Draft PR #129. However `moveSegment(tx,wireId,segmentIndex,offsetUm)` takes **index**, while the canvas carries stable `segment_id`: see formal cross-review on PR #129. Do not link a stale index to an active drag; adapt by stable ID and source revision CAS.
`BLOCKED WAITING_FOR #125/#121`: React/Vite dependency locks, actual JSX typecheck and Playwright mouse smoke. CHAT 5 Mantine components exist in isolated Draft PR #132 but are not wired to this canvas.

**Not an R2 acceptance.** The committed source is a narrow independent reviewed geometry adapter. For full TSX viewport candidate use the separate artifact from CHAT 4 and import only after MASTER coordinates file ownership.