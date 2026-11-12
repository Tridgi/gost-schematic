# ГОСТ 2.304-81, чертёжный шрифт типа А

Status: implementation available; **typeface outlines not formally certified**.

## Normative geometry

ГОСТ 2.304-81 (таблица 1) establishes:
- `h`: uppercase glyph height. Standard choices: 2.5, 3.5, 5, 7, 10, 14, 20 mm
- `d = h / 14`: line thickness
- `c = 10h / 14`: lowercase glyph height
- `a = 2h / 14`: distance between characters
- `e = 6h / 14`: minimum distance between words
- `b = 22h / 14`: minimum line pitch
- straight or tilted around 75°; both remain Type A if font geometry matches

For h=3.5 mm: d=0.25 mm, c=2.5 mm, a=0.5 mm, e=1.5 mm and b=5.5 mm.

These values are expressed exactly with `fractions.Fraction` in
`standards/type_a_font.py`. They are neither pixel sizes nor the font's em
size. Applying `font-size:3.5mm` alone can produce incorrect physical
capital height, so our `inspect_type_a_font` measures the loaded face's
Cyrillic capital **Н** and derives the correct `TextStyle.em_height_um` for
both FreeType hitbox calculation and SVG `font-size`.

The `TypeAAngle` enum covers `upright` and `inclined_75`. The latter
requires the actual **italic** font file; it deliberately refuses an upright
face rather than applying a synthetic SVG skew. The italic file must come
from a valid licensed source and should be verified against the standard's
75-degree figure. The recommended OpenGOST v0.7 release currently exercises
the upright face; it is not presented as a slanted specimen.

The measurement checks capital height scale, **not** all glyph shapes,
weight `d`, spacing `a`, slope or the full published glyph grids.
A complete ГОСТ typography approval requires comparing the actual font
glyph geometry and kerning against the standard.

## Independent, open-licensed font

The project does not redistribute any font binaries. A recommended open
implementation is [OpenGOST Type A, ingenium-am/open-gost-arm
v0.7](https://github.com/ingenium-am/open-gost-arm/releases/tag/v0.7),
licensed SIL OFL-1.1. Read [upstream LICENSE.txt](https://github.com/ingenium-am/open-gost-arm/blob/master/LICENSE.txt).

Download into your own local font directory with the optional helper:

```bash
python scripts/install_opengost_type_a.py
fc-cache -f
```

The script reports the actual download SHA-256; pin that value using
`--expected-sha256` before creating a reproducible released document.
If the online installer cannot locate a Type A TTF/OTF face in the
v0.7 release, manually install a legally obtained Type A font instead.
The library never falls back silently from Type A to DejaVu Sans.

When using an existing KOMPAS font, supply its path and declared family
explicitly. Only use faces whose licensing permits your intended use.

## Actual measurement and review

```bash
FONT_FILE="$(find "$HOME/.local/share/fonts" -type f -iname '*TypeA*.ttf' | head -1)"
python -c "from gost_schematic.standards.type_a_font import inspect_type_a_font; import sys; print(inspect_type_a_font(sys.argv[1]))" "$FONT_FILE"

python examples/review_type_a_capacitors.py \
  --font-file "$FONT_FILE" --font-family "OpenGost Type A" \
  --height-mm 3.5 --output-dir output/type-a-capacitors
```

The viewer must have the SAME typeface installed under the same name.
A browser that substitutes another font may display different glyph bounds,
even though the exported SVG records the target font family. To guarantee
portable output later, implement either licensed font embedding or glyph
outlines and verify its redistribution conditions before release.

The older DejaVu preview remains a general geometry diagnostic and must
not be presented as an approved ГОСТ specimen.
