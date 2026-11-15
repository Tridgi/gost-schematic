# YGO2 Cycle 13 parallel continuation — actual compact A3 source ink gate

Date: 2026-11-15. Existing Draft PR #113 on `parallel/catalog-tl494-source-fidelity-cycle9`.
**No merge, no main/integration/frozen source modification.** Frozen original
`e695c415fdced164b0e0c39c5249d030795a0aa6`, 9 old ERROR /32 WARN
negative print fixture. All 36 catalog UGO are **DRAFT**, zero APPROVED.

## Exact genuine owner sources (no fake stubs)

The independent `.github/workflows/tl494-cycle11-owner-contract.yml`
tests REAL downloaded checked-out owner HEADs, never substitutes a mock
`Circuit` or manually regenerated SVG, against both Python 3.12 and 3.13:

| Owner | Exact pinned commit | What the worktree actually verifies |
| --- | --- | --- |
| NET #114 | `a370d637fe67ec44870899d503f53c0a6f8ee3af` | 13 printed source UGO × 8 D4, all physically contacting conductive leads, real source obstacles and conservative 0.30 mm stroke AABB within 2 µm |
| PAINT #93 | `f872ce50ac699ad089391b0bbd58e2cb92f2b7f6` | Actual native `_actual_root` clean/diagnostic SVG for 104 poses, 224 numbered physical pin markers precisely on true contacts, original MOS decorative dot, no green debug rectangles in clean |
| IC #97 | `7c30c209ea5e97a245844b24a3bbc4d3d30118ea` | Actual signed, frozen 23 component /15 original Net /62 PinRef source model, 16 manufacturer IC pins, 13 selected source UGO, no edited physical Nets |
| RECON #115 | `73025965efeb94585e8723ba3f0b636229e8a5de` | **New**: call real `compact_source_assembly` and `actual_component_occupied_mm` on source symbolic 23/15/62 after exact physical X1=(17 mm,35 mm) position-only move; verify 13 source-stroke footprints and 104 exact D4 poses with 224 true lead checks, distinguish source `b_NEGATIVE_OUTPUT` legacy alias `OUTPUT_NEG` with **FU1.2, X2.1, R5.2**; original X1=(16 mm,35 mm) is a *fresh in-memory negative* that must exceed A3 print margin without writing anything to the frozen source |

## Owner checkout and permissible staging

Owner source is a detached temporary worktree at the exact commit, proven by
`git rev-parse HEAD`. Only YGO's public source footprint and its exact
original *unchanged* source catalogue JSON are temporarily overlaid. If an
already present owner source part or symbol has different bytes, CI immediately
fails `SOURCE_CATALOG_DRIFT`: the current actual owner figure must never be
quietly replaced or classified as accepted.

RECON #115 is **reference-based**, not integration-based. Its isolated
checkout does not contain newly implemented IC #97 source modules. The workflow
additionally pins the **genuine IC SHA** and stages eight actual Python owner
modules from the separate unchanged IC commit, exactly as RECON's own
`tl494-v5-current-owner-candidates` run does. It never copies our own
unverified IC shims into RECON.

The RECON positive assertion is **typed source geometry and paper margin
only**: X1 now starts x=17000 µm and the true installed symbol ink with 10mm
paper inset lies within real A3 landscape (420×297 mm). The old 16000 µm X1
candidate is *in-memory negative evidence*, not a second accepted variant.
Record per-reference complete source footprint SHA, source pin identity,
real printed ink bounds and physical lead stroke geometry.

## Release decision

Even if all eight owner matrix jobs are green, **there is no unconditional
approved 15/15-Net electrical route**. This CI deliberately emits
`route_15_net_pass=false`, `normative_status=DRAFT_NOT_APPROVED` and
`release_verdict=BLOCKED_INCOMPLETE_15_NET_ROUTE_AND_GOST_1TO1`.

**OUT OF SCOPE:** PAINT's non-electrical two b stub *graphical strokes*,
reconstructed true full-sheet A3/A2 print after 15Net route, global 3/2/1mm
DRC, Type A real *complete sheet* label collisions and original photo 1:1
calibration. These must be confirmed by their owners/independent QA, and can
fail without weakening this catalog source-identity contract.

If any owner publishes a later SHA, the immutable pinned matrix evidence
does not extend to that later SHA: repin and rerun before reporting it.

## Distinct physical source-glyph stroke clearance — conservative only

The RECON detached worktree now measures all **78 unordered distinct pairs**
among the 13 original-source physical UGO, using the true
`SourceFootprint.ink_obstacles` stroke-expanded per-primitive boxes.
Every pair's minimum is the integer floor of the **Euclidean separation**
of those already-conservative source graphic AABB obstacles, in micrometres.
A source pair with <2000 µm measured conservative separation is rejected.
The **closest pair IDs, minimum separation, 78 pair count** and complete
**original-pose 13 footprint records/physical leads** are emitted into the
signed owner JSON report, along with the 104 D4 positions and 224 true tips.

Additional positive/negative/threshold tests on *typed original
`SourceFootprint` and `BoxObstacle` records* measure exact 0, 1999, 2000,
2001, 3500 µm gaps; empty graphic inventory fails closed, never passes as
"unoccupied." This is an engineering **source UGO subset preflight**, not an
ESKD APPROVED declaration or a replacement for ESKD's 253 printed pairs
including all 23 components and separate DA1, or 1mm printed text and
3mm parallel-wire edge DRC. Full-sheet print still BLOCKED.


## Cycle 14: independently tested real RECON/IC/PAINT source ink

This is **LOCAL evidence**, not GitHub CI. A separate detached Windows
worktree checked out the actual RECON source SHA
8453ea5e2438844ad468b8a9042806ec12e1f125, staging only authentic
IC modules from d7e70a8bfaed5f4e4f7fb340fdc7dbe4fc466e7b and PAINT
modules from 6ebd97d5d51facf15b733a1f909c4530262f5bc8, plus YGO
physical catalogue code from the existing Draft PR. No mock source
graphics, fake Net, signed contact or route output was created.

**LOCAL Python 3.12 and 3.13 PASS:**
- 23 real Circuit parts, 15 Net, 62 original memberships, 16 DA1 pins
- 13 genuine source UGO and 104 D4 poses with 224 conducting pin tips
- 656 rendered graphic primitive obstacles across the 104 D4 source poses
- 78 distinct source UGO pairs; shortest conservative stroke-ink gap:
  C5 ↔ C6 = **16,315 µm = 16.315 mm** (not all 253 real printed pairs)
- X1 moved to (17000,35000) µm: actual source glyph stroke box is
  [10850,31850,27151,53150] µm, hence 10.850 mm left sheet margin
- X1 historical x=16000 in-memory negative: box
  [9850,31850,26151,53150] µm, 9.850 mm left margin, a genuine
  **150µm violation** of the required 10mm printable paper inset
- 36 source catalogue UGO still DRAFT, zero normative APPROVED.

**Separate real owner defect, not silently patched:** RECON's
NativeV5Assembly.symbols does not contain the actual PAINT DA1 symbolic
geometry, although the typed Circuit contains 23 components and all
16 real manufacturer contacts. Thus
actual_component_occupied_mm(assembly, assembly.symbols) raises
KeyError: 'reference.tl494cn'. RECON route_candidate_driver._build_obstacles
synthesizes the missing *real* owner PAINT glyph independently. The
YGO source gate now proves only the true 13 original UGO + actual X1
stroke and explicitly exports
whole_23_component_printed_bounds =
BLOCKED_REAL_DA1_RENDERED_SYMBOL_NOT_IN_SOURCE_ASSEMBLY.
It **does not** fabricate the 23rd DA1 symbol or approve the whole
A3 sheet. RECON #115 was notified with precise owner SHAs and traceback.

Earlier real 8-job YGO GitHub CI failed RECON on Python3.12/3.13 with
ModuleNotFoundError: gost_schematic.rendering.ic_rectangular in isolated
reference-based worktree. The updated workflow now stages ten actual
rendering Python modules from the exact PAINT SHA together with real IC
owner modules. No owner source branch is written to. Repeat GitHub
Action PASS is required before upgrading this **LOCAL** evidence.

**New negative tests** reject a true source contact moved exactly 1µm
(5 source representatives), stale D4 pose (3), and disappearing VD1
ink even with a rehashed apparently correct SHA256 (1). All **89
source-footprint unit cases PASS on both LOCAL Python 3.12 and 3.13**;
Ruff PASS. An attempted all-project LOCAL Windows run exposed an
unrelated existing QA fixture hash drift; this is not a pass waiver.

Finally, this source-only proof does not check the other ten printed
components, full 253 pairs including DA1, 3/2/1mm wiring/text DRC,
graphical b-X2/b-R5 strokes, 15/15 connected routing or calibrated
original-photo/primary-standard GOST 1:1. All remain independently
BLOCKED until real owner QA and ESKD acceptance.
