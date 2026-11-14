# ESKD #107 / #108 / #109 / #110 — independent normative TL494 E3 source gate

**Date:** 2026-11-14. **Separate documentation branch:** `parallel/standards-tl494-ugo-ground-cycle8`, created from current `integration/stage0-12` at `afd359cf2c63337471e746e5ff7f399b76394612` with no production `src/` changes. Historical accepted #95/#101/#104 remain untouched. **Normative UGO approval: ZERO; DRAFT only.**

**Primary drawing originals (not copies):** [ГОСТ 2.730-73 original May 2002 with changes №1–4, PDF table4 p3 + table5 p4 + table7/8 pp5–7](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf); [ГОСТ 2.728-74 official 2002 with changes №1–2, printed table4 at PDF page7](https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf#page=7); [ГОСТ 2.723-68 official collection 2010 incl changes №1–3, table1 p5 and table2 p6](https://docs.guap.ru/regdocs/stands/gost_2-723-68_ver-2010.pdf#page=6); [ГОСТ 2.721-74 official 2008, table6б page11/12 (earth etc), table6в pp12–13](https://ohranatruda.ru/upload/iblock/328/4294852095.pdf#page=11); [ГОСТ 2.701-2008, §§5.3.4,5.4,5.5.1–5.5.4 and 5.6.2, PDF page7–8](https://rosgosts.ru/file/gost/01/100/gost_2.701-2008.pdf#page=8); [ГОСТ 2.743-91 §2.1.6 fig3/4 and §2.2.6](https://meganorm.ru/Data/190/19085.pdf#page=4); [ГОСТ 2.759-82 §1.1 and §1.8 analog fields](https://files.stroyinf.ru/Data2/1/4294849/4294849490.pdf#page=2). [TL494 manufacturer pin inventory — TI 2026 Rev.J, figure4-1 and table4-1](https://www.ti.com/lit/ds/symlink/tl494.pdf#page=3).

**Systematic evidence:** [21 exact normative cards](issue107-ugo-normative-matrix.json) with standard edition/table/position/printed figure URL, normative vs project geometry, positive/negative and separate statuses; [12 source-pinned production-catalog DRAFT owner snapshots](issue107-ugo-source-snapshots.json), [Schottky exact 1:1 owner JSON D4 paper-mm gallery](evidence/issue107-schottky-d4-owner-1to1.svg) and [12 UGO gallery](evidence/issue107-catalog-12-draft-source-gallery.svg). These SVGs are **independent vector renderings of PINNED project JSON**, NOT bitmap copies of the copyrighted primary standards and NOT a certified source-to-target original 1:1 overlay. Coil examples are marked `EDITORIAL_PROFILE_ONLY_NOT_OWNER_RENDERER_OUTPUT`; the true catalog inductor winding-profile drawing must separately be visually proved.

**Freeze:** integration pin `afd359...`; reference `reference/tl494-native-rework-20261114` HEAD `e695c415fdced164b0e0c39c5249d030795a0aa6`; actual [reference manifest](https://github.com/Tridgi/gost-schematic/blob/reference/tl494-native-rework-20261114/examples/tl494_named_truth_output/TL494_named_photo_manifest.json) blob `b2375feb43ad18b8a8e5a515bfc007d169b26908`. Reference 23 distinct parts, 15 Circuit.Net, 16 connected DA1 physical pins, 91 authored wires, DRAFT, not electrically verified; two *expected* (not silently absent) continuation diagnostics `WIRE_NET_DISCONNECTED` and `WIRE_DANGLING_END` for split `b` and no objective full stroke-aware clearance proof. Original user's image pair is **not present as a certified stable blob in this docs branch**; independent source photograph comparison marked BLOCKED, do not infer polarity/ground via diagram conventions or replace unknown source with an editorial picture.

## 1. Schottky cathode, asymmetric evidence and true 90° rotation (P0)

**Ground truth original:** ГОСТ 2.730-73 **table 4 position 9** shows the Schottky effect graphic; **table 5 position 9** uses that graphic on the DIODE'S CATHODE, while position 1 is the ordinary diode. [Direct original drawing table5/9 (PDF page 4)](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf#page=4). The original has the ANODE LEFT and CATHODE RIGHT. The *upper* extension of the cathode vertical stroke **goes to the RIGHT** then bends **DOWN**. The *lower* extension goes **LEFT** then bends **DOWN**. The hooks are **not mirror symmetric** about the diode axis; preserve exact chirality, number of corners, and signed position under a pure 90° geometric rotation. **DO NOT symmetrize visually** or replace with ordinary Zener bar.

**Independently read actual catalog JSON** `src/gost_schematic/catalog/symbols/diodes/schottky.json` Git blob `38cf0cd20b111719cb2b9b3147397346e455b231`: in mm, central cathode x=+2.5, A=(-10,0), K=(+10,0), stem y=-3.3..+3.3. Upper hook `(2.5,-3.3)→(4.2,-3.3)→(4.2,-1.8)`; lower hook `(2.5,+3.3)→(0.8,+3.3)→(0.8,+4.8)`. The **absolute lengths 1.7/1.5mm, stroke 0.3mm, extents and lead lengths are PROJECT-EDITORIAL**, not numerically specified by table5/9.

For **rotated 90° on paper with standard SVG screen y increasing downward**:
```
R90_screen_clockwise(x, y) = (-y, x)
A=(-10,0) -> (0,-10) [TOP]
K=(+10,0) -> (0,+10) [BOTTOM]
upper-hook: (3.3,2.5) -> (3.3,4.2) -> (1.8,4.2)
lower-hook: (-3.3,2.5) -> (-3.3,0.8) -> (-4.8,0.8)
```
Thus in the frozen TL494 ref claim **VD1 A TOP, K BOTTOM** is arithmetically consistent with rotating the original A-left/K-right glyph 90° screen-clockwise, **but is not proof that the photographed circuit physically works**; manufacturer 1N5822 A/K and electrical operating conditions need source evidence. `R90` must apply to **all** primitives, terminals and annotations coherently, with provenance. R180/R270 preserve origin and swap appropriate A/K coordinates, D4 mirrors require separately documented source allowance and meaning. FAIL: rotate glyph but not PinRef, mirrored hooks with no approved transform, K at top while model still claims K bottom, making the two hooks symmetric after rotation. **PASS source shape orientation only; full norm 1:1 measurements from printed PDF BLOCKED**.

## 2. Capacitors — two different valid normative depictions (P1)

[ГОСТ 2.728-74 original TABLE 4, PDF p7](https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf#page=7):
- **Table 4 position 1 and its immediately adjacent NOTE**: fixed capacitance with **two THIN parallel plates**; when polarization must be conveyed, **the + marking near the actual positive plate**. This is fully source-supported and **must remain `capacitor.polarized` for photo-selected C1/C2/C3/C5/C6**.
- **Table 4 position 2а**: separate **polar electrolytic capacitor with the double/thick outlined electrodes**, marked + (note allows omitting only when no misunderstanding); position 2б is NONPOLAR electrolytic without +. This is also a real normative alternative, but **is NOT automatically the source-photograph chosen C1/C2/etc**. Do not infer "electrolytic chemistry" solely from actual polarity or thickness.
- `capacitor.fixed` tab4 pos1 remains C4/C7 unpolarized. `capacitor.polarized` current source blob `ba14a82d52696f8ffb8f89344c39b153374ffaa0`, `capacitor.electrolytic` blob `8094edd30765c502c3474d75724e543da6bcb211`, and `capacitor.fixed` blob `3e173b1cd52120f4cedd26e0f43348864119ec47`.
- Absolute gaps, electrode lengths, ink stroke and + placement measured from DRAFT JSON **are not universal standard dimensions**; printed source table6 positions and separate profile 1:1 must be reviewed. **Polarity is electrical claim**: reference manifest lists `POLARITY_UNVERIFIABLE` for all five C1/C2/C3/C5/C6 because no computed node potentials were provided; matching the photo's "+" symbol is **graphic source PASS only, not electrically correct voltage/polarity**. Don't auto-flip + as an artistic selection or silently change the underlying capacitor's actual + pin.

**Explicit acceptance:** lookup source photo by BOM item and exact photo orientation; select thin+ C1,C2,C3,C5,C6 and no+ fixed C4,C7. Reject all thick-electrolytic substitution for those selected positions. Thick electrolitic family remains DRAFT catalog supported by table4/2a, not prohibited globally.

## 3. Coil and choke cores (P0)

[ГОСТ 2.723-68 official 2010 printed table1 and table2, PDF pp5–6](https://docs.guap.ru/regdocs/stands/gost_2-723-68_ver-2010.pdf#page=6):
- Table **1 position 1** supplies winding half-loop; number of semi-circles and direction of terminals are **not fixed by the standard**.
- Table **1 position 2a**: **ferromagnetic magnetic core indicated by a SOLID bar** parallel to winding; **table 2 position 8** shows a **choke with ferromagnetic core**; the photo's L1/L2 were described as this form. Current `inductor.ferromagnetic` profile `turns=4, radius=2mm, lead=4mm, stroke=.3mm` source blob `d1030f7b79778b3ecb69135db2a6c59c10b86c66` is a **catalog choice** not a numeric GOST requirement.
- Table **1 position 2б**: air-gap core has deliberate gap; **2в** magnetic dielectric uses **DASHED** bars; ferrite/subtype may use source-defined heavy ink; these types are NOT interchangeable for source-fidelity. `inductor.air_core` fails source photo L1/L2 when photo clearly shows core.
- Magnetic core line is **not a physical electrical third pin** and must not attach to any `Circuit.Net` merely because of graphic intersection.

**Gate:** 2 true physical contacts, solid bar on appropriate side, 1:1 actual owner winding renderer with line weights source-independent paper metrics. D4 rotates both coil and core together. Original source dimensions not reconstructed from a scan.

## 4. Common 0V vs chassis vs earth vs protective earth (P2 / #109)

[ГОСТ 2.721-74 TABLE 6б, PDF page11 (printed С.10)](https://ohranatruda.ru/upload/iblock/328/4294852095.pdf#page=11), separately picture-verified:
- **Табл.6б поз.1:** *заземление, общее обозначение* (three gradually shorter horizontal lines). Despite translation "general ground", this is **a depiction of grounding**, not a universal proof that any arbitrary 0V conductor is actually grounded. Model `COMMON` is merely a named circuit network, may be a **floating reference**, entirely no Earth/PE connection.
- **Табл.6б поз.2:** noiseless/clean ground, distinct extra semicircular contour.
- **Табл.6б поз.3:** **защитное заземление** is ground glyph inside a **CIRCLE**, applicable when actual PE exists (not every "GND" terminal).
- **Табл.6б поз.4:** connection to chassis/mass (hatched-base / T variants), distinct from earth generic.
- **Табл.6б поз.5:** equipotential bonding, distinct triangular/marker variants, not a synonym for earth physical terminal.
- A net marker is a **visual reference to one confirmed existing `Circuit.Net` and an exact anchored source point**, not a physical component with new `PinRef`, not a conductor, and not a reason to merge distinct Nets. Different marker profiles are **mutually semantically distinct**, regardless of superficial shapes. A physical PE/chassis terminal only exists in the PartDefinition when the actual manufactured device/contact is verified.
- Reference photo and connected named graph source **COMMON** with **DA1.7, X1.2, X2.2, R6.2...**. This is evidence for same **0V Net identity**, NOT an independent proof of protective earth bond. Consequently issue #109 `net-marker.common/0V` is **BLOCKED for applying earth graphic without explicit source bond evidence** and is **PASS as an optional textual COMMON / 0V net label** if the topology is unchanged. `net-marker.chassis`, `net-marker.earth`, `net-marker.protective_earth` are valid source families **only for independently verified wiring**.

**Negatives:** (1) duplicate a new PE Net from a symbol, (2) short COMMON to chassis or PE by matching glyph labels, (3) place a PE mark on DA1.7 purely because TI calls pin7 GND, (4) equate common circuit line with electrical-to-case lead. **All prohibited.**

## 5. Dimensions, wire DRC and 1:1 signoff (P3 / #108)

[ГОСТ 2.701-2008 original §5.3.4 and §§5.5.1–5.5.4](https://rosgosts.ru/file/gost/01/100/gost_2.701-2008.pdf#page=7):
| Type of requirement | Exact figure | Status |
|---|---|---|
| Space between neighboring UGO graphic strokes | **≥1.0 mm** | **mandatory** 5.3.4 |
| Distance between separate UGO | **≥2.0 mm** | **mandatory** 5.3.4 |
| **Separate adjacent parallel interconnection lines** clear gap | **≥3.0 mm** | **mandatory** 5.3.4; do not apply as a blanket rule to true same-net T joins or nonparallel X crossing |
| Interconnection line stroke | **0.2–1.0 mm** | **mandatory interval** 5.5.1 |
| Recommended interconnection stroke | **0.3–0.4 mm** | recommendation 5.5.1, **NOT independent mandatory width** |
| Route | H/V and minimum kinks/crossings | 5.5.2 mandatory design objective; limited inclined segments allowed |
| Across sheet/document continuation | **break with NO arrows** and own name/id + `(sheet,zone)` address/document | §5.5.3 exact scope |
| Within one sheet interrupted line | may be interrupted **with arrow** and destination details | §5.5.4 explicit exception, not contradictory with 5.5.3 |
| UGO with alphanumerics | source direction and permitted whole-symbol rotation counter-clockwise 90°/45° within §5.4 | only a whole UGO rule, **not** generic independent internal-PWM text rotation approval |
| Annotation and keepout 2.5/3.5mm, default h, label limit 6 | no universal 6-glyph limit | font in proper ГОСТ 2.304; guard/insets are editorial |
| Quantized coordinates | integer micrometers, D4 | **project design**, not a GOST dimension |

**Gap is a true ink-stroke clear spacing**, not just the distance between path centerlines; for two parallel 0.3mm strokes center-to-center ≥3.3mm is needed to leave 3.0mm edge-to-edge. One shared intentional T on the same Net is not a false 3mm violation; opposite-net near-parallel segments and crossings must remain semantically disconnected unless explicitly joined. At 300DPI a 3mm true paper gap is ~35.43px; 1px white ≠ 3mm. For user R5/R6 and DA1 near-parallel lines **actual source owner DRC not run in this ESKD branch**; **BLOCKED until owner records numeric pairwise min_clearance with wire IDs and net IDs**. Existing reference renderer `strict_layout=False` and net validation are not routing DRC.

**Important correction to earlier simplistic intersheet-address opinions:** ГОСТ 2.701 **§5.5.3 itself explicitly prescribes sheet and zone in parentheses for inter-sheet lines**. ГОСТ 2.709-89 §5.14 reciprocally refers to *physical opposite element/device/group connection* as another, separately scoped representation. Do not wrongly mark a genuine `(5,А6)` sheet-zone address as per se illegal: context (§5.5.3 vs §5.5.4 vs §5.14) and actual printed connection details decide.

## 6. Portrait PWM bottom→top and TL494 abbreviations (#110)

**TI original [TL494 Rev.J 2026 page3, Figure4-1 and Table4-1](https://www.ti.com/lit/ds/symlink/tl494.pdf#page=3):** 16 source pins in order 1 1IN+, 2 1IN−, 3 FEEDBACK, 4 DTC, 5 CT, 6 RT, 7 GND, 8 C1, 9 E1, 10 E2, 11 C2, 12 VCC, 13 OUTPUT CTRL, 14 REF, 15 2IN−, 16 2IN+. These are **manufacturer pin-function labels and chip package map**, not automatically GOST 2.743 approved functional symbols. No numbering may change for convenience.

**Project-specific <=6 visible chars**: `FEEDBACK→FB`, `OUTPUT CTRL→OC`; preserve original manufacturer function text in immutable metadata, prohibit `[:6]` automatic truncation and collisions. `FB/OC` are *editorial defined abbreviations*, not hard character limits of ГОСТ 2.743; ГОСТ 2.701 §5.6.2 does not give blanket permission for unlisted abbreviation words, so define selected aliases in drawing legend or project profile. `C1/C2` pin names must remain namespace-separated from capacitors with same refdes; actual `PinRef("DA1","8/11")` and `capacitor C1/C2` cannot collapse by string equality.

**Portrait PWM bottom-to-top visual orientation**: for a default portrait IC with page coordinate y increasing downward, **the horizontal text baseline after `rotate(-90°)` runs bottom→top**. `rotate(+90°)` moves the word top→bottom. Use explicit signed orientation/semantic `bottom_to_top` not ambiguous unsigned `90`; with screen transform, `matrix(0,-1,1,0,0,0)` has baseline vector (0,-1). *The body, pins, all 16 physical numbers, other field labels, Circuit.Net and external wire Point must stay IDENTICAL.* Verify all 8 D4 physical placements; rotation/mirror of the **whole UGO** changes page-frame glyph axes and requires actual 300DPI QA reading test, no guess from JavaScript angle sign alone. `GOСТ 2.743-91 §2.1.6 fig3` permits specific alternative whole UGO composition and not universal rotation-only function. Source-general **0° CONDITIONAL PASS**, independent -90° **EDITOR DRAFT / GOST BLOCKED**; not elevate on technical PAINT green CI.

**Release and owner handoff:** production symbol fixes/real owner PNG, routing DRC, image/photo side-by-side, 0 physical Net mutation, user chosen ground marker, actual source scale, font metrics, manufacturer pin map/signals all require independently pinned owner HEAD and QA. A green isolated docs CI supports only the checks as written. No production code/main/merge.
