# QA 2 — Cycle 11: source-locked physical TL494 acceptance

Status: **DRAFT, NO PRINT RELEASE**. This file documents independent QA only.
It is not an approval of component UGO geometry, net topology recovered
from an unavailable user bitmap, or ESKD figure conformance.

## Separation of evidence

The historical `e695c415fdced164b0e0c39c5249d030795a0aa6`
source is immutable. It contains 23 component reference IDs, 15 logical
Nets, 62 unique physical PinRefs (16 on DA1), 91 original wire segments,
37 authored junctions, **9 original DRC errors and 32 warnings**. Its output
is a *known-bad source detector*. It must not become a green original print
gate through suppressed tests, substituted symbols, or moved wires.

The NEW owner route is different graph data, not a replacement for the frozen
original. Its source-authored Net names include `a_INPUT_PLUS`,
`TRANSFER`, `b_NEGATIVE_OUTPUT`; the `b` continuation has two typed
nonphysical labels requiring genuine relocated sheet association. The exact
62 physical PinRefs and SI Decimal BOM must survive any move/route.

`reference.tl494cn` is the original historical Part ID; the source-verified
#97 manufacturer Part ID is `ti.tl494cn.pdip16`. The C11 source bridge must
change only DA1 Part ID in a **new in-memory Circuit**, preserve 22 other
part IDs, all 15 actual original named Net *tuples*, 62 contacts, nominals,
physical DA1 pose and manufacturer pin roles. Original source is untouched.

## Immutable runtime snapshot (tested only when exact CI jobs complete)

| Owner | Isolated checkout |
| --- | --- |
| Frozen physical reference | `e695c415fdced164b0e0c39c5249d030795a0aa6` |
| RECON #115 positioned/typed source | `c58e224700b318892ee92197f8bfd391807a7325` |
| ELEKTRIK IC #97 | `1e4baf7ea713f649e0dabb4d6119e97281901f03` |
| PAINT #93 | `f69d891e2f17797878627447eb7f05a66f311ca0` |
| NET #114 | `b5436ecc800bf7c4a99e1d71cce0cb5dc854ed52` |
| YGO2 #113 | `eb16121e07efec71de77dfc7b8123bc09f66ddd6` |

**Provenance is a gate, not a suggestion.** The RECON source report embeds
its *earlier* owner SHAs `19d14c4b...`, `32f2efb2...`, `50336597...`,
`eb16121...`; independent QA detects and separately reports any mismatch
between embedded source provenance and actual ephemeral runtime. A mismatch
prevents release. These are *exact snapshots*, not a perpetual claim of
the latest branch HEAD.

## Actual independent QA source files

- `scripts/qa_tl494_next_route_gate.py`: source-verified 15 named Net-tree
  completeness, original 62 members and 16 DA1, actual conductor/junction
  counts and geometric print DRC; synthetic malicious source/Net/DRC
  mutations are rejected rather than xfailed.
- `scripts/qa_tl494_cycle10_candidate_gate.py --cycle11`: authentic
  RECON 15-tree JSON/accepted route graph, original BOM and signed Net
  identities, ten attempted fraudulent mutations, checked owner SHAs.
  Any partial graph with zero DRC errors remains **BLOCKED**.
- `scripts/qa_tl494_cycle11_part_bridge.py`: actual manufacturer
  legacy→TI source-typed Part ID upgrade + seven source-derived negative
  mutations, real IC source-sealed PAINT clean/diagnostic 16 leads.
- `scripts/qa_tl494_current_editor_cycle10.py --cycle11`: physical
  16 contact manifest from actual 23/15/62 photo Circuit and eight
  adversarial foreign Net/NC/anchor/number/unit/duplicate cases.
- `scripts/qa_tl494_cycle11_native_300dpi.py`: reads the REAL PAINT
  23-part NEW graph SVG, validates 23 native symbol groups, all physical
  DA1 leads and true green targets only in diagnostic mode, source graph
  hash, all claimed Net counts and whole-sheet print DRC flags. Renders
  **the original SVG bytes** to PNG at 300 DPI without modifying SVG art,
  verifies physical millimetres, pixel dimensions and embedded DPI.
- `scripts/qa_tl494_current_reference.py` +
  `scripts/qa_tl494_source_triage.py`: independently keep historical
  known-bad 9/32 and three old visual/Net defects red while recognising
  genuine complete owner native DRAFT 23-part and 8 D4 acceptance. The
  real PAINT 16 editor squares are correctly **one root foreground layer**
  after copper, *not inside* the IC symbol group.
- `scripts/qa92_specialist_triage.py`: classifies old ten missing editor
  galleries, four unsafe low-level bypasses and four synthetic 8-pin
  PWM_CONTROLLER ink overflow cases. New typed owner safety does not
  waive old reachable low-level API vulnerabilities.
- `scripts/qa_install_opengost_release.py` and
  `tests/test_qa_font_direct_release.py`: direct upstream v0.7 Type A
  ZIP, exact known SHA256 `f77d96f8...`, checked SFNT header,
  five offline hostile ZIP/Type B/counterfeit tests. No font bytes in
  Git commits or uploaded QA artifacts.

## Reproducible CI

`.github/workflows/qa92-cycle11-current-owners.yml` runs separate
Python 3.12 and 3.13 jobs with *only* exact source checkouts in an
ephemeral runner. It records:

1. An independently checked original SHA and 5 exact owner heads.
2. Strict Ruff and five genuine font-file reject tests before network.
3. Actual RECON/NET/PAINT/UGO positive, negative, geometry, D4 and
   integration pytest (no skipped negative assertions).
4. Source-locked original BOM/netlist/full accepted graph report.
5. Actual IC16 sealed target and manufacturer-ID bridge verification.
6. PAINT output of NEW graph through its production renderer, then
   independent clean/diagnostic SVG and 300 DPI PNG metadata/geometry
   check. The partial route stays labelled nonprintable.
7. JSON manifests retained even when other owner tests fail; `if: always()`
   on independent audits does **not** make the overall CI green.

Historical specialist workflows are intentionally NOT rewritten into
unconditional success. They exist alongside the new current-owner tests.

## Final release acceptance (fail closed)

**All** must be proven on an exact snapshot before recommending a merge:

- Original photo/BOM and 15 Net, 62 PinRef, 16 manufacturer pins unchanged;
  `DA1.3` FEEDBACK and `DA1.13` OUTPUT CTRL manufacturer type INPUT;
  display aliases FB/OC, PWM word bottom-up.
- Real latest owner router produces **15/15 physically connected Net
  trees** (not 15 attempted, 6 done), and no foreign X/T dot or shorts.
- True whole-sheet *post-render* 3/2/1mm wire, symbol/UGO, measured
  OpenGOST Type A glyph ink DRC has **zero illegal errors**, full A3 1:1
  ink fit, all true b continuation markers correctly bound without
  invented PE/ground.
- Final native source graph clean and diagnostic SVG and real PNG
  metadata at 300 DPI passed independent no-manual-retouch QA.
- Normative source 1:1 UGO comparisons and the actual original user
  screenshot calibrated comparison obtained. Unknown reference bytes
  means **PHOTO PARITY BLOCKED**, not green.
- A documented AI/MCP/Skill pipeline reproduces these artifacts from
  actual typed source data, rather than generating faked SVG or assigning
  unchecked ESKD certification.

Even when all technical routing gates become green, final normative and
coordinator acceptance is a **separate** decision. PR #99 stays Draft,
no branch self-merge or changes to main/integration.
