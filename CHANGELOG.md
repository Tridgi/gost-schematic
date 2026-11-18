# Changelog

The library remains an experimental, non-certified collection of draft symbols.
This changelog records technical increments, **not** approval to use a symbol
as a conforming ГОСТ/ЕСКД drawing.

## Unreleased — Stage 0.12 (2026-11-12)

- Added [ESKD standards registry](docs/standards/registry.md) with source links,
  applicability, version dates and a per-UGO review matrix.
- Added machine-readable `eskd-ru-2026-11` standard rules and explicit
  selection of early/future-effective editions per document date.
- Added exact graphic conductor topology separate from external electrical
  nets: authored strokes/junctions, winding taps, unconnected crossings,
  distinct capacitor plates and resistor terminals.
- Added negative regression cases for broken arcs, missed junctions,
  false plate bridges, rotations and mirrored symbols.
- Added limited GOST dimensional validation (10×4 mm resistor and
  8 mm/1.5 mm capacitor plates) and explicit unknown state for 15 coils.
- Added conservative independent wire validation for GOST 2.701-2008:
  0.2–1.0 mm strokes and ≥3 mm edge gap between parallel wires.
- Fixed false positive geometry approval for staggered capacitor plates,
  incomplete mid-plate leads, and multiple resistor bodies.
- Fixed collinear overlapping-wire diagnosis: same-net fragments generate
  a consolidation warning, conflicting/unknown-net overlays are errors.
- Replaced recursive graph lookup with iterative path compression for long
  UGO conductor chains (regression covers 1800 nodes).
- Run Ruff, pytest, full catalog audit, and actual wheel-payload validation
  on **both** supported Python runtimes; verified 364/364 tests per runtime,
  18/18 draft UGO and 0 structural errors in
  [Actions #43289319096](https://github.com/Tridgi/gost-schematic/actions/runs/43289319096).
- Explicit [known-limitations and signoff matrix](docs/standards/known-limitations.md)
  documents machine-checked vs experimental vs unimplemented functionality.
- All 18 UGO remain DRAFT. Comprehensive schematic ERC and true external
  netlist↔routing verification not claimed.
- See [PR #9](https://github.com/Tridgi/gost-schematic/pull/9).

## Unreleased — Stage 0.11 (2026-11-12)

- Added linear-time checks for missing and outward-facing graphical connector
  leads (`PIN_GRAPHIC_DISCONNECTED` and `PIN_LEAD_NOT_INWARD`).
- Repaired the broken sliding-contact pointer path in parametric coils.
- Added `SymbolDefinition.stroked_bounds` and stroke-aware collision checks
  for magnetic cores without changing legacy geometric `bounds`.
- Added physical `resistor.fixed` passport and audit of all current physical
  pin maps.
- Added deterministic catalogue-wide integrity JSON report with SHA-256 of
  source definitions and GitHub Actions artifact.
- Added regression tests and quality-policy documentation.
- Verified CI: 303 tests on each Python 3.12/3.13; Ruff clear;
  18 draft symbols, 0 structural errors.
- See [PR #8](https://github.com/Tridgi/gost-schematic/pull/8)
  and [project log](docs/project-log.md).

## Earlier experimental stages

- **0.10:** 15 parameterized inductor/choke JSON families, core strokes,
  true SVG semicircle primitives, physical tap/slider contact functions.
  [PR #7](https://github.com/Tridgi/gost-schematic/pull/7).
- **0.9:** physical pin polarity for polarized capacitors and conservative,
  scenario-based voltage ERC. [PR #6](https://github.com/Tridgi/gost-schematic/pull/6).
- **0.8:** OpenGOST type A typography validation and draft capacitor symbols.
  [PR #5](https://github.com/Tridgi/gost-schematic/pull/5).

See the [roadmap](docs/roadmap.md). All changes remain in the stacked draft
PR chain unless subsequently reviewed and merged explicitly.
