# TL494CN connected-photo PAINT Cycle7 — legibility, aliases, ink and print review

Status: **ENGINEERING DRAFT** / **WHOLE-SHEET NORMATIVE RELEASE BLOCKED**.
Refs: Issues [#88](https://github.com/Tridgi/gost-schematic/issues/88),
[#107](https://github.com/Tridgi/gost-schematic/issues/107),
[#110](https://github.com/Tridgi/gost-schematic/issues/110),
[#108](https://github.com/Tridgi/gost-schematic/issues/108).

## Frozen source and immutable electrical identity

Authoritative reconstruction reference is
`reference/tl494-native-rework-20261114`, exact SHA
`e695c415fdced164b0e0c39c5249d030795a0aa6`.
The actual 23-component source is
`examples/tl494_named_truth_output/TL494_named_photo_clean.svg`,
viewBox `-194.15 9.1 679.3 220.051`, body DA1 `rect x=65 y=87
width=60 height=67.5` millimetres. In that source there are **16**
exact external TL494 electrical lead endpoints, **91** authored wire
segments (each original `data-net` and exact x1/y1/x2/y2), **37**
real source junction circles and **2** nonphysical `b` continuation
markers `b-X2`/`b-R5`, radius `0.65mm`. There is **no** supplied
typed `a` continuation marker. Adding a third graphic junction by
guessing a from the label `INPUT_POS` is prohibited.

`scripts/rework_tl494_photo_svg_readonly.py` consumes that exact old
SVG, reconstructs the 16 source-pin numbers, roles and Points from
the *source physical lead x2/y2* and verifies original printed full TI
labels before rendering. It replaces **only the DA1 SVG ink group**,
not a circuit node. It asserts every source wire Net ID and coordinate,
37 authored junction circles, both `b` identifiers, frame, and every
numbered physical pin world Point remain unchanged. The output has
**the exact source sheet 679.3mm dimensions**; no secretly rescaled
or rewired drawing. No sheet-level `Circuit.Net` is inferred from
nearby graphical intersections or text, and source device pin type
is not silently corrected. Full manufacturer pin names are recorded
in SVG `data-full-manufacturer-name`.

## P0: whole function word direction

`IcFunctionReading` has three explicit typed modes:
`HORIZONTAL=0°`, `TOP_TO_BOTTOM=90°` and
`BOTTOM_TO_TOP=270° (-90°)` in **SVG positive-Y-down coordinates**.
For an unrotated portrait body:

- prior **+90°** text vector `(1,0)->(0,+1)` reads **top-to-bottom**
- requested **−90°/270°** text vector `(1,0)->(0,−1)`
  reads **bottom-to-top**; actual SVG matrix begins
  `matrix(0 -1 1 0 ...)`
- `HORIZONTAL=0°` retains paper-horizontal reading when selected

The **new** `IcTypographyProfile.TL494_PORTRAIT_V3_DRAFT`
defaults to bottom-to-top and requires a physically taller-than-wide
existing authoritative body. The pre-existing
`PORTRAIT_FUNCTION_V2_DRAFT` and legacy defaults remain unchanged.
The long-run glyph measurement and independent 0/90/270 text choices
share protected source geometry. Reflection/D4 are exact
integer-composed orthogonal transforms, **not** approximated Euler
rotations and never used to move a physical PinRef.

For source graphic `DA1`, new full-word PWM is anchored to the
actual original 60×67.5mm body, and the existing 16 world endpoints,
numbers and all 91 external-wire segments are **unchanged**. The
printed frame is not resized to make the label fit. A too-small source
body still fails with `IC_TEXT_OVERFLOW` / source revision required.

## P1: 16 source-specific editorial display aliases

Per user project policy (NOT claimed as an official ГОСТ six-character
limit) the full set of **16** TI TL494CN pin names is retained. The
separate `display_alias` field is only what the print uses.
Source numbers 3 `FEEDBACK → FB` and 13 `OUTPUT CTRL → OC`
are explicit named substitutions. All other 14 full source pin names
are retained as their short official-style labels and each visible
alias has no more than six Unicode characters. No automatic
truncation, duplicate rendered labels or implicit Net mapping. The
physical terminal namespace `DA1.8 / DA1.11` must not be
confused with external capacitors `C1/C2`.

**Important independently found model defect:**
`reference/.../examples/tl494_ic_paint_reference.py` at frozen
source SHA declares `FEEDBACK` pin 3
`ElectricalType.OUTPUT`; the TI TL494 datasheet identifies it as
an **INPUT**. Correction belongs to ELEKTRIK IC / reference source
owner and remains a separate BLOCKER; PAINT merely renders aliases.
No claim operating converter correctness is made.

## P2: actual whole-sheet print scale

Original source width: **679.3mm**; height: **220.051mm**.
A full-width 640px preview has `640/679.3=0.942px/mm`.
Its normal 0.3mm line is **0.283 pixels** wide, and an existing
b-circle of radius 0.65mm displays a **1.225px diameter**.
Therefore that thumbnail is inherently incapable of visual acceptance.

Without a **source-authored layout/routing revision**, even an
A2 landscape sheet (594mm wide) is too narrow; one A3 landscape
sheet (420mm wide) cannot fit. PAINT does NOT fake A3 by uniform
downscaling or moving source electrical leads. Instead the visual
artifact presents **two A3 landscape review tiles at 1:1 physical
millimetres** with 20mm source overlap and explicit
`NOT A FORMAL TWO-SHEET SCHEMATIC` label. This is a graphical
review mosaic only; wires crossing the tile border have no separately
authored source addresses, so normative two-sheet E3 is **BLOCKED**
until ELEKTRIK NET/ESKD author a legal revision. Also generated are
real OpenGost 300DPI full SVG/PNG, a deliberately 640px
before thumbnail and large **TL494 / R5–R6 / VD1 Schottky / C1–C2 /
two b continuation** detail views (diagnostic scales identified).

Printed Type A face is measured at `h=3.5mm` for the new PAINT
TL494 text and refs. Original other-sheet components retain the
original source rendering/font; source GOST approval of their typeface,
all annotations, symbols and nominal values is NOT claimed.
Normal wires stay 0.3mm, NOT arbitrarily enlarged to compensate for
a bad browser thumbnail.

## P3: source continuation a/b

Exactly two source-authoritative `b` graphical circles exist:
`b-X2` at `445mm,45mm`, `b-R5` at
`−135mm,214mm`. Their radius and typed source semantics remain
unchanged, and **both** are included in zoomed reference views and
at 1:1 A3 scale. Orange dashed editor-only rectangles indicate
reading/clearance **diagnostic zones**, not copper pads, physical
connector pins or junctions. Clean output contains no such overlays.
The source **does not include** an authoritative graphic a-marker.
A proper new a leader/continuation must await source-specific
ELEKTRIK NET / ESKD review; no fabrication.

## P4: real path-stroke overlap and spacing

`scripts/review_tl494_print_readability.py` audits **actual
finite SVG conductor segments**, independent of topology validation,
using true `stroke-width` expanded visible ink and orthogonal
parallel projection overlap. MOSFET's true inner circle is measured
as an exact circle-radius + stroke; Schottky and capacitor symbols
use actual primitive lines/rects; different symbol groups receive a
2mm inter-UGO stroke check. Complex inductor arc curves and
sheet-wide text-run-versus-wire raster geometry remain explicitly
**BLOCKED**, not silently classified PASS.

**At least five confirmed source parallel-wire distance violations
of 3mm (actual visible stroke-to-stroke):**

| Source wire IDs | Distinct source Nets | True edge gap |
|---|---|---|
| 27 / 62 | COMMON / FEEDBACK | 1.95mm |
| 28 / 71 | COMMON / OSCILLATOR_CT | 1.45mm |
| 42 / 85 | CONTROL_REFERENCE / COMMON | 1.70mm |
| 54 / 63 | SOFT_START / FEEDBACK | 1.70mm |
| 56 / 72 | ERROR_INPUT / OSCILLATOR_CT | **0.70mm** |

An endpoint-only distance algorithm used during development found
only two of these; fixed to use actual **projected finite
parallel-segment overlap**. Five exact original coordinate
regression tests preserve the correct failure result alongside
2.99/3.00mm threshold, circle/dot and nonjoining-X tests.
Stroke proximity to symbols may include intentionally wired pins;
the source *electrical* ownership must be checked independently
before declaring an intersection erroneous. This gate does not
invent a Net for unmarked orthogonal crossings, pretend to
auto-route, or claim accepted source photo 1:1.

## Actual evidence and PASS/FAIL/BLOCKED gates

- **PASS**: transparent original before source, after DA1-only true
  whole-word bottom-up, source-typed FB/OC and 16 positions, 91
  source `data-net` wire records, 37 junctions and two b indicators.
- **PASS**: real pinned OpenGost Type A 3.5mm, both 16-pin 0/90/270
  and all eight D4 poses, separate clean/diagnostic real SVG and 300 DPI
  PNG, exact external pixel targets, no colored target in clean.
- **PASS**: actual 420×297mm A3 source-vector tiling at 1:1 print size
  and sufficiently large problem-area crops **as previews only**.
- **FAIL**: 5 old-source 3mm parallel wire clearances; **FAIL** single
  unchanged A3 or A2 sheet physical width.
- **BLOCKED**: source-corrected FEEDBACK direction, any missing
  manufacturer verification, source-authoritative a indication,
  legal E3 two-sheet continuation addresses, independent
  normcontrol of original symbols and all curves/text keepouts,
  and all-wire auto-router/Circuit.Net release.

This document belongs to PAINT Draft PR #93 ONLY. Other owner
branches / integration / main are never written or merged by PAINT.
