# GOST Schematic Engine

A deterministic, standards-aware foundation for generating electrical schematic diagrams with a reviewable symbol catalog.

> **Status: experimental — architecture stage 0.** No symbol, exported drawing, or document is claimed to be GOST/ESKD-compliant until its applicable rules and geometry have been verified and approved. The initial resistor is deliberately marked **draft**.

## Scope

- Immutable schematic domain models (part definitions, graphic symbol definitions, instances, nets).
- Exact integer micrometre geometry, mm only at data/API boundaries.
- Typed graphical pins with stable physical pin numbers.
- Physical terminal polarity stored on part pins (not graphical +/- labels),
  with conservative scenario-based polarity ERC and explicit unknown results.
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
- Parametric GOST 2.723-68 draft coils/chokes (15 source JSON profiles):
  air/ferro/ferrite/gapped/magnetodielectric, trimmed/variable, taps/sliders;
  true semicircle SVG paths, core stroke patterns and stable physical contacts.
- Independent DRAFT fixed and polarized capacitor symbols (8 mm plates, 1.5 mm gap),
  normalized capacitance values and collision-safe annotations.
- Type A + capacitor clean and diagnostic SVG specimens from real OpenGOST in CI.
- Typed pin-escape corridors with physical pin ownership and outward-only
  conductor access, independently checked from text obstacles.

**Not implemented yet:** dynamic voltage simulation, capacitor voltage-rating checks,
automatic component placement and wire routing, comprehensive ERC, formally certified
ГОСТ font outlines, PDF export, an approved ГОСТ symbol catalog, BOM and document
composition. These are planned stages, not current features.

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
See [Inductor/choke family](docs/architecture/inductors.md),
[Type A typography](docs/architecture/type-a-font.md) and
[Capacitor template rules](docs/architecture/capacitors.md).

Nominal display (including strict fallbacks for undefined ГОСТ ranges) is
specified in [Nominal display](docs/architecture/nominal-display.md).

See [Annotation layout](docs/architecture/annotations.md),
[Architecture](docs/architecture/README.md), [Review process](docs/symbol_approval/README.md), and [Roadmap](docs/roadmap.md).

## Project log and integrity audit

Progress and checked results are recorded in
[Project log](docs/project-log.md).
Each milestone begins with a [documented plan](docs/plans/stage-0.11-quality-audit.md)
and proceeds through separate draft PRs.
[Quality gates](docs/quality-gates.md) distinguish structural validation
from formal ГОСТ compliance.

To audit current versioned symbol catalog and physical pin mappings:

```bash
python scripts/audit_symbol_catalog.py \
  --output output/catalog-integrity-audit.json
```

This outputs stable JSON with per-symbol source hashes, diagnostic codes,
contact types and conservative ink extents. It is a structural check only.
The symbols remain DRAFT until explicitly reviewed against original drawings.
See [ADR-0009](docs/decisions/0009-pin-attachment-and-stroked-extents.md).

## Design commitments

1. Electrical connectivity and geometric wiring are distinct.
2. A part's **physical pin identity** never changes when its graphic representation is rotated, rearranged or split.
3. Catalog definitions are immutable and versioned; placement belongs to instances.
4. Rendering and routing depend on geometry contracts, never on hard-coded resistor/IC-specific logic.
5. A symbol may be marked approved only by a separate, explicit review process, accompanied by normative references and regression fixtures.
6. The engine must fail visibly when a constraint cannot be satisfied; never silently distort UGO geometry.

## Physical polarity ERC (experimental)

The separate physical part catalog assigns the positive and negative
terminals of `capacitor.polarized` to **physical pins 1 and 2**.
These identities remain constant when the UGO is rotated or mirrored.

Explicit, same-reference net voltages may be checked at one operating point:

```bash
python examples/review_polarity_erc.py --output output/polarity-erc-review.json
```

Output distinguishes forward differential voltage, reversed polarity
(ERROR), equal-terminal voltage (INFO), and missing evidence (WARNING).
Net names such as `GND` or `+12V` are never guessed to be voltages.

See [Polarity ERC](docs/architecture/polarity-erc.md) and
[ADR-0007](docs/decisions/0007-physical-pin-polarity.md).

## License

MIT. The repository does not redistribute proprietary CAD libraries, standards texts, or fonts.
