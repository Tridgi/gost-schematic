# CHAT 8 — Canonical SVG and PNG300 export bridge (R1 owner branch)

**Source:** existing Python `gost_schematic.rendering.sheet_svg.render_sheet_svg` or
`render_external_wire_sheet.render_external_wire_sheet` with diagnostics off. Their
real symbols/pins and signed Net graph originate in the existing engine, not in
this bridge. The caller supplies the **actual model-authored clean SVG bytes**.

`canonical.py` wraps this scene into A4/A3/A2 physical pages at 1:1 scale,
checks XML, rejects editor/review layers, and converts the **same SVG** into
PNG with explicit pixel dimensions and pHYs resolution using CairoSVG+Pillow.
Coordinates remain integer µm through placement, converted to millimetres only
for SVG. The only electrical junction dots are those already in the source
Python engine. No visual X/T crossing is promoted to an electrical connection.

- **Font policy:** `strict_font=True` rejects all visible SVG text because
  CairoSVG does not attest that it used the exact external OpenGOST font file;
  optional `strict_font=False` allows preview **only**, warning
  `FONT_RENDER_UNVERIFIED`. Production path requires a verified fontdb with
  SHA-256 (e.g. Rust resvg) or legally vector-outlined glyphs. No font binary
  is included or embedded.
- **Title block:** optional `include_title=True` uses the existing Python
  `draw_form_one_geometry` DRAFT. It does not invent certified GOST form fields.
  No real signatures or credentials are generated.
- **Selected region:** `region_um=(x,y,width,height)` is an exact crop of a
  page, not a filtered project selection; source scene filtering by stable
  object IDs is blocked on #122's model API.
- **No PNG security promises for arbitrary untrusted SVG:** source validation
  uses an intentionally small allowlist; only controlled renderer-generated
  SVG should be passed, and the native worker must have OS/process limits.
- **Reproducibility:** SHA-identical outputs in one pinned Python/Cairo/Pillow
  environment. Cross-OS font/render byte identity is **not** promised.
- **Existing page model:** `formatted_sheet.PageProfile` handles A4/A3;
  equivalent A2 page dimensions are implemented here for export bridging,
  but normative A2 form-one acceptance needs independent QA.
- **Ownership:** `ui/bridge/export/**` and
  `ui/editor/src/export/contract.ts` per ADR-0010. MASTER #125 integrates;
  neither this file nor this branch changes `main` or legacy branches.

## Local checks

```powershell
py -3.12 -m pip install 'CairoSVG==2.9.1' 'Pillow>=12.3,<13' 'pytest>=8,<10'
$env:PYTHONPATH='ui/bridge/export;src'
py -3.12 -m pytest -q ui/bridge/export/tests/test_canonical.py
```

Local first POC validated with CairoSVG 2.8.2 and Pillow 12.3.0 on Linux
Python 3.13.5. New version 2.9.1 is the intended security-updated Windows
candidate but still needs execution and licensing/packaging review on Windows.

## Pending interface dependencies

- **#122** ProjectFileV2's `ProjectSnapshot`, `sheet_id`, stable symbol and
  graphic IDs, and actual no-scaling scene adapter; no auto-coercion from old
  `gse-project` v1.
- **#123** `pin|junction|splice|free` route consistency, wrong-Net rollback,
  explicit T/X semantics. Export strictly consumes validated geometry.
- **#118** supervised worker and Rust Tauri IPC, sandbox file writes, fontdb,
  signed binary dependencies and Windows build.
- **#125** one app root and CI/test/commit wiring. Do not merge PR #126.
