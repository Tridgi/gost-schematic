# Cycle 7 — Electronic devices, multi-pin E3 microcircuits and net continuations

**MAIN 2 decision:** documented experimental backlog; no production code or GOST approval in this change. Start branch `integration/stage0-12` at `957c73e9889d595575b0ea26ee3bee1ac4790297`; `main` unchanged.

## Current inventory
The registered baseline has 21 DRAFT symbols: 1 `resistor.fixed`; 3 capacitors (fixed/polarized/electrolytic); 2 diodes (general/zener); 15 generated parametric inductance variants. **Missing** in the accepted E3 catalog: DA/DD physical ICs, variable potentiometers/trimmers, BJTs/FETs, Schottky/LED/photo/varicap diodes, fuses, genuine physical plug/socket connectors and document-scoped net-continuation markers. 12 early semiconductor/contact normative cards already exist from Issue #27 and must be reused.

## Issue map

| Ticket | Owner | Branch | Purpose |
|---|---|---|---|
| [#86](https://github.com/Tridgi/gost-schematic/issues/86) | MAIN 2 | integration | Epic, staged release gate |
| [#87](https://github.com/Tridgi/gost-schematic/issues/87) | ELEKTRIK | `parallel/electrical-ic-contract-cycle7` | E3 PartDefinition / MultiPin IC / shared physical pin positions |
| [#88](https://github.com/Tridgi/gost-schematic/issues/88) | PAINT | `parallel/rendering-ic-cycle7` | Main/supplementary rectangular fields, real OpenGost glyph ink and pin keepouts |
| [#89](https://github.com/Tridgi/gost-schematic/issues/89) | YGO 2 | `parallel/catalog-electronic-cycle7` | Potentiometer, trimmer, semiconductor variants, fuse, physical connector DRAFT symbols |
| [#90](https://github.com/Tridgi/gost-schematic/issues/90) | ELEKTRIK | `parallel/electrical-netrefs-cycle7` | Net labels/continuations and explicit cross-sheet addresses — view only, no phantom part |
| [#91](https://github.com/Tridgi/gost-schematic/issues/91) | ESKD | `parallel/standards-electronic-cycle7` | Source-bound normative matrix and independent edition/size checks |
| [#92](https://github.com/Tridgi/gost-schematic/issues/92) | QA | `parallel/qa-electronic-cycle7` | Actual owner code/negative/ink/PDF-gallery independent QA; no faked approvals |
| [#74](https://github.com/Tridgi/gost-schematic/issues/74) | AI/MCP | `parallel/ai-project-p11-readonly` | E3 persisted read-only P1.1 before actual edit MCP; future typed catalog APIs |

Existing E1 owners PR #78/#80, PAINT L1 PR #79 and QA #83 remain independent and cannot be silently merged into Cycle 7 branches. Catalog before rendering: #91 source decisions and #87 semantically stable pin contract, then #88/#89, #90, #92. In parallel #74 may implement read-only P1.1, not arbitrary editing.

## Architecture guardrails
1. **E3 IC is a physical electric component:** separate immutable real `PhysicalPin` identity + physical vendor pinout, symbol `GraphicPin`/layout, manufacturer package/footprint metadata and `Circuit.Net`. Unlike E1 FunctionalBlock, an E3 IC is not a semantic directed functional link.
2. **Digital:** ГОСТ 2.743-91 main rectangle and optional left/right supplemental fields, function code first main row, pin labels with indicators, actual pin numbering per §2.3.12 on pin lines (inputs left/outputs right or permitted in line break), pin side restrictions §2.1.5–2.1.6. **Analog:** ГОСТ 2.759-82 distinct source evidence.
3. **Text + rectangles:** choose pinned external OpenGost Type A and measured glyph *ink* bounds, not character count or SVG CSS em. Layout line by line downward with separate glyph/frame/field/port/escape keepouts. Calculate width from longest real row, height from rows+pins; grow on source-verified modular grid. Never clip, ellipsize, rotate text incorrectly, or silently scale height below norm. Unknown font or impossible sheet => fail closed.
4. **Real physical distinction:** BJT/MOS enclosure is optional schematic circle/outline when standard permits, NOT selected SOT-23 or TO-220 mechanical package depiction. Part real physical pin number must be source-based. G/D/S/B and B/C/E chemical/semiconductor meaning must remain intact after transforms. Existing #27 NPN source issues cannot be bypassed by copying another form blindly.
5. **Discretes:** begin with 3-terminal variable pot/trimmer, ordinary Schottky/LED/photo/varicap, PNP/NPN, enhancement N/P MOS, general FU fuse, simple physical XP/XS after normative source; extended JFET/depletion/thyristor/triac/opto/diode arrays P1 after source evidence.
6. **Net continuation:** ГОСТ 2.721-74 table6 pos8 graphical break+continuation code and ГОСТ 2.709-89 §5 identification/address. Two visible fragments can reference ONE existing `Circuit.Net` with sheet addresses. No invented electric net from same text, visual proximity or SVG crossing; physical connector is a PartDefinition + distinct real contacts.
7. **DRAFT only:** all families independent SVG + genuine 300-DPI PNG gallery, current SHA, source table/page references, negative tests, transformations, physical pin ↔ graphic position audit, Ruff + Py3.12/3.13 + wheel and dynamic catalog counts. ESKD review then MAIN 2 acceptance; never merge worker PRs.

## Release slices
- **S7-A:** core 8/14-pin DA/DD and 3pin pot + ordinary FU + Schottky/LED + two named net continuation fragments in a 2-page E3 experiment; independent tests.
- **S7-B:** 40/64 pins, additional semiconductors and actual datasheet pin mapping, true analog IC classes, D4 and wide-text stress, multi-unit split only after accepted schema.
- **S7-C:** curated extended semiconductor library and real connector modes, general routing, agent project edit MCP after P1.1; user-facing 'complete catalog' still not asserted without evidence.

**Acceptance demonstration:** one well-laid-out E3 multi-sheet design with real DA/DD, VT BJT+FET, VD Schottky/LED, potentiometer, FU, physical connector and matched off-page labels. Text leaves visible ink margin; all physical PinRefs and Net members exact; no phantom joins, no E1/E3 type confusion.
