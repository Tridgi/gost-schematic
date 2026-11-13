# Coordination status — 2026-11-12

**Scope:** experimental work only. `main` and historical PR #2–#9 remain untouched; all 18 existing symbols remain **DRAFT**, 0 approved.

## Accepted integration batch

- **#15 / Issue #11 — ESKD normative evidence:** merged to `integration/stage0-12` as `122b4caff1962841d98f43ac5e36cc3896240da2`. CI after merge: https://github.com/Tridgi/gost-schematic/actions/runs/43299843402 (success).
- **#16 / Issue #12 — external wire graph prototype:** merged as `bcfdec9b9c1101ba7ce5d3028ec624acf7c47da0`. CI after merge: https://github.com/Tridgi/gost-schematic/actions/runs/43300060566 (success).
- **#14 / Issue #13 — 18-UGO SVG review harness:** merged as `c31b16a24f967f99b780166a075d615aa73a6ce5`. **Combined CI**: https://github.com/Tridgi/gost-schematic/actions/runs/43300234625 (success, **408/408 tests** on Python 3.12 & 3.13, Ruff pass, catalog audit 18 draft / 0 hard errors, wheel verification success).
- Issues #11, #12, #13 closed as completed development tasks, **not** as normative UGO approvals.

## Active / blocked

- **Issue #10 `parallel/catalog`**: standalone polarized electrolytic capacitor DRAFT. Normative sources from #11 handed off in coordinator comment: https://github.com/Tridgi/gost-schematic/issues/10#issuecomment-6834997778 . Exact final geometry/controlled vector and full dimension authority still pending. Any experimental dimensions must be clearly named editorial and not claim ГОСТ certification. New JSON/physical part requires tests, isolated contacts, correct polarity, explicit topology.
- **Issue #17 — Rendering catalog growth**: refactor review sheet to include all current DRAFT symbols dynamically, not hard-coded 18. Coordinate with #10; no shared model/core/catalog changes. https://github.com/Tridgi/gost-schematic/issues/17
- **Normative manual review**: 15 inductor shapes remain unapproved, high-risk `double_tapped`, `sliding_contact`, `trim_copper`, `variable` need controlled KOMPAS/original comparison; not a blocker for isolated DRAFT engine evolution.

## Review decisions

- Three PRs were reviewed by coordinator and merged **only** into experimental integration, not `main`.
- No automatic promotion from DRAFT to APPROVED. Green CI checks implementation properties, not full compliance with ГОСТ.
- Current integration code baseline before this status document: `c31b16a24f967f99b780166a075d615aa73a6ce5`. Future workers must fetch current `integration/stage0-12` HEAD, not use old `67c66da` baseline.
- New work must use independent branches, clear Issue scope, and new Draft PR; preserve existing reviewed commits and avoid rewriting unrelated history.

## 2026-11-12 — Parallel batch #2 integrated (experimental)

Base for this cycle: `9e9d056e410c8a54dc3c9fc9d5cc56b74e6f225b`.

- **PR #21 / Issue #18** normative high-risk inductor cards: merged `dc1d7a35e98158b0b3c12b6e337e81603596ac6e`. Correctly identifies `trim_copper` dash as defect; `double_tapped`, `sliding_contact` remain adaptations, all DRAFT.
- **PR #20 / Issue #19** external wire graph on real parts: merged `3def08ed408967dc11a7a8bf2e2b93359d8edb29`. 7 reproducible JSON cases, physical pins and netlist comparison, no auto-router.
- **PR #22 / Issue #17** dynamic SVG gallery: merged `7a11f7a3311ea88506db9fbe34396982c4a8917e`. Catalog scanning / real part passports, expansion and diagnostics; dynamic rendering workflow needs follow-up trigger for catalog changes.
- **PR #23 / Issue #10** separate `capacitor.electrolytic`: merged `135c2b11c5a498345a27f9202a1c7c2a351da7e0`. 19th DRAFT symbol, separate physical + / − and graphic conductor groups; **8 mm plate length, 1.5 mm electrode gap and related geometry remain editorial assumptions**, not verified dimensions of the special electrochemical UGO.
- **Combined CI** on final integrated HEAD `135c2b11c5a498345a27f9202a1c7c2a351da7e0`: [Actions #43305090995](https://github.com/Tridgi/gost-schematic/actions/runs/43305090995) = SUCCESS, Python 3.12 and 3.13 **505/505 tests**, Ruff PASS, **19/19 symbols DRAFT, 0 hard errors**, wheel **4 symbol passports + 4 physical parts + 15 inductor profiles + 1 normative profile**.
- Issues #10/#17/#18/#19 closed as **technical** tasks. This does not constitute visual normative acceptance of any UGO; **0 APPROVED**. `main` remains unchanged.

Next-cycle Issues: [#24 copper-core correction](https://github.com/Tridgi/gost-schematic/issues/24), [#25 SVG on catalog changes](https://github.com/Tridgi/gost-schematic/issues/25), [#26 end-to-end wired diagram](https://github.com/Tridgi/gost-schematic/issues/26), [#27 next-source-backed UGO family](https://github.com/Tridgi/gost-schematic/issues/27).

## 2026-11-12 / 13 — Third parallel batch integrated

- **PR #30 / Issue #27**: next-family normative shortlist; 12 source-backed DRAFT/BLOCKED candidates, not implemented. Merge `a5b459bf1ad9b6a6da8a50ac1d45c4861e990fcf`. Official status of GOST 2.730-73 and 2.755-87 independently checked; universal unshielded NPN source still requires stronger normative basis. No model/catalog change.
- **PR #31 / Issue #24**: correct `NONMAGNETIC_COPPER` continuous nonconductive core and honest provenance for double-tap/single slider. Merge `56e120464e552db6042d8f1ab0320472709f100a`. Remaining manual 1:1 inductor geometry BLOCKED.
- **PR #29 / Issue #26**: reproducible end-to-end 6 actual parts, 5 nets, 18 authored conductor segments, 3 explicit junctions, clean/diagnostic SVG and tests/JSON cases; does not autoroute or certify ГОСТ. Merge `442fa611fd7b9aba033476ed87141dde42896662`.
- **PR #28 / Issue #25**: dynamic catalog-triggered SVG/PNG visual regression workflow, with 7 SVG/7 PNG and source-font provenance, actual 19-UGO clean/review sheets. Merge `6f359e3324338bad73b8443cc69857571fbaffd0`. Important follow-up: test `test_real_19_catalog_entries_and_unique_C_references` contains exact 19-count assertions, and must be adapted before adding a 20th symbol.
- **Combined CI HEAD** `6f359e3324338bad73b8443cc69857571fbaffd0`: [run #43309918713](https://github.com/Tridgi/gost-schematic/actions/runs/43309918713) **SUCCESS** on Python 3.12/3.13, 623/623 tests each, Ruff pass, catalog audit 19 DRAFT / 0 hard errors, wheel verified. Separate [rendering #43309918718](https://github.com/Tridgi/gost-schematic/actions/runs/43309918718) successful, artifact `draft-rendering-sheet-review` id 13985526602.
- All above merged **only** into experimental `integration/stage0-12`, not `main`. Review of code and generated artifact structure does not equal manual normative acceptance or KOMPAS comparison; **0 APPROVED**.

## 2026-11-13 — Cycle4 coordinator partial review and routing safety gate

**Current experimental integration SHA** `41e23513176d51c21bde5b4363ea4f67469e3bd8` before this status commit.

- **#37** already merged: dynamic 20+ gallery and authored-wire rendering adapter.
- **#47 / #43** merged `8ffbab3be3735add4fc0021a803aeef2d5f70556`: test `nominal=None` is legitimate and no longer crashes. Visual regression CI 19 DRAFT passes; new diode 21-DRAFT run must be done by YGO 2 after syncing.
- **#48 / #40** merged `42cb8ff63cd5685f98e24081f85c947262c12c08`: detect unassigned real physical pin touched by wire interior, without auto net attachment. 365 tests added; integration CI green. Separate QA hypothesis #54 remains to verify other-net crossing when a pin already has another attachment.
- **#38 / #35** merged `41e23513176d51c21bde5b4363ea4f67469e3bd8`: source-backed full-sheet/ESKD review; no approved UGO.
- **Combined integration CI** [#43455652130](https://github.com/Tridgi/gost-schematic/actions/runs/43455652130) **SUCCESS**, Python 3.12/3.13, 1019 tests, Ruff PASS, audit 19 DRAFT/0 hard errors, wheel verified.
- **#49 / #45** standalone 2.728-74 C3 normalized-source review approved for documents, but merge blocked by conflict in `docs/standards/registry.md` and `known-limitations.md` after #38; ESKD asked to sync while preserving both sections. No silent symbol replacement, both DRAFT.
- **#42 QA** and **#53 QA follow-up** remain Draft to update stale #40 xfail/retroactive report and remove brittle permanently Git-fetched router SHA source test; original evidence kept.
- **#39 / #34 autorouter** remains **BLOCKED**: independent QA #50 and #52 (unassigned pin/wire stroke clearance) and #51 (far-away keepout + cell limit). Mandatory remediation tracked in **#55**, no claim of universal safe routing; separate placement quality #44.
- **#32 YGO 2** may now resume: both historical visual regressions (#37 and #47) have fixes integrated, next full catalog is 21 DRAFT once two diode JSON and physical part passports are accepted.
- **#41** malformed geometry should emit CatalogError and remains open.
- `main` was never changed, **0 APPROVED**, all normative/visual acceptance remains separate manual work.

## 2026-11-13 — Coordinator integration review: diode, ESKD, safety, router, and C3

- **PR #49** accepted and merged as `9cca588a364561ef32050cec2ae14fa1840bbf4a`: normative evidence for `capacitor.polarized` vs special outlined `capacitor.electrolytic`. No physical/graphics mutation, both remain DRAFT; controlled 1:1 normative overlay still needed.
- **PR #60** accepted/merged as `8c222019397668eb00711b34bd341228946d5ce8`: MAJOR #58 fixed in validator, real physical pin foreign-net interior contact diagnostic, preserves unmarked X semantically separate.
- **PR #57** accepted/merged as `3f0b2fca929079f836ecb38ea93d42a6556db247`: `diode.general`, `diode.zener`, physical A/K and 21 DRAFT/0 hard errors; no APPROVED.
- **PR #39** accepted/merged as `a3aefe4447dff840eabd894d71a3b83eb77b0f64`: restricted *experimental* two-pin typed safe adapter, #50–52 independent latest-HEAD QA evidenced via PR #61, not full multi-net placement or professional safety certification. Low-level geometry-only helper requires complete barriers.
- **PR #62** accepted/merged as `f464879d79d3b964fff52e884c4c446d0057d677`: C3 live authored specimen moved y75→y80mm, 18→16 wires, TOP backtrack 5→0mm, bends 4→2, total TOP+RIGHT length remains 142mm. Old archived 18-wire fixture and normative Issue35 test preserved. Manual source improvement, NOT autoroute placement.
- **Full combined CI** on `f464879d79d3b964fff52e884c4c446d0057d677`: [Actions 43471846041](https://github.com/Tridgi/gost-schematic/actions/runs/43471846041) SUCCESS, Python 3.12 and 3.13 **1372 passed each**, Ruff PASS, **21 DRAFT / 0 hard errors**, installed wheel payload 6 symbolic/6 physical plus 15 winding/1 normative profile.
- Closed issues #32, #45, #58, #34, #55, #50, #51, #52 and investigation #54 as scoped technical milestones, **not** normative approval or completion of full routing. #44 remains open for automatic placement-aware optimization.
- **HOLD PR #59**: typography/form-one geometry/clean-first revised, CI green on its own old base, but tests and example still assume live C3 y75mm / 18 wires. Must sync after merged #62, adapt to archival-vs-live (16 wires), regenerate SVG/PNG, seek independent ESKD normative review Issue #63. Do not merge without visual acceptance.
- **HOLD QA PR #61**: independent new-HEAD #39 safety proof accepted, but strict `xfail` for #58 must convert to ordinary PASS after #60; add tests against actual integrated router modules, not frozen-source alone, and rerun on 21-DRAFT base. Historical QA PR #42/#53 retained pending reconciliation/archival, never merge stale xfails.
- **Issue #63** ESKD independent normative form-one review; branch `parallel/standards-form1-review` forked from last combined head. `main` remains unchanged; 0 symbols approved to ГОСТ.

## 2026-11-13 — Sixth parallel cycle started: schematic annotation, form-1 completion, structural Э1, agent vision

- **PR #61 QA** merged `ecd3e1647220160ddb9d8ce706ceb0463386329c`: pinned and shipped actual router regression, #50–#52 + #58 regular PASS, 21 DRAFT, no historical strict xfail; CI [#43488050648](https://github.com/Tridgi/gost-schematic/actions/runs/43488050648) SUCCESS.
- **PR #66 ESKD** merged `e2b280d91957ff678c90b792e2c94fa9e73e27ae`: independent source-backed title-form 38-card matrix (24 PASS, 6 FAIL, 8 BLOCKED), 300 dpi evidence, C3 18 archive vs 16 live intact; CI [#43488484665](https://github.com/Tridgi/gost-schematic/actions/runs/43488484665) SUCCESS. Normative Issue #63 closed as completed **review** only; form remains DRAFT/BLOCKED.
- **PR #59 PAINT** remains on hold for production form-one corrections [#67](https://github.com/Tridgi/gost-schematic/issues/67): left-aligned duty captions rather than universal center, distinct role(10)/surname(11)/sign(12)/date(13), missing form columns (30)/(33)/(35)/(31)/(32); no fictitious documentation. Separate label-gap quality issue [#68](https://github.com/Tridgi/gost-schematic/issues/68) addresses L1 placed high above winding because specimen label uses body_keepout.min_y, which may include tall tap. ГОСТ 2.702-2011 §5.3.11 prescribes near UGO (above/right), not universal fixed gap.
- **Structural electrical diagram Э1** new workstream, distinct from physical-principle Э3: [#69 normative](https://github.com/Tridgi/gost-schematic/issues/69), [#70 typed functional blocks/side ports](https://github.com/Tridgi/gost-schematic/issues/70), [#71 graphic dossier YGO](https://github.com/Tridgi/gost-schematic/issues/71), [#72 QA independent checks](https://github.com/Tridgi/gost-schematic/issues/72). Center of side for a single port is a sensible **editorial default**, not a hard quote of ГОСТ. Directed process links cannot be silently treated as electrical nets/pins.
- **AI Integration** remains P0 in [#65](https://github.com/Tridgi/gost-schematic/issues/65) / #64: real PNG MCP ImageContent and detail crops; do not derail P0 to structural mode until respective models are agreed.
- New isolated branches: `parallel/annotation-refdes-cycle6` (PAINT after form), `parallel/standards-structural-e1` (ESKD), `parallel/structural-e1-model` (ELEKTRIK), `parallel/catalog-structural-e1-design` (YGO), `parallel/qa-structural-review` (QA). All forked from `e2b280d`. Branches do not grant rights to merge into main; no automatic ESKD symbol approval.
