# Cycle 7 / Issue #89: E3 discrete components — first independently reviewable batch

**Status: DRAFT, NOT APPROVED.** Work branch: `parallel/catalog-electronic-cycle7`. Parent: #86. First batch is deliberately 3 symbols, not an unsupported claim of a complete semiconductor library. Existing 21 DRAFT and E1 #78 are untouched.

## Primary source-backed visual choices

| New ID | Official source | Specific printed figure | Real graphical/physical pins | Editorial dimensions |
| --- | --- | --- | --- | --- |
| `resistor.variable` | ГОСТ 2.728-74 | Table 1, item **4**, PDF p.3; table 6 item 3, PDF p.20 | 1=A, 2=B, 3=W (wiper has **real separate lead and pin**) | Resistor 10 × 4 mm, horizontal, top wiper 9 mm, 0.3 mm stroke; no signed overlay |
| `resistor.trimmer` | ГОСТ 2.728-74 | Table 1 item **9**, PDF p.6; table 6 item 5, PDF p.20 | 1=A, 2=B, 3=W (upper elbow terminal) | Resistor 10 × 4 mm, elbow contact at (0,-5) to (9,-5), 0.3 mm stroke; review-only |
| `fuse.general` | ГОСТ 2.727-68 | §4, table 3, item **2**, PDF p.3 (general melting fuse) | 1=A, 2=B | Horizontal D4 equivalent of printed vertical rectangle + axial line; 8 × 4 mm editorial body and 0.3 mm stroke |

Primary official standards: [2.728-74](https://protect.gost.ru/gost/details/ba115ccd-e5aa-4ba1-a672-b17170f1a7f2) and [2.727-68](https://protect.gost.ru/gost/details/60ad0e53-944d-4bd4-bcc2-af8d934abc49). Scans for detailed figure/table inspection: [2.728-74 PDF](https://prikladmeh.ru/Standart/2.728-74.pdf#page=3), [2.727-68 PDF](https://www.nuvis.com.ua/GOST_2.727-68_ESKD.pdf#page=3). The vector dimensions listed as editorial are **not** claimed to be normative. All 1/2/3 pins are **abstract catalogue numbers**; physical IC/resistor/fuse manufacturer pin assignment is impossible without a vendor datasheet. Distinct electrical-role labels A/B/W are independent of manufacturer package numbers.

The visual arrow on `resistor.variable` terminates in a **third conductor island W** and is not a decorative free-standing slash. The `resistor.trimmer` variant uses the separate adjustment elbow instead of an ordinary potentiometer arrow, following table 1 item 9. A rheostat connection is **not a new two-pin physical part**: `Circuit.Net("RHEOSTAT_TIED_END", (PinRef("R4","1"),PinRef("R4","3")))` is one of several legal wiring choices; terminal 3 remains in `PartDefinition`. The painted fuse axial segment is the internal symbol sign and is **not indexed as a conductor** joining left/right pins, thus cannot create a false zero-ohm net.

## Visual assets and regression

Run `python -m examples.review_electronic_cycle7 --output-dir output/cycle7-first-batch` to generate six vector SVG files, 3 physical pin mapping reports, SHA-256 of source/part/SVG in a deterministic `manifest.json`. CI rasterizes each clean/diagnostic SVG using `rsvg-convert --dpi-x 300 --dpi-y 300` and verifies the output pixel size from SVG physical mm. Every ID has independently reviewable DRAFT physical part, conductive topology, SVG visual and 8 D4 transform tests, negative fabricated physical pin and bridge tests, real `Circuit.Net` examples, wheel payload and dynamic catalog audit. The independent ESKD signed 1:1 normative KOMPAS comparison is **not delivered**.

## Next batches, not silently implemented

Prioritized separate packages follow the machine-readable [Cycle7 source cards](electronic-cycle7-first-batch-cards.json): (1) `diode.schottky/led/photodiode/varicap` with distinct cathode and non-conducting optical arrows; (2) `transistor.bjt_pnp/npn`, `mosfet_n_enh/p_enh`, but plain NPN graphic MUST be independently confirmed to avoid confusing table 7/1b **shielded** device from Issue #27; (3) remaining diode/transistor/JFET/SCR/triac/opto variants only after cards; (4) special fuses per table 3/3a–c; (5) physical XP/XS connector pairs only after #91 verification. These steps do not introduce new generic shape primitives or public APIs without an RFC.

**Normative status:** 3 NEW DRAFT, baseline 21 DRAFT = 24 review records after CI. No APPROVED, no E1 changes, no merge.


## Дополнение после расширения (Cycle 7)

Первый пакет из трёх УГО остаётся исходным содержимым PR #94, а не отдельной веткой. В сводную галерею включены 15 новых УГО. У `resistor.trimmer` редакторская защита текстовой области расширена до `body_keepout_mm.min_y=-9` мм: реальная геометрия резистора по-прежнему 10×4 мм, движок W остаётся отдельным третьим физическим контактом, а новая охранная область **не является размером корпуса**. Два реостатных подключения через реальные `Circuit.Net` A↔W и B↔W подтверждены регрессионными проверками.
