# TL494CN genuine Texas Instruments physical E3 pinout, editorial labels & PWM direction

**Owner:** ELEKTRIK IC #87 / #110; Epic #107. **Draft PR #97 only**.
**Source:** TI TL494 Pulse-Width-Modulation Control Circuits, SLVS074J
(revised September 2026), §4 p.3 Figure 4-1 and Table 4-1:
<https://www.ti.com/lit/ds/symlink/tl494.pdf#page=3>.

`IcDeviceDefinition` with `PinoutOrigin.MANUFACTURER_DATASHEET` is
physically authoritative; it owns 16 separate typed `IcPhysicalPin`
numbers with preserved full manufacturer pin names and descriptions.
`IcPinAliasProfile` is strictly a **separate display-only project preference**,
not a GOST-mandated 6-glyph limit, not a manufacturer data-sheet modification,
not a physical connection to external nets. The original example
`examples/tl494_ic_paint_reference.py` used to map `FEEDBACK` **OUTPUT**;
the replacement derives its `PINS` from the source model and now maps
pin 3 to **INPUT**. Pin 13 `OUTPUT CTRL` is also **INPUT**.
ERC success is *not* a proof of either role; all 16 are compared against
TI source whitelist (also deliberately adversarial wrong-type tests).

| Real physical PinRef | TI full name | Short E3 label | TI I/O | Typed electrical role |
|:--|:--|:--|:--|:--|
| DA1.1 | 1IN+ | 1IN+ | I | INPUT |
| DA1.2 | 1IN- | 1IN- | I | INPUT |
| DA1.3 | FEEDBACK | FB | I | INPUT |
| DA1.4 | DTC | DTC | I | INPUT |
| DA1.5 | CT | CT | – | PASSIVE (oscillator setting) |
| DA1.6 | RT | RT | – | PASSIVE (oscillator setting) |
| DA1.7 | GND | GND | – | POWER_INPUT (return, NOT PE) |
| DA1.8 | C1 | C1 | O | OUTPUT (uncommitted terminal) |
| DA1.9 | E1 | E1 | O | OUTPUT (uncommitted terminal) |
| DA1.10 | E2 | E2 | O | OUTPUT (uncommitted terminal) |
| DA1.11 | C2 | C2 | O | OUTPUT (uncommitted terminal) |
| DA1.12 | VCC | VCC | – | POWER_INPUT |
| DA1.13 | OUTPUT CTRL | OC | I | INPUT (mode select) |
| DA1.14 | REF | REF | O | POWER_OUTPUT (5 V reference) |
| DA1.15 | 2IN- | 2IN- | I | INPUT |
| DA1.16 | 2IN+ | 2IN+ | I | INPUT |

**TI “–” means unspecified I/O direction in the manufacturer column**:
the model's finer role is our E3 editorial annotation, not a verbatim TI
I/O category. The TL494 has uncommitted output transistor terminals:
do not automatically make E1/C1/E2/C2 a tied Net, and do not label them
digital push-pull outputs merely because TI reports `O`.
TI Revision I from July 2022 describes BJT collector/emitter terminals;
Revision J from September 2026 refers to MOSFET drain/source terminals.
The physical pin name/number and topological ownership are unchanged.
This draft deliberately avoids claiming definitive internal transistor
technology or a verified operating power-converter circuit.

## E3 display-side decisions and normative separation

The **authoritative** graphical view uses named sides
`TI_E3_LEFT=(1,2,3,4,5,6,13,15,16)`,
`TI_E3_RIGHT=(8,9,10,11,14,12,7)`. Logical INPUTs LEFT,
OUTPUTs RIGHT; GND/VCC on RIGHT as nonlogical pins in
ГОСТ 2.743-91 §2.1.4 / 2.759-82 §1.1.
This **explicitly is not** the physical package top-view pin order and
**does not reproduce** the source circuit photo's prior arbitrary
left/right order. A router must neither use the package drawing to
change electrical pin identity nor reorder these sides to minimize wires.
The scheme builder in #107 owns central placement and the user photo's
net/wire routing separately. **No floating GND symbol is added** and
GND is not equated with protective PE. This model-only source contains
one `Circuit.ComponentInstance("DA1")` and **zero fabricated Nets**.

Power presentation options `FREE_SHEET_TEXT`, common control block,
power in one section, and separate power outline are covered separately
in `ic_power_presentation.py`; **TOP VCC / BOTTOM GND on LR housing
remains DRAFT experimental/not ESKD-approved**. The TL494 reference
uses plain legal nonlogical LEFT/RIGHT power pins. Full GOST line/letter
normative verification and source-photo whole-sheet integration
still require ESKD #91 and QA #92/#99 sign-off.

## Signed typography (not the IC or pin rotation)

Rendering uses a **portrait body** and reserves a source-authored
graphic revision `IcSymbolSpec(revision+1)` with actual measured
OpenGost Type A 3.5mm glyph ink, pin number and name zones.
The text-only selector changes function text 0↔270 (same body,
same physical pins and `Circuit.Net`). Old `IcTextAngle.VERTICAL=90`
is TOP-TO-BOTTOM in our SVG y-down coordinate system; the
TL494-specific `IcTextAngle.BOTTOM_TO_TOP=270` is explicitly
**bottom-to-top** and maps the text advance unit vector
`(1,0) -> (0,-1)`. Actual PAINT #93 renderer must produce
`matrix(0 -1 1 0 tx ty)`; `matrix(0 1 -1 0 ...)`
is a hard FAIL, not an alternate user-requested appearance.
Function word remains a complete `PWM` text run, not stacked
letters; physical body/ports are never rotated by this preference.

`IcGeometryConsent` names exact source fingerprint and **all**
affected true physical PinRefs before any proposed new body/lead
position is accepted. It is only geometry authorization, not an
electrical wire routing operation. No silent `Circuit.Net` mutation.

## P0–P3 evidence / QA minimum

- 16/16 TI signed physical source whitelist, strict custom
  alias `manufacturer_pin_name`, `physical_number`,
  `schematic_short_label`, `electrical_type`, `real_pin_ref`,
  `display_orientation`, `source_document_reference`.
- Hard `max_display_chars=6` editorial project profile, Unicode
  canonical NFC/casefold uniqueness; no substring truncation, no
  duplicate or blank/foreign alias. Full TI names remain in
  `IcPhysicalPin.name` and `function`. The `C1/C2` within
  `DA1.P8/P11` are *pin names*, not `C1/C2` capacitors.
- Strict source-vs-Paint true integer µm external world PinRef endpoint,
  all 16 lead tips. Sign/angle/regression against D4 rotations/mirrors;
  green editor markers only in diagnostic, no green in clean.
- 4 print specimens: 0° clean/diagnostic and 270° clean/diagnostic,
  each genuine SVG + physical 300 DPI PNG; font SHA, hashes,
  16 pin numbers and 16 alias runs, real 3.5mm height.
- Tests: 1µm mismatch (shared editor target contract), FEEDBACK→
  OUTPUT, CTRL→OUTPUT, power/CT/RT type corruption, 6-vs-7 characters,
  duplicate case-insensitive abbreviation, wrong physical component
  reference, malicious manufacturer metadata and wrong source document,
  0/270 and all 8 D4 preserve PinRef/Net/physical body, **clockwise
  90° wrong direction explicitly fails**.

The artifacts are print-review DRAFTs. Final photo-faithful whole-sheet
placement and routing, full printed ESKD normative approval, and
independent QA remain BLOCKED until ESKD/PAINT/MAIN acceptance.
