# Cycle 4 — bounded two-physical-pin orthogonal route prototype (Issue #34)

> **Mandatory safety update — Issue #55:** this document describes the original PR #39 baseline, before QA #50–#52. The authoritative, updated routing contracts, safe physical-pin adapter, mixed foreign stroke policy, local adaptive window and limitations are in [electrical-cycle4-safety55.md](electrical-cycle4-safety55.md). Old statements here assuming an unknown 300µm foreign wire stroke or treating body keepouts alone as sheet-safe are superseded. Use `route_circuit_two_pins` for actual schematics; the original low-level helper is geometry-only.

**Verified parent**: `integration/stage0-12` and `parallel/electrical-cycle4` at `caf7db7ad22d9cd22202664471da5ff3a49a754c` before changes. Scope restricted to `engines/routing/two_pin_orthogonal.py`, a separate example and independent tests. The original core, model, catalog, renderer, validator and public API are unchanged.

## What the route algorithm actually does

`route_two_pins(start, end, *, keepouts=(), existing_wires=(), grid_um=1000, clearance_um=400, stroke_um=300, bounds=None, max_cells=50000)` routes exactly **one 2-contact net**, with the following strict contract:

- `start` and `end` must be different exact `Point` values in integer µm and **already on the grid**, aligned to global zero. There is never silent rounding, snapping, or changing contact coordinates. Off-grid input yields `ROUTE_OFF_GRID` and **no wire**.
- Four cardinal moves, each exactly one `grid_um` step. Search uses bounded Dijkstra, minimizing the lexicographic objective **(total grid steps, number of 90° bends)**; deterministic Y/X/direction tie breaking and sorted obstacles. Consecutive collinear steps collapse into maximal straight runs.
- Real UGO body keepout boxes are expanded by `clearance_um + ceil(stroke_um/2)`; collision against the **closed** expanded rectangle rejects even tangential contact. The demo supplies keepouts of the endpoints' own symbols too, rather than granting an implicit exception.
- Every existing wire (regardless of its net label) is conservatively excluded by its entire geometric AABB expanded by `clearance_um + 2 * ceil(stroke_um/2)`. A diagonal wire's enclosing rectangle is more restrictive than its exact stroke. This rejects unintended endpoints, unmarked X contacts, and even collinear overlaps or same-net tie-ins. **No** automatic junction inference.
- Search window is finite: either the exact explicit `bounds` or the endpoint/obstacle envelope padded by four grid cells. `max_cells` rejects oversized searches instead of partially routing. A failed bounded window says only **no feasible path within this model/window**, not mathematical impossibility on an infinite canvas.
- Returned immutable `TwoPinRoute` contains points and machine diagnostics; success-only `external_graph(net_name)` converts them directly into the existing `ExternalWireGraph` with empty explicit junctions. Error cases have no points and cannot create partial wires.

Failure codes include `ROUTE_COORDINATE_INVALID`, `ROUTE_COINCIDENT_PINS`, `ROUTE_GRID_INVALID`, `ROUTE_OPTIONS_INVALID`, `ROUTE_OFF_GRID`, `ROUTE_OBSTACLE_INVALID`, `ROUTE_WINDOW_INVALID`, `ROUTE_PORT_BLOCKED`, `ROUTE_CELL_LIMIT`, and `ROUTE_NO_PATH` (each `Severity.ERROR`).

## Reproduce real component integration

```bash
python -m pip install -e ".[dev]"
python -m examples.review_two_pin_routing --output-dir output/routing-cycle4
ruff check .
python -m pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
```

The example loads **real checked-in catalog definitions** using the existing definitions helper. It places `R1` fixed resistor, `R2` blocking fixed resistor, and `C1` electrolytic capacitor. `Circuit.nets` has a single requested `LINK: R1.2 → C1.1`; exact physical terminals are `Point(28000,20000)` and `Point(91000,20000)` in µm. The obstacle at R2 forces two 90° bends; source and destination body keepouts are also respected. This calculated connection is validated by existing `validate_external_wires` and `validate_wire_clearance`, then rendered read-only by `render_sheet_svg`. The emitted SVG segment endpoints are tested against the **same computed graph**, not an independently hand-authored SVG route.

The example regenerates `two-pin-clean.svg`, `two-pin-review.svg`, and `two-pin-diagnostics.json` on demand. These are **experimental** geometry previews, not complete drawing packages. Generic specimen-only labels are not a calibrated ГОСТ typeface.

## Regression matrix / boundaries

Tests include: direct horizontal and vertical, a one-bend pair, obstacle detour with two bends, permutation/repeat reproducibility, exact integer and off-grid failures, blocked endpoints, true no-path behind a full-height wall in an explicit finite window, absent/invalid window, excessive grid, foreign wire X crossing, shared point, collinear overlap, and diagonal AABB exclusion. Existing wires are deliberately excluded even when same-net because the prototype does not implement tie/junction authorization. Output is always zero-length on failure.

**Not implemented**: routing whole `Circuit` or multi-terminal branches, multi-net joint optimization, pin approach-direction enforcement, port escape permissions, crossing bridges, source/target pin body stroke exclusions, automatic text/label reservations, precise stroked-distance DRC beyond the documented AABB margins, net ties, global labels, obstacles of all possible sheet decorations, simulated electrical behavior, and ГОСТ/ЕСКД certification. Source part/symbol status remains DRAFT (19 entries); no change to shared `api.py` or `model/*`. Additional capabilities must be scoped via coordinator RFC.

Review requires Ruff, full pytest on Python 3.12/3.13, 19-DRAFT/0-hard-error catalog audit and wheel verification. Open Draft PR to `integration/stage0-12`, do not merge or close Issue #34 from this workstream.
