# Changelog

The library remains an experimental, non-certified collection of draft symbols.
This changelog records technical increments, **not** approval to use a symbol
as a conforming ГОСТ/ЕСКД drawing.

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
