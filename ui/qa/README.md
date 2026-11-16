# CHAT 1 (#117) — UX/E2E acceptance pack (R2–R4)

**Status:** independent QA code on `ui/chat1-ux-e2e-r2`; **NOT** working-editor E2E PASS. This is an independent follow-up branched from shared `44dc17d9ea756eadb1656c83cd369ef2b2a3b828`; no edits to integration. Consumed by MASTER #125 after review. No changes to shared `ui/visual-cad-mvp`, `main`, or `integration/stage0-12`, no PR or merge.

## Files and actual run commands

- `acceptance-contract.mjs`: 12 case IDs with deterministic fixtures, action and invariant per case.
- `tests/manifest.test.mjs`: self-contained Node unit tests for manifest/source coverage.
- `visual-cad.ux.spec.mjs`: browser Playwright **mouse/keyboard assertions**, fails when fixture/QA adapter is missing. Snapshot is read-only, never used to mutate scene.
- `source-b-compat.mjs` + `tests/source-b-interop.test.mjs`: isolated read-only bridge and five negative/positive checks against **actual** `tl494-source-e695-v2.gscad.json` and #120 Canvas projector. Does not repair production Canvas; proves two non-electrical b marks must not be lost or converted to Wires.
- `package.json`: dependency-free `npm test` runner for Node>=22; only browser E2E needs Playwright installed.

```powershell
# Runnable now on Node >=20 in repository root:
cd ui/qa
npm test
npm run check:e2e

# Only after MASTER adds Playwright dependency and starts a Vite editor:
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:5173'
cd ui/qa
npx playwright test visual-cad.ux.spec.mjs --reporter=list
```

**The first two commands validate only QA source, not GUI behavior.** Browser tests must not be skipped and must not be reported as PASS until the actual UI + data/wire engine are implemented and tested. Per-case proof must cite exact UI HEAD/lockfile SHA, browser version/OS, traces, and saved export bytes.

## Requested development-only test protocol (negotiation with #125/#120/#121/#122/#123)

1. `/?qaFixture=qa-r-c|qa-two-nets|qa-crossing|qa-e695-tl494`: deterministic UI fixture loader, dev/test builds only. Stable fixture IDs `R1`, `C1`, `R2` and physical numbers; `qa-two-nets` has same-Net `R1:1 → C1:1`, different-Net `R2:1`, and at least one pre-existing wire with draggable interior segment. `qa-crossing` contains one same-Net and one other-Net unmarked X, an eligible same-Net T and a splice.
2. `window.__GSCAD_QA__.snapshot()` — **read-only** engineering-state observation, omitted in production. Return `{project:ProjectV2.project,workspace:{...ProjectV2.workspace,theme,active_tool},topology:{auto_connected_crossings,junctions_at_unmarked_crossings,electrical_graph,visible_junction_dot_count,visible_splice_dot_count},revision,history_depth,persistence:{last_saved_sha256},export:{...}}`. **Canonical graph fields**: `project.provenance.source_sha`, `project.nets[].members`, `project.components[].part_id`, `project.part_definitions[].physical_pins`, `project.sheets[].instances[].rotation_deg`, `project.sheets[].wires/junctions/splices/graphics`, `project.settings.grid_visible/snap_enabled`. Never invent `project.source_nets`, `project.wires`, `project.da1_physical_pins`, `project.source_sha`. The ephemeral `workspace.theme/active_tool` are QA observations, **not persisted engineering state**. Prevent exposing write/mutate methods on the dev-only QA bridge.

3. Controls: stable `data-testid`: `editor-root`, `project-toolbar`, `sheet-tabs`, `catalog`, `catalog-search`, `catalog-item-resistor`, `cad-canvas`, `object-tree`, `inspector`, `status-bar`, `tool-select`, `tool-wire`, `tool-junction`, `selected-component`, `inspector-nominal`, `anchored-wire-endpoint`, `inspector-vertex-x`, `diagnostic-PIN_ANCHOR_MISMATCH`, `toggle-grid-visible`, `toggle-grid-snap`, `toggle-theme`, `command-palette`, `wire-segment-handle`, `junction-target`, `save-project`, `export-svg`, `export-png300`, `diagnostic-NET_CONFLICT`.
4. Physical pin hit targets have `data-testid="pin-target"`, `data-component-id`, `data-physical-pin-number` matching source `PinRef=(component_id,physical_pin_number)`. Exact target is a domain ID, not a proximity/coordinate inference; grid snapping independent.
5. When `R`, `W`, `Ctrl+K`, `Esc` shortcuts operate, focus inside editable Inspector/Name fields must not inadvertently change tools; show focus rings and useful aria labels. `Ctrl+K` may be browser-reserved, supply an equivalent palette button.
6. Save must reflect completed canonical persistence, not client-only dirty flag. The dev/test-only `/?qaOpenLastSaved=1` route MUST reload actual saved bytes (not reinstate the source fixture). Browser preview must offer genuine downloadable SVG/PNG to Playwright; the test reads SVG XML/physical mm and PNG chunk structure/pHYs 300 DPI directly. Native Tauri save/export also requires Windows E2E by #118/#125. Do not implement dummy metadata or an in-memory-only fake save to satisfy tests.

## Evidence/acceptance mapping

| Gate | Tests | Readiness |
|---|---|---|
| R2 shell and selection | CAD-UX-R2-01..05 | Pending live Vite app and Mantine shell (#125,#121) |
| R3 manual wire and negative topology | CAD-UX-R3-01..05 | Pending geometry/pin adapter (#120), v2 model (#122), wire transactions (#123) |
| R3 save/export bytes | CAD-UX-R3-06 | Test checks persisted-project roundtrip, SVG XML and PNG signature/IHDR/pHYs; still BLOCKED until real app & download adapter; #124 adds parity/font tests |
| R4 source authenticity | CAD-UX-R4-01 | Pending genuine frozen E695 importer (#122/#125), not synthetic TL494 |

## Accessibility / manual verification (not automated by this pack)

- Keyboard-only search/placement/selection/editor focus; Escape exits state and never commits ghost wire. Check accurate language/role/aria-describedby for diagnostic items.
- Windows 11 at **125% and 200% system scaling** on WebView2, with 1280×720 and wide desktop; CSS browser zoom is NOT equivalent to OS display scaling.
- Visually inspect high-contrast dark/light, disabled states, screen-reader announcement of source Net / physical pin, error/warning not color-only.
- Save/restore keyboard focus after modal, do not steal native `Ctrl+S` inside text field. Resizable dock panels must remain reachable.
- Wrong-Net and +1µm anchored endpoint errors must reject with unchanged project revision/history; wire X never electrically joins automatically.

## Handoff

`BLOCKED WAITING_FOR`: #125 React/Vite root + deterministic QA loader, #120 SVG canvas pointer gestures, #121 UI selectors/components, #122 `gscad-project` v2 typed model/fixture, #123 exact wire transaction API, #124 canonical export bytes. Until these paths are committed with SHA, **do not report UI E2E PASS**. Keep integration branch protected by MASTER ownership and no auto-merges.

## Cross-review findings / exact fixture requirement

- Actual source E695 23 components/15 Nets/62 memberships/DA1 16 physical pins/2 non-electric b marks is checked in `source-b-interop.test.mjs`. Native #120 `projectToCanvasScene` at `44dc17d9ea756eadb1656c83cd369ef2b2a3b828` **throws `UNKNOWN_GRAPHIC_KIND`** on `Graphic.kind='source_b_continuation'`. QA-only `projectForUXReview()` produces 23 symbols, 2 non-electric b strokes, 0 wires and leaves input byte-identical. Production owner #120 must add native support and negative tests, then remove the QA workaround or keep it as an oracle; no silent net addition.
- The fixture `qa-two-nets` must use **real ProjectFileV2** `Component.id` values `R1/C1/R2`, a **valid source Net** shared by `R1:1,C1:1`, another Net containing `R2:1`, and one draggable bent wire. Do not import `gscad-spike` v1 into ProjectFileV2.
- The `qa-e695-tl494` fixture must load the **actual** `ui/fixtures/tl494-source-e695-v2.gscad.json`, not synthetic 16-pin IC. Never mark unrouted source Nets verified.
