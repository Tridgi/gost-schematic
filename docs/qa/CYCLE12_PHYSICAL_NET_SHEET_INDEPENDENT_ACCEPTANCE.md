# QA 2 — Cycle 12 independent physical NET TL494 acceptance

Status: **DRAFT / print NO-GO**. This document records independent
engineering evidence. It is not a replacement for the native E3 engine
and does not declare any unsupported UGO or user-supplied bitmap APPROVED.

## Frozen source vs real new route

| Independent input | Typed evidence |
| --- | --- |
| Original frozen source | `e695c415fdced164b0e0c39c5249d030795a0aa6` |
| Exact original TI photo-fixture Git blob | `a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65` |
| Physical elements and original Net identities | **23 / 15** |
| Physical membership and DA1 manufacturer terminals | **62 / 16** |
| Three legacy-to-source Net alias pairs | `INPUT_POS→a_INPUT_PLUS`, `ENERGY_TRANSFER→TRANSFER`, `OUTPUT_NEG→b_NEGATIVE_OUTPUT` |
| Two nonphysical `b` continuation symbols | `b-X2` / `b-R5`; NEVER new electrical Nets |
| Original frozen wire geometry | **91 wires / 37 junctions** |
| Original known-bad DRC | **9 errors / 32 warnings**, retained as negative control |
| Factory FEEDBACK pin 3, OUTPUT CTRL pin 13 | both manufacturer **INPUT** (must be independently signed) |
| Catalog status | **DRAFT**, no blanket GOST approval |

Original source does not provide a separately validated immutable
original photo raster for crop-based pixel equality. The typed topology
and GOST normative conformance are also separate gates.

## Independently opened actual owner output (not a rerouted print)

Source run
[`NET #114 / 43654672504`](https://github.com/Tridgi/gost-schematic/actions/runs/43654672504)
at immutable NET SHA `5c6feb90580ed846aa297c71d3c91afacfc3f0bc`.
The actual downloadable artifact
`owner-114-compact-A3-source-23net-3.12` (artifact ID `14138967475`)
was opened as a ZIP, not inferred from a GitHub status check.

**Confirmed** native 23/15/62/16 component, Net and pin membership
inventory; 15 attempted Net trees, **10 actually complete**, **62 accepted
new conductor segments**, genuine 16 real PAINT IC leads, 16 diagnostic
contact squares, zero in clean, DRC **0 errors only on accepted 10/15**.
**Five real incomplete trees** are:

| Uncompleted Net | Exact source-derived primitive guard |
| --- | --- |
| `GATE_DRIVE` | `DA1#15/16`, `R8#1/2`, `VT1#0/1`; R8.1 blocked |
| `CONTROL_REFERENCE` | `R1#1/2`; R1.1 blocked |
| `FEEDBACK` | `DA1#2/3/4`; DA1.3 blocked |
| `OSCILLATOR_RT` | `DA1#6`; DA1.6 blocked |
| `COMMON` | `DA1#7`; DA1.13 blocked |

The owner rejects a legacy unsafe DA1 input wire W2 crossing real lead
ink. No historic 91-wire rendering was altered to get the 62 accepted
new conductor segments.

**Additional native print defect:** XML reports
`data-draft-paper=A3`, but actual `width=402.6mm`,
`height=244.052mm`, not ISO A3 landscape `420×297mm`.
The real 300 DPI PNG is ~4756×2883 pixels and has ~300 DPI physical
metadata for those **smaller** dimensions, *not for nominal A3*.
The actual owner's DRC JSON correctly lists these frame obstacles:

- `A3_10MM_COMPONENT_BOUNDS`
- `A3_10MM_MEASURED_TEXT`
- `A3_10MM_WIRE_ENDPOINTS`

This is a diagnostic preview, **not a normative sheet**; neither visual
scale fix nor ad hoc manual image retouch is authorized. A2 or correctly
continued multisheet processing must retain true UGO and pin dimensions.

Evidence sent to NET #114:
[`issuecomment-6892677163`](https://github.com/Tridgi/gost-schematic/pull/114#issuecomment-6892677163).
A newer NET branch HEAD cannot claim successful 15/15 based on this
older immutable owner's successfully executed CI.

## Cycle12 independent regression implementation

New QA source script:
`scripts/qa_tl494_cycle12_net_sheet.py`

New QA GitHub Actions workflow:
`.github/workflows/qa92-cycle12-real-net-acceptance.yml`

The workflow source-locks full owner HEADs to immutable snapshot
values, stages real owner modules **only in a disposable NET
worktree**, runs **A3 on Python 3.12 and 3.13** and **A2 on Python
3.13** with genuine original `Circuit`, catalog `PartDefinition`
and `SymbolDefinition`, real physical IC leads and actual NET
router. It never creates or merges a replacement PR. The exact
initial Cycle12 owner checkout snapshot is:

| Owner | Immutable snapshot used by this specific CI |
| --- | --- |
| NET #114 | `219946b73ba67d8f9a0f7dccb7ea4dcabb63c246` |
| RECON #115 | `6b451797dea682283b2627ccacaa36e50e4a1117` |
| IC #97 | `90a493a2f2c08b29db50f410332b91f807869a7b` |
| PAINT #93 | `21d39840f016d8418e658ce13842ff2031fefddc` |
| YGO #113 | `e4de411bcf1d8a910687fd914143e92652dc3f92` |
| Historical source | `e695c415fdced164b0e0c39c5249d030795a0aa6` |

The script parses the genuine owner DRC report, original member-order
Netlist, all 15 tree records and each accepted segment; re-counts
measured symbol/text DRC errors; checks 16 physical manufacturer
lead endpoints and every diagnostic **700µm** green square exactly
centered on each real `DA1.P1..16` endpoint with correct
source Net and no active false NC.

It compares original SVG physical millimetres to the PNG's actual
300-DPI dimensions and header. Two real native source-mode SVGs
are rasterized through CairoSVG **directly from unchanged bytes**.
A source photo-pixel test is explicitly BLOCKED until authentic
original input pixels are furnished.

The test rejects **16 simulated malicious source/print/Net/DRC/UGO
claims** plus **8 in-memory mutations of actual emitted SVG markup**
at the real manufacturer editor targets (1µm displacement,
nonphysical pin number, forged PE, incorrect connection role,
duplicate pin, false 1mm square, wrong manufacturer ID).
No scenario is xfailed, skipped to force success, or allowed to
treat a partial-graph zero-error DRC as completion.

## Layered acceptance

1. **G1 source topology** — all 23 real physical refs, exactly 15
   user-named Nets, 62 unique PinRefs, 16 real TL494 contacts, correct
   SI Decimal BOM. Exact reversible manufacturer Part ID
   `reference.tl494cn` → `ti.tl494cn.pdip16`, no other source changes.
2. **G2 physical routing** — **15/15** connected real trees and each
   native wire/PinRef/junction certified by the owner's source-locked
   Net, global 3/2/1mm DRC including measured Type A glyph ink.
   Source b continuation remains nonphysical, no phantom PE.
3. **G3 physical sheet** — real A3 420×297mm (or verified A2 594×420mm
   or compliant multisheet), complete margins, no scaled/suppressed UGO,
   full-sheet ERC, 0 print-invalid DRC; real independently reproducible
   clean/diagnostic SVG and stamped PNG at 300 DPI.
4. **G4 provenance / normative** — source art/photo 1:1 crop only
   if original authoritative pixel file is available; independent
   per-figure ГОСТ/ЕСКД review by ESKD #112 and MAIN3. All 36 UGO
   remain DRAFT/0 fully approved until normative proof.
5. **G5 integration** — original baseline negative tests still red;
   new owner integration matrix on exact current HEAD after upstream
   fixes; merge only by MAIN3 after complete reviewed checks, never
   by QA2.

An actual 15/15 technical DRC pass can appear in the owner SVG as
`DRC_PASS_QA_NOT_APPROVED` and is *not* final normative APPROVED.
QA's checker supports this future positive but refuses print release
without the independent source, typography, geometry, ESKD and photo
requirements.
