# GOST Schematic Engine

A deterministic, standards-aware foundation for generating electrical schematic diagrams with a reviewable symbol catalog.

> **Status: experimental — architecture stage 0.** No symbol, exported drawing, or document is claimed to be GOST/ESKD-compliant until its applicable rules and geometry have been verified and approved. The initial resistor is deliberately marked **draft**.

## Scope

- Immutable schematic domain models (part definitions, graphic symbol definitions, instances, nets).
- Exact integer micrometre geometry, mm only at data/API boundaries.
- Typed graphical pins with stable physical pin numbers.
- Exact SI Decimal nominals, independent of label formatting and BOM source values.
- Symbol geometry transformations (right-angle rotation and mirroring).
- Independent validation and diagnostics.
- Versioned, human-reviewable JSON symbol catalog.
- Deterministic reference SVG output for symbol inspection.
- Collision-aware annotations with separate glyph ink, text hitbox and reserved zones.
- Exact font measurement from an explicitly supplied TTF/OTF resource using FreeType.
- Candidate placement, obstacle and wire collision validation, pin-escape protection.
- Clean and annotated SVG inspection with independent diagnostic overlays.
- Optional ГОСТ 2.702-2011 §5.3.20 compact labels (`2,3к`, `0,1мк`),
  full SI units and per-component visibility overrides.
- ГОСТ 2.304-81 type A upper-case-height calibration (upright or separately supplied real
  italic face), font-file SHA-256 protection and font-audited SVG metadata.
- Independent DRAFT fixed and polarized capacitor symbols (8 mm plates, 1.5 mm gap),
  normalized capacitance values and collision-safe annotations.
- Type A + capacitor clean and diagnostic SVG specimens from real OpenGOST in CI.
- Typed pin-escape corridors with physical pin ownership and outward-only
  conductor access, independently checked from text obstacles.

**Not implemented yet:** automatic component placement and wiring routes, complete ERC, formal glyph-by-glyph ГОСТ font certification, PDF export, an approved ГОСТ symbol collection, BOM and document composition. These are planned stages, not current features.

## Development

Requires Python 3.12+.

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
python -m gost_schematic.cli render-symbol src/gost_schematic/catalog/symbols/resistors/fixed.json --output resistor.svg
```

The annotation subsystem requires a font file that YOU provide; the repository
does not include proprietary ГОСТ fonts. For a technical preview in Codespaces,
find an installed font with `fc-match` and use:

```bash
FONT_PATH="$(fc-match -f '%{file}' 'DejaVu Sans')"
gost-schematic render-annotated-symbol \
  src/gost_schematic/catalog/symbols/resistors/fixed.json \
  --ref R1 --nominal 2300 --unit ohm --nominal-mode eskd_compact \
  --font-file "$FONT_PATH" --font-family "DejaVu Sans" \
  --review-overlay --show-pin-connections --output output/resistor-annotations-review.svg
```

For the next experimental milestone, **sheet layout** places reference labels
above or to the right of symbols and visible nominals below them. It checks
text and connector corridors against neighboring elements without claiming
automatic electrical routing. Run `python examples/review_sheet_annotations.py
--font-file "$FONT_PATH" --output-dir output/sheet-review` after
choosing a local TTF/OTF font to generate six multi-component SVG previews.
See [Sheet labels](docs/architecture/sheet-annotations.md).

For a real **ГОСТ type A** specimen (requires a permitted external font file,
not provided by this repository):

```bash
python scripts/install_opengost_type_a.py
fc-cache -f
FONT_FILE="$(find "$HOME/.local/share/fonts" -type f -iname '*TypeA*.ttf' | head -1)"
python examples/review_type_a_capacitors.py \
  --font-file "$FONT_FILE" --font-family "OpenGost Type A" \
  --output-dir output/type-a-capacitors
```

The public font uses its own SIL OFL-1.1 license and is **not committed**.
Actual glyph outline approval and slanted font sources need separate review.
See [Type A typography](docs/architecture/type-a-font.md) and
[Capacitor template rules](docs/architecture/capacitors.md).

Nominal display (including strict fallbacks for undefined ГОСТ ranges) is
specified in [Nominal display](docs/architecture/nominal-display.md).

See [Annotation layout](docs/architecture/annotations.md),
[Architecture](docs/architecture/README.md), [Review process](docs/symbol_approval/README.md), and [Roadmap](docs/roadmap.md).

## Design commitments

1. Electrical connectivity and geometric wiring are distinct.
2. A part's **physical pin identity** never changes when its graphic representation is rotated, rearranged or split.
3. Catalog definitions are immutable and versioned; placement belongs to instances.
4. Rendering and routing depend on geometry contracts, never on hard-coded resistor/IC-specific logic.
5. A symbol may be marked approved only by a separate, explicit review process, accompanied by normative references and regression fixtures.
6. The engine must fail visibly when a constraint cannot be satisfied; never silently distort UGO geometry.

## License

MIT. The repository does not redistribute proprietary CAD libraries, standards texts, or fonts.
