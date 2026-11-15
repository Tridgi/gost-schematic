# Cycle 4 — QA risk matrix and execution contract

Baseline: `integration/stage0-12` / `parallel/qa-cycle4` at `caf7db7ad22d9cd22202664471da5ff3a49a754c`. Scope: read-only production code. Issue: #36. All 19 baseline symbols are **DRAFT**; this is not a GOST/ESKD certification.

## Architecture map

| Layer | Main contracts | Existing checks | Adversarial focus | Risk |
|---|---|---|---|---|
| Physical catalog | `PartDefinition`, `PhysicalPin`, part JSON | `test_catalog*`, `test_physical_pin_polarity` | missing/duplicate pins, polarity, stable numbers | High |
| UGO catalog | `SymbolDefinition`, JSON loader, 15 generated inductors and 4 stored symbols | `test_catalog_integrity_audit`, `test_inductor_family`, `test_graphic_integrity` | DRAFT, permutations, topology, invalid nested JSON | High |
| Geometry | integer-µm `Point`, `Box`, `Transform`, `Semicircle` | `test_geometry`, `test_graphic_integrity` | 8 dihedral transforms, negative coordinates, exact round-trips | High |
| Ink topology | `ConductorTopology`, `inspect_conductor_topology` | `test_conductor_topology` | unexpected bridges, explicitly selected strokes, taps and sliders | Critical |
| Circuit | `Circuit`, `Net`, `PinRef`, `validate_circuit` | `test_circuit`, `test_polarity_erc` | independent physical identities, duplicate owners, unknown refs | Critical |
| External wiring | `ExternalWireGraph`, `validate_external_wires` | `test_external_wire_checks`, `test_external_wire_catalog` | endpoints/T/X, overlap, zero length, 1-µm gaps, phantom pins, random order, deterministic diagnostics | Critical |
| SVG | `draw_primitive`, `render_symbol_svg`, `render_sheet_svg` | `test_svg`, `test_sheet_svg`, rendering gallery | exact primitive count, XML parsing, stable SVG, text/source identity | High |
| Layout and review | text metrics, keepouts, `layout_sheet`, wire clearance | `test_sheet_layout`, `test_pin_escape`, rendering review | collision precision, transformed footprints and annotations | High |
| Packaging | `pyproject.toml`, audit scripts, wheel payload, CI | `test_catalog_integrity_audit`, CI 3.12/3.13 | runtime catalog count vs hard-coded 19, JSON payload, wheel growth | High |
| Performance | pairwise wire scan + endpoint scan; SVG proportional to primitives | no separate QA baseline | measured 10/50/200/500 segments, bounded runs; no timing SLA | Medium |

## Independence and QA rules

- Only create new files under `docs/qa/`, `tests/qa_*.py` and `scripts/qa/`; never modify another team's generator, model, workflow, public API, code or branch.
- Tests are dynamically populated from installed catalog data; do not hardcode the number 19 as a future invariant.
- `tests/qa_*_test.py` follows both Issue #36's ownership path and pytest's default `*_test.py` discovery rule.
- Run all 8 rigid orientation configurations (4 rotations × mirror false/true) and use independently computed or metamorphic invariants. Comparison of `SymbolDefinition` instances is **not** a normative geometrical approval.
- Generate adversarial inputs with a fixed seed and finite count; ensure that source data remains immutable.
- A regression test must assert a behavioral invariant rather than a byte-for-byte snapshot that hard-codes today's catalog composition.
- Test execution environment and performance observations must be recorded separately from hypotheses. A green CI does not prove ESKD compliance.

## Immediate gap register (verify, do not automatically fix)

1. `validate_external_wires` has pairwise intersection / endpoint scans: likely quadratic in segment count. Measure, do not assert an SLA.
2. `parse_symbol` catches `KeyError`, `TypeError`, `ValueError`, `IndexError`, but not `AttributeError` when `geometry` is a JSON array instead of object; verify public `CatalogError` contract.
3. A single physical point may have multiple graphical pin owners after placement. Distinguish normal net short from ambiguous accidental superposition; avoid inferring connectivity from mere drawing overlap.
4. CI workflow copy and `tests/test_catalog_integrity_audit.py` include literal 18/19 counts; parallel renderer branch #33 addresses gallery scalability, but packaging/audit changes must also be reviewed as diode catalog grows.
5. `render_sheet_svg` renders authored `WireObstacle` lines and no electrical junction dots in baseline; rendering team #33 owns this, not QA.
6. Full as-printed normative dimensions, font compliance, layout certification and routing completeness remain explicitly outside current structural validators.

## Commands

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -q
pytest -q tests/qa_*_test.py
python scripts/audit_symbol_catalog.py --output output/qa-catalog.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
python scripts/qa/benchmark_cycle4.py --sizes 10 50 200 500 --repeat 3 --output output/qa-cycle4-benchmark.json
```

Record actual outputs and environment in `docs/qa/cycle4-full-audit.md`; do not mark unexecuted commands as PASS.
