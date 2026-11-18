# Issue #55 — Safety hardening of the existing two-pin router PR #39

**PR #39 preserved:** original head `4e86e2e0e10d05c591ed004c4d6096de21520007`; merged *into the PR feature history* (not into `main` or `integration/stage0-12`) the current integration `2052e9d3a903edea860c100e00609ceee3c9062b` via commit `18cfc3b3e85e3fdcd9fc8ed793d91ba4af2e3fb8`. This includes already merged electrical validation fix #48. Subsequent changes are only in this feature branch. **No force push, no merge by this workstream.**

This is **EXPERIMENTAL ROUTING**, not a complete schematic autorouter nor a claim of ГОСТ/ЕСКД approval. The original Dijkstra search, corner compression, exact-micrometre grid and `ExternalWireGraph` construction are preserved.

## #50 — unassigned real physical contact safety

The original `route_two_pins` was only a geometry solver and knew the symbol body keepouts, not the full catalog pin map. The exact QA case R1 origin (8000,-10000), R3 origin (8000,0), R2 origin (8000,10000) passes body keepouts but runs vertically through **unassigned R3.1 at (0,0)**.

A **new, isolated typed adapter** `route_circuit_two_pins` in `engines/routing/two_pin_sheet.py` accepts an immutable `Circuit`, existing parts/symbols catalog, source/target `PinRef`s, declared two-member net label and physical `WireObstacle` values. It:

1. Resolves **every real physical contact** after rotation/mirroring with `component.pin_positions(symbol)`; checks the physical catalog-to-symbol mapping.
2. Includes **all** transformed catalog symbol body keepouts; protects **every non-endpoint real physical contact** with a strictly-positive contact box and the existing standard pin-escape corridor. This includes unassigned pins and even other pins on the same net (conservative: this first two-pin prototype does not construct branches/junctions).
3. Authorizes ONLY the exact two declared source and target `PinRef`s, not the entire component, SVG stroke, an arbitrary same-net location or a visually crossing contact. Rejects unknown or ambiguous pin IDs and non-two-member net declarations.
4. After route geometry is computed, **revalidates the exact generated `ExternalWireGraph` with existing `validate_external_wires`** (including issue #40 merged fix) before returning success. Any ERC diagnostic fails closed (`ROUTE_ELECTRICAL_REJECTED`) with **no partial graph**. It never edits `Circuit`, net membership, or `ExternalWireGraph.junctions`.

Call the typed adapter for real circuit sheets. The original `route_two_pins` is explicitly a **geometry-only helper**, not an intrinsically pin-safe public-sheet API. Callers using it directly are responsible for all omitted physical/annotation barriers.

## #52 — real printed foreign stroke width

The preexisting `WireSegment` carries a net name and precise centerline, **not ink stroke thickness**. Guessing that every foreign wire uses the same thickness as the new wire is unsafe.

- The low-level router retains `existing_wires` for call compatibility, but if it is non-empty and widthless, returns ERROR `ROUTE_FOREIGN_WIDTH_REQUIRED` (never a silently assumed 300µm).
- A new optional experimental `foreign_wires: tuple[WireObstacle,...]` takes the EXISTING typed drawing obstacles, whose `stroke_um` is the actual ink width. Negative/zero foreign widths fail closed; mixed widths are handled per-wire.
- Conservative closed-boundary AABB exclusion uses `M = clearance_um + ceil(new_stroke_um/2) + ceil(foreign_wire.stroke_um/2)` relative to the foreign centerline AABB. **No** undercounting of different width conductor edges. Example #52: new 300µm, foreign 1000µm, required 400µm edge-to-edge gap → **1050µm** centerline AABB expansion. This is conservative for diagonal wires, with no authorized same-net contacts or shorts.
- Typed sheet adapter forwards actual `WireObstacle` widths without converting to lossy `WireSegment`. It doesn't change `WireObstacle`, `WireSegment`, the models or renderer.

## #51 — irrelevant remote obstacle cannot exhaust local search budget

The old implicit window enclosed **all** keepouts anywhere in the sheet. A remote `Box(10**9,10**9,10**9+1000,10**9+1000)` enlarged a 1mm direct connection search window to approximately 1e12 cells and returned `ROUTE_CELL_LIMIT` even with `max_cells=1000`.

- Initial implicit window contains **only** source and destination envelope, with a 4-cell pad on all sides. If it has no free path, padding grows deterministically by **4 grid cells** per retry (4,8,12,16,...). Individual attempts never exceed `max_cells`.
- Each attempt checks only closed-boundary obstacle rectangles intersecting that local window. Remote obstacles do not influence the local grid dimensions, search order, or final direct route.
- Explicit `bounds` still produce **one** deterministic fixed-window attempt; complete wall across that finite window returns `ROUTE_NO_PATH`. A planned larger search exceeding budget returns `ROUTE_CELL_LIMIT` (means **limited budget**, not global impossibility). No uncontrolled expansion or random paths.

## Regression matrix (mandatory QA examples plus extra controls)

New `tests/test_two_pin_route_hardening.py` covers:
- **Exact QA #50** three-resistor reproducible placement with every body keepout, plus verified diverted route, no wire through R3.1, empty ERC diagnostics, no junction or inferred pin membership.
- **5 real catalog kinds × 4 rotations × 2 mirror settings × 4 route directions = 160 real-pin-safe checks**, including the actual catalog tapped winding; and **40** identical transforms with 1 µm perpendicular displacement, preserving contact identity and clearance.
- QA #51 extreme remote keepout (with/without other distant obstacles), fixed-window counterpart, bounded adaptive detour, explicit infinite-wall-as-no-path and genuine max cell cap.
- QA #52 actual 1000/300/100µm foreign ink widths, 300µm new, 400µm clearance, exact 1050µm boundary, mixed-width order independence, invalid zero/unknown width, same-net foreign exclusion.
- Adapter rejects incorrect net membership, preserves original immutable pins/netlist, no cross-layer mutations and the existing SVG/JSON example remains byte-deterministic.

Existing `tests/test_two_pin_orthogonal.py` tests are retained. Two old tests using widthless `existing_wires` are updated to construct typed `WireObstacle` inputs with the previously implicitly assumed but now **explicit** 300µm stroke; their expected route geometry and clearance calculations remain otherwise unchanged.

The real-catalog demonstration `examples/review_two_pin_routing.py` now uses `route_circuit_two_pins` rather than raw geometry-only routing, checks ERC + clearance and renders via the existing SVG renderer. `report_json()` serializes the same route points and `ExternalWireGraph` segments consumed by SVG; no independently authored duplicate route geometry. Both clean/review SVG and JSON remain deterministic.

## Reproduce

```sh
python -m examples.review_two_pin_routing --output-dir output/routing-cycle4
ruff check .
pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
```

**Limitations:** a low-level geometry-only request with incomplete `keepouts` cannot guarantee physical contact safety; users must enter via the adapter for real circuits. The adapter is conservative: every other physical pin even on the same net is blocked; only exact two-member nets can be routed in this version, other declared multi-terminal nets in the same sheet can cause downstream ERC rejection. Existing wire ink AABB may over-restrict diagonals. Full text/annotation keepouts must still be passed by the caller; no fully automatic label placement, bridge syntax, junction synthesis, multi-net optimization or GOST-certified drawing clearance is claimed. Exported SVG labels remain specimen-only and do not constitute approved typography.

## Workstream ownership

No edits to `src/gost_schematic/core/*`, `model/*`, `rendering/*`, catalog or public `api.py`. Correctness is bounded, deterministic and fail-closed. QA/coordinator must independently review the updated Draft PR #39; **merge is coordinator-only**.
