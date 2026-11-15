# GOST SCHEMATIC — VISUAL CAD R0 (independent isolated spike)

**Status: EXPERIMENT / NOT A RELEASE.** Prepared for [Issue #125](https://github.com/Tridgi/gost-schematic/issues/125) under [#116](https://github.com/Tridgi/gost-schematic/issues/116). No change to `main`, `integration/stage0-12` or existing PRs. The proposed Tauri/React architecture is **not approved**: all eight sibling R&D reports have now been received and reviewed, but no shared branch/API acceptance or native/browser smoke is complete.

## Run on Windows (PowerShell)

Unpack this folder, open PowerShell in the folder containing `index.html`, and execute:

```powershell
py -3 -m http.server 8000 --bind 127.0.0.1
```

Open **http://127.0.0.1:8000** in Microsoft Edge / Chrome. There are no network requests or installed frontend packages. To run 19 core tests, separately install Node.js 22+ and execute:

```powershell
node --test tests/core.test.mjs
node --check core.mjs
node --check app.mjs
```

`npm`/`Tauri`/`Rust` are **not needed for this experimental preview**. This is not a `.exe`; there is no verified Windows installer. Its clean SVG and native `.gscad.json` are generated directly by the browser.

## Test workflow

1. Select **⌁ Проводник** (or `W`). Blue contacts appear on the source-aligned draft R/C and the **synthetic demonstration** TL494.
2. Click `R1.2`, then `C1.1`. A genuine four-vertex ortho polyline is added with both endpoints tied to typed `PinRef`, and a locally-created Net `N$1`.
3. Switch to **↖ Выбор** (`V`). Drag the **middle vertical** wire segment. Outer endpoint segments are locked.
4. Select an element. Drag it to relocate it; use `R` to rotate or modify `X/Y` to 0.001 mm in the right inspector. Connecting wire endpoints follow it.
5. `Ctrl+Z` / `Ctrl+Shift+Z` for undo/redo. Use **Сохранить**, then **Открыть** with the downloaded `.gscad.json`.
6. Toggle **Сетка** independently of **Привязка**. Export **SVG** and **PNG 300**; grid/selection/pin targets do not appear in the output.
7. Choose **Новый** to reset. Add another sheet using `+`. You may also click or drag a catalogue element into the workspace.

### Implemented in this standalone source

- Top project/sheets, left library/search, vector mm sheet, SVG preview/pan via wheel zoom, right hierarchy and inspector, bottom status + grid/snap toggles, settings and dark/light themes.
- Synthetic 16-pin TL494 demo **not a signed original IC**; R/C are drawn from the exact DRAFT dimensions and pin coordinates of the `integration/stage0-12` catalogue.
- Millimetres in presentation, integer micrometres in canonical model, independently configured grid/snap, typed PinRef, named electrical Nets and authored wire graph. Connected symbol motion calls `reanchor()`.
- True editable `gscad-spike` JSON with `version: 1`; guarded parse. Local storage writes recovery snapshots; a guarded recovery prompt restores them on reload (browser runtime unverified).
- User wires, multi-PinRef extension of a newly authored net, orthogonal internal segment displacement, explicit same-net junction records carrying connectedWireIds (no full segment split/splice yet), prevention of accidental declared Net merges.
- Real 420x297mm SVG via model serialization, not a DOM screenshot. PNG by rasterizing that same SVG and attaching actual `pHYs` metadata for 300 DPI.

### Known blockers / limitations

- **Not authentic TL494**: source-locked `e695c415fdced164b0e0c39c5249d030795a0aa6` fixture (23/15/62) and exact 16 signed package pins have **not been imported**. The TL494 drawing here is a conspicuous synthetic illustration; no manufacturer pin functions are asserted. Existing 9/15 auto-route work is untouched.
- **Not an integrated GSE project**: the strict current `gse-project` v1/ProjectService write contract differs; no unsafe JSON downcast or silent net join is attempted. Adapter needs data-model and physical IC signing.
- No real external Python process, Tauri/React shell, MSI/EXE, font-locked Type A, production validation, collision engine or full source DRC, no arbitrary manual partial endpoint commits, no bus/label net resolution, no full manual multi-branch junction route re-authoring.
- Outer docks have pointer/keyboard resize and local preference persistence in code (**browser unverified**); there is no nested tree/inspector resize, command palette or browser E2E completion. Performance of browser UI / Windows installation NOT measured.
- Browser test in the controlled authoring environment was blocked with `ERR_BLOCKED_BY_ADMINISTRATOR` for both localhost and file access. **The app therefore has not been proven functional in a user browser**; test it on Windows before declaring release acceptance.
- PNG exporter source is exercised in a unit test for the `pHYs` chunk; the sample raster `sample-export-300dpi.png` was separately generated from the same SVG using CairoSVG and then tagged with that PNG chunk. **That is not evidence of an end-to-end browser PNG download.**

## Files

- `index.html`, `style.css`, `app.mjs`: standalone browser GUI implementation.
- `core.mjs`: canonical geometry, typed graph, validation and true SVG/PNG functions.
- `tests/core.test.mjs`: Node built-in `node:test` unit tests.
- `sample-project.gscad.json`, `sample-export.svg`, `sample-export-300dpi.png`: real fixture/output generated offline to check geometry and DPI.
- `docs/ADR-0001-CANDIDATE.md`: explicitly **provisional** weighted architecture comparison.
- `docs/MASTER-REPORT.md`: coverage, evidence, risks, integration strategy.
- `docs/INTEGRATION-CONTRACT-R1.md`: proposed multi-agent ownership and R1→R3 typed handoff gates.

## Licensing and provenance

This spike's authored source is MIT. It bundles no additional JavaScript packages, proprietary fonts, third-party SVG art, tldraw code or copied KiCad/QElectroTech source. Draft R/C dimensions and exact pins match:

- `src/gost_schematic/catalog/symbols/resistors/fixed.json`, blob SHA `4114cecde344ce184b8271851141c254cfa9f7aa`
- `src/gost_schematic/catalog/symbols/capacitors/fixed.json`, blob SHA `3e173b1cd52120f4cedd26e0f43348864119ec47`

Symbols remain **DRAFT**, not normative ГОСТ/ЕСКД approved. Main repository uses MIT. `sample-export-300dpi.png` was rasterized with **CairoSVG** as a testing-only tool, LGPLv3 (not a bundled runtime dependency).

## MASTER R0 local hardening patch — 2026-11-16

This independent R0 package remains a **sandbox prototype** in `gscad-spike` v1 format. It is not the authoritative `gscad-project` v2 of Issue #122 and MUST NOT be imported without a reviewed migration. The local follow-up addresses atomic `appendWire` validation, orphan junction removal when deleting a wire, stricter malformed network/wire/sheet rejection, and guarded UI commit/save behavior. `node --test tests/core.test.mjs`: 26 PASS / 0 FAIL in this environment. Full browser gesture acceptance and a native Tauri build are still unverified. These changes have NOT been committed to GitHub; only the separately authored `ui/integration/source-gate.mjs` is on branch `ui/visual-cad-mvp`.

## Browser smoke (2026-11-16, Chromium in restricted Linux sandbox)

`python tests/browser_smoke.py` runs real browser pointer/keyboard/download interactions against the R0 HTML/CSS/ES modules in Chromium 142 using Playwright; the local browser policy prevents any `http://`, `https://` or `file://` navigation, so the harness embeds trusted original static assets in an inert about:blank document and replaces localStorage with an ephemeral in-memory shim. This validates browser interaction/render/export **only**, not deployment by a real local HTTP server, multiwindow storage persistence, npm/Vite, React/Mantine, or Windows/Tauri. It requires Python Playwright, Chromium and Pillow installed separately; no online code is fetched by the test.

Observed PASS: pin R1.2 -> C1.1 by actual mouse clicks, orthogonal wire, Undo/Redo, interior segment displacement ~3mm with endpoints unchanged, separate grid/snap toggles, dark/light switch, JSON save+reload, clean mm SVG export, A3 4961x3508 PNG with ~300DPI pHYs. An actual screenshot is captured at `/mnt/data/r0-inline-e2e-final.png`. Real E695 frozen 23/15/62/16+2 graphics is *not* part of this demo. A dark-theme visual regression (white lines on white schematic sheet due inherited currentColor) was corrected by explicitly setting the SVG symbol group color #202935.