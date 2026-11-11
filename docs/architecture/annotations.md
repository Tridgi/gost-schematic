# Annotation layout, independent hitboxes and text-sensitive constraints

Status: experimental implementation, requires user acceptance and a licensed font.

## Modules

- `model/annotations.py`: immutable `AnnotationSlot`, `TextStyle`, semantic roles,
  anchor candidates, and resolved `AnnotationPlacement`.
- `engines/annotation/metrics.py`: measured glyph ink bounds using a user-supplied
  TrueType/OpenType font file; no built-in fallback or guessed character widths.
- `engines/annotation/collision.py`: integer-geometry checks for text rectangles
  against obstacles and strokes on drawn segments (including diagonals).
- `engines/annotation/layout.py`: candidate solver, explicit collision reports,
  body keepout and pin escape corridors.
- `rendering/annotation_svg.py`: clean SVG and diagnostic overlay with separate
  colors for symbol/pin corridors, ink and text collision rectangles.

## Semantics

Definitions declare preferred *slots*, not fixed text rectangles.
Instances bind content: `refdes` from `ComponentInstance.reference`, `value`
from a caller-provided mapping. Glyph metrics are recomputed when text or style
changes; there is no per-symbol hardcoded text size.

Each placement has `ink_bounds`, `collision_bounds` and an optional independent
`reservation_bounds`. Collision bounds include an explicit clearance margin.
Fixed/locked annotations use only their first anchor and never move silently.

All four orthogonal rotations and mirrored instances transform the *anchors and
protected symbol regions*, while annotations remain upright and readable.

Pin escape corridors are considered independent hard obstacles. They are not
part of the symbol's text hitbox.

When no acceptable candidate exists, the layout returns
`ANNOTATION_UNPLACEABLE` (ERROR) with identifiers of blocking objects.
It does not shrink text, hide labels or silently overlap objects.

The current placement solver checks all candidate obstacles (adequate for
individual symbol approval). Index-based incremental whole-sheet layout and
full wiring integration are later stages.

## Measuring and viewing fonts accurately

Text measurement uses Pillow/FreeType with an explicit .ttf/.otf file. The
`em_height_um` is the typographic *em* size, not automatically the capital
letter height required by a particular ГОСТ profile.

For visual fidelity, the exact font used for measurement must also be available
to the SVG viewer. SVG currently uses a `font-family` reference and does
**not** embed font data or convert glyphs to paths. If the browser substitutes a
font, the preview may differ from measured collision rectangles. Therefore
visual approval must include font verification.

No GOST font is distributed in this repository. A legitimate, user-provided
font and its license should be checked before profile approval. Until then,
using DejaVu Sans is suitable only for technical diagnostics, never for claiming
GOST-compliant typography.

## Inspect a resistor with annotations

Install project tools:

```bash
python -m pip install -e ".[dev]"
```

On Codespaces (Ubuntu), get the path of a font installed in that environment:

```bash
fc-match -f '%{file}\n' 'DejaVu Sans' | head -1
```

Run, substituting the returned **existing** font path:

```bash
python -m gost_schematic.cli render-annotated-symbol \
  src/gost_schematic/catalog/symbols/resistors/fixed.json \
  --ref R1 --value '10 kΩ' \
  --font-file /path/to/font.ttf --font-family 'DejaVu Sans' \
  --review-overlay --output output/resistor-annotations-review.svg
```

Review overlay colors are intentionally NOT part of the actual electrical
schematic. For a clean output, omit `--review-overlay`.

## Implemented validation tests

- Different reference/nominal strings produce different measured bounds.
- Overlap against another label, a component keepout and crossing wire is
  detected without electrical-net inference.
- Locked annotations report an error if their position is unavailable.
- Fallback positions are selected deterministically.
- Reserved regions are separate from ink and collision bounds.
- Rotations and mirrors move anchors but retain upright text.
- Clean output excludes all diagnostic overlays.

## Known limits

- One-line text only (multi-line blocks and curved text are future work).
- SVG text depends on font availability in the viewer.
- No complete ГОСТ rule validator or finished schematic auto-router.
- No automatic text layout across entire sheets with incremental spatial indexes.
- No comprehensive rule exceptions for explicitly approved label/leader overlaps.
