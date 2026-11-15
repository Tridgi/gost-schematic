# TL494CN v5 — MAIN 3 / QA и ELEKTRIK NET handoff, 15.11.2026

**Status: MODEL / UGO / IC / FONT / A3 LAYOUT PASS; ALL-15-NET ROUTE & FINAL PRINT BLOCKED.**

- Repository: [Tridgi/gost-schematic](https://github.com/Tridgi/gost-schematic)
- Continue **only** [Draft PR #115](https://github.com/Tridgi/gost-schematic/pull/115), branch `reference/tl494-audit-v4-20261114`.
- Frozen original `reference/tl494-native-rework-20261114` and its source SHA **`e695c415fdced164b0e0c39c5249d030795a0aa6`** are untouched.
- **Do not merge** into `integration/stage0-12` or `main`. All catalog UGO remain **DRAFT**.
- The original user's two source photos' SHA-256 and BOM are frozen in [v4 plan](tl494_v4/RECONSTRUCTION_PLAN.md), but no certified calibrated photographic 1:1 overlay has been approved.

## 1. Ruff and original tests: completed

A standalone review-only style diff was generated, inspected, and committed as [`cbb4303281ddb97559fcb7273f2326063e8b854a`](https://github.com/Tridgi/gost-schematic/commit/cbb4303281ddb97559fcb7273f2326063e8b854a). Controlled changes in exactly 13 files: 20 v4 + 23 inherited original findings addressed; global `ruff check .` passed and 21 targeted original tests passed in [style CI](https://github.com/Tridgi/gost-schematic/actions/runs/43641098664). Frozen old SVG/manifest SHA-256 and exact old 9/32 DRC source were independently asserted unchanged. No wire, Net, PinRef, component, UGO geometric primitive or BOM was revised by Ruff edits.

## 2. True owner assembly / 300DPI IC: completed, source-locked

- [`native_circuit.py`](tl494_v5/native_circuit.py): builds actual typed `Circuit` with **23 real ComponentInstance, 15 source Net and 16 TI TL494 manufacturer pins**. It reuses the real catalog and the existing source `photo_nets` without auto-ground/phantom Net/PE. Produces [BOM/Netlist JSON] as a structured owner-CI artifact. Preserves FEEDBACK metadata while displaying **FB**, OUTPUT CTRL metadata while displaying **OC**; input type on physical pin 3 and 13.
- 13 actual source-selected YGO2 profiles — Schottky, MOSFET, thin polarized C1/C2/C3/C5/C6, fixed C4/C7, ferro-core L1/L2, variable three-pin R5, fuse FU1 — remain `DRAFT`. Real selector fails closed on wrong variant.
- [`owner_paint_smoke.py`](tl494_v5/owner_paint_smoke.py): true ELEKTRIK IC + PAINT Type A render of **DA1 only**, portrait PWM **bottom→top**, all 16 real `PinRef` external tips. Both clean and diagnostic real SVG + 300-DPI PNG, no editorial diagnostic green in clean.
- Owner-pinned isolated CI [run #43643335788](https://github.com/Tridgi/gost-schematic/actions/runs/43643335788) **Python3.12 / Python3.13 both SUCCESS**; [full CI #43643339406](https://github.com/Tridgi/gost-schematic/actions/runs/43643339406) both PASS at same source snapshot. New owner CI after source model additions also independently green.
- Owner revisions used by this version without merge: ELEKTRIK IC #97 SHA `6161e9102cbc0c9e0491fb27ed7a496dc0b274bc`; YGO2 #113 SHA `edc71a48035723d48a203ae2ea12588701f68ba8`; PAINT #93 SHA `e3ea841dbe087952577121d5690fe41e9a9a5c83`. Newer owner HEADs may exist; do not silently substitute.

## 3. Compact A3, typed positions only: completed

- [`compact_layout.py`](tl494_v5/compact_layout.py) creates a **new, independent** source-typed Circuit, moving only `ComponentInstance.origin` and real owner DA1 placement by the corresponding rigid offset; compares all PartDefinition identifiers, rotations, nominals, exact Net objects and source 16-pin identity. No source Net split/merge or invented SVG.
- Actual real catalog+PAINT stroked UGO extents, source TypeA font, annotation ink: **395.300 × 228.351 mm**, fits **A3 landscape 420×297 mm** with 10 mm margins, no UGO scaling; `layout_sheet.valid=true`, **39 source annotation placements**, no symbol/annotation geometry errors in local execution.
- Five additional compact source tests plus seven owner typed Circuit tests. Owner-pinned read-only A3 preflight [run #43644590180](https://github.com/Tridgi/gost-schematic/actions/runs/43644590180) Python **3.12/3.13 SUCCESS**. The run succeeds in honestly diagnosing route refusal, **not in declaring print PASS**.
- [`route_preflight.py`](tl494_v5/route_preflight.py) derives the DRC-only DA1 geometric obstacle from the real PAINT `<rect>` and 16 real `<line>` graphic strokes. This is **not** a new approximate UGO for printing, not hand-retouched final SVG. Real actual user-clean DA1 ink remains owned by PAINT.
- Exact router owner snapshot #114 pinned in preflight: SHA `b3a8263944c5a687492a49555d8149e538f0902b`. Input `page_box=Box(0,0,420000,297000)`, 25 000 search nodes, measured TypeA text protect. Output is **JSON only**, never a fake final SVG.

## 4. Objective remaining block: all 15 Net routing and print

Owner multi-terminal router #114, on the new compact source, first net `INPUT_POS`:

```text
INPUT_POS: X1.1, L1.1, DA1.12, DA1.8, DA1.11
Connected X1.1 + L1.1 (one segment); next DA1.12 cannot attach.
25 000 nodes: ROUTE_POST_DRC_ERROR:DRC_WIRE_SYMBOL_INK
2 500 nodes: ROUTE_GRID_TOO_DENSE:DA1.12
DA1.12 exact world pin: (205000, 138750) µm
All-15-Net completion: FALSE
Print PASS: FALSE
```

With no successfully completed Net tree, the **new temporary preview graph has zero accepted wires** and may report `drc.error_count=0` on that EMPTY preview. **This does not erase or pass** the old real 91-wire negative DRC; and is **not** evidence the new full circuit is routed.

Exact old independently verified source [full DRC JSON](tl494_v4/evidence_runs/43608095630-1/full_stroke_and_text_drc.json): **9 ERROR / 32 WARNING**, 91 original wire segments, 37 junctions, 23/15, including five 3mm parallel-clearance errors, same-Net X no dot, X1/DA1 graphics collisions, 32 warning X crossings. None was deleted or automatically waived.

Communicated real reproduction and explicit request for foreign stroke offending segment coordinates and legal lane to owner [Issue #108](https://github.com/Tridgi/gost-schematic/issues/108) and [PR #114](https://github.com/Tridgi/gost-schematic/pull/114). DO NOT synthesize a dummy passing route or merge source Net identities to silence DRC.

## 5. Independent QA acceptance TODO and truth label

The accepted final version still needs: actual 15/15 named routes, 0 routing/2–3mm violations, all false-X/T semantics, genuine `b` continuation typed by `NetContinuationProject`, separation of COMMON/0V from chassis/PE, 16 real TL494 pins, PAINT clean 300DPI full sheet A3 (zero green), geometry-validated SVG/XML and 300DPI PNG, original photo/BOM/net identity side-by-side, ESKD/YGO normative review (all symbols `DRAFT` until approved), Python 3.12+3.13 Ruff/pytest/wheel, and independent QA SHA-locked evidence.

**NO-GO** for production electrical behavior and print release. The converter's VD1 orientation and the source's R7=680kΩ/C7=1nF versus ~100kHz note remain unverified. A green ERC or empty-preview DRC cannot make these true.

**Next owner dependency:** ELEKTRIK NET #114 must make input DA1.12 route legally around genuine symbol/ink and prove 15/15. Independent QA #99 must verify before any final `AFTER` PNG/SVG is labeled printable.
