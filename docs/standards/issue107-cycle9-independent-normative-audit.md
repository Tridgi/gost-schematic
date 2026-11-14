# Cycle9 ESKD independent normative gate — TL494 / Issue #107–110

**Date:** 2026-11-15. **Coordinator:** MAIN 3. **PR:** #112 only, `parallel/standards-tl494-ugo-ground-cycle8` (Draft).  
**Frozen electrical reference:** `e695c415fdced164b0e0c39c5249d030795a0aa6`; original source is not edited by this audit.  
**Gate:** DRAFT / SOURCE-SCOPED; **0 APPROVED**. No merge, no green-print claim, no fabricated photo parity.

## 1. Source editions and exact figures inspected

A link to a standard is not a graphic approval certificate. Source figure, inferred project symbol and the **physical printer-output artwork** are distinct audit objects.

| Scope / catalog ID | Primary standard and precise locus | Scope of observed evidence | Unresolved release gate |
|---|---|---|---|
| `diode.schottky` | [ГОСТ 2.730-73, May 2002 amendments 1–4, table 4 pos9 on PDF page 3](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf#page=3), [table 5 pos9 on PDF page 4](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf#page=4) | Confirmed distinct asymmetric cathode hooks: in horizontal A-left/K-right orientation, upper bend right, lower bend left; owner original SHA `38cf0cd20b111719cb2b9b3147397346e455b231` | Actual production 0/90/180/270 + mirror/print at prescribed dimension and physical A/K wiring: BLOCKED |
| `transistor.mosfet_n_enh` | [ГОСТ 2.730-73, table 8 pos3б and 4 on PDF page 6](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf#page=6) | Confirmed distinct insulated gate, enhancement N-channel semantic class; 3b vs 4 distinguish substrate depiction/bond. Owner `0ca4a854d72ba314aca897b067477c2aca621ab5` | Owner arrow, gap, possible body contact and printed pin numbers need explicit source-image overlay; catalog's original limited PASS is **not** final shape approval |
| `capacitor.polarized`, `capacitor.fixed`, `capacitor.electrolytic` | [ГОСТ 2.728-74, May 2002 amendments 1–2, table 4 positions 1 note and 2а, PDF page 7](https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf#page=7) | Thin plates + separate '+' symbol are an accepted **graphic family**, independent of optional thick-electrode electrolytic form. C1/C2/C3/C5/C6 thin polarized and C4/C7 fixed remain **photo-mapping DRAFT** | Circuit operating voltage and polarity and printed plate widths: BLOCKED |
| `resistor.variable` | [ГОСТ 2.728-74, table 1 position 4 and notes, PDF page 2](https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf#page=2) | Arrow marks a moving contact; unused terminal may be omitted only with relevant circuit context | R5 actual wiper PinRef and resistance source trace plus SVG/print: BLOCKED |
| `inductor.ferromagnetic`, `choke.ferromagnetic` | [ГОСТ 2.723-68, official 2010 collection table 2 position 8, PDF page 6](https://docs.guap.ru/regdocs/stands/gost_2-723-68_ver-2010.pdf#page=6) | Solid ferromagnetic core above coil is distinct from dashed magnetodielectric table 2 pos5 and no-core pos1. Four turns and 2mm arc radius are project editor choices, not compulsory GOST dimensions | Actual owner renderer / photo matching of L1/L2 and printed source calibration: BLOCKED |
| `fuse.general` (not among initial 22 source cards) | [ГОСТ 2.727-68, 2010 official reprint, §4, table 3 position 2](https://www.gostrf.com/normadata/1/4294833/4294833334.pdf) | Owner file `src/gost_schematic/catalog/symbols/fuses/general.json` frozen blob `6af105eb850211b0f86e5fc7df59da28719d2e76`: 2 physical pins, one rectangle, continuous **drawn** centre segment. This segment is not permission to electrically short across the fuse in ERC | Source-to-owner ink 1:1 not measured; no source-figure PDF anchor certified in this cycle: **BLOCKED**, DRAFT |
| `net-marker.earth`, `net-marker.noiseless`, `net-marker.protective_earth`, `net-marker.chassis`, `net-marker.equipotential` | [ГОСТ 2.721-74, official 2008 reprint, table 6б pos1–5, PDF page 11](https://ohranatruda.ru/upload/iblock/328/4294852095.pdf#page=11) | Five independent ground/body/equipotential semantics. **COMMON 0V is NOT a sixth synonym for earth.** Existing illustration is DRAFT editorial dimensions, not a normative source vector | Must confirm what source physical Net is connected. No auto PE/chassis/equipotential, no auto new Part/PinRef |
| `ic.TL494CN`, internal 'PWM' | [ГОСТ 2.743-91 (2003 reprint), §2.1.6 figures 3–4 PDF page 4](https://meganorm.ru/Data/190/19085.pdf#page=4); [ГОСТ 2.759-82 §1.8 PDF page 2](https://files.stroyinf.ru/Data2/1/4294849/4294849490.pdf#page=2); [ГОСТ 2.701-2008 §5.4.4 PDF page 9](https://rosgosts.ru/file/gost/01/100/gost_2.701-2008.pdf#page=9) | Conditional alternate **whole-symbol** input/output orientation exists; manufacturer 16-pin map and body must be kept separate from independently rotating a function word | Independent PWM -90° word-only approval **BLOCKED**, although `matrix(0,-1,1,0,0,0)` is mathematically bottom-to-top in SVG page coordinates |
| Type A `2.5/3.5mm` print labels | [ГОСТ 2.304-81, official 2007 reprint, §2.1 and table 1](https://files.stroyinf.ru/Data/13/1360.pdf) | `d=h/14`: h=2.5 -> d≈0.1786mm; h=3.5 -> d=0.25mm. This is **letter stroke**, not schematic wire width | Verify genuine selected OpenGost glyph outlines, ink bbox, horizontal/vertical running text in actual 300-DPI render: BLOCKED |

**Current-status note (Russia, 2026-11-15):** The [Rosstandart registry for ГОСТ 2.304-81](https://protect.gost.ru/gost/details/2acb3258-c28c-4e4a-b7ac-208043f2d95e) says current, but has a [registered 2026 supersession notice](https://protect.gost.ru/gost/changesdetails/129283d4-ae9b-4e2e-abd0-af1627846674): after **2027-10-01**, use ГОСТ Р 2.304-2026 in RF. No automatic switch in November 2026. [ГОСТ 2.701-2008 currently in force](https://protect.gost.ru/gost/details/87f1f382-a055-48b7-ae80-f359ff5e1f4e).

## 2. Critical SOURCE-LINK defect found and corrected in the existing matrix

The previous independent test asserted only that links contained a `#page=` fragment; it **did not test that the linked PDF page contained the claimed drawing**. 12 legacy anchors were inaccurate by 1–3 pages.

| Catalog IDs / group | Previous PDF page | Correct one-based PDF page |
|---|---|---|
| Ferromagnetic inductor / choke | 5 | **6**: table 2 pos8 |
| Magnetodielectric inductor | 4 | **6**: table 2 pos5 |
| Six earth/noiseless/PE/chassis/equipotential/COMMON comparison cards | 10 | **11**: table 6б |
| Other-sheet continuation | 7 | **9**: §5.5.3 |
| Same-sheet continuation | 7 | **10**: §5.5.4 |
| `drc.clearances` 3/2/1 grouping | 7 | **8**: §5.3.4 main distances (further §5.5.1 at PDF page 9) |

Corrected in `issue107-ugo-normative-matrix.json` with per-card `cycle9_page_correction.previous_page/verified_page`. Independent frozen expected page fixture and adversarial tests in `tests/test_standards_issue107_cycle9_independent.py` ensure a reverted old link fails despite still containing `#page=`.

These corrections are **evidence-location fixes**; no source figure has become APPROVED because of a hyperlink patch.

## 3. Distances — exact applicability, printed ink, no blanket 3mm

Primary text: [ГОСТ 2.701-2008 §5.3.4 PDF pp7–8, §5.4.3–5.4.4 and §5.5.1–5.5.4 pp9–10](https://rosgosts.ru/file/gost/01/100/gost_2.701-2008.pdf#page=8).

| Classification | Hard rule / note | Correct numeric assertion | Incorrect assertion |
|---|---|---|---|
| Two adjacent **lines belonging to UGO** | ≥1.0mm clear | Compare actual visible ink edge, not centerlines | Demand 3mm on any lines inside one component |
| Two **separate UGO** | ≥2.0mm clear | Distinct symbol outlines/actual ink | Treat every orthogonal wire or touching connector as a separate UGO |
| Neighboring **parallel interconnections** | ≥3.0mm clear | For distinct parallel segment projections with positive overlap, measure centre distance minus half-widths: `g=Δ−(w1+w2)/2` | Use 3mm on every perpendicular X crossing or intentional T/junction; allow 3mm center distance for two 0.3mm strokes |
| Interconnection stroke | 0.2–1.0mm allowed, 0.3–0.4mm recommended | Actual printed output line width, source profile dependent | Declare every 0.25mm line noncompliant solely because not recommended 0.3mm |
| Whole UGO stroke | §5.4.3: same thickness as interconnection | Compare intended same strokes, not Type A text's separate `h/14` | Equate Type A glyph line thickness to required wire width |

**Examples:** Two 0.3mm parallel lines must have centres **≥3.3mm apart** for 3mm clear ink; centres 3.0mm apart leave only 2.7mm, **FAIL**. With disjoint Y projections, the specific *parallel neighbour* test does not apply. A crossing, intentional junction or collinear duplicate still needs appropriate electrical/topology review; exemption from this particular 3mm parallel test does **not** mean universal PASS. The stand-alone test's geometry is didactic negative evidence, **not** a claim that the full 91 authored segments were actually checked.

§5.5.3: cross-sheet continuation ends **without arrow** with source line name plus sheet/zone (when present). §5.5.4: interrupted within-sheet line uses **arrow(s)** and interruption reference; these are different cases, not interchangeable visual conventions.

## 4. Symbol rotation / 'PWM' function text / font

The actual [ГОСТ 2.701 §5.4.4](https://rosgosts.ru/file/gost/01/100/gost_2.701-2008.pdf#page=9) allows general UGO rotations subject to meaning/readability; specifically **UGO containing alphanumeric content** may be rotated counterclockwise 90° or 45°. This is a rule for a **whole symbol** and **does not automatically authorize an independent free rotation of one internal label**. Reference graphics [ГОСТ 2.743 §2.1.6 figs3/4](https://meganorm.ru/Data/190/19085.pdf#page=4) show alternative whole digital-UGO orientations including label layout and input/output arrangements; [ГОСТ 2.759 §1.8](https://files.stroyinf.ru/Data2/1/4294849/4294849490.pdf#page=2) separately permits inputs above, outputs below for analog UGO. These do not establish unconditional isolated `PWM -90°` acceptance. **Keep word-only -90 as PROJECT EDITORIAL / NORMATIVE BLOCKED** until direct figure/paragraph evidence and an actual render demonstrate conformity.

For normal SVG screen frame, word-only `-90°` means baseline moving bottom-to-top; this **mathematical property is PASS, not a normative approval**. Pin identities, positions, functional sections, unrotated fields, Net and PinRef must be unchanged. Evaluate all eight D4 symbol transformations plus independent function text orientation if supported. Print clean: diagnostic green hotspots **absent**; print debug: hotspots at **real exposed terminal/wire ends**, never at arbitrary body corners. Colored diagnostic squares are **not part of ГОСТ UGO**.

[ГОСТ 2.743 §2.2.1](https://meganorm.ru/Data/190/19085.pdf#page=5) **does not prescribe a 6-character upper limit** for function notation; short `FB/OC` are **project-specified display aliases**. Keep original manufacturer `FEEDBACK` and `OUTPUT CTRL` in metadata with pin numbers 3/13. If `PWM` is treated as a user-defined function label not otherwise listed in the applicable normative table, §2.2.6 requires explanation on the schematic field.

**Font:** 2.5 and 3.5mm Type A glyph height is a selectable typography profile, not a blanket mandatory minimum for every caption. The selected font needs measured *printed glyph ink* bounds, Unicode glyph coverage, baseline, stroke/advance fidelity, and legibility at 300 DPI. 300 DPI is a QA **rendering convention**, not a ГОСТ general minimum printer-resolution requirement.

## 5. Existing test audit: what genuinely passes and what did not prove anything

- **Evidence preservation PASS limited to file integrity**: original 12 symbol/coil JSONs are frozen with 40-character SHA strings; the earlier test `len(sha)==40` was **not an actual Git SHA verification**. New test independently computes the *exact Git blob header SHA1* from current owner file bytes and compares it with frozen source SHAs, requiring draft state.
- **Schottky owner-vector transform PASS limited to arithmetic**: eight D4 transforms in new test retain A/K roles and distinct signed hooked points; this **does not constitute eight production-rendered images**.
- **PDF source-linked matrix fixture PASS limited to scanned source locators**: new test verifies 12 corrected page numbers against independently reviewed printed figures; independent negative input with old page now fails.
- **Print geometry negative samples PASS limited to synthetic unit examples**: wires 3.3/3.0mm centre separation at 0.3mm stroke; and partial vs empty projected overlap. Actual owner R5/R6/DA1 full ink DRC still **BLOCKED**.
- **Text direction arithmetic PASS**: -90/0/+90 SVG baseline read directions tested; no unconditional ISO/GOST normative approval for independently rotated internal PWM.
- **Old permissive tests** checking only text fragments like `"arrow" in string`, SVG group counts, or 22 cards do not independently verify correct actual rendered line connectivity, print typeface or standard dimensions.
- **Electrically required**: confirm positive/negative polarity, no ghost contact dots, real PE/chassis source bond, D4 physical pin identity, print labels unclipped, all 23 components / 15 Net / 16 TL494 physical pins, no silent replacement of existing warnings. Existing reference has 91 *authored* wire segments, not an accepted global autorouter output.

## 6. Handoff / outcome

**Recommending to MAIN 3, YGO, PAINT, ELEKTRIK NET, QA:** load the corrected normative matrix and keep this addendum's hard-vs-editorial separation. Treat catalog figure-family checks as source-scoped `PASS`, actual source-printed 1:1, 300DPI, polarity/Net and detailed device orientation as `BLOCKED` unless source-authenticated proof arrives. `fuse.general` is now covered by a separate draft test/row in this addendum but not silently counted as card #23 in original 22-card matrix.

**No APPROVED. No merge. No edit to production `src/`, integration or main.** CI and exact HEAD are recorded separately in PR discussion after workflow verification.


## 7. Printed electrical schematic release: current edition and mandatory traceability

**Additional current Russian normative references and exact source scope (2026-11-15):**

| Concern | Source / edition | Acceptance rule | Evidence status |
|---|---|---|---|
| Electrical principle scheme contents | [ГОСТ 2.702-2011, §5.3.1](https://gostrf.com/normadata/1/4293800/4293800211.pdf), [Rosstandart current registry](https://protect.gost.ru/gost/details/d9c1c334-2a90-45cb-ac00-c31da92d706b) | Show all required electrical components, electrical connections and termination devices of incoming/outgoing chains | `BLOCKED`: 23 parts, 15 Net, 16 IC PinRefs / 91 original authored route segments are frozen, **not** a physical schematic acceptance |
| Graphic symbol specificity | ГОСТ 2.702-2011 §5.3.4 | Use established ESKD UGO; if standard UGO does not exist, show developed UGO plus explanation on scheme | `BLOCKED`: 36 catalog symbols remain draft, per-symbol printed source overlay absent |
| Reference designators | ГОСТ 2.702-2011 §§5.3.7–5.3.11 | Unique positional labels under ГОСТ 2.710; number in each class; default ordering top-bottom and left-right with stated exceptions; put next to UGO **above or to the right**, or permitted inside rectangle | `BLOCKED`: automatic actual SVG layout and clean print label inspection required. Do not claim random nearby text positions are normative. |
| Traceable parts list | ГОСТ 2.702-2011 §5.3.18 | Each depicted element/device must be identified unambiguously, either list on first sheet or separate E3 list as allowed in its subclauses | `BLOCKED`: compare generated named list, all 23 source elements and printed reference names; do not silently drop FU1 or other parts |
| Main title block for RF | [ГОСТ Р 2.104-2023 (in force from 2024-03-01)](https://protect.gost.ru/gost/details/69d422a2-3c0e-4561-a521-0c99f9cf4417), [ГОСТ 2.104-2006 now expired in RF](https://protect.gost.ru/gost/details/53cdd9bb-5de1-4f45-a6e9-17cd681e4abd) | Printable machine-building formal ESKD page has a conformant main title block and supplementary fields; do **not** default silently to superseded 2006 Russian practice | `BLOCKED`: actual physical PDF/SVG frame and title-block template not validated against the **current** rule |
| Sheet formats | [ГОСТ 2.301-68](https://protect.gost.ru/gost/details/aa681f87-ff49-4115-ad25-169e15d2af06) current; [ГОСТ Р 2.301-2026](https://protect.gost.ru/gost/details/ca4c6e2d-fcde-4d46-b851-b0cbd10a7e53) adopted **effective 2027-10-01**, earlier voluntary use permitted | Match actual paper format to declared format, preserve true mm dimensions/fit, printer margins/frames; **A3 is not mandatory for every electric scheme** | `BLOCKED`: no demonstrated true-sheet 1:1 exported PDF fit test |
| Print typography | ГОСТ 2.304-81 (for this 2026 Russian cycle), project Type A h=2.5/3.5 as chosen | Use genuine outlined/typeface metrics; text not clipped/overlap; width h/14 for Type A is not wire width | `BLOCKED`: font-installed exact 300DPI capture with glyph ink bbox is missing |
| Rasterization | Project QA convention, not a blanket ГОСТ 2.702 print DPI clause | SVG/PDF physical unit print dims and any PNG 300DPI 11.811px/mm. Diagnostic green squares **only on debug** | `BLOCKED`: actual owner full clean+debug exported at true 300DPI and compared to original |

**Revision trap:** `ГОСТ Р 2.104-2023` supersedes previous `ГОСТ 2.104-2006` on the **territory of the Russian Federation**, effective 2024-03-01. `ГОСТ Р 2.301-2026` is registered but not yet mandatory in November 2026 (effective 2027-10-01, earlier application allowed). Never choose an edition solely from the largest year number; keep jurisdiction/date explicit.

**QA expected false negatives (must not be treated as PASS):** glyph shape checks cannot substitute real printed page checks; a page labelled `A3` without correct physical dimension/font/title block is not accepted; an element list with 23 strings but wrong terminals or missing fuse semantics is not correct; and current 91 hand-authored route segments with no wire-to-wire ink DRC cannot be called autorouted or print conformant.

**Primary PDF visual review limitation:** publicly accessible textual clause locations are source-verified, but independent automated vector-to-scanned-figure calibrated 1:1 and complete printed primary-source comparison is still blocked. A PDF fetch/screenshot error is not evidence of an absent rule or a PASS.
