# CHAT 4 — SVG viewport geometry review candidate (R2)

**Role:** #120 canvas owner. **Base:** `ui/visual-cad-mvp` @ `9d2d8c1c683efba29338addc86631f8a6b68a6e6`. **Source scope:** this directory only; **target:** MASTER #125 Draft PR #126. Branch is independent; no merge to main/integration or to PR #126.

## Actually committed
- `precision.mjs`: dependency-free exact micrometre/pixel transforms, cursor-centered zoom, snap independent of physical PinRef, y-down exact quarter-turn+mirror terminal position/normal, physical pin hit-testing, fail-closed ambiguity when two signed pins coincide, no inferred junction from X, visible Junction prioritized over wire geometry. UI hit path emits visual results only and never writes electrical Net membership.
- `precision.test.mjs`: reproducible Node 22+ tests for 50/100/200% zoom, 1µm precision, unsafe coordinates, signed pins, mirror/rotation, bare X vs intentional junction, ambiguous overlap and malformed diagonal route.

```powershell
git fetch origin
git switch agent/chat4-canvas-r2-20261116
node --check ui/editor/src/canvas/precision.mjs
node --test ui/editor/src/canvas/precision.test.mjs
```

**Observed independently during this active session:** 18 synchronous function-level checks executed in the connected GitHub submission process before the identical function source was committed. A separate richer local TypeScript canvas candidate + 29/29 Node tests (geometry/controller) was built and is available as a downloadable archive in CHAT 4's conversation, **not committed to this branch**. The independent committed Node test file should be rerun by CI/MASTER; **we do not claim that GitHub already ran it**. No React JSX pointer E2E, no Vite/npm, no 1000-symbol FPS, no source-locked TL494 importer, no Python IPC or Tauri build.

## How to integrate without changing the Net graph
- #122 supplies `CanvasScene` with approved symbol strokes, symbol origins and the actual `(component_id,physical_pin_number)` terminal anchors; do not derive a contact ID from refdes, coordinates, React handle or shape ID.
- #123 supplies `beginWire`, `commitWire`, `moveSegment`, `toggleJunction`, reanchor+undo transactions and rejects wrong Net, unknown physical pin, stale revision, 1µm drift. Canvas only emits user intentions; it cannot mutate `Net.members`, create free IDs or infer junctions from X.
- #125 supplies React/Vite root, browser and Windows test harness; #121 supplies controls and theme. The larger staged TSX `CanvasView` source has these interfaces but needs complete canonical v2 model and command API before integration.
- #119 should independently rerun 50/100/200% pin hit, ambiguous X, move interior H/V segment tests; #117 should verify keyboard/pointer capture and accessibility.

## Pending blocks
`BLOCKED WAITING_FOR #122`: committed typed `gscad-project v2` model, approved Part/SymbolDefinition exporter and exact `CanvasScene` adapter (SHA needed).
`BLOCKED WAITING_FOR #123`: committed tagged pin/junction/splice/free commands and revision/Undo callbacks (SHA needed).
`BLOCKED WAITING_FOR #125/#121`: Vite+React dependency locks, real JSX typecheck/Playwright mouse smoke (SHA needed).

**Not an R2 acceptance.** The committed source is a narrow independent reviewed geometry adapter. For full TSX viewport candidate use the separate artifact from CHAT 4 and import only after MASTER coordinates file ownership.