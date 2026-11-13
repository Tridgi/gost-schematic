# QA follow-up cycle 4 — PR #39 adversarial negative scenario matrix

**Target under test**: [Draft PR #39](https://github.com/Tridgi/gost-schematic/pull/39) / Issue #34, head `4e86e2e0e10d05c591ed004c4d6096de21520007`, router source Git blob `50b9102191fbe7f5876b14bd9ef10dcbbb1fe600`. **Separate QA branch baseline**: `integration/stage0-12` at `73bc6f88a814d7b92267326fc1dab8f127e92e77`. No review of a later changed PR39 head is implied.

The router is **not merged** into the baseline. `scripts/qa_followup_pr39.py` loads **exactly** the PR SHA and checks the source Git blob hash. The GitHub Actions shallow checkout fetches the immutable commit when necessary. It fails closed if unavailable; tests do not silently skip and do not copy/change another team's production module.

These scenarios deliberately differ from author-owned `tests/test_two_pin_orthogonal.py` and earlier QA PR #42. All device geometries and physical pin identities come from the **installed actual versioned catalog** in the baseline.

## Confirmed open defects

| Case | Actual behavior | Expected / why unsafe | Severity | Issue | QA test |
|---|---|---|---|---|---|
| Real unrelated unassigned terminal | A vertical net R1.1→R2.1 is drawn through R3.1=(0,0), with **all three body keepouts provided**. Downstream `validate_external_wires` returns no error. | Prevent unintentional physical connector contact; route preflight must include pin/lead geometry, not only component bodies. | **MAJOR** | [#50](https://github.com/Tridgi/gost-schematic/issues/50), related [#40](https://github.com/Tridgi/gost-schematic/issues/40) | `test_pinned_router_passes_through_real_unassigned_pin_outside_all_body_keepouts` |
| Remote obstacle pollutes auto-window | Start=(0,0), end=(1000,0) and remote Box near (1e9,1e9) cause `ROUTE_CELL_LIMIT` for **1,000,020,000,100 cells**; explicit small bounds gives valid direct route. | Irrelevant far-away object should not prevent locally feasible one-grid-step route. | **MODERATE** | [#51](https://github.com/Tridgi/gost-schematic/issues/51) | `test_remote_irrelevant_obstacle_does_not_exhaust_cell_budget_for_clear_direct_path` |
| Existing wire differs in stroke | New 0.3mm conductor routes within the required printed 0.4mm clearance of an existing 1.0mm conductor; `WireSegment` has no width, router assumes both strokes equal. | Use known existing ink width or explicit ink keepout; otherwise output does not satisfy stroke-edge clearance. | **MAJOR** | [#52](https://github.com/Tridgi/gost-schematic/issues/52) | `test_mixed_existing_wire_stroke_must_respect_actual_printed_clearance` |

The three cases initially **failed reproducibly** in CI on the unchanged pinned router. Retained as **strict expected failures** pending the electrical owner's corrections; `XPASS(strict)` demands review if behavior changes. QA does not change router, catalog, electrical semantics or graphics.

## Passing independent negative and positive controls

| Scenario | Expected invariant |
|---|---|
| All 8 real resistor/electrolytic orientations and mirrors, with real middle blocker | Exact physical pin IDs, orthogonal nonzero strokes, unchanged semantic nets, no hit with any provided body keepout |
| 12 seeded real-component blockers, randomized orientations/locations | Order of keepouts cannot affect the chosen result; bounded deterministic success, no intersections with provided boxes |
| Existing foreign wire passes through selected contact | `ROUTE_PORT_BLOCKED` and empty route; success-only conversion rejects failure |
| A real resistor body forms a wall across a strict finite sheet window | `ROUTE_NO_PATH` with no partial segments; larger but still bounded window allows safe detour |
| Another real resistor body covers a source terminal | `ROUTE_PORT_BLOCKED`; physical contact location unchanged |
| Origin moved by exactly 1µm, otherwise real UGO | `ROUTE_OFF_GRID`, never silently snap or fabricate a wire |
| Unassigned real contact pre-protected by extra explicit pin keepout | Divert without intersecting that physical terminal |
| Existing 1.0mm ink width represented by pre-expanded keepout | Safe detour with actual clearance, verifying Dijkstra can work given correct obstacle metadata |
| Failure route → `external_graph` | Raises; cannot leak partially built wire/net |

## Exact reproduction

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -q tests/test_qa_followup_router.py
pytest -q
```

All tests require Git to access the pinned PR commit; when PR39 code is eventually integrated, coordinator should explicitly transition tests from pinned snapshot to the accepted implementation commit. A green baseline CI on `integration/stage0-12` alone **cannot** prove PR39 correctness.

## Related but nonduplicated prior issues

- [#40](https://github.com/Tridgi/gost-schematic/issues/40): the **external wire validator** is silent on an unassigned pin crossed in the wire interior. PR39 routing makes this observable as a generated-wire defect (#50), but fixing either issue alone does not necessarily resolve both.
- [#41](https://github.com/Tridgi/gost-schematic/issues/41): malformed catalog JSON leaks `AttributeError` instead of `CatalogError`; independent of routing. Keep PR #42's existing negative regression; do not clone it here.

## Scope and limitations

The QA suite checks geometric and semantic invariants for the particular sample routes, not normative GOST certification of all symbols, all pin escape orientations, legal visual junction dots, other fonts or full automatic multi-terminal placement. The PR39 algorithm intentionally does **not** support multi-net routing, branches, snap, or the entirety of Circuit; the QA tests do not treat these documented omissions as defects.
