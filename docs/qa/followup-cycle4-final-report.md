# Independent QA follow-up cycle 4 — PR #39 / Issues #40, #41, #44

**Reviewed router:** [Draft PR #39](https://github.com/Tridgi/gost-schematic/pull/39), exact head `4e86e2e0e10d05c591ed004c4d6096de21520007`; source blob `50b9102191fbe7f5876b14bd9ef10dcbbb1fe600` (`src/gost_schematic/engines/routing/two_pin_orthogonal.py`). **Follow-up baseline:** `integration/stage0-12` SHA `73bc6f88a814d7b92267326fc1dab8f127e92e77`, and initially identical `parallel/qa-followup-cycle4`. The baseline did **not** include PR #39 or preceding QA PR #42. No cross-branch merge or production changes were performed.

## Executive finding

**Recommendation: keep PR #39 in DRAFT until the coordinator accepts a pin/ink-aware preflight contract and resolves the new issues.** The bounded Dijkstra itself preserves exact on-grid endpoints and avoids rectangles it is actually given. However, building keepouts exclusively from UGO bodies, as the PR's own real-catalog demonstration does, does not suffice to protect exposed conductive terminals. In addition, mixed-width existing wire ink metadata is lost in `WireSegment`. A third defect causes remote objects to waste the entire grid search cap. These are **observed reproducible behavior**, not merely imagined missing features.

| Severity | Finding | Issue | Evidence |
|---|---|---|---|
| **MAJOR — integration safety** | Wire is routed through a genuine **unassigned resistor terminal** when all real body keepouts are supplied. Existing validator returns zero diagnostics. | [#50](https://github.com/Tridgi/gost-schematic/issues/50), related [#40](https://github.com/Tridgi/gost-schematic/issues/40) | CI [43450510595](https://github.com/Tridgi/gost-schematic/actions/runs/43450510595) / `test_pinned_router_passes_through_real_unassigned_pin_outside_all_body_keepouts` |
| **MAJOR — clearance contract** | Foreign wire 1.0mm stroke + new 0.3mm stroke can violate requested 0.4mm printed separation; router assumes foreign/new strokes equal. | [#52](https://github.com/Tridgi/gost-schematic/issues/52) | CI [43451967831](https://github.com/Tridgi/gost-schematic/actions/runs/43451967831) / `test_mixed_existing_wire_stroke_must_respect_actual_printed_clearance` |
| **MODERATE — false failure / resource consumption** | Irrelevant keepout near (1e9,1e9) enlarges default grid to **1,000,020,000,100** cells; 1mm direct path refused with `ROUTE_CELL_LIMIT`, explicit local bounds succeeds. | [#51](https://github.com/Tridgi/gost-schematic/issues/51) | CI [43450510595](https://github.com/Tridgi/gost-schematic/actions/runs/43450510595) / `test_remote_irrelevant_obstacle_does_not_exhaust_cell_budget_for_clear_direct_path` |

**Three open regressions are `pytest.mark.xfail(strict=True)`**: a fix that changes behavior demands an explicit update to the test and issue; QA does not patch the router. No new confirmed failure in the valid bounded two-real-net scenario, rotated/mirrored contact mapping, terminal exclusion positive controls, unrouteable real-body wall or source blocking.

## How the PR39 code was independently executed without modifying it

Because PR #39 is still unmerged, `scripts/qa_followup_pr39.py` retrieves the exact source file through `git show <SHA>:<path>`; on shallow CI checkouts it first fetches that one immutable Git commit. The loader verifies the Git object blob hash **before** execution. It fails hard rather than skipping the test if the SHA cannot be fetched. No router copy, source edit or production API change appears in the QA PR. Execution is an explicit test-only, reviewed-source exception to lint's dynamic-code rule; inputs are verified commit/blob identifiers.

Future integration must deliberately repoint tests to the accepted PR39 commit/merged code; passing tests against a pinned old SHA does **not** certify later changed heads.

## Test coverage (independent of PR #42 and author-owned PR #39 tests)

- **Real contacts, 8 transformations:** `resistor.fixed` → `capacitor.electrolytic`, with a real middle blocker, 0/90/180/270° and mirror on/off; all routes return exact on-grid physical pin coordinates, remain orthogonal/nondegenerate, avoid supplied body keepouts, and satisfy the actual external-net validator for a legitimate net.
- **12 reproducible seeded blockers:** `Random(3944007)`, real obstacle positions and rotations; canonical and reversed keepout ordering give byte-identical routing results. No random or infinite fuzz search.
- **Real multi-net crossing:** physical R1/R2 form new LINK; physical R3/R4 carry an already authored vertical FOREIGN wire. The router detours around FOREIGN; the combined two-net `ExternalWireGraph` is independently checked without inadvertent shorts. This adds a full multi-net post-check without making PR39 a multi-net router.
- **Failure-on-contact:** existing live wire at target/source → `ROUTE_PORT_BLOCKED` and zero partial lines, conversion to graph raises. Second real component body covering selected source pin also blocks without retargeting.
- **Bounded no-path vs possible path:** real resistor body spans a narrow allowed window, causing `ROUTE_NO_PATH` and empty output; widening the window permits a valid detour with no body collision.
- **Exact 1µm endpoint offset** on a real transformed component → `ROUTE_OFF_GRID`, no silent snapping.
- **Unassigned terminal negative:** real center component's graphical pin lies outside its body keepout; returned wire passes directly over R3.1; existing validator #40 is falsely silent. Positive control: adding the missing pin exclusion box forces a safe route.
- **Mixed-width negative:** new conductor width0.3mm, existing1.0mm, requested clearance0.4mm, grid0.1mm; an independently calculated printed-ink expanded AABB is illegally intersected. Positive control: explicitly pre-inflated foreign ink keepout succeeds.
- **Remote irrelevant hazard negative:** prevents a trivial route only because the auto-window includes the far-away AABB. Explicit finite local window succeeds.

The three negatives have standalone minimal reproductions in their GitHub issues and [the test matrix](followup-cycle4-routing-negative-matrix.md). These assertions are not duplicated from PR #42's whole-catalog structural tests or PR39's original direct-route tests.

## Issue #44 — layout aesthetics with hard electrical safety

Independent six-component example: relocate C3 from (100,75) to (100,80) mm, update TOP/RIGHT branches, retain five nets and all three explicit junctions. Verified in `tests/test_qa_followup_layout.py` that the new real C3 pins are exact, both source and candidate graphs pass external-wire validation, and no modified segment enters the 0.55mm-expanded body keepout of another real UGO. Font/annotation rectangles and final normative page layout have **not** been checked.

| Measured geometric metric | Original | Relocated C3 |
|---|---:|---:|
| Total two-branch wire length | **142mm** | **142mm** |
| Orthogonal 90° bends | **4** | **2** |
| TOP excess vs endpoint Manhattan lower bound | **10mm** | **0mm** |
| TOP geometric backtrack | **5mm** | **0mm** |
| TOP same-axis sign reversals | **1** | **0** |

This proves optimizing only total wire length cannot remove the user's C3 dogleg. A QA-only illustrative weighted cost (length + 5mm×bends + 2×detour + 5mm×axial reversal + moved distance) decreases **187 → 157 mm equivalent**. The weights require calibration on more than one human-reviewed schematic.

[Detailed acceptance gates and proposed metrics](followup-cycle4-layout-quality-issue44.md) cover physical pin/net identity, junctions, actual foreign stroke widths, graph and text collisions, orthogonal validity, length, bends, backtrack, short stubs, near-miss penalties, alignment, displacement and bounded deterministic search. Any electrical error or newly blocked contact is an **absolute rejection**, not something a cheaper visual score can offset. This is a proposal and does not implement component auto placement.

## Legacy defects and independence

- **#40:** remains open. Current validator ignores a wire interior contact with an unassigned physical pin. #50 extends this from hand-authored to **router-generated** wire. It is not fixed by a passing net-validation result.
- **#41:** remains open. Wrong nested catalog geometry type can escape as `AttributeError` rather than `CatalogError`. This is independent of PR39; retain PR #42's existing test, **do not duplicate it** in this follow-up.
- **#42:** untouched, separate QA PR still in Draft at audit start.
- **PR #39:** read-only, no edits to source, tests or target branch.

## CI and reproducibility

**Clean push CI** on QA follow-up SHA `8864d633636c73fe0b9bee733a5f2d4a1c8017da`:
[GitHub Actions run #43452636133](https://github.com/Tridgi/gost-schematic/actions/runs/43452636133), Python 3.12 + 3.13 jobs `SUCCESS`, Ruff PASS, **660 passed / 3 xfailed**, 19 DRAFT symbols / 0 catalog hard errors, wheel content PASS.

**Newer two-real-net integration test push** SHA `bba8390705931f835306302c56088d5323e60a80`: [run #43452854139](https://github.com/Tridgi/gost-schematic/actions/runs/43452854139). Ruff and `pytest` passed for both versions: **661 passed / 3 xfailed**, 19 DRAFT catalog, wheel content PASS. Python 3.13 overall job SUCCESS. Python 3.12 overall job FAILED **only in pre-existing external OpenGOST font download**, which returned `HTTP Error 403: rate limit exceeded`. It did **not** fail a QA test; this rate-limited optional visual artifact installation is not caused by router code. If this persists, do not claim a complete green workflow; retry after rate-limit recovery, do not change someone else's workflow in QA.

Local reproduction (requires Git to fetch pinned PR39 SHA once, already verified in GitHub CI):

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -q tests/test_qa_followup_router.py tests/test_qa_followup_layout.py
pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
```

**No performance SLA or GOST/ESKD approval is claimed.** Baseline has 19 DRAFT symbols. Full sheet text layout, legally compliant line crossings/junction dots, optimized full multi-net routing and font certification remain separately owned capabilities.

## Coordinator disposition

1. Hold PR #39 as a narrowly scoped experiment until #50 and #52 have either enforced typed preflight adapters or explicit fail-closed input contracts, and #40 is resolved at the independent validator.
2. Review #51's remote obstacle search-window policy; keep finite cell caps while avoiding arbitrary unrelated-object failures.
3. Approve Issue #44's hard-gated route/placement score criteria before attempting general auto placement.
4. Re-run QA against an **explicit new accepted SHA** after fixes; check strict xfails and replace with passing assertions only after the expected invariant is met. A fixed design must never begin inferring a net from an unmarked X crossing.
5. Keep this follow-up QA PR **Draft, not merged**; do not change the other teams' branches or PR #42.
