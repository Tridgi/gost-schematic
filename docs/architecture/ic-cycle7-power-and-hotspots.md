# PAINT Cycle7 #88/#100 — Source-scoped Power and Diagnostic Pin Ends

**Status:** Experimental engineering DRAFT. **No normative GOST approval, no main
or integration merge.** The real authority for nets and physical pins remains
ELEKTRIK `Circuit.Net` and exact `PinRef → Point`; every reviewed example in
this PAINT branch is synthetic rather than a manufacturer pinout.

## 1. Primary 2.743-91 source classification

Original scanned **ГОСТ 2.743-91**:
<https://meganorm.ru/Data/190/19085.pdf>

- Original printed **с. 3**, PDF p. 4 (zero-index 3), **§2.1.4**:
  *ordinary digital* logical inputs LEFT, outputs RIGHT; bidirectional and
  nonlogical pins (including power) may be LEFT or RIGHT. Therefore existing
  SIDE pins remain source-backed and cannot automatically be shifted to
  TOP/BOTTOM merely because a case is portrait.
- Printed **с. 3**, **§2.1.6, fig.3**: alternative **entire UGO**
  TOP-in/BOTTOM-out. It is not a universal authorization for top VCC/bottom
  GND in otherwise LEFT/RIGHT IC, or for free-standing center-only PWM90.
- Printed **с. 14**, PDF p. 15 (zero-index 14), **§2.3.11 fig.6**:
  supply as free-sheet text, supply in common control block (6a), in
  one logical unit of split IC (6b), or a separately drawn power contour
  (6c). Figure 6's actual wires are to the **left**. The figure's method
  combinations must follow its exact note; no invented universal mixture.
- Printed **с. 14**, **§2.3.12**: pin numerals adjacent to own lead; do
  not replace physical numbers with Net names or reshape source terminals.
- **ГОСТ 2.759-82** for analogue DA must be source-scoped separately.
  Analog U/OV and digital VCC/GND are *display labels only*; neither a
  manufacturer pin number nor inferred net identity.

### Typed power presentation profiles

`src/gost_schematic/rendering/ic_power_profiles.py`:

| Typed choice | Source/graphical view requirement | Engineering | Normative |
|---|---|---|---|
| `SIDE_PINS` | Explicit role=power on physical L/R PinRef; digital VCC/GND or analog U/OV | **PASS source-typed SVG** | **DRAFT / ESKD review** |
| `COMMON_CONTROL_BLOCK` | Authoritative common control block and its special outline, not ordinary rectangular box | **BLOCKED** on absent contour, named error | **DRAFT fig6a** |
| `ONE_SPLIT_UNIT` | One explicitly identified graphical split unit owns power pins, the other unit IDs are declared | **PASS source-profile validation**, renderer reuses true owner view | **DRAFT fig6b** |
| `SEPARATE_CONTOUR` | Dedicated source-authored view containing *only* power pins, preserving one physical component | **PASS view guard** (no fabricated connection) | **DRAFT fig6c** |
| `EXPERIMENTAL_TOP_BOTTOM` | True typed TOP/BOTTOM physical power anchors, not D4 or aspect-ratio inference | **BLOCKED for current L/R**, separate opt-in candidate | **NO-GO normative** |
| `FREE_SHEET_TEXT` | Sheet-level authored text and verified origin/physical pin members | **BLOCKED** absent author note/geometry | **DRAFT §2.3.11** |

`IcPowerProfile` is immutable. It binds specific physical
`PinRef(reference, number)` values, actual `role="power"` inventory, actual
local source-unit owner and any other units sharing the same physical device.
It never derives supply from string `VCC`, `GND`, `U`, `OV`, moves a
contact, creates a Net, duplicates a chip, infers a manufacturer datasheet,
or treats an unrendered special contour as a completed diagram.

An opt-in view carries `data-power-layout`, `data-power-normative` and
`data-power-pinrefs`. Legacy export without a specified profile remains
unchanged. Future 1:1 fig6 actual outline geometry needs an ELEKTRIK
authoritative source view and ESKD #91 approval before PAINT draws it.

## 2. Real diagnostic endpoint overlays — Issue #100

Root problem: `review_overlay=True` was **ink-only**. A target requires
`editor_overlay=True` **and** real `IcConnectionTarget` records. The
generator now emits for every 4/8/14/40/64 source L/R, real T/B, 8/14/40/64
portrait angle 90/0, plus 8 D4 poses × mirrors × long PWM/Cyrillic × 90/0:

- `-clean.svg`: black/white physical UGO only; **no** green/red or editor
  layer (same rule for clean PNG / future clean PDF).
- `-diagnostic-ink.svg`: glyph/stroke protected regions, no endpoint color.
- `-diagnostic-pins.svg`: real editor-only `IcConnectionTarget` rectangles,
  green eligible / red actual NC, no text-ink color layer.
- `-diagnostic.svg`: both independent debug layers.

Each 0.7mm **EDITORIAL static review** square has center exactly equal to
its external lead `x2/y2` and authoritative world-coordinate integer µm
`Point`. Every rect carries `data-pin-ref`, `data-pin-number`,
`data-pin-id`, `data-pin-role`, `data-net-id`, `data-reason`,
`data-connectable`, `data-external-anchor-x-um/y-um`.
A literal NC label is now also **physical role=nc**, disabled red with
explicit reason, no Net. Other known nets are explicitly authored synthetic
`Circuit(Net(...))` memberships—not guessed by label. Missing/untrusted
foreign `PinRef.reference`, duplicate/unknown pin, 1µm bad endpoint,
attempted NC network membership fail closed.

`scripts/verify_ic_debug_gallery.py` checks physical source lead identity,
exact vector rectangle centers, real 300-DPI raster RGB sampling at every
green and red center, marker count, unchanged texts/frames/leads across all
four modes, and grayscale-only clean PNG. It does **not** create image-level
fake marks. The 0.7mm-size is a diagnostic illustration; interactive
zoom-independent CSS-pixel hit regions, keyboard focus, wire junction
selection and transactional route changes remain **Issue #100 BLOCKED**.

## 3. PWM_CONTROLLER D4 regression, protected union

The core renderer now computes `shared_function_envelope=True` for the
explicit versioned portrait draft, not legacy. The source-size proposal
reserves the **union of horizontal and vertically rotated ink** for
the same function and reserves the longer axis as full main row span.
At D4 90/270 the paper-upright function at 0° may span multiple
body-local rows rather than being forced into a single ~7.5mm-wide
transformed cell. This unblocks an authored source-wide candidate while
preserving the physical body/lead Point at 90→0.

All eight D4 poses, mirrors, `PWM_CONTROLLER` and
`КОНТРОЛЛЕР_ШИМ` are independently proposed then rendered at 0° and
90°. A source whose box was already accepted but is inadequate for the
union MUST fail with `IC_TEXT_OVERFLOW` and request a new
`IcSymbolSpec` revision from ELEKTRIK. A valid consent for moving a
previously connected point is NOT granted by PAINT rendering; no silent
rewiring or font shrink.

### Release gates

- **P0 diagnostic marker:** PASS only after exact-head full Type A SVG+PNG
  verification, expected valid count per view and actual disabled NC.
- **P1 2.743 power:** SIDE model/ink PASS as DRAFT; common/sheet notes
  and top-bottom retrofit BLOCKED; fig6b/c source-unit-only validation
  PASS as DRAFT and 1:1 source normalization remains BLOCKED.
- **P2 long PWM:** exact-head Python 3.12/3.13, real font, all D4 and
  original QA #99 external red gate must each be examined separately.
- **P3 visual:** only the generated GitHub Actions artifact at final SHA
  establishes complete real 300-DPI proof; synthetic preview does NOT
  imply certified analogue/digital manufacturer source.

All five programmatic modes remain **non-APPROVED** until ESKD #91/#101,
QA #92 and MAIN2 independent release acceptance. Do not merge.
