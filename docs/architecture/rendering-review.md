# Rendering workstream — reproducible DRAFT sheet review

**Issues:** [#13](https://github.com/Tridgi/gost-schematic/issues/13),
[#17](https://github.com/Tridgi/gost-schematic/issues/17), and
[#25](https://github.com/Tridgi/gost-schematic/issues/25).
**Follow-up baseline:** `9e9d056e410c8a54dc3c9fc9d5cc56b74e6f225b`, from
`integration/stage0-12`. This review is **not** a GOST/ESKD approval.

## Run

Install Python 3.12+ and the project's development dependencies. Supply a
legal TTF/OTF file installed on the host, matching the SVG viewer's actual font:

~~~bash
python -m pip install -e ".[dev]"
FONT_FILE="$(fc-match -f '%{file}' 'DejaVu Sans')"
python examples/review_full_sheet.py \
  --font-file "$FONT_FILE" --font-family "DejaVu Sans" \
  --output-dir output/rendering-review
~~~

To measure the actual upper-case height of the OpenGost Type A face rather
than just the em size, install the external font via the existing
scripts/install_opengost_type_a.py and use
--font-family "OpenGost Type A" --type-a. This calibrates the
sample's *requested* 3.5 mm capital height; it does not approve glyph outlines.

## Outputs

| File | Contents |
|---|---|
| catalog-clean.svg | All currently versioned DRAFT UGO, typed *example* nominals where supported, upright text, no overlays |
| catalog-diagnostic.svg | Same geometry plus source keepouts, pin exits, ink/hitboxes, and red AABB intersections |
| overlap-diagnostic.svg | Deliberately invalid two-resistor overlap; red collision region and original layout errors |
| review-manifest.json | Actual catalog ID/revision/source, reference/pins in µm, demonstration SI nominals, text extents, SHA-256 font provenance, and focused-capacitor IDs |
| capacitor-electrolytic-clean.svg / capacitor-electrolytic-diagnostic.svg | Real `capacitor.electrolytic` vector UGO (no font/text), unchanged source drawing with/without keepout and physical contact markers |
| capacitor-polarized-clean.svg / capacitor-polarized-diagnostic.svg | Real general `capacitor.polarized` source-vector comparison (not a substitute for electrolytic) |
| visual-gate.json | Executed SVG/PNG post-export checks for expected count, actual catalog primitives, pin mapping, unique refdes, no unexpected collisions and font-source SHA-256 |

The review dynamically scans **every** `catalog/symbols/**/*.json` and
`catalog/inductors/*.json` file, matching the structural catalog audit's
inventory scope. Static symbols require a corresponding physical passport
under `catalog/parts/` at the same relative path. The winding factory
already supplies its own physical passport. As of Issue #25, **19 actual
DRAFT symbols** are installed, including `capacitor.electrolytic` with its
independent `capacitor.electrolytic` physical part. The library also retains
`capacitor.polarized` as a separate general polarized UGO. The rendering
inventory remains dynamic and does not assume exactly 19 entries in future.

Entries are sorted by symbol ID, revision, physical part ID and relative
source path. Component identifiers use the **real** physical passport
`reference_prefix` and independent numbering within each prefix; duplicate
references are skipped rather than reused. If the catalog contains two
symbols with the same physical part ID or duplicate symbol ID+revision, the
renderer refuses to proceed instead of overwriting a dictionary entry.
A genuinely unsupported multiple-graphics-per-part model still needs a
separate agreed interface; it must not be faked with synthetic part IDs.

The cell grid expands by the actual transformed `stroked_bounds`, body
keepouts and pin escape zones. Column widths and row heights grow with the
UGO count and dimensions; example padding is **editorial**, not normative.
Real physical pin numbers survive clockwise 0/90/180/270-degree transforms
and selected mirrors. The placed UGO graphics are immutable catalog
primitives, not redrawn artwork.

The visualization's resistor/capacitor/inductor example values are **sample
nominals only**, stored on local `ComponentInstance` for the preview. They
do not modify catalog physical data or any electrical network. Unknown
`nominal_kind` yields no nominal label, never a fabricated quantity.

The diagnostic SVG reuses render_sheet_svg and only adds an independent
red overlay (data-layer=collision-markers); data-kind, data-first,
data-second document the suspected overlap. Every figure is marked
data-approval-status=DRAFT. The deliberately failing specimen demonstrates
that a broken scene raises layout errors instead of silently looking correct.

## Interpretation and limits

- **AABB** means conservative axis-aligned bounding box. For diagonals,
  winding arcs and empty interiors, intersecting boxes may yield false
  positives: a red rectangle is **not** pixel-accurate proof of collision.
  Primitive-specific stroke width and transformed coordinates are respected.
- `SheetLayout` may omit unplaceable text while reporting
  `ANNOTATION_UNPLACEABLE`. The example runner fails rather than shipping a
  misleading partial gallery. Collision review checks labels, strokes,
  other component bounding boxes and pin exits; diagnostic metadata preserves
  the original codes.
- Missing/mismatched physical passport, duplicate mapping or an unexpected
  `approved` symbol fails explicitly as `CatalogReviewError`; there is no
  silent omission of an unknown UGO.
- The example compares each discovered `(symbol_id, revision, source)`
  triple with live `audit_catalog()` output, requiring equal counts,
  all DRAFT and zero hard errors. The manifest records this audit and
  all source paths, not a hardcoded count.
- Connector corridors are routing reservations, **not** drawn wires or proof
  of net connectivity. Circuit.nets is never inferred or modified.
- The actual font file is not committed or embedded. The viewer must use
  the same face and font version measured by FreeType; otherwise the shown
  text can diverge from the measured hitboxes. The manifest records the
  font SHA-256 to aid reproducibility.
- No wire routing, page border/title block, certified ESKD lettering,
  manually approved source-standard comparison, or exact stroked-path
  polygon intersections are implemented. All discovered symbols remain DRAFT.
- GitHub Actions automatically regenerates on pull requests targeting
  `integration/stage0-12` and changing actual JSON symbols/parts, inductor
  profiles/factory, or rendering-related sources. A merge changing the same
  paths triggers a separate `push` run on **integration only**. Regular
  feature-branch pushes do not create duplicate image workflows.
  `workflow_dispatch` also supports an explicit manual regeneration.
- Each run outputs three sheet SVGs and four focused UGO SVGs, with seven
  corresponding PNG previews, JSON manifest and `visual-gate.json`.
  The focused pair uses `render_symbol_svg` to draw the **original catalog
  primitives** only. It never reconstructs electrolytic plates by painting
  a bitmap. In particular, the current DRAFT implementation has 12
  original line elements for the electrolytic and 6 for the general
  polarized symbol; a deliberate change requires a new visual review.
- The workflow installs the external OpenGost Type A face and checks that
  Fontconfig resolves the **same file** as the geometry text measurer.
  A source font SHA-256 is recorded in the manifest and on each sheet
  SVG text element; the artifact verifier requires these to agree. The
  font binary is **not embedded**, however. Inkscape, browsers, operating
  systems and PDF converters may silently substitute a different face,
  metric or slant. A local viewer must install and verify the identical
  font SHA and visually compare the result; exported SVG acceptance by CI
  cannot guarantee any arbitrary external viewer's pixel output.
- The post-export gate checks that every vector primitive is identical to
  the current transformed catalog source, all expected physical pins and
  nominal examples are preserved, all valid-scene AABB collisions are zero,
  and PNG headers and dimensions are valid. PNGs remain inspection aids;
  this is **not** a pixel-by-pixel normative approval or a certificate
  of compliance with ГОСТ 2.728-74.

## Regression gates

Run ruff check ., pytest -q, and
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json.
Tests check deterministic full-catalog discovery, upright labels, 90°/180°/270°
transforms/mirrors, exact pin coordinates, nominal immutability, no unexpected
collisions, and the deliberately invalid scene. The expansion fixture copies
the catalog into a temporary directory, adds one legitimate-structure DRAFT
`capacitor.electrolytic`+part **without modifying the repository**, and
verifies all elements appear; once real electrolytic is integrated, the same
test introduces an independently named extra variant and remains valid.
Negative tests exercise missing/mismatched part records and oversized text.
Issue #25 adds regression checks on **19 real sources** (no simulated
electrolytic substitution), separate electrolytic/general-polarized geometry,
strict source-primitive to SVG comparison, refdes/pin mapping, image-in-SVG
injection, omission of one vector stroke and invalid font-family provenance.

To reproduce the exported artifact gate after generating SVG and PNG:

~~~bash
python examples/verify_rendering_review.py \
  --output-dir output/rendering-review \
  --font-file "$FONT_FILE" --min-symbols 19
~~~

The verifier emits `output/rendering-review/visual-gate.json` on success.
When the installed catalog legitimately grows to 20+, the same workflow
continues to discover all UGO (19 is only the minimum supported inventory).

This work introduces an internal rendering adapter and an example. It **does
not change** shared model/*, core/*, catalog/* contracts, numerical
values, or public API signatures.
