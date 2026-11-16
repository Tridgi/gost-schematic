# CHAT 8 — canonical SVG/PNG300 and validated ProjectV2 export (R2/R3 candidate)

Owner: Issue #124, Draft PR #130, isolated branch `ui/chat8-export-bridge-r1`.
The integration target is `ui/visual-cad-mvp`; **do not merge without authorization**.

## Actual paths and authority

1. **Original Python engine:** `engine_adapter.py` calls the existing
   `gost_schematic.rendering.external_wire_sheet.render_external_wire_sheet`
   with `diagnostic=False`, `strict_layout=True`; these real engine UGO
   primitives and authored lines are handed to `canonical.py`. No inference
   of Nets or junctions from SVG pixels.
2. **New validated `gscad-project` v2:** `project_v2.py` accepts the *exact*
   `ui/editor/src/model/contract.py` document. It calls `validate` and
   checks `digest(document)` against `expected_project_sha256` before
   rendering. The read-only scene projection uses
   `PartDefinition/SymbolDefinition.graphics`, placed component transforms
   (`pin_world`, integer µm), actual authored `WirePolyline.segments`,
   `Net.name` and stable `PinRef=(component_id,physical_pin_number)`.
   Only explicit junctions paint black dots; Splice is invisible; graphically
   coincident Free endpoints or X/T crossings never create connections.
   `Graphic.kind='source_b_continuation'` is always non-electrical.
3. **Page/raster:** `canonical.py` retains one true SVG serialization
   (`width/height` physical mm and mm `viewBox`) and rasterizes this very
   SVG using CairoSVG, with Pillow PNG pHYs metadata. For v2 sheets,
   `page_coords=True` preserves exact absolute page coordinates, disables
   implicit centering or resizing, and rejects mismatched paper formats;
   original engine's *content-sized* SVG still uses explicit 1:1 page layout.
   A4 portrait `2480x3508`, A3 landscape `4961x3508`, A2 landscape
   `7016x4961` at nominal 300 DPI (PNG pHYs ~299.9994 DPI).

**Important:** the v2 fixture currently carries source-inspired **DRAFT**
symbol graphics, not an attested approved source-engine UGO catalogue. This
module can accurately export them but cannot certify them as normative.
The full frozen E695 v2 source has 23 components, 15 declared literal Nets,
62 PinRef memberships, 16 DA1 physical pins and two non-conductive b graphics,
with **zero authored wires imported from old defective routing**. No 15/15
auto-routing or complete ERC is claimed.

**Font policy:** `strict_font=True` rejects visible external-family SVG
text until the exact licensed Type A glyphs are demonstrably pinned/outlined
in the raster backend. `strict_font=False` only generates preview and
records `FONT_RENDER_UNVERIFIED`; not ready for signed production prints.
No OpenGOST or other font binaries are bundled. Title-block geometric
`include_title=True` reuses the existing Python engine's **DRAFT** form-one,
not approved text fields/signatures.

**Security / limits:** source SVG is allowlist-validated; DTD, entities,
external resources, scripts, non-whitelisted elements, review overlays and
unknown glyph geometry are rejected. Exact stroke bounds are checked for
lines, rectangles, circles, polylines and the Python engine's known
semicircular arc path grammar. Arbitrary SVG paths fail closed.
PNG enforces maximum pixel budget and exact integer pHYs metadata.
Native safe file writes/worker limits belong to desktop CHAT2/#118.

## Reproduction in CI (preferred; target branch has #122 v2 model)

```bash
python -m pip install -e ".[dev]" "jsonschema>=4.26,<5" "CairoSVG==2.9.1" "Pillow>=12.3,<13"
python -m ruff check ui/bridge/export
python -m pytest -q ui/bridge/export/tests
```

The dedicated `.github/workflows/visual-cad-chat8-export.yml` executes
exactly these checks for Python **3.12 and 3.13** on PR merge snapshots, and
is the authoritative CI evidence. The default root `pytest` testpaths only
includes `tests/`, so a green general root workflow alone did *not*
previously execute CHAT8's targeted tests.

### Programmatic API

```python
from ui.bridge.export.canonical import ExportRequest
from ui.bridge.export.project_v2 import export_v2
from ui.editor.src.model.contract import digest, strict_loads

doc = strict_loads(open("project.gscad.json", "rb").read())
sha = digest(doc)  # validates source graph and checksum
result = export_v2(
    doc, "sheet-1",
    ExportRequest(page="A3", orientation="landscape",
                  include_frame=True, strict_font=False),  # preview only
    expected_project_sha256=sha,
)
# result.svg and result.png are real bytes. Never write them through
# arbitrary user-controlled worker paths; #118 owns safe desktop writes.
```

This example needs to run from the repository root with `ui` importable.
The specialist *head branch itself* was created before CHAT6 model commit;
run on the PR merge ref or clone the integration target with CHAT6 source.
Do not misdescribe specialist branch-only checkout as a fully integrated app.

## Required remaining work

- #118: Tauri IPC `render_export` dispatch, safe paths/process limits, verified
  fontdb (or legally outlined glyphs), Windows print smoke and packaging.
- #120/#123: real editor intent -> validated v2 sheet, segment IDs, T/X/canvas
  gestures and 1µm source pin accuracy.
- #125: integrate one full React/Mantine/Tauri shell and production save/open;
  wire browser Playwright gesture tests into source-signed export replay.
- #122/#125: replace placeholder v2 symbol geometry with authentic, reviewed
  Python engine catalogue mapping (do not copy GPL images), confirm sheet
  title block and page-margin overlap behavior, add genuine printer 1:1 QA.
- Selected object-ID filtering (unlike physical region crop), vector PDF/DXF,
  BOM/Netlist and cross-OS byte-identical font render are future work.
