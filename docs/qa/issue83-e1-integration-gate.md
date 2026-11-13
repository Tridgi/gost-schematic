# Issue #83 — Independent real-code Э1 integration QA gate

**Date:** 2026-11-13. **Status:** QA DRAFT — independent evidence only, no production files changed, NO MERGE. **Target:** `integration/stage0-12` at `e79a12003144a1981bdec829573784215ecaf6d7`.

## Immutable source identities: distinguish historical and current

| Scope | ELEKTRIK PR #80 | YGO2 PR #78 | Review outcome |
|---|---|---|---|
| Initial owner's cross-PR contract | `9c7f62510baafb12685acb67c5034ebfbb8a6b8b` | `c49b7632cac33eafd77b29cc746a37978838f3e4` | Five real old failures, reproduced; **historical** after owner corrections |
| **Current independently executed cross-PR contract** | **`82d400d2472a0a546dafcbf18f70d581642ca284`** | **`0ea11ae8ba608259080fda7341cc81d5b15f5d14`** | **PASS** 7/18/9 real typed SVG; 20mm auto ports quantized identically; genuine OpenGost text |
| Exact current key file blobs | `structural/validation.py` **`a73dfd1f454031e65142dc91e01f87748b842001`**; `structural/__init__.py` **`c651d580daf68193554199fbcbfc75107d3a210c`**; seven-block example **`40a7c8362d67aa65b9941a0c01934d78ac8f6f5d`** | typed `review_structural_e1_model.py` **`d596ca85bab975367843def6706833ae9412e392`**; stand-alone `review_structural_e1_design.py` **`a4355f76daa5a586f4058bd9f4df26c4acc6634b`** | All source SHA bytes independently checked as Git blobs |

Both owner PRs are **Draft / unmerged**, so this tests byte-identical code re-materialized under pytest temporary directories and loaded under its real module names. There are NO fake `StructuralDiagram`, `FunctionalBlock`, `BlockPort` or SVG renderer substitutes. No Git fetch/network is required in pytest; external font installation is isolated in a dedicated Actions workflow. The **only QA-only drawing** is the explicitly labelled *historical* initial seven-block diagnostic overview, NOT used to claim current rendering integration.

## Current PASS/FAIL/BLOCKED matrix

| ID | Gate | New SHA independent result | Reason / evidence |
|---|---|---|---|
| E83-01 | Genuine model↔SVG declared PortRef geometry | **PASS** | Seven blocks, **18** actual `PortRef` markers; **0** path-`d` endpoint mismatches / **0** marker mismatches |
| E83-02 | **20,000µm / two right-side ports** | **PASS** | Actual model and visual positions are **6,667µm / 13,333µm** along side, single half-away-from-zero rounding AFTER absolute origin. 24,000µm gives 8,000/16,000 |
| E83-03 | `1/3`, `1/2`, `2/3`, `3/7`, `7/16` | **PASS typed model** | Exact Fraction survives canonical JSON; 70,000×3/7 = 30,000µm, 64,000×7/16 = 28,000µm |
| E83-04 | Collision **after** integer µm quantization | **PASS rejection** | Distinct fractions mapping to the same final integer receive `E1_PORT_COLLISION`; no silent merged sideport |
| E83-05 | Tiny block / port gap / text reserve | **PASS failure-closed** | Side-port pitch and corner policies are editorial, not invented ГОСТ numerics. Current new model exposes `validate_port_clearances`, view refuses text overflow |
| E83-06 | Dangling, duplicated, wrong-side ports | **PASS rejection** | 24 original semantic vectors replayed against current strict decoder; 8 actual graphic negatives replayed against current PR78 |
| E83-07 | FunctionalLink source/target directions | **PASS rejection** | Real strict decoder and graphic invalid-link validation reject wrong direction or unknown target |
| E83-08 | Visual X crossings without conductive junction | **PASS** nonconductive SVG; **BLOCKED** general route↔model chord contract | Current PR78 draws two directed paths without junction or net. PR80's diagnostic straight-chord validator can raise `E1_LINK_CROSSING` on graph projected from valid orthogonal visible routing. Do NOT infer a physical E3 short; owners must decide inspection vs routed-link semantics |
| E83-09 | Orthogonal rotations / mirrors / transformations | **PASS current legacy SVG D4** | 8 actual YGO2 poses retain stable port ID and verified transformed SVG circle coords; typed renderer `BlockView` is separate and uses resolved real model anchors |
| E83-10 | Deterministic `structural_to_json/from_json` | **PASS** | Current PR80 canonical 7block 18port 9link graph roundtrips; current PR78 `semantic_projection` now includes mandatory `diagram_type:E1` |
| E83-11 | Multi-line text, protection and clipping | **PASS measured 7block** / **BLOCKED formal ГОСТ** | Real OpenGost Type A face SHA-256 `f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`, measured uppercase **2500µm**, actual `PillowTextMeasurer` hitboxes all inside intended rectangles. 0 overflow; external font not shipped |
| E83-12 | Independence from `Circuit`/`PinRef`/electrical networks | **PASS** | Real 7block model contains typed `PortRef` directed links; real SVG contains no junction circles or `Net` semantics. Existing 21 electrical DRAFT catalog symbols unaffected |
| E83-13 | **Actual shared seven-block sample** | **PASS** | PR80 `specimen()` + `ygo2_visual_seed()` aligns **7 blocks, 18 ports, 9 links** on latest PR78, typed clean & diagnostic SVG, genuine 300DPI PNG, all nine SVG `d` paths parsed as integer µm |
| E83-14 | Standalone *decimal projection* of **nonterminating** `3/7` | **FAIL / needs contract** | Old YGO `Fraction(Decimal(...))` converts finite string to a *different rational value*. The new typed model↔SVG renderer avoids this by using original `Fraction`; a general roundtrip through legacy 6block visual string format still needs a rational schema representation |
| E83-15 | Formal ESKD paper approval, norms/spacing/whole E1 sheet | **BLOCKED** | Graphic numbers are project/EDITORIAL design policy, not a certificate. Require ESKD 1:1 standards review before claiming conformity |

**Important historical distinction:** old PR80 9c7f failed 20km third-grid with `E1_PORT_OFF_GRID`; old PR78 c49b omitted `diagram_type`, approximated 3/7, drew visual X the old PR80 inspection chord refused, and failed old tiny seven-block POWER. These are confirmed **old-SHA regressions**, not five present-day production failures. Tests preserve them with **positive assertions on exact archived SHA** instead of keeping already fixed behavior as stale xfails. The current 82d400 model uses final signed half-away rounding, and current 0ea11a visual projection contains the correct diagram type.

## 32 earlier Issue72 vectors now actually executed

The original `tests/fixtures/qa_structural_e1_negative_vectors.json` from **accepted PR77** is not merely counted:
- **24 semantic cases** are instantiated with exact typed JSON against real **current PR80** `structural_from_json` and `validate_structural_diagram`; reject cases must actually reject.
- **8 view-only cases** run against real **current PR78** `validate_design` / `render_svg` for multi-line overflow, invalid 45° pose, dense sideports, crossing, attempted fake electrical fields, reversed arrow and fanout.
- Historical old owner snapshots separately reproduce the original five failures, with no acceptance skew or inactive `xfail` covering the corrected behavior.
- New distinct geometric cases add signed halfµm, D4 pose, explicit multiport fractions, 20km and semantic/ink checks.

Source loader: `tests/qa_e1_integration_support.py`, snapshots under `tests/fixtures/qa_e1_pr80`, `qa_e1_pr78`, `qa_e1_current80`, `qa_e1_current78`. Original `.txt` Python is never modified, Git hash is validated, then executed as genuine `.py` modules in a temporary directory; never vendored into `src/`.

## Images: actual owner graphics, not substitute illustrations

Dedicated workflow `.github/workflows/qa-e1-issue83.yml`:
1. Installs unmodified exact owner-source Python into temporary package paths and installs genuine **SIL OFL OpenGost Type A 0.7** externally (no binary redistribution).
2. Calls REAL current PR78 `render_structural_model` with the actual current PR80 graph (7/18/9), produces **clean/diagnostic SVG + PNG** at 300DPI using CairoSVG, and per-variant JSON manifest. Routes only the owner's L9 using **`((380000,180000),(70000,180000))`**, with endpoints from authoritative real PortRef positions.
3. Parses each physical SVG `path d` into integer µm, checks both link endpoint refs, 18 real port markers, all 9 arrows, 7 blocks, no electrical junctions, determinism SHA, TypeA cap height and every text hitbox within its rectangle.
4. Also emits standalone YGO2 sixblock clean/diagnostic and X-crossing SVG+PNG, separate **QA-ONLY** old semantic diagnostic overview, current PR78 sevenblock standalone diagnostic SVG, measured code/coordinates and JSON SHA manifest; each source clearly identified.
5. Archive named `qa-issue83-e1-pr78-pr80-images` in the workflow run; the active source SHA and font fingerprint are in `qa-e1-current-seven-report.json`.

**Confirmed successful real seven-block run:** [Actions image evidence #43509910504](https://github.com/Tridgi/gost-schematic/actions/runs/43509910504), artifact **`14077662860`**, **current PR80 82d400 / PR78 0ea11a**. All nine actual paths match, 0 marker mismatches, 0 measured hitbox overflows, 2500µm cap-height OpenGost. No font files committed.

## Separate nonregression of form 1 (Issue #67)

**Not part of the E1 interface.** Existing integrated QA tests from PR77 remain in full CI: `tests/qa_form_one_review_test.py` and `tests/qa_form_one_fixed_71ee7f_test.py`. The old bad form1 source (`c42f7b`) and the corrected Draft PAINT `71ee7f` are both SHA-verified; fixed role labels stay left-aligned, graph10 immutable, graph11 surname/12 signature/13 date separate, service captions restored, long texts reject without clipping. This confirms preservation of the **accepted QA evidence**, not approval of a new PAINT HEAD or production E1/form integration.

## Release recommendation

**Independent experimental model↔typed graphical integration: PASS at pinned current PR80/PR78 SHA, conditional.** Do NOT merge on QA authority. Complete or explicitly accept outstanding **BLOCKED** items: model inspection-chord versus routed visual crossing semantics; general exact rational transfer in legacy decimal visual format; formal 1:1 ESKD review. Owner PR78's own real-model workflow has been rechecked separately and should be required green at the exact source HEAD before coordinator merge.

**CI / PR:** Final SHA and final Python 3.12/3.13 Ruff/pytest/audit/wheel + image artifact run links recorded in Draft PR after code/fixture checks. No production code changed; no merge.
