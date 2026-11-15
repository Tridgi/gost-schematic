# Cycle 13 — RECON #115 selective integration manifest (DRAFT, NO-GO)

**Owner:** RECON, existing open Draft PR #115, branch `reference/tl494-audit-v4-20261114`.  
**Source lock:** `e695c415fdced164b0e0c39c5249d030795a0aa6`.  
**Decision:** **DO NOT merge PR #115 directly.** Its base is a frozen reference
branch, not `integration/stage0-12`. MAIN 3 must review and stage *small
independent diffs*, only after fresh Python 3.12/3.13 CI and QA acceptance.

## Source authenticity that must survive every selective port

- 23 real components and original SI/Decimal BOM nominal values.
- 15 original Net identifiers, including `a_INPUT_PLUS`, `TRANSFER`,
  `b_NEGATIVE_OUTPUT`; 62 unique physical PinRef memberships.
- All 16 authentic TL494CN manufacturer's physical pins. The legacy
  `reference.tl494cn` → `ti.tl494cn.pdip16` bridge is **strict and reversible**
  through IC #97, not a graphic string replacement.
- Two actual historical *non-electrical* `b` continuation stubs, not extra
  electrical wires/Nets or fabricated junctions.
- The old 91 wire sections / 37 junctions / 9 DRC errors / 32 warnings remain
  an unchanged negative control. A partial new graph with zero reported DRC
  errors is **not** an accepted 15/15 print.

## Minimal Cycle 13 RECON-owned changes for isolated review

| Scoped file | What to selectively port | Must remain true |
|---|---|---|
| `examples/tl494_v5/test_cycle11_b_continuation.py` | Exact strict negative expectation `TL494_C11_B_OLD_SOURCE_TYPED_INVALID:E3_CONT_STUB_OFF_ANCHOR` | Wrong 1 mm b endpoint is still rejected |
| `examples/tl494_v5/compact_layout.py` | Exact A3 paper bounds, `A3_bbox_within_margins`, X1 x=17 mm in **new** compact-only layout | Never move original source X1 or change Net/Pins/UGO |
| `examples/tl494_v5/test_compact_layout.py` | Four rigid-shift negative A3 boundary checks | Off-page physical ink cannot masquerade as on-page |
| `examples/tl494_v5/route_candidate_driver.py` | Strict read-only fixed and new owner-NET congested-veto route modes; exact owner snapshot pins | No custom RECON router or imported partial Nets |
| `examples/tl494_v5/cycle13_placement_matrix.py` | Four deterministic 2.5 mm position-only candidates, bounded search, real verified graph evidence | No result claims print PASS; no 0 DRC on incomplete graph |
| `examples/tl494_v5/test_cycle13_placement_matrix.py` | Genuine signed physical model and forged router/result negative tests | Keep source 23/15/62/16, preserve aliases |
| `.github/workflows/tl494-v5-current-owner-candidates.yml` | Isolated real IC/NET/PAINT/YGO typed source workflow on Python 3.12/3.13 | Never copy unreviewed files into main |

**Port rule:** review individual hunks; keep each owner module in its own PR.
Never cherry-pick #115 wholesale or modify `main`, `integration/stage0-12`,
the source-locked commit, or source/photo files before coordinator approval.

## Exact typed `b` contract (current proposed A3 only)

Real `NetContinuationProject.stubs` after
`examples.tl494_v5.cycle11_b_continuation.rebind_true_source_b`:

| Nonphysical graphic identifier | Existing physical pin | Stub start (µm) | Stub end (µm) | Signed movement vector |
|---|---|---|---|---|
| `b-X2` | `X2.1` | (389000,35000) | (374000,35000) | (-15000,0) |
| `b-R5` | `R5.2` | (25000,224000) | (25000,236000) | (0,+12000) |

**Electrical Net only:** `b_NEGATIVE_OUTPUT`, members
`FU1.2`, `X2.1`, `R5.2` (unchanged source PinRef).
These numbers are *witness values*, not hard-coded renderer geometry.
X1 x16→17 mm does not move X2/R5. For future relocation, PAINT consumes
actual `project.stubs`, verifies both end points and font family, and
checks graphic ink; QA independently verifies both serialized SVG lines.
Referenced actual CI artifact:
[RECON #43709838138](https://github.com/Tridgi/gost-schematic/actions/runs/43709838138),
`C11_SIGNED_REAL_SOURCE_B_PROOF.json`.

## Owner-level read-only dependency snapshot

| Owner | SHA pinned by RECON placement workflow |
|---|---|
| IC #97 | `d7e70a8bfaed5f4e4f7fb340fdc7dbe4fc466e7b` |
| PAINT #93 | `6ebd97d5d51facf15b733a1f909c4530262f5bc8` |
| NET #114 | `027cee506a8dc9b3926b44b1abba66e1ae25b183` |
| YGO #113 | `a805f0d7685187a05064cb801bcff4c893edf811` |

GitHub concurrent work may advance all four owner branches. Any re-pin must
be explicit and CI-verified. The one approved Type A font witness used in
current source contracts is SHA256
`f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`;
never bypass face verification or substitute a look-alike font.

## Required independent acceptance, still NOT satisfied

1. Exact-head Ruff and full + specialist pytest PASS separately on 3.12/3.13.
2. Real 23/15/62/16 signed manufacturer and two typed-b source stubs verified.
3. Source-authentic full 15/15 routing with every required PinRef actually
   attached; no false T/X/PE, no resized DRAFT symbols.
4. Complete full-sheet printed ink/text/UGO/new-wire 3/2/1 mm DRC zero;
   correct paper bounds including b markers, no mistaken printed connections.
5. Actual clean/diagnostic SVG and PNG 300 DPI/BOM/Netlist/SHAs from engine,
   independent PAINT/QA/ESKD evidence and genuine user photo comparison when
   original raster is available.
6. MAIN 3 selective integration review **before** any user-authorized main.

No `APPROVED` claim for source symbols and no 1:1 photo parity claim.

**Next:** inspect placement matrix statuses and real per-PinRef
`INK_VETO/WIRE_VETO` for the remaining five Nets; if no legal A3 path,
evaluate actual A2 and lawful multi-sheet, without erasing source topology.
