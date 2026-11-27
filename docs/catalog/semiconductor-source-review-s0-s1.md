# Semiconductor source review — S0 / S1

Baseline: 9116198, 112 DRAFT symbols, 6 diodes and 8 transistors. User reference batch 2026-11-27, 20 sheets in upload order. Primary reference: ГОСТ 2.730-73, [PDF](https://files.stroyinf.ru/Data2/1/4294848/4294848038.pdf), changes 1–4, inspected rendered tables 1, 4–12; the user crops are reference artwork, not normative evidence. Do not copy unverified foreign glyphs into GOST profiles. No redundant rotated/mirrored IDs; configurable lead layout preserves physical terminal identities and never creates conductive bridges. No new symbols in S1.

| Photo | Source identification and decisions |
|---|---|
| 1 | Cathode primitive marks; general, tunnel, backward, unilateral and bilateral Zener, thermoelectric, varicap, Schottky, two angled-cathode alternate forms (not table 4); LED and photodiode four orientations each; ordinary bridge and Schottky-style bridge variant. Table 4, 5, 9, 12. Prioritize base diode revisions, bilateral Zener and ordinary bridge; tunnel/backward and thermo optional. Angled forms require independent source. |
| 2 | Split optocoupler emitter (table 10 note), unexplained vertical arrow crossing diode (unverified), photobattery, photocell (table 9), battery and cell (separate source family). |
| 3 | Split optical receivers: phototransistor without/with base, photoresistor, photodiode; combined phototransistor coupler without base. Table 9/10. Use combined 4-pin optocoupler first. |
| 4 | Lamp (2.732-68), combined optotransistor with base, optotriac (modern extension not certified exact table 10). |
| 5 | Circle plus/minus and arrow source variants GV/GI; not semiconductor parts. Compare 2.721-74 ideal source symbols, do not claim these exact shapes as GOST. |
| 6 | Zero-cross optotriac ZCC; optional feature or explicit symbol later, not ordinary optotriac with invented extra contacts. |
| 7 | Left top-down: reverse-blocking dinistor, reverse-conducting dinistor, symmetric dinistor, general triode thyristor, anode gate SCR, cathode gate SCR. Middle: turn-off anode and cathode gate, reverse-conducting anode and cathode gate, triac. Right: two tetrode gate arrangements and another triac. Table 6. Prioritize SCR cathode, DIAC, TRIAC, GTO cathode; defer rare variants. |
| 8 | Symmetric dinistor and triac alternative orientations/layouts, not extra parts. |
| 9 | NPN in case with B/C/E labels. |
| 10 | NPN/PNP with and without case; four combinations of collector/emitter exit directions; keep identities even when emitter is at top. |
| 11–12 | Insulated-gate bipolar-looking diagrams; source 12 places arrow on branch labeled C and both use B instead of G. Do not certify channel or terminal mapping before independent IGBT reference. |
| 13–14 | N/P enhancement MOSFET with and without case, three pins, drawn substrate tied to S; four lead styles each. |
| 15 | N/P MOSFET with explicitly drawn parallel intrinsic diode; four lead styles. Do not model body diode as ideal short, Zener or Schottky without device evidence. |
| 16 | N/P depletion-type MOSFET, case, continuous channel, three pins. |
| 17 | N/P depletion-type MOSFET, case, independent body terminal, four pins. |
| 18 | Same depletion family without case: N/P, 3/4 pins, four lead styles each. |
| 19 | N/P JFET, case optional, four lead arrangements each. |
| 20 | N-base and P-base unijunction transistor, two arrangements each, terminal legends and a composite MOSFET/resistor/diode circuit, not another atomic component. |
 
S1: port reviewed PR #149 (dce42d2) diode artwork and tests into this branch; preserve current cycle7 diagnostics, fix eight stale D4 stroke-count assertions in test_diode_cycle4_transformed_svg.py. All six retain A/K terminal coordinates, independent conductor islands, current protection, revision 2. For varicap the drawn centre axis stops at the first plate. Source/crop archive was prepared separately in chat; not committed binary references. CI required. S2: common useful diode additions and bridge. S3: thyristors. S4: transistor parametric geometry, stable B/C/E and G/D/S/BODY roles, optional case and independent lead direction; protect all strokes and maintain optical arrow orientation by dedicated profile logic. S5: opto and sources. S6: native clean/diagnostic/protection views, source vs render visual acceptance. No automatic normative approval or Windows GUI claim.
