# Cycle 4 — Independent full QA audit report

**Issue:** [#36](https://github.com/Tridgi/gost-schematic/issues/36)  
**Baseline:** `integration/stage0-12` @ `caf7db7ad22d9cd22202664471da5ff3a49a754c`  
**QA branch:** `parallel/qa-cycle4` (only new `tests/qa_*.py`, `scripts/qa/`, `docs/qa/` files)  
**Verification:** GitHub Actions run [43313381824](https://github.com/Tridgi/gost-schematic/actions/runs/43313381824), both Python 3.12.16 and 3.13.18, after all source/test additions through `eeb4bab65ac13c06b90b1189325294500796748e`; subsequent docs-only changes do not alter the tested Python.  
**Status:** complete independent QA pass with **two confirmed unresolved defects** and measured performance risk. **No claim of ГОСТ/ЕСКД approval**. No production code, public API, generator, CI workflow, physical model or external team branch changed. No merge.

## 1. Executive decision and severity

**NOT safe to label production-ready**: an external wire may silently cross a real unassigned physical connector. Existing structural catalog tests passed; that fact is insufficient to establish safe connectivity.

| Severity | ID | Verified result | Impact and action |
|---|---|---|---|
| **MAJOR** | [#40](https://github.com/Tridgi/gost-schematic/issues/40) | Passing wire through real resistor R1.2 while the pin is unassigned and lies strictly inside a wire gives **no diagnostics at all**. | A rendered circuit may appear to contact an unassigned pin. Electrical validator owner must choose and implement an explicit diagnostic contract. Reproducer: `tests/qa_wires_test.py`, `docs/qa/cycle4-reproducers.md`. |
| **MINOR** | [#41](https://github.com/Tridgi/gost-schematic/issues/41) | Valid JSON with `"geometry": []` raises `AttributeError` instead of the catalog's `CatalogError`. | Batch callers catching public catalog errors may crash unexpectedly. Catalog loader owner should explicitly validate nested schema types. Reproducer: `tests/qa_catalog_test.py`. |
| **PERFORMANCE RISK** | observation, not a correctness defect | For 500 external segments validation required 3139.899 ms (Python 3.12, instrumented single sample), compared to 38.450 ms for 50; approx. **81.7× elapsed** for **10× segments**. | Quadratic pairwise segment comparison / endpoint scan is apparent in source; benchmark below. Electrical owner should profile a representative full sheet before promising scale. **No performance SLA exists**, so not classified as MAJOR/BLOCKER. |
| **INTEGRATION RISK** | recommendation, not a confirmed regression | Some baseline tests/docs and `scripts/verify_wheel_payload.py` use fixed 19/15/4 counts or a four-symbol allowlist. | New diode family may be insufficiently checked by the wheel verifier. Coordinate dynamic coverage with #32 and #33; QA tests already discover source symbols dynamically. |

**Confirmed BLOCKER defects: 0; MAJOR: 1; MINOR: 1.** No other production correctness bugs were verified by the bounded tests. An `xfail` is an **open defect**, not a green result.

## 2. Exact execution evidence

GitHub Actions [43313381824](https://github.com/Tridgi/gost-schematic/actions/runs/43313381824), push of `eeb4bab65ac13c06b90b1189325294500796748e`, jobs:

| Gate | Python 3.12.16 | Python 3.13.18 |
|---|---|---|
| `ruff check .` | PASS | PASS |
| `pytest -q` | **665 passed, 2 xfailed**, one benchmark reporting warning; 7.80 s | **665 passed, 2 xfailed**, one benchmark reporting warning; 6.17 s |
| `scripts/audit_symbol_catalog.py` | **19 symbols, 19 DRAFT, 0 hard errors** | same |
| `pip wheel . --no-deps` and `scripts/verify_wheel_payload.py` | PASS: 4 static symbol JSON, 4 physical part JSON, 15 generated inductor JSON, one normative requirements profile | same |
| Remaining SVG/font and example artifact pipeline | job conclusion **success** | job conclusion **success** |

The 2 `xfail` entries correspond to exact reproduction of #40 and #41, deliberately not repaired under QA scope. Previous intermediate CI runs failed while new tests revealed #40 and while Ruff uncovered test-only style errors; those test-only errors were fixed before this successful reference run. Do not cite intermediate failures as the final QA result.

## 3. Catalog, physical pin identity and transformations

- Enumerated the installed package tree at runtime: **4 authored symbol JSON** (resistor + fixed/polarized/electrolytic capacitor) and **15 generated inductor/choke variants**, total **19**; all currently DRAFT.
- Every catalog symbol was checked against a real physical `PartDefinition`. Number sets must match, no invented pin numbers or net associations.
- All **8** orientations (0/90/180/270 × `mirror_x=False/True`) exercised for **every real symbol**, including TAP, SLIDER, copper-core variants and electrolytic capacitor.
- Independent assertions: graphical pin numbers/labels and side orientation; exact world-space contact `transform.apply(pin.at) + origin`; keepout and every geometric primitive invertibility; immutable conductor indices/junctions/pin group partition; post-transform `validate_symbol` and `inspect_conductor_topology` not reporting ERROR.
- All original conductor islands preserved across each rigid transform. These are structural consistency assertions, **not** comparisons to the original ГОСТ drawings.

**Outcome:** no confirmed transform/pin identity failure among the 19 baseline DRAFT symbols. This does not establish that winding/plate/conductor geometry is normatively correct.

## 4. Electrical connections and adversarial conditions

`tests/qa_wires_test.py` uses actual catalog parts and symbols. Tested:

- Net connections attached to the true physical pin position on 19 catalog part variants × 8 orientations.
- Deterministically generated **10, 50, 200** segment real-resistor wire chains; fixed-seed permutation of segment order; repeated check on the original graph; no spurious disconnections.
- Exact 1-µm interruption introduced into each chain size; `WIRE_NET_DISCONNECTED` and `WIRE_DANGLING_END`, no invented net short.
- **32** seeded, translated orthogonal X crossings on real resistors: without a junction they remain distinct; with explicit junction they detect `WIRE_NET_SHORT`. Diagnostic equality checked on repeated calls.
- Negative type cases: floating/boolean `Point` coordinates, zero-length `WireSegment`, blank net labels, duplicate explicit junction coordinates.
- **Confirmed bug #40**: a line can traverse a non-owned real pin interior without producing an ERROR, WARNING or INFO. CI first exhibited a failed test, then retains that exact reproduction as a documented `xfail` pending electrical owner correction.

Already-existing baseline tests cover explicit T junctions, endpoint matching, overlapping collinear wires, diagonal crossings, missing physical pins, orphan conductors, labelled shorts, unknown nets, duplicated references and 1-µm gaps. We **did not copy** those tests merely to inflate count. Newly added tests widen data variation and catalog coverage.

## 5. Vector SVG and coordinate integrity

- For **every one of the 19** symbols, parsed clean SVG using `xml.etree.ElementTree`; verified XML well-formed, title matches symbol ID, physical dimensions and four-number `viewBox`, no `<image>` raster substitutes.
- Asserted **one SVG graphical node per catalog primitive** and checked integer-mm-serialized coordinates against the original immutable primitive for `Line`, `StyledLine`, `Rectangle`, `Circle`, and `Semicircle`; checked semicircle arc sweep and stroke/dash parameters.
- A real resistor placed at all 8 transforms was rendered into one sheet; group `data-reference` order and every review-overlay physical pin coordinate were validated against the world-coordinate part model.
- XML escaping checked for untrusted special characters in component references/labels without losing their original text meaning. Seeded integer↔mm formatting round-trip sampled at exact 1 µm and up to ~10^12 µm.
- Existing tests already check DRAFT gallery collision overlays, annotation hitboxes, type-A samples, pin corridors and sheet layouts. These do **not** prove 1:1 normative fidelity.

**Outcome:** these structural/vector invariants passed at reference SHA. No raster replacement or inadvertent pin renumbering observed. Whole-sheet symbolic collisions, final routing of new #34, line-junction drawing from #33 and ГОСТ typeface/glyph correctness are **not signed off by this QA run**.

## 6. Bounded performance observations

Source: `tests/qa_performance_test.py` CI warning from run 43313381824; reproducible standalone tool `scripts/qa/benchmark_cycle4.py` with `--sizes 10 50 200 500 --repeat 3 --output output/qa-cycle4-benchmark.json`. The CI job runs **one sample per size** to avoid resource waste; report below is the actual sample, **not a fabricated three-run median**. `tracemalloc` measures Python allocation peaks for each operation, not whole-process resident memory. Both operations use real `resistor.fixed` data. SVG benchmark uses a `SheetLayout` with no annotations; it is raw SVG rendering, not full layout.

| N (segments or components) | Wire ms, Py3.12 | SVG ms, Py3.12 | Wire peak KiB, Py3.12 | SVG peak KiB, Py3.12 | Wire ms, Py3.13 | SVG ms, Py3.13 |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 3.525 | 4.164 | 10.8 | 42.0 | 2.956 | 4.195 |
| 50 | 38.450 | 19.064 | 21.7 | 189.7 | 25.211 | 18.199 |
| 200 | 502.950 | 74.053 | 62.6 | 737.7 | 301.099 | 74.393 |
| 500 | 3139.899 | 188.824 | 146.4 | 1836.4 | 1919.614 | 179.807 |

Measured environment: GitHub-hosted `ubuntu-latest`, CPython 3.12.16 and 3.13.18, runner-controlled hardware; no independent controlled bare-metal profiling. No SLA assertion in tests. At 50→500 segments validation time increased ~81.7× on Py3.12; SVG ~9.9× for components. The nested `for i ... for j ...` and repeated endpoint scan in `validation/external_wire_checks.py` support the quadratic-risk interpretation, but a single instrumented CI sample cannot yield a reliable fitted asymptotic exponent. Memory peaks should not be compared against machine RSS.

## 7. Input robustness and packaging

- Negative input tests cover malformed JSON (unsupported schema versions, duplicate/invalid geometry, zero-length lines); source code inspection identified that wrong nested `geometry` type bypasses `CatalogError`: **#41**.
- Public constructors reject non-integer micrometre points, zero-length external wires, malformed net names and repeated explicit nodes; these rejection paths were independently tested.
- Source catalog audit and installed wheel gate passed for the baseline fixed 19 symbols; no physical passport absent in the currently scanned catalog.
- **Forward-compatibility warning:** existing `tests/test_catalog_integrity_audit.py` asserts `total_symbols == 19`, while the wheel verifier has a fixed four-symbol allowlist and `len(inductors) == 15`. This can block valid catalog growth or under-check newly added families; do not change other teams' files here. With a future diode family, cross-check wheel archive JSON set against dynamically discovered catalog and map every static symbol to a physical passport. Coordinate with #32/#33.
- No measurements of OS RSS, fuzzing with unbounded mutation, generated circuit synthesis above 500 segments, pathological adversarial coordinate magnitudes, or third-party XML viewer rendering.

## 8. Remaining integration gates for coordinator

1. **Electrical #34 / maintainer:** review and resolve **#40** with an agreed diagnostic contract, then change QA `xfail` to strict passing assertion. Do not join nets implicitly from crosses.
2. **Catalog #32 / maintainer:** resolve **#41** using explicit JSON schema type validation; preserve `CatalogError`. Replace QA `xfail` with passing assertion.
3. **Rendering #33 and catalogue #32:** on actual expanded branch/merged catalog, re-run *all* dynamic QA tests and ensure wheel verifier checks new families and physical passports. An isolated baseline pass does not validate unmerged work.
4. **Normative #35:** independently verify real ГОСТ source drawings, line widths, frame/title block, typography, symbol dimensions. Nothing in this report grants approval: baseline **19 DRAFT, zero approved**.
5. Before production claims, establish representative full-schematic performance expectations and profile wire-validation hotspots, while retaining exact-µm and deterministic diagnostics.

## 9. Reproduction and artifact index

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -q tests/qa_catalog_test.py tests/qa_wires_test.py tests/qa_svg_sheet_test.py tests/qa_performance_test.py
pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
python scripts/qa/benchmark_cycle4.py --sizes 10 50 200 500 --repeat 3 --output output/qa-cycle4-benchmark.json
```

Run-specific measurements (above) originate from GitHub Actions rather than from local manual execution. The standalone `--repeat 3` command is a **supported optional protocol**, not a claim it was executed during this audit. The failed reproducibility cases have standalone snippets in [cycle4-reproducers.md](cycle4-reproducers.md), with risk/ownership inventory in [cycle4-risk-matrix.md](cycle4-risk-matrix.md). CI outputs may change in a future run due to machine contention and other teams' concurrent merges; new checks require a new SHA and re-audit.

**Decision:** keep Draft PR open, leave `integration/stage0-12` unchanged until coordinator approves; do **not** merge.
