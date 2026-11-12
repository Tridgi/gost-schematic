# Rendering workstream — reproducible DRAFT sheet review

**Issue:** https://github.com/Tridgi/gost-schematic/issues/13
**Baseline:** 67c66da9950fe36d5955b86a6c1ce93217ca4edc, from
integration/stage0-12. This review is **not** a GOST/ESKD approval.

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
| catalog-clean.svg | 18 live catalog UGO, typed nominal values, upright text, no overlays |
| catalog-diagnostic.svg | Same geometry plus source keepouts, pin exits, ink/hitboxes, and red AABB intersections |
| overlap-diagnostic.svg | Deliberately invalid two-resistor overlap; red collision region and original layout errors |
| review-manifest.json | Catalog symbol ID/status, exact pin coordinates in µm, physical SI nominals, label hitboxes, diagnostic codes, SHA-256 font provenance |

The current complete catalog contains one resistor, two capacitors and fifteen
parametric inductors/chokes. It is loaded from the **existing JSON/factory**
rather than being redrawn. For each instance, its original physical pin
numbers survive clockwise 0/90/180/270-degree transforms and selected mirrors.
The positions form a fixed editorial review grid, not an automatic placer
and not prescribed sheet dimensions.

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
- SheetLayout may omit unplaceable text while reporting
  ANNOTATION_UNPLACEABLE. The diagnostic metadata keeps these codes visible;
  no arbitrary emergency placement is performed.
- Connector corridors are routing reservations, **not** drawn wires or proof
  of net connectivity. Circuit.nets is never inferred or modified.
- The actual font file is not committed or embedded. The viewer must use
  the same face and font version measured by FreeType; otherwise the shown
  text can diverge from the measured hitboxes. The manifest records the
  font SHA-256 to aid reproducibility.
- No wire routing, page border/title block, certified ESKD lettering,
  manually approved source-standard comparison, or exact stroked-path
  polygon intersections are implemented. All 18 symbols remain DRAFT.
- Samples from CI are built and uploaded as a separate workflow artifact,
  including PNG previews rasterized from **vector** SVG with the installed
  OpenGost font; images are inspection aids, never substitute symbol definitions.

## Regression gates

Run ruff check ., pytest -q, and
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json.
Tests check determinism, 18 DRAFT specimens, upright labels, 90°/180°/270°
transforms and mirrors, exact pin coordinates, nominal immutability,
non-overlapping valid labels, and the intentionally invalid scene.

This work introduces an internal rendering adapter and an example. It **does
not change** shared model/*, core/*, catalog/* contracts, numerical
values, or public API signatures.
