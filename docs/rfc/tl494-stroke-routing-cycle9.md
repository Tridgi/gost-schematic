# TL494 source-faithful E3 layout / routing — Cycle9 independent owner package

**Owner:** ELEKTRIK NET. **Issue:** #108, Epic #107, grounding #109.  
**State:** DRAFT; no auto-merge; no modifications to `main`, `integration/stage0-12`, or ongoing PR #106.  
**Source:** `reference/tl494-native-rework-20261114` @ `e695c415fdced164b0e0c39c5249d030795a0aa6`, `examples/tl494_named_photo_sheet.py` and its original clean SVG + manifest. This is a source-derived photo-trace **not** normative ESKD approval, an electronic simulation, or manufacturer signoff.

## 1. Immutable source and evidence

A frozen source snapshot lives in `tests/fixtures/tl494-routing-source-e695c415.json` and `.svg`. It contains all **23 distinct component references, 15 exact Circuit.Net names, all physically typed PinRef members including DA1.1–16, 91 directed authored segments, 37 explicit real junction Points** and original 0.3-mm printed strokes. The source clean SVG is the original read-only print sample from that same SHA, not a replacement hand-drawn circuit. The declared `OUTPUT_NEG` net has the deliberate named continuation `b`; two already documented `ExternalWireGraph` diagnostics must not be silently erased by inserting a long phantom wire. No real Net or PinRef membership is altered.

The original 679.3 × 220.051 mm viewBox includes source photo control on the left and power devices to the right. Its width already rules out unaltered printing within an A3 420mm or A2 594mm sheet. A1 841mm width can accommodate it in principle, but approval still depends on frame/title areas, checked glyph ink and text; larger paper alone does NOT fix routing geometry.

## 2. P0 — exact stroke-aware geometric DRC

New isolated module `gost_schematic.validation.route_drc` accepts the actual immutable `Circuit` and `ExternalWireGraph`; native `SymbolDefinition` geometry and **actual measured** `AnnotationPlacement.collision_bounds` are optional extra **coverage** inputs. It validates real `PinRef` net inventory without graph-repair side effects. Its output makes `checked_symbol_geometry` and `checked_measured_text` explicit. When these are absent, a source wire-only result is **not a full-sheet PASS**.

Authoritative source-scoped constraints (per ГОСТ 2.701-2008 as scoped by ESKD in Epic #107):
- **3.000mm minimum printed edge-to-edge gap** of adjacent *parallel* electrical connection strokes whose projections overlap; 0.3-mm actual line strokes are subtracted from centerline spacing. Equality is legal; 2.999mm fails. Calculation is exact in integer µm/Fraction until final human report rounding. Vertical, horizontal and skew parallel cases are measured. This rule is not applied globally to perpendicular X crossings or intentional T/join.
- **2.000mm between distinct UGO** as drawn, stroke-expanded native symbol envelopes. Additionally **1.000mm between different UGO graphic strokes**; the current AABB stroke envelopes are deliberately conservative for curved symbols, so a borderline false positive requires actual primitive/PAINT manual review, never a silent PASS. The 2mm whole-UGO gate is inherently stronger when evaluated on the same bounds. Genuine same-unit internal strokes are not separately compared as distinct UGO.
- Wire stroke validity 0.2–1.0mm; annotation `collision_bounds` are actual measured protected text ink regions and are also checked against stroked wire segments. Body keepouts and non-owner symbol graphics are protected. A physical `PinRef` attachment does not grant a blanket exemption for crossing the component body.
- A **true same-net T** demands an explicitly authored `graph.junctions` dot; legitimate collinear fragments of that same real Net are permissible. An unmarked same-net X and 3+ endpoint branch are flagged. An **unmarked different-Net X** is recorded as a nonconnecting crossing with visual ambiguity warning, never electrically connected by a geometric coincidence. A different-Net T, physically shared endpoint or different-Net overlapping collinear strokes is an error. `Circuit.Net` remains unchanged in all cases.
- No non-parallel 3mm **automatic** rule, no bend created simply because optical wires touch, and no transitive wire-to-wire contact assumed from an SVG pixel.
- Numeric output covers **every unordered pair of authored wire segments** (91×90÷2 = **4095**), their printed edge separation, all applicable parallel comparisons, crossing events, 37 authored junctions, orthogonal/diagonal segments, per-wire/per-Net accumulated lengths and geometric incident corner pairs. The latter are reported as corner **pairs**, not fabricated ordered path bends through branched nodes.

**On the pinned source only**, wire geometry already finds five independent violations of the parallel 3mm clearance (source-index pairs W56/W72 0.7mm, W28/W71 1.45mm, W54/W63 1.7mm, W42/W85 1.7mm, W27/W62 1.95mm). It also has additional geometric diagnostics that must not be hidden. Total authored printed conductor length is **4691.25mm**, of which COMMON is **1995mm**. These measurements motivate new placement rather than a claim that the current drawing passes.

## 3. P1 — component placement constraints and safe route preview

`gost_schematic.engines.orthogonal_route_planner` contains two **separate** functions:

1. `evaluate_placement(Circuit, native symbols, page, margin_um)`: checks existing transformed full stroke envelopes, ≥2mm UGO gaps, page area A4/A3/A2/A1/A0 and the actual TL494 functional ordering. It does not move any component: X1→L1, control left/below DA1, power high, DA1→VT1/R8→X2 right, common at bottom. If page capacity fails, it returns `ROUTE_PAGE_CAPACITY` and a larger nominal paper **candidate** rather than shrinking UGO. A more extensive multi-sheet optimization is not implied by that capacity check.
2. `preview_orthogonal_route(..., first: PinRef, second: PinRef, net_name, physical parts, symbols, page_box)`: re-verifies both *physical* PinRefs against real part+symbol mapping and exact existing Net membership; uses resolved D4-transformed µm terminal positions and outward terminal normals, blocks component bodies, actual graphics and printed existing conductor obstacles. Deterministic Manhattan visibility grid with bounded node expansion, a 50mm-equivalent per-bend penalty, actual route lengths and no foreground wire crossings. Rejects wrong-net selection, NC/missing physical map, illegal pin escape, impossible page, obstructed/too-dense search or a detour above configured ratio. **Result is an immutable route preview with zero writes and zero junction creation**. A physical 15-Net global multi-terminal optimizer is **NOT** implemented or falsely claimed; future work must solve explicit branching, page splitting and route orders at an atomic ProjectService revision.

The original frozen reference alone cannot be naively imported into integration as a complete runnable current-native `PartDefinition` set: it was built on a separate isolated PAINT/IC reference branch. The fixture therefore retains exact wire and pin Net evidence, while its `checked_symbol_geometry=false` and `checked_measured_text=false` remain explicit. The reusable DRC can check both when supplied by the real integrated source builder. Joint QA acceptance must pin all participating branch SHAs.

## 4. P2 — COMMON vs chassis vs PE

`gost_schematic.electrical.reference_markers` adds a **nonphysical view marker**, not a `PartDefinition` or new Net:
- `ReferenceRole.COMMON_0V`: points only to a real existing `Circuit.Net` such as `COMMON`, with an exact authored wire index/coordinate or authoritative physical `PinRef`/Point.
- `ReferenceRole.CHASSIS`: equipment frame reference, separately verified and not freely interchangeable with COMMON.
- `ReferenceRole.PROTECTIVE_EARTH`: true protective conductor, never assumed because a reference photo shows a bottom rail.

`validate_reference_markers` rejects foreign pins, foreign wires, forged coordinates, unknown/duplicate NetIdentity, and **PE/chassis labels on a COMMON net**. The current source confirms `COMMON` including `DA1.7`; it does **not** prove protective-earth bonding. Graphic symbols under ГОСТ 2.721-74 table 6б require independent YGO2/ESKD source 1:1 signoff; no provisional PE earth glyph is printed to disguise lack of physical evidence.

## 5. Executable regression and artifacts

`tests/test_route_drc_cycle9.py` covers:
- Parallel strokes with **0.001mm, 2.990mm, 2.999mm, 3.000mm exactly** after line thickness; off-axis and non-overlapping spans not subject to blanket 3mm rule.
- Real T with/without dot; unjoined different-Net orthogonal X; foreign T/end and collinear overlap; 3+ incident branch. All 8 D4 rotations/reflections preserve author-defined topology.
- Whole-UGO ≥2mm, separate ink ≥1mm, and actual measured-label keepouts (synthetic supplied label box).
- Source frozen full 23/15/16/91/37 and 91 original SVG wire elements; no lost physical pin Net members, no fabricated b-bridge, no false whole-sheet pass.
- Deterministic one-net two-pin H/V preview, blocked foreign-Net connect, obstacles, short page and excessive U-turn fallback.
- COMMON marker reference to confirmed original Net; PE cannot be grafted onto COMMON.

Dedicated CI 3.12/3.13 generates the complete JSON measurements, byte-preserved source `TL494-routing-source-clean.svg`, optional **nonprinting** annotated `TL494-routing-drc-diagnostic.svg`, and real **300-DPI** PNG rasterizations with OpenGost Type A available to the renderer. The diagnostic overlays are *not* normative artwork; the clean source is preserved without change.

**Open release blockers:** actual joint 23-symbol PAINT/native source geometry and protected Type A ink boxes, exact user photo comparator, current D4 Schottky/IC signoff, complete placement + 15-Net multi-terminal autorouting, A3 optimization/semantic sheet split, source-proved PE connection and independent QA. No claim of normative APPROVED from a green unit-test run.
