# CHAT 1 (#117) — UX/E2E acceptance pack (R2–R4)

**Status:** independent QA code on `ui/ux-acceptance-117`; **NOT** working-editor E2E PASS. Consumed by MASTER #125 after review. No changes to shared `ui/visual-cad-mvp`, `main`, or `integration/stage0-12`, no PR or merge.

## Files and actual run commands

- `acceptance-contract.mjs`: 12 case IDs with deterministic fixtures, action and invariant per case.
- `tests/manifest.test.mjs`: self-contained Node unit tests for manifest/source coverage.
- `visual-cad.ux.spec.mjs`: browser Playwright **mouse/keyboard assertions**, fails when fixture/QA adapter is missing. Snapshot is read-only, never used to mutate scene.

```powershell
# Runnable now on Node >=20 in repository root:
node --test ui/qa/tests/manifest.test.mjs
node --check ui/qa/visual-cad.ux.spec.mjs

# Only after MASTER adds Playwright dependency and starts a Vite editor:
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:5173'
npx playwright test ui/qa/visual-cad.ux.spec.mjs --reporter=list
```

**The first two commands validate only QA source, not GUI behavior.** Browser tests must not be skipped and must not be reported as PASS until the actual UI + data/wire engine are implemented and tested. Per-case proof must cite exact UI HEAD/lockfile SHA, browser version/OS, traces, and saved export bytes.

## Requested development-only test protocol (negotiation with #125/#120/#121/#122/#123)

1. `/?qaFixture=qa-r-c|qa-two-nets|qa-crossing|qa-e695-tl494`: deterministic UI fixture loader, dev/test builds only. Stable fixture IDs `R1`, `C1`, `R2` and physical numbers; `qa-two-nets` has same-Net `R1:1 → C1:1`, different-Net `R2:1`, and at least one pre-existing wire with draggable interior segment. `qa-crossing` contains one same-Net and one other-Net unmarked X, an eligible same-Net T and a splice.
2. `window.__GSCAD_QA__.snapshot()` — **read-only** engineering-state observation, omitted in production. Contract: `{project:{source_sha,source_topology_hash,source_nets,components:[{id,rotation,physical_pin_numbers}],wires:[{id,vertices:[{at_um,anchor}]}],junctions,da1_physical_pins,non_electrical_b_graphics},workspace:{grid_visible,snap_enabled,theme,active_tool},topology:{auto_connected_crossings,junctions_at_unmarked_crossings,electrical_graph,visible_junction_dot_count,visible_splice_dot_count},revision,history_depth,persistence:{last_saved_sha256},export:{last_svg_width_mm,last_png_dpi}}`. Use actual authoritative transactions, not pixel inference. `source_topology_hash` remains invariant for purely visual edits.
3. Controls: stable `data-testid`: `editor-root`, `project-toolbar`, `sheet-tabs`, `catalog`, `catalog-search`, `catalog-item-resistor`, `cad-canvas`, `object-tree`, `inspector`, `status-bar`, `tool-select`, `tool-wire`, `tool-junction`, `selected-component`, `inspector-nominal`, `toggle-grid-visible`, `toggle-grid-snap`, `toggle-theme`, `command-palette`, `wire-segment-handle`, `junction-target`, `save-project`, `export-svg`, `export-png300`, `diagnostic-NET_CONFLICT`.
4. Physical pin hit targets have `data-testid="pin-target"`, `data-component-id`, `data-physical-pin-number` matching source `PinRef=(component_id,physical_pin_number)`. Exact target is a domain ID, not a proximity/coordinate inference; grid snapping independent.
5. When `R`, `W`, `Ctrl+K`, `Esc` shortcuts operate, focus inside editable Inspector/Name fields must not inadvertently change tools; show focus rings and useful aria labels. `Ctrl+K` may be browser-reserved, supply an equivalent palette button.
6. Save status must reflect completed canonical persistence, not client-only dirty flag. SVG/PNG metrics are **receipts**, but real file readback, SVG XML mm/viewBox, PNG pHYs and 300 DPI must be independently checked by #124/#125. Don't implement dummy values just to satisfy the test.

## Evidence/acceptance mapping

| Gate | Tests | Readiness |
|---|---|---|
| R2 shell and selection | CAD-UX-R2-01..05 | Pending live Vite app and Mantine shell (#125,#121) |
| R3 manual wire and negative topology | CAD-UX-R3-01..05 | Pending geometry/pin adapter (#120), v2 model (#122), wire transactions (#123) |
| R3 save/export bytes | CAD-UX-R3-06 | Partial browser receipt only; #124/#125 byte-level roundtrip required |
| R4 source authenticity | CAD-UX-R4-01 | Pending genuine frozen E695 importer (#122/#125), not synthetic TL494 |

## Accessibility / manual verification (not automated by this pack)

- Keyboard-only search/placement/selection/editor focus; Escape exits state and never commits ghost wire. Check accurate language/role/aria-describedby for diagnostic items.
- Windows 11 at **125% and 200% system scaling** on WebView2, with 1280×720 and wide desktop; CSS browser zoom is NOT equivalent to OS display scaling.
- Visually inspect high-contrast dark/light, disabled states, screen-reader announcement of source Net / physical pin, error/warning not color-only.
- Save/restore keyboard focus after modal, do not steal native `Ctrl+S` inside text field. Resizable dock panels must remain reachable.
- Wrong-Net and +1µm anchored endpoint errors must reject with unchanged project revision/history; wire X never electrically joins automatically.

## Handoff

`BLOCKED WAITING_FOR`: #125 React/Vite root + deterministic QA loader, #120 SVG canvas pointer gestures, #121 UI selectors/components, #122 `gscad-project` v2 typed model/fixture, #123 exact wire transaction API, #124 canonical export bytes. Until these paths are committed with SHA, **do not report UI E2E PASS**. Keep integration branch protected by MASTER ownership and no auto-merges.
