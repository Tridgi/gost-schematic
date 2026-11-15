# YGO 2 / Issue #89 / Epic #107 — TL494 true UGO selection & normative review

**Scope:** 13 source-linked positions, existing 36 DRAFT catalog untouched. Base integration SHA `afd359cf2c63337471e746e5ff7f399b76394612`; reference photo implementation branch `reference/tl494-native-rework-20261114` SHA `e695c415fdced164b0e0c39c5249d030795a0aa6`. PR #105 XP/XS remains a separate and untouched branch. This is a DRAFT source fidelity gate, NOT a certified 1:1 original picture match.

## Directly inspected primary normative figures

- [ГОСТ 2.730-73, table 4 pos.9 Schottky effect and table 5 pos.9 diode](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf#page=4): 2002 edition (amendments 1–4). Original cathode **asymmetric**: on local y-down page, upper hook extends toward +x, lower toward -x; ends lie on different x-sides. Existing native `diode.schottky` has ten line primitives. Difference from `diode.general` consists of **four** extra line segments forming **two** bends. No cosmetic resymmetrization. Absolute coordinates are editorial mm, source crop is not independently calibrated.
- Canonical Schottky extra strokes in integer µm: `(2500,-3300)→(4200,-3300)`; `(4200,-3300)→(4200,-1800)`; `(2500,3300)→(800,3300)`; `(800,3300)→(800,4800)`. Anode `1/A=(-10000,0)` and cathode `2/K=(10000,0)` independently conductive until actual Circuit.Net.
- **VD1 in working TL494**: clockwise D4 90° on y-down coordinates transforms A to `(0,-10000)` and K to `(0,10000)`, i.e. A on **upper** wire, K on **lower** wire. Reference stage netlist assigns A to TRANSFER and K to COMMON. This is a verified code-to-photo-reference **model/pose**, but electrical operating correctness and precise original-photo pixel match are **BLOCKED**.
- [ГОСТ 2.730-73 table 7 pos.1a PNP / 1б shielded NPN; table 8 pos.3б N-channel enhancement MOS](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf#page=6): no false assertion that a generic 3-pin NPN exactly matches screened NPN table 7/1б. Optional schematic case ring does not imply SOT/TO mechanical footprint or physical fourth pin. MOS G left `(-11000,0)`, D above `(0,-18000)`, S below `(0,11000)`, isolated gate at x=-4000, enhancement channel split between y=-1000 and +1000, N arrow toward negative x. Source working reference adds a **photo-specific** 250µm graphical dot at `(0,5000)` where two source-side ink strokes meet; no new PhysicalPin, no implied vendor body tie.
- [ГОСТ 2.728-74 table 4 pos.1 NOTE / pos.2a](https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf#page=7): pos.1 note shows thin-plate polarized capacitor with **+**; pos.2a is the separately available *electrolytic* heavy-plate variant. C1/C2/C3/C5/C6 **must** be `capacitor.polarized`, and C4/C7 **must** be `capacitor.fixed` (table4/1 base) in THIS reference. Generic part family cannot substitute an alternative figure.
- [ГОСТ 2.723-68 table 1 parts1/2а + table 2 pos.8](https://vkopilke.narod.ru/file68.pdf#page=3): L1 and L2 from `inductor.ferromagnetic` have 4 true semicircle primitives and a separate nonconductive `StyledLine` core. Ordinary `inductor.air_core` fails source profile. Actual numeric lobe dimensions are editorial. No phantom core net.
- [ГОСТ 2.727-68 table 3 pos.2](https://www.nuvis.com.ua/GOST_2.727-68_ESKD.pdf#page=3): FU1 has two independent physical terminal islands; no zero-ohm bypass net.
- [ГОСТ 2.728-74 table 1 pos.4](https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf#page=2): R5 keeps a real third WIPER contact. Shorting W to end 1 is a Circuit.Net decision, never a JSON pin deletion.

## Exact working-reference selection (no refactoring of production catalog)

| Reference | Locked SymbolDefinition | D4 clockwise | PinRef | Normative certification |
|---|---|---:|---|---|
| VD1 | `diode.schottky` | 90° | VD1.1=A; VD1.2=K | BLOCKED independent 1:1 |
| VT1 | `transistor.mosfet_n_enh` | 0° | VT1.1=G; VT1.2=D; VT1.3=S | BLOCKED vendor/1:1; circle only photo-specific |
| C1,C2 | `capacitor.polarized` | 0° | 1=PLUS; 2=MINUS | BLOCKED 1:1 |
| C3 | `capacitor.polarized` | 90° | 1=PLUS; 2=MINUS | BLOCKED 1:1 |
| C4 | `capacitor.fixed` | 0° | 1=A; 2=B | BLOCKED 1:1 |
| C5,C6 | `capacitor.polarized` | 270° | 1=PLUS bottom; 2=MINUS top | BLOCKED 1:1 |
| C7 | `capacitor.fixed` | 90° | 1=A; 2=B | BLOCKED 1:1 |
| L1,L2 | `inductor.ferromagnetic` | 0° | 1=START; 2=END | BLOCKED 1:1 |
| FU1 | `fuse.general` | 0° | 1=A; 2=B | BLOCKED 1:1 |
| R5 | `resistor.variable` | 90° | 1=A; 2=B; 3=W | BLOCKED 1:1 |

## Reviewer gallery and what is *not* shown

`python -m examples.review_tl494_ugo_source_cycle9 --output-dir output/tl494-cycle9` exports **13 real source-pose closeups in clean and diagnostic SVG**, 64 all-8-D4 clean samples for eight semiconductor base/case variants, and 2 combined 13-position vector sheets: 92 true SVG files, plus corresponding 92 raster PNG @300DPI in workflow. Each physical PinRef is listed in manifest, true source-local point coordinates and transformed pose. Clean SVG has no green squares. Source-specific extra VT1 dot is clearly marked DRAFT.

`output/tl494-cycle9/index.html` is a two-column review interface: left **direct link to the actual primary normative PDF table/page**, right the engine-generated source-pose PNG. **It does NOT embed original copyrighted scan pixels nor pretend a redrawn source figure is an original.** Without original user photo bytes and independently calibrated printed crop/nominal dimensions, a literal visual 1:1 overlay is *BLOCKED*. The project Issue #107 explicitly says the actual latest user's third screenshot was inaccessible when the reference branch was made.

Tests: source-SHA pinning; 13 exact component ID/pose and physical endpoints; wrong-selected capacitors, coils, VD1/VТ1/R5/FU1 negative; opposite Schottky hook math and D4; BJT NPN/PNP arrow and schematic-circle guard; MOS 3-port isolated gate, arrow and local source dot; actual magnetic core; clean SVG no editor target; wheel includes source profile. No source photo net semantics rewritten; no main/merge.

## Release decision

- **PASS required:** explicit profile selection, existing vector identities, authored physical D4 positions, selected magnetic core, clean/diagnostic and physically-scaled PNG 300 DPI, Ruff, Python3.12/3.13, wheel audit.
- **BLOCKED:** independent 1:1 calibrated published drawings, specific IRFZ44N and 1N5822 manufacturer's package contact pinout, source-photo pixel parity, MOS internal dot's exact normative option, real device electrical correctness, sheet routing/clearance and GND semantics (Issue #109).
- Keep all 36 already merged UGO `DRAFT`; do not promote `APPROVED`. Do not merge into integration or main. QA/EСКД review required.
