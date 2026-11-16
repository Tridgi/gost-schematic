# CHAT 4 — SVG CAD viewport modules / integration handoff (R2 candidate)

**Owner:** Issue #120. **Draft PR:** #133 into `ui/visual-cad-mvp`; MASTER #125 owns the target branch. This directory is a view/interaction layer, **not** the electrical graph, native save format, certified GOST renderer or packaged application.

## Code delivered

| File | Role |
|---|---|
| `precision.mjs` | Signed µm camera transforms, discrete rotated/mirrored PinRef locations + normals, safe pointer hit testing. 7 CSS px pin vs 5 CSS px wire threshold, ambiguous overlap fails closed; zero/diagonal segments rejected; zoom validates camera. |
| `scene-projection.mjs` | Read-only canonical `gscad-project v2` Part/Symbol/Instance mapping, source physical pin number check, `top/bottom` to `up/down` normal, line/rect/polyline to strokes. `Graphic.kind=source_b_continuation` is strictly **non-electric ink**, no wires or source Net changes. |
| `wire-intents.mjs` | Captures `segment_id`, project/source lock and revision at pointer-down, resolves current segment index inside CAS boundary, passes command to #123 ManualWireEngine; rejects stale/duplicate/foreign identity. Does not directly mutate project/wires. |
| `controller.mjs` | Pure pointer/keyboard state machine: select pin, begin/commit wire intent, bend, free end Enter, Escape cancel, H/V segment drag, viewport pan; command dispatcher owns reject/rollback and Undo. |
| `render-preview.mjs` | SVG **viewport-only** painter for transformed UGO strokes, signed wires, explicit junction dots and two E695 graphical b continuation marks. No dots for splices or bare X. NOT physical print export. |
| `CanvasViewport.tsx` | Real controlled React SVG rendering layer: signed `ProjectFileV2` symbol strokes and PinRef circles, current `WiringSnapshot` wire segments, explicit junction dots, source-b non-electrical ink, grid, zoom/pan, pointer/keyboard interactions dispatched to the host through `CanvasIntent`. It is a component to be mounted by MASTER, **not** a separate CAD app. |
| `precision.d.mts`, `scene-projection.d.mts`, `controller.d.mts`, `wire-intents.d.mts` | Explicit TypeScript interfaces compatible with CHAT 6 model, CHAT 7 ManualWireEngine and MASTER's React scene. Reject accidental implicit `any[]` coordinate tuples in production call sites. |
| `*.test.mjs` | Exact model fixture, negative cases, source lock, state machine, viewport and QA regressions. |

## Reproducible tests (Node >=22, no npm dependencies)

```bash
git fetch origin
git switch agent/chat4-canvas-r2-20261116
node --check ui/editor/src/canvas/precision.mjs
node --check ui/editor/src/canvas/controller.mjs
node --check ui/editor/src/canvas/scene-projection.mjs
node --check ui/editor/src/canvas/render-preview.mjs
node --check ui/editor/src/canvas/controller.mjs
node --test ui/editor/src/canvas/*.test.mjs
```

Tests ingest the **actual** committed `ui/fixtures/tl494-source-e695-v2.gscad.json`: 23 components, 15 original named Nets, 62 source PinRef memberships, 16 DA1 physical pins, 2 b source-graphics, 0 accepted legacy wires. This is NOT 15/15 route acceptance. Symbols are still DRAFT.

**Observed during current active session:** exact GitHub JavaScript source and tests executed in an isolated V8 harness: **43 PASS / 0 FAIL**, including actual frozen fixture; GitHub Actions `canvas-and-qa` completed **83/83 PASS** at `fca756a31411060a926e4ec0d5446f4230ba8a44` ([run 43895600182](https://github.com/Tridgi/gost-schematic/actions/runs/43895600182)); independent CHAT 3 `ui/qa/chat3-canvas/real-integration.test.mjs` from PR #136: **13 PASS / 0 FAIL** when rerun against our updated production modules in V8. The V8 harness provides Node assert/test substitutes; CI's 83/83 PASS is the independently run real Node suite. Neither validates the new React viewport mouse gestures without Playwright. GitHub Actions `canvas-and-qa` on PR #133 and root UI must be checked at exact latest HEAD before PASS_AT_SHA.

## Integration boundary for MASTER

- #122 canonical `ProjectFileV2` is the authoritative document, `projectToCanvasScene` is strictly a one-way view projection. No Net inferred from pixel X/T or shape click.
- #123 typed `ManualWireEngine`: translate signed source and target PinRefs into validated `constructWire` and atomic CAS. The canvas only emits intentions. `commitSegmentDrag(engine,token,delta,commandId)` provides the first safe stable ID→index adapter; don't use a stale rendered index.
- #121 Mantine `EditorShell` accepts a canvas slot; MASTER must supply React/Vite root, command dispatcher, model→wire snapshot and history. `controller.mjs` is ready to wrap in a UI component; the prior TSX candidate exists in CHAT4 archive but is **not** in PR #133 and not JSX-compiled.
- #124 canonical Python SVG/PNG300 stays separate from `render-preview.mjs`. UI screenshot or viewport SVG is NEVER the native engineering export.

**BLOCKED WAITING_FOR:** #125 integrated React/Vite app root, browser pointer captures and Playwright smoke; #117/#119 independent human/cursor gestures at zoom 50/100/200%; #123 approved checked ProjectV2→WireEngine transaction dispatcher and Net conflict rollback; #124 physical 300DPI export through same validated canonical scene; #118 verified Windows Tauri bridge. No PR merge without user permission.

Current browser environment cannot navigate even localhost in Chromium (`ERR_BLOCKED_BY_ADMINISTRATOR`), so browser E2E was NOT passed here.
