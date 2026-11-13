# Issue #44 — manual C3 dogleg correction in six-part specimen

**IMPORTANT:** This is a deterministic **manual** correction of the existing authored example, **not** an automatic placement-and-routing algorithm. No inferred component position, AI layout optimizer, search, Dijkstra change, new routing API, model mutation, or generalized optimization is implemented.

## Separate workstream and boundaries
- Base: `integration/stage0-12` `2052e9d3a903edea860c100e00609ceee3c9062b`.
- Branch: `parallel/electrical-layout44`, distinct from safety Issue #58 `parallel/electrical-fix58` (Draft PR #60) and untouched Draft PR #39.
- Only the existing handwritten six-part demonstration, its tests/new versioned fixtures and this explanatory document are changed, **plus a narrowly scoped correction to the historical Issue #35 standards test's SVG-to-archive-JSON comparator**. No edits to `src/`, `api.py`, shared `core/model`, physical catalog, renderer, normative rule cards or historic fixture bytes.
- Existing special `capacitor.electrolytic` remains the SAME DRAFT type, with physical pin 1=PLUS on TOP and pin 2=MINUS on RIGHT. This patch does not resolve whether a different specialized/standard polar capacitor symbol should be selected.

## Exact manual coordinate changes

| Item | Before (µm) | After (µm) |
| --- | --- | --- |
| C3 origin | (100000, 75000) | **(100000, 80000)** |
| C3.1, TOP | (91000, 75000) | **(91000, 80000)** |
| C3.2, RIGHT | (109000, 75000) | **(109000, 80000)** |

Original TOP path: (40,40)→(40,80)→(84,80)→(84,75)→(91,75) mm.
**New TOP path:** (40,40)→(40,80)→(91,80) mm.
Original RIGHT path: (120,40)→(120,75)→(109,75) mm.
**New RIGHT path:** (120,40)→(120,80)→(109,80) mm.

The original 12 external-wire segments from the other 5 devices are unmodified; 6 originally appended C3 branch segments become 4. The final graph has **16** authored segments, **3** original explicit junctions, **5** semantic nets and **6** actual catalog components. No other physical pins, polarities or net memberships are changed.

## Exact before/after quality (not arbitrary score)

The function `c3_manual_layout_metrics()` in the **example only** computes metrics from the original two preserved reference paths and the updated, real `ExternalWireGraph` branches. It outputs reproducible integer µm values in `manual_c3_layout_comparison` in `end-to-end-diagnostics.json`. The metric function does not alter or choose placement.

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| TOP length | 96 mm | 91 mm | **−5 mm** |
| TOP 90° bends | 3 | 1 | **−2** |
| TOP excess over Manhattan | 10 mm | 0 mm | **−10 mm** |
| TOP backtrack = excess / 2 | 5 mm | 0 mm | **−5 mm** |
| RIGHT length | 46 mm | 51 mm | +5 mm |
| RIGHT 90° bends | 1 | 1 | 0 |
| **Combined TOP+RIGHT length** | **142 mm** | **142 mm** | **0** |
| **Combined bends** | **4** | **2** | **−2** |

Therefore the improvement is **simpler graphical route geometry** without any net change or combined wire length reduction. Do not state that the total routing length shortened.

## Safety and negative checks
- Real transformed `PartDefinition`/`SymbolDefinition` positions prove C3.1=(91000,80000), C3.2=(109000,80000). C3 remains electrolytic, PLUS/MINUS retained and correctly assigned to TOP/RIGHT.
- `validate_external_wires` accepts the entire 16-segment authored graph; `validate_circuit` has no ERROR-level findings in the nominal test. The three explicit marked nodes at (40000,20000), (40000,40000), (120000,40000) are preserved unchanged.
- Each of the four C3 branch segments is checked against EVERY real symbol's transformed `body_keepout`, including C2, L1 and C3, expanded by **550µm** (400µm nominal clearance + half of 300µm wire ink). No intersections.
- Existing original negative scenarios still detect an intentional 1µm wire gap, missing T junction, explicit short at an unmarked X when a junction is added, and reverse C3 bias.
- `tests/test_rendering_external_wire_sheet.py` checks actual rendered wires, exact graph/SVG parity, explicitly drawn T/X junction markers and the existing annotation placement engine. These tests use their own controlled test-font metrics, **not** real printed GOST font approval.
- Regenerate the exact clean SVG, review SVG and JSON from the same source graph under **new versioned** `tests/fixtures/electrical-layout44/`. The updated fixture is tested for deterministic, byte-identical regeneration. Keep the historical `tests/fixtures/electrical-cycle3/` untouched: the preexisting normative Issue #35 rule cards and their independent tests explicitly describe the original 18-wire/70.301mm revision, which must not silently be rewritten as modern evidence.

## Reproducibility

```sh
python -m examples.review_end_to_end_circuit --output-dir tests/fixtures/electrical-layout44
ruff check .
pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
```

**Limits:** This specimen is authored by hand, has only six components and does not demonstrate whole-sheet auto-placement, net branching optimization, universal obstacle coverage, authoring of bridges, complete ANSI/ГОСТ font metrics or нормативное утверждение. All 19 catalogue symbols remain DRAFT. A separate real placement-aware routing RFC is still needed for automatic optimization.

**Merge and approval** are coordinator-only; this workstream does not touch or merge PR #39 or safety PR #60.
