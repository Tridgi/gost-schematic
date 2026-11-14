# Cycle 9 — owner NET real native-ink multipin routing contract (Draft PR #114)

**Status:** experimental read-only route generator; **not a print certification**. The user-provided TL494 photo is *not* treated as a calibrated pixel/position source. Do not merge or alter main/integration from this owner branch.

## Source identity

- Frozen `e695c415fdced164b0e0c39c5249d030795a0aa6`: 23 source components, 15 source `Circuit.Net`, 16 original physical DA1 pins and 91 old conductor segments.
- Original 91-wire drawing remains an intentionally negative regression: **9 ERR**, **32 WARN** with 5 explicitly measured offending parallel pairs. It must never be made green by skipping this reference or rewriting its topology.
- Independent compact A3 source profile from RECON #115 is 23/15/16 with **62 immutable source `PinRef` memberships**. Source-specific 13 UGO remain **DRAFT**; no separate PE is inserted into COMMON and no photoshopped elements are substituted for native Parts.

## Geometry-first route-search gate

`_source_ink_obstacles(circuit, symbols, stroke_um)` maps **every primitive** of the *installed* `SymbolDefinition` into the component's physical world position with exact `ComponentInstance.transform.primitive` (all eight D4 poses). Each native `Line` or `StyledLine` preserves its *actual primitive-specific ink width*; the candidate WireSegment width is included.

For linear primitives, preflight rejects actual segment-vs-segment painted stroke intersections using **exact rational squared distance**, avoiding diagonal-AABB false positives. For filled/curved/nonlinear shapes, their conservative stroked bounds remain keepouts. Noncandidate component body/text boxes remain protected. No generic `owner=DA1` or `same Net` exception is permitted.

A candidate may share the cap of **its exact physical authorized `PinRef`** if and only if the candidate starts or ends on that lead's real tip and goes **outward** with respect to its transformed side normal. This cannot be used to ignore a different pin of the same IC or a different Net. All other physical IC pin leads, even a lead on the current component, are a hard keepout.

### Pinned independent source-real repro

Compact A3 historical head (MAIN 3 Issue #107, PR #114) measured:

- DA1.12 physical connector: **(205000, 138750) µm**.
- Old rejected W2 trial: **(203460, 138750) → (203460, 43201) µm**. This walks through the real DA1 lead forest, had no endpoint at DA1.12, and gave `DRC_WIRE_SYMBOL_INK`.
- Test enforces W2 as **REJECTED** during route search, not after a supposed electrical success.
- Candidate x=208150µm *outside the right pin tips* is a provisional geometric probe, not an approved global lane. It must independently satisfy component keepouts, measured text ink, occupied wires, parallel clearances and actual sheet format; no x hardcoding in the router.

## Electrical semantics and scoped clearances

`candidate_wire_clearance` provides the same context-aware wire-pair semantics in two-PinRef preview and multi-PinRef routing:
- 0.3mm + 0.3mm printed wire stroke means parallel centerline **3.300mm** for 3.000mm printed edge clearance; **3.299mm fails**. Parallel gap 3mm applies to overlapping-projection *separate* connection lines, never universally to X crossings.
- Different-Net orthogonal X has no electrical join; a marked cross-Net X or T is a hard short.
- Same-Net T/complex branch requires an explicitly authored junction Point; graphic coincidence does not create `Net` membership. No contact is created at a fractional-submicrometre intersection.
- Symbol gap 2mm and adjacent distinct UGO graphic-line gap 1mm are checked by separately scoped native sheet DRC, not by blindly applying 3mm to these categories.
- Real measured text and symbol stroke collision hitboxes are not bypassed for routing convenience. Whole-sheet new graph DRC is run **again** after construction, including actual label placements.

## Route construction and deterministic optimization

A Net-tree is built from actual source `PinRef` anchors and outward normals; each additional physical pin is attached to an authored existing trunk point, with an explicit dot on every actual T. Dijkstra minimizes cost of length + bends + distinct-net crossing warnings on an orthogonal visibility lattice; invisible X cannot silently become T.

Nets with at least five physical pins may be ordered by deterministic Manhattan Prim proximity to any already selected *real* physical contact; notably `COMMON` should not begin with a 400mm `X1.2→X2.2` detour solely because that is the declarative Net ordering. None of this edits Circuit.Net.

Independent global functional-order trial can recompute separate immutable circuits' route **from an empty graph** using (1) original functional order, (2) COMMON first, (3) power then COMMON; accepted previews are ranked on **completed nets, hard geometry errors, crossings, bends, length**. Each candidate keeps its own graph and cannot splice together segments from incompatible trials.

### No fake PASS policy

The output `GlobalRoutePreview.print_pass` remains false unless **all 15 trees** are complete and both geometry and measured glyph checks pass. Partial reports expose source `PinRef` identities, exact list of completed/blocked contacts, search restarts, candidate ink veto, source owner/primitive and candidate µm coordinates, post-route `Wn` data and DRC findings. A true zero-error DRC on a **partial** graph is **not a successful reconstruction**.

The owner provides raw native review SVG/PNG 300 DPI only with explicit DRAFT/BLOCKED metadata, independent full before/after numerical JSON, and unchanged source Net inventory. A complete **printed PAINT IC** composition, independent QA #99 approval and source-photo comparisons are separate release gates. Never present the surrogate collision adapter as a finished/manufacturer-approved UGO.

## Reproducibility and negative coverage

Source branch owner workflow `.github/workflows/tl494-routing-cycle9-review.yml` uses immutable original e695+PAINT source, real Type A font, 3.12/3.13, 91-wire old FAIL and new draft DRC, actual before/after raster with 300DPI.

New compact `.github/workflows/tl494-compact-a3-router-integration.yml` checks out immutable e695, RECON A3, compatible physical ELEKTRIK IC, 13 real source YGO symbols and native PAINT leads **into isolated CI workspaces only**; not a merge. It asserts 23/15/16/62 and 16 genuine SVG-derived physical lead segments, uses measured PAINT glyph and `layout_sheet` guards, enforces the exact historical DA1.12/W2 negative and exports new **partial** clean/diagnostic native-engine SVG/PNG 300 DPI + numerical JSON.

Focused tests additionally cover real PinRef versus wrong-Net/wrong pin, 0.7/2.999/3.000mm printed gaps, X/T signed semantics, 3-/4-contact T, eight D4 transforms, actual source typography pin coordinates, bounded search and page overflow, and exact ink-vs-wire diagonal AABB counterexamples.

**Known remaining blockers at last audited owner revision:** original composition **9/15 complete**, six Net searches blocked despite partial DRC 0 ERR; compact A3 and independent QA acceptance remain to be verified against exact latest owner SHA. Frozen original source is a deliberately invalid print artifact, not a specification of permissible wire placement. Never relabel DRAFT UGO as APPROVED.

## Cycle 11 (2026-11-15): active-HEAD interoperability and source-real print blockers

This subsection supersedes the Cycle9 provisional source-applicable CI figures above where noted. The immutable original source remains SHA `e695c415fdced164b0e0c39c5249d030795a0aa6`; historical **9 ERROR/32 WARNING** is a deliberately FAIL-closed regression, not an approved print.

### Observed successful CI checkpoints

- Full standard CI Python 3.12 and 3.13: [run 43652933994](https://github.com/Tridgi/gost-schematic/actions/runs/43652933994), owner SHA `b5436ecc800bf7c4a99e1d71cce0cb5dc854ed52`, PASS. This revision fixes the exact Ruff I001 at `examples/review_tl494_compact_cycle9.py` and eight formerly incorrect diagonal D4 negative test probes. The old negative test line was genuinely ~636µm away from the graphic stroke, so a checker rejecting it would be wrong; the repaired test actually crosses the line.
- Specialized route/real source tests: [run 43652928514](https://github.com/Tridgi/gost-schematic/actions/runs/43652928514) PASS both versions: **86 targeted tests each**, original 23/15/16 physical IC, source 91 original segments, **9 of 15 routed Net trees**, **46 newly accepted segments, 1951.151mm**, 0 *new* DRC ERR on **partial only**; remaining 6 are `OUT_BEFORE_FUSE`, `CONTROL_REFERENCE`, `SOFT_START`, `OSCILLATOR_CT`, `OSCILLATOR_RT`, `COMMON`. The geometry indexed [run 43653180409](https://github.com/Tridgi/gost-schematic/actions/runs/43653180409) also PASS all four jobs 86 targeted tests per version, still 9/15. Both explicitly BLOCK all print certification.
- True owner-source compact A3 integration: [run 43651703658](https://github.com/Tridgi/gost-schematic/actions/runs/43651703658), Python 3.12/3.13 success, original **23/15/62 and 16 TL494 pins**, 13 actual source UGO, 73 measured PAINT Type A text guards; **7/15 completed, 35 new segments, 1519.562mm** and 0 new DRC errors only on PARTIAL accepted graph. Eight blocked Nets. Genuine clean/diagnostic DRAFT SVG and real PNG300 artifacts exist but DO NOT represent full reconstructed print. In other words, a green integration job indicates the controlled **BLOCKED** state was correctly detected.

### Additional route-search changes awaiting exact-HEAD CI

- Dijkstra visibility subgraph now indexes actual printed symbol primitive and text collision boxes by orthogonal x/y lane, preserving the exact same closed-boundary projection semantics while avoiding irrelevant full-scan collision checks on every candidate. It NEVER skips a potentially intersecting box: inclusion on the fixed row or column is necessary for any axis-aligned segment/box intersection.
- Genuine manufacturer physical PinRef outward stroke-cap protection treats a split straight outward segment within the printed cap as continuous even when a search-grid knot lies inside the 150µm end cap. This is NOT an arbitrary same-component exemption: both ends must lie exactly on that PinRef's D4-transformed exterior normal ray, not inside its lead or another lead. Actual 3mm parallel geometry, all other ink/text, postroute DRC and explicit junction logic still apply. New positive and negative tests cover 8 D4 poses, inward overlap, off-normal move and wrong PinRef.
- A previously unreachable detour restart was fixed: before trying geometric pin order permutations, repeat the same exact physical terminal order at a bounded greater detour budget. This is particularly important for two-terminal Nets whose canonical original terminal tuple is the only meaningful first route. Existing `Circuit.Net` and raw `PinRef` are never mutated; failed attempts are still BLOCKED.
- New A3 vs A2 comparison uses identical original 23 ComponentInstance positions and Nets, same symbols/Type A/ink guards, and never shrinks artwork. It checks the actual page-frame 10mm editorial source margin separately for each physical page and outputs per-format draft reports and SVG/PNG300, with A2 an independent *feasibility experiment*, not a claim that paper change solved the route.

### Current real owner adapter interoperability

The actual source fixture and physical source owner #97 use `a_INPUT_PLUS`, `b_NEGATIVE_OUTPUT`, `TRANSFER`; older #115's print/editor display uses `INPUT_POS`, `OUTPUT_NEG`, `ENERGY_TRANSFER`. These three source names refer to **exactly the same physical PinRef tuples**, never alternative electrical Net connectivity. A first genuine current-owner run [43653545916](https://github.com/Tridgi/gost-schematic/actions/runs/43653545916) FAILed `TL494_PHOTO_REBIND_NET_IDENTITY_OR_MEMBERSHIP_CHANGED`, exposing this API mismatch (not an electrical short).

The C11 compatibility smoke `examples/tl494_cycle11_active_owner_smoke.py` now relies on **the original-owner RECON #115 verified 23/15/62 restoration** (`route_candidate_driver.restore_original_named_nets`) and its signed manufacturer bridge (`cycle11_ti_bridge.bind_verified_compact_ti`) using **current owner #97's** typed `IcCircuitBinding`. It independently crosschecks the three explicit reversible names, SHA-locked original members and nominals, official `ti.tl494cn.pdip16` 16-pin part, source-owned D4 world coordinates and `orthogonal_route_planner._resolve_real_pin`, signed JSON roundtrip, and rejects forged DA1 ID, missing physical PinRef and DA1 physical movement. The historical original and old RECON Circuit remain untouched. CI `.github/workflows/tl494-cycle11-live-owners.yml` pins independent owner SHA of #97, #93, #113, #115 in a disposable worktree on Python3.12/3.13; this is **not** a merge nor a fake manufacturer symbol render.

The owner PAINT #93 now has its own `render_routed_native_sheet` for a true source-typed new route and complete real 16-contact clean/debug composition. That renderer and independent QA #99, not manual SVG post-processing, must own a future approved full print. The legacy A3 artifact is explicitly DRAFT, so it cannot bypass PAINT's current final assembly or the b-negative-output continuation project.

**Release gate remains BLOCKED.** No 15/15 source-faithful new graph, no 0-error full E3 printed DRC, no independent QA 1:1 image+Net approval, no 36 catalogue UGO normative approval and no accepted autonomous LLM-driven arbitrary netlist writer have been demonstrated. Every print-clean deliverable remains an *unapproved review proof* until those facts change.
