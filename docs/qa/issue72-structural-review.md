# Independent QA Issue #72 — L1 ink gap, form 1 PR #59, structural E1 threats

Status: **DRAFT QA / NO production changes / NO merges**. Date: 2026-11-13.

## B0. New PAINT SHA after historical PR66 audit — separate fresh QA (2026-11-13)

**Important: the PR #59 owner advanced independently while this review was running.** The original normative PR #66 matrix (**24 PASS / 6 FAIL / 8 BLOCKED**) describes **OLD SHA `c42f7b617942c8a0b1cae45e432ef12cede7f876` / `form_one.py` blob `9025fefd18ec9e50118d7353f5b2565eb064b5c4`** and remains immutable history. It must **NOT** be presented as an audit of the **NEW Draft PR #59 HEAD `71ee7f0c26d2f2f41a67d9e4450aa33d265286fa`**, new `form_one.py` blob `ffa94169439353ab5c35738c5dfae9c7fb6dfe6f`.

This QA therefore independently pinned **both** byte-for-byte source snapshots and added `tests/qa_form_one_fixed_71ee7f_test.py`. The new file uses a deliberately **synthetic narrow 2.5mm-cap deterministic glyph metric** ONLY to isolate and test the structural rendering API; it is **not** an actual OpenGost physical/print test or source-author approval. Real OpenGost Type A 1:1 updated title-block proof still requires independent ESKD review of PR #59's output. No code from PR #59 has been merged into this QA integration.

| Requirement originally FAIL (old PR66) | Old pinned SHA `c42f7b` | New pinned SHA `71ee7f0` — independent result |
|---|---|---|
| Five role captions left ink-aligned | **FAIL**: all centered | **PASS behavior**: five actual role captions use same `800µm` left ink inset, fixed 17mm × 5mm row; measured `PlacedField.ink.min_x - cell.min_x == 800` with deterministic height-2.5mm QA metrics. **0.8mm is editorial**, not a GOST-required numeric inset |
| Fixed role (10) vs surname (11) | **FAIL**: `developed="Иванов"` overwrote «Разраб.» | **PASS behavior**: `developed="Иванов"` raises `TITLE_ROLE_RESERVED`; `developed_surname="Иванов"` creates a separate graph-11 object while retaining graph-10 «Разраб.» |
| Surname, signature, date | **FAIL**: none per role | **PASS structure**: five independently addressable `*_surname` (x17..40mm), `*_signature` (x40..55mm), `*_date` (x55..65mm); all separate from role x0..17mm |
| Auxiliary (30) dashed | **FAIL**: no dashed graphics | **PASS vector data**: exactly one source-labelled `data-service-graph=30` SVG line with `stroke-dasharray="3 2"`, from x65..175mm at y8mm |
| «Зона» (33), «Вер.» (35) | **FAIL**: absent | **PASS structural output**: explicit text graph numbers 33/35 and distinct cells in captioned source |
| «Копировал» (31), «Формат» (32) | **FAIL**: absent | **PASS structural output**: explicit caption nodes 31/32 at relative y55..60mm (bottom sheet margin, outside 185×55 stamp) |
| Role font cap-height, no autoshrink | **PASS old Type A profile** | **PASS with QA deterministic 2500µm glyph contract**; **BLOCKED** final independent verification with actual OpenGost Type A, 300 DPI, physical 1:1 print and office-specific applicability |
| (2)/(30), (9)/(31)/(32) exact controlled Annex B.1 placement | **BLOCKED** | **BLOCKED** still: altered geometry must be independently compared to dimensioned 1:1 original, including external service cells and printer stroke |

The new source does **not** fabricate signatures/dates or declare full paper-ESKD approval; blank output remains blank. The older **DejaVu Sans** fallback is too wide for some 5–7mm cells even at measured cap height 2.5mm and appropriately raises `TITLE_FIELD_OVERFLOW`; this proves why a random OS sans-serif substitute cannot certify OpenGost and why the QA functional tests label their metrics as **synthetic contract-only**. The new renderer is **Draft**, and print approval remains **BLOCKED** pending ESKD.

**Critical distinction:** the six original FAIL criteria are confirmed *fixed in the new implementation's supported source/functional geometry*, while the 8 original BLOCKED conditions are **not automatically resolved** by a developer declaring the changes done. Refer to exact SHA of each sample.

---

## Precise source snapshots

| Target | Exact immutable source |
|---|---|
| Current integration, containing previously accepted PR #61 | `45d4451eb06e7e469aa4e3c26e728ac8a5bdf3c5` |
| Real six-part generator `examples/review_end_to_end_circuit.py` | blob `c1e4bb33b15d1f5bda7c32310705132381582ebb` |
| Real sheet SVG renderer `src/gost_schematic/rendering/sheet_svg.py` | blob `96b57568f28356bbcc36999d5810c30700f71049` |
| Sheet label policy `src/gost_schematic/engines/sheet_layout.py` | blob `bff7f3c77ceacba264aca3783bd8ee908c134d75` |
| Tapped inductor profile `inductor.tapped.json` | blob `ed082050e946b77023b30345d2317c74af2b8fb5` |
| Separate unmerged PAINT Draft PR #59 | HEAD `c42f7b617942c8a0b1cae45e432ef12cede7f876` |
| SHA-verified *test-only* frozen PR59 `form_one.py` | blob `9025fefd18ec9e50118d7353f5b2565eb064b5c4` |
| Accepted **normative** PR #66 matrix (38 rules) | `docs/standards/issue-63-form-one-matrix.json`, blob `2dc00fd1ed8f0cba47ea6fb9caa561c6b266a99d` |
| Independent normative PR #66 explanatory report | blob `ebd7f7169a5d037ff7f6ba33f79786cfe6549daa` |

This QA does not modify the draft PAINT code; it only imports a pinned source copy from `tests/fixtures/qa_form1_pr59_c42f7b_snapshot.txt` into an isolated module namespace. The source is verified using Git's `blob <length>\\0<bytes>` SHA1; **no Git retrieval/network access in pytest**, and no mock replaces an installed production module.

## A. L1 true six-part rendered ink clearance — PASS measurement / FAIL visual consistency

**Observed direct source:** `authored_specimen()` consists of real R1, R2, C1, C2, L1, C3; C3 was moved to (100,80)mm by accepted PR #62. `specimen_svg()` draws *actual* authored component primitives and has an independent specimen-only `text-anchor=middle; font-size=3.5mm; font-family=sans-serif` label layer. Unlike the real `layout_sheet()` alternative, this preview uses the top of `body_keepout`, then puts every baseline `2.5mm` above it. The label ink is measured through Pillow/FreeType using the font selected for `sans-serif` by Linux fontconfig, **DejaVuSans.ttf**, SHA256 `b4c632e3cdf9acc7f28758fb5a323c8524d7fc6660d46904d9b6cbe2809c419c`. Font is external; not copied, embedded or asserted to satisfy ГОСТ Type A. The rectangle-based distance is to **actual stroked primitive AABB**, a conservative reproducible proxy for the exact curved ink distance (not a pixel-to-pixel font proof). Units are mm.

| Printed label | SVG baseline (x, y) | Top of project `body_keepout` | Baseline→keepout | Ink→visible core/plate or resistor body | Ink→nearest ink of ANY UGO stroke |
|---|---:|---:|---:|---:|---:|
| **R1** | (20, 15.5) | 18.0 | 2.5 | **2.350** | **2.350** |
| **R2** | (20, 55.5) | 58.0 | 2.5 | **2.350** | **2.350** |
| **C1** | (60, 13.5) | 16.0 | 2.5 | **2.302** | **2.302** |
| **C2** | (60, 52.3) | 54.8 | 2.5 | **3.502** | **3.046** |
| **C3** | (100, 72.0) | 74.5 | 2.5 | **3.802** | **2.980** |
| **L1** | (100, 30.5) | 33.0 | 2.5 | **7.350 to winding turns** | **0.350 to upper tap** |

**Root cause, with exact independent integer-µm geometry:**
- L1 is the generated 4-turn 2mm-radius tapped winding, centered at `(100000,40000)`µm. Four semicircles have *actual stroke-included* minimum y **37850µm**, i.e. 7.350mm below the baseline.
- Pin `L1.3` (tap) is at `(98000,31000)`µm; upper end of its 300µm ink stroke reaches **30850µm**, only **0.350mm** from the baseline (and FreeType ink lower edge of 'L1' is at baseline).
- The protective `body_keepout` top is **33000µm** (7mm above winding origin), **2mm BELOW the tap's nominal 31000µm contact**. Thus the body box is neither a faithful 'top of winding ink' nor an enclosure of all physical pin strokes. The SVG baseline blindly uses `body_top - 2500µm`.
- The winding gap 7.35mm is **3.13× R1**'s 2.35mm and **3.19× C1**'s 2.302mm, despite identical baseline→body gaps. Moving L1 text down without considering the tap and external wires could cause a real collision.

**QA conclusion:** numeric source geometry **PASS**; consistent visible L1-to-winding layout **FAIL (visual/editorial Issue #72)**; safe automated repositioning **BLOCKED** until proposed placement is measured on the actual annotated + routed scene with the final font and all pin/wire/annotation obstacles. ГОСТ 2.702-2011 §5.3.11 allows designators above/right; **no numeric 'correct L1 gap' is invented**. Recommendation: offer an explicit right-side preferred candidate for tapped winding with collision/reservation checks; keep a clearance corridor at L1.3, do not shrink the top tap box, and do not blindly modify winding geometry or intrinsic electrical connectivity.

**Reproduction:** `pytest -q tests/qa_structural_l1_test.py -s` parses the actual six-part SVG, recomputes transformed UGO strokes + actual measured text ink in µm, checks fixed tap/body/coil coordinates and compares all six labels. CI warning prints the exact ink AABBs and font fingerprint. Positive absolute distances do not certify a project clearance threshold.

## B. Historic form 1 / Issue #67 / PR #66 — old PR59 SHA FAIL, NOT new SHA

Normative source: **ГОСТ Р 2.104-2023**, appendix Б.1 (form 1), §5.7 table 1 graphs (10)–(13); auxiliary graphs (30), (31), (32), (33), (35); **ГОСТ 2.304-81** font. Read as controlled by accepted normative **PR #66**, **24 PASS / 6 FAIL / 8 BLOCKED**, not as an unqualified design approval. Observed **actual PR59 form_one.py** stays pinned at `c42f7b... / blob 9025fe...`. ESKD corrections in Issue #67 are **not in this pinned OLD PR59 SHA**. For independently tested NEW HEAD, see B0 above.

| Requirement / test | Status on PINNED PR59 | Reproduced result |
|---|---|---|
| Form-one outline | **PASS** | 185×55mm, 0.7mm outer border / 0.25mm internal SVG stroke |
| Role column (10) structure | **PASS** | 17mm wide, five 5mm rows, corresponding keys `developed/checked/tech_control/norm_control/approved` |
| Cap height | **PASS in PR66 controlled OpenGost A sample; BLOCKED for arbitrary font fallback** | Controlled source reports measured Cyrillic Н cap=2.5mm, SVG em≈3.914mm; CI DejaVu Sans also calibrated at 2.5mm cap but wide `Н. контр.` fails closed `TITLE_FIELD_OVERFLOW`. Do not mistake surrogate font for approved Type A |
| Same left ink-x for Разраб./Пров./Т. контр./Н. контр./Утв. | **FAIL** | Pinned source uses `tx=(cell.min_x + cell.max_x - ink.min_x - ink.max_x)//2`: independently confirms *centered ink*, not common left inset, despite equal cells. **A measured small common inset is editorial, not mandated mm in ГОСТ** |
| Graph (10) role caption distinct from (11) surname | **FAIL (MAJOR)** | `fields={"developed":"Иванов"}` replaces fixed «Разраб.» *inside* role cell (10), x0–17mm; not graph (11). Asserted with actual fixed-code renderer |
| Graphs (11)/(12)/(13) surname/signature/date | **FAIL (MAJOR)** | No independent typed cells or write API. Empty sample is correct; inability to fill the correct cells is not |
| Auxiliary (30) dashed | **FAIL** | Exactly 25 internal grid lines and no dash metadata in source vector |
| Captions (31)/(32)/(33)/(35) | **FAIL** | «Копировал», «Формат», «Зона», «Вер.» absent in a captioned source sample |
| Geometry of (9)/(2)/(30), controlled printed 1:1, full conditional graph applicability | **BLOCKED** | PR66 already records these gaps; do not use naive pixel-overlay of a figure with dimension breaks |
| Blank draft (no fictional signatories), clean mode | **PASS** | Missing invented name/signature/date is deliberately NOT a defect; default empty fields and separate unframed clean output remain valid |

**Independent test strategy:** `tests/qa_form_one_review_test.py` checks immutable blob; compares PR66 rule codes; calls pinned `draw_form_one_geometry` and field positioning through real Pillow/FreeType, measures left insets and role overwrite; verifies known *historical failures* as **passing evidence tests**. It never inserts a failing acceptance assertion against a known broken Draft PR59 into current integration CI. This **does not mark PR59 as PASS**. One surrogate-font overflow has an explicit **positive assertion for fail-closed rejection**. For current expected corrections/approval, PAINT must supply a fresh SHA and controlled Type A SVG/PNG.

## C. Future structural Э1 — 32 reproducible contracts, implementation BLOCKED

Owners: ELEKTRIK Issue #70 (typed model), YGO Issue #71 (block graphics), ESKD Issue #69 (normative). **None of these future APIs are silently simulated as current production**, nor are functional blocks added to electrical PartDefinition/Circuit/PinRef.

**QA fixture:** `tests/fixtures/qa_structural_e1_negative_vectors.json`, **32** deterministic mutation-based scenario vectors under a common two-block / two-signal source graph. Each has an ID, textual expected outcome, tentative diagnostic *family*, precise JSON pointer edits, responsibility (`model`, `renderer`, `text_measurer`, `crossing_router`, fanout or side-spacing policy), and **project vs ГОСТ disclaimer**. Five topics:

| Threat group | Cases / expected |
|---|---|
| Invalid IDs and references | Duplicate block/port/link IDs, dangling source/target blocks or ports → REJECT |
| Port coordinates / multiple ports | Unknown side, values outside [0,1], wrong type, arbitrary side-point attachment, same-coordinate side ports, deliberately ordered multiple ports on same side allowed, dense-port packing BLOCKED pending minimum clearance policy |
| Direction and links | INPUT-as-source, OUTPUT-as-target, reversed arrowhead, backward process arrow, self-link, reverse link, multiple links on one port require explicit fanout policy |
| Shapes and text | Zero/negative dimensions, invalid 45° transform; two-/three-line overflow and clipped text require **true ink bounds** before PASS; negative page origin itself is allowed |
| Crossings and electrical isolation | Unmarked X crossing is **ACCEPT_NO_MERGE** of two functional links; forced implied electrical junction is REJECT; no creation of physical `PinRef`, electrical `Net`, or fake part catalog |

**Tests:** `tests/qa_structural_e1_contract_test.py` checks the 32 manifests are syntactically reproducible and their base two-link graph has declared and directed ports, but **does not import an E1 model** or claim to have exercised unmerged ELEKTRIK code. Final future runtime checks are **BLOCKED** until the owner exposes a stable typed `StructuralDiagram` interface and approved port clearance / text measurement contracts. A one-port midpoint at 0.5 and equal spacing of N ports are sensible editorial defaults, **not an unconditional ГОСТ rule**.

## D. Acceptance and release decision

| Criterion | QA |
|---|---|
| Current actual six-part source and L1 exact ink geometry | **PASS measured** |
| Consistent L1-to-winding visual label spacing | **FAIL editorial**; source of discrepancy established |
| PR59 form 1 geometry/cap in controlled PR66 | **PASS for supported cells** |
| PR59 *old* left alignment + signer cells / **new SHA** | **old FAIL / new PASS functional; print BLOCKED** |
| PR59 *old* auxiliary graphics and services / **new SHA** | **old FAIL / new PASS functional; print BLOCKED** |
| Future Э1 model behavior (ports, crossing, text, arrows) | **BLOCKED not merged** |
| Future Э1 QA regression vector completeness | **PASS fixture sanity only** |
| General ГОСТ/ЕСКД approval of form 1 or E1 | **BLOCKED** |
| No production edits, no merges, no changes to others' PRs | **PASS** |

**Next actions:** PAINT reports the six Issue #67 fixes implemented at NEW SHA `71ee7f0c26d2f2f41a67d9e4450aa33d265286fa`; independent Type A full-sheet artwork/1:1 print and remaining BLOCKED normative cases still require ESKD review. ELEKTRIK/YGO/ESKD should agree on E1 typed schema and provisional diagnostic classes before wiring QA vectors into functional tests. User/coordinator should decide target L1 placement based on actual routed scene and approved font, not an arbitrary numerical gap.

**CI / HEAD SHA:** appended after completing Actions on the final Draft QA branch. Follow `parallel/qa-structural-review` head and verify both Python 3.12/3.13, Ruff, pytest, catalog audit 21 DRAFT and wheel packaging. Only QA files in the diff; no production/generator modification.
