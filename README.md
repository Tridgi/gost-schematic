# GOST Schematic Engine

A deterministic, standards-aware foundation for generating electrical schematic diagrams with a reviewable symbol catalog.

> **Status: experimental — architecture stage 0.** No symbol, exported drawing, or document is claimed to be GOST/ESKD-compliant until its applicable rules and geometry have been verified and approved. The initial resistor is deliberately marked **draft**.

## Scope

- Immutable schematic domain models (part definitions, graphic symbol definitions, instances, nets).
- Exact integer micrometre geometry, mm only at data/API boundaries.
- Typed graphical pins with stable physical pin numbers.
- Symbol geometry transformations (right-angle rotation and mirroring).
- Independent validation and diagnostics.
- Versioned, human-reviewable JSON symbol catalog.
- Deterministic reference SVG output for symbol inspection.

**Not implemented yet:** automated placement and routing, full electrical rule checking (ERC), true GOST typography, PDF export, a verified ГОСТ symbol collection, BOM and document composition. These are planned stages, not current features.

## Development

Requires Python 3.12+.

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
python -m gost_schematic.cli render-symbol src/gost_schematic/catalog/symbols/resistors/fixed.json --output resistor.svg
```

See [Architecture](docs/architecture/README.md), [Review process](docs/symbol_approval/README.md), and [Roadmap](docs/roadmap.md).

## Design commitments

1. Electrical connectivity and geometric wiring are distinct.
2. A part's **physical pin identity** never changes when its graphic representation is rotated, rearranged or split.
3. Catalog definitions are immutable and versioned; placement belongs to instances.
4. Rendering and routing depend on geometry contracts, never on hard-coded resistor/IC-specific logic.
5. A symbol may be marked approved only by a separate, explicit review process, accompanied by normative references and regression fixtures.
6. The engine must fail visibly when a constraint cannot be satisfied; never silently distort UGO geometry.

## License

MIT. The repository does not redistribute proprietary CAD libraries, standards texts, or fonts.
