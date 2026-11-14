# ELEKTRIK #87: physical pin endpoints, editor-only marks and power placement (DRAFT)

**Own branch:** `parallel/electrical-ic-contract-cycle7`, existing PR #97.
**Other owners:** PAINT #93 / Issue #88, ESKD #91, independent QA #92/#99.
No changes to public `Circuit`, main, integration, PAINT or E1. No merge.

## Source-backed normative boundaries (not an approval of our raster graphics)

- **Digital** ГОСТ 2.743-91 §2.1.4: logical INPUT on LEFT,
  OUTPUT on RIGHT; BIDIRECTIONAL and NONLOGICAL may be LEFT or RIGHT.
  Supply and return are nonlogical; do not classify `POWER_INPUT` as
  logical `OUTPUT`. §2.1.6 TOP signals/BOTTOM outputs is an alternative
  orientation of **the whole IC**, **not** automatic permission for placing
  *only* VCC on top and GND on bottom of a fixed LEFT_RIGHT symbol.
- §2.3.6 table 5: the supply mark is Vcc (VCC in CAD), U also allowed;
  common ground GND, permitted OV variants; extra explanatory markings
  have to be verified. Real pin **numbers** require a manufacturer data
  sheet, not a guess derived from these texts.
- §2.3.10 NC (nonlogic free pin) has its own marking. The physical NC
  PinRef is present as a contact location but is **not connectable**.
- §2.3.11, fig.6: supply shown on the free schematic field, inside the
  **common control block** (6a), **one physical logical unit** (6b),
  or in a **separate graphical power contour** (6c). Fig.6 note permits
  6a+6b or 6a+6c, not 6b+6c together in one documentation set.
  These presentations are not *different circuits*. An explicit sheet
  arrangement must be selected and validated separately from the actual
  `PinRef` and `Circuit.Net` graph.
- **Analog** ГОСТ 2.759-82 §§1.1,1.8, Table 2 uses `U` and `OV`.
  Analog placement obeys source-specific logical/nonlogical rules; naming
  `V+` or `V−` **does not prove** a datasheet pin number or electrical
  connected net.
- Original source references:
  https://www.gostrf.com/normadata/1/4294849/4294849507.pdf
  https://gostrf.com/normadata/1/4294849/4294849490.pdf
  https://meganorm.ru/Data2/1/4294849/4294849507.htm
  https://ohranatruda.ru/ot_biblio/norma/217811/
  ESKD #91 owns independent source-specific 1:1 print signoff.

## P0 physical editor contact contract

`IcPhysicalEditorContact` carries:
`device_id`, `package_id`, `component_ref`, `unit_id`,
the **real** `PinRef(component_ref, physical_number)`,
`physical_number`, manufacturer/synthetic `pin_name`,
PAINT-facing `role`, source `IcPinType`, integer-micrometre
`anchor: Point`, `net_id: str|None`, `connectable: bool`
and `reason`. **Physical pin and logically presented unit are two
separate identities**. `IcEditorContactManifest` is complete over every
represented terminal, with one and only one unique physical PinRef and
external world Point for the whole physical package.

`make_ic_editor_manifest(IcPaintBinding, Circuit|None)` first validates
real model↔PAINT exact row and unit semantics, including D4 transforms
and package inventory, then reads the actual `Circuit.Net.members` when
supplied. No inferred nets from text `VCC`, `GND`, `U`, `OV` or
a real pin name. `None` means **unknown/not provided**; it must not
be interpreted as definitely unconnected in an external project.

`verify_ic_editor_manifest` rebuilds independent truth from authoritative
model and circuit and requires exact equality. Foreign components,
incorrect unit ownership, duplicate contacts, omitted physical pins,
wrong electrical types, invented Net IDs and **1 µm** coordinate drift
fail closed. No hidden tolerance or deduplication. NC cannot be enabled
or assigned a Net. All other genuine named electrical roles
(INPUT, OUTPUT, BIDIRECTIONAL, POWER_INPUT, POWER_OUTPUT, OPEN_COLLECTOR,
PASSIVE) are individually retained, including POWER_OUTPUT that PAINT
renders under its generic `power` presentation role. A particular
name does not automatically grant power semantics.

`make_paint_editor_targets` converts this manifest to PAINT #93's
existing `IcConnectionTarget` per source unit, validates exactly
ONE target per `ResolvedIcPin`, and rejects partial or malformed
inventories. PAINT's lightweight `IcConnectionTarget` currently
lacks section/type/package fields, so ELEKTRIK retains and validates
the full rich typed source **before** that compatibility conversion.

`render_ic_editor_review` produces **two explicit modes**:
`diagnostics=False` → grayscale clean physical SVG (no editor layer),
`diagnostics=True` → real `data-layer=editor-connection-targets` markers,
green `#148645` only when `connectable=True`; NC disabled red
`#8b1e27` with machine-readable reason and Net label; both are
**nonprinting review overlays** (`data-physical-print=false`).
Each marker centre equals the **external SVG lead x2/y2** and the same
source world `PinRef→Point` in micrometres, not the symbol frame entrance,
a wire crossing, label or non-physical continuation.

The real 300DPI QA workflow checks actual PNG marker RGB pixel at each
authoritative end and requires clean PNG color neutrality at the same
positions. This is a diagnostic *preview*, not yet a CSS-pixel radius,
keyboard focus, zoom hit-test, or working CAD connection button (#100).

## P1 six deliberately different power plans

`IcPowerMode` is independent of the IC's physical package and PinRef
ownership and has:
`NONLOGICAL_SIDE`, `FREE_SHEET_TEXT`, `COMMON_CONTROL` (fig.6a),
`IN_ONE_SECTION` (fig.6b), `SEPARATE_OUTLINE` (fig.6c),
`EXPERIMENTAL_TOP_BOTTOM_RAILS`.

`IcPowerPinLabel` **always** names an explicit physically present
number and its actual owner `IcUnit.id`, an independent typed
`IcPowerMeaning.SUPPLY|COMMON|SUPPLY_OUTPUT`, and a source-specific
graphic `label`. `IcPowerPresentation` belongs to one real
`component_ref`, never makes a second phantom Circuit component.
The host graphical section for fig.6b is explicit and need not be the
physical owner of all supply pins. `validate_ic_power_presentation`
rejects foreign number/unit/package, ambiguous types, unknown labels,
missing actual power pins and NC masquerading as a power source.
`POWER_OUTPUT` is a supply SOURCE OUT, not logical data OUTPUT.
Analog generic markers U/OV differ from digital VCC/GND.

**Experimental top VCC / bottom GND remains BLOCKED by default**:
only `experimental_preview=True` may accept the metadata, which
still does **not move** actual L/R anchors, authorize a new TOP/BOTTOM
physical view or allow clean normative export. Sheet-level validation
rejects mixing fig.6b and fig.6c and rejects experimental placement
in a certified document. These objects are SOURCE-VALIDATED
presentation plans, **not finished painted UGO outlines**. Full 6a/b/c
actual production SVG is a remaining PAINT/ESKD joint task.

All physical numbers in the new examples are visibly **SYNTHETIC**.
A real pinout needs an `IcPackage(origin=MANUFACTURER_DATASHEET)`
with explicit manufacturer, https datasheet and revision. No claims of
real VCC, AVDD, DVDD, AGND, V+/V− or GND numbers.

## P2 portrait PWM_CONTROLLER

An opt-in `IcGraphicProfile.experimental_portrait_pwm()` uses a
portrait source box, LEFT/RIGHT physical sides and independent 90°
whole-word `PWM_CONTROLLER`. Updated `propose_ic_paint_binding`
measures *both* text angles, reserves their maximum width, height and
function row span in the **new explicit graphical revision**, and
preserves old Circuit.Net. The source requires
`validate_ic_graphic_revision` with
`IcGeometryConsent(source_sha256, movable_pinrefs,
connected_reroute_pinrefs)` before a moved connected endpoint can be
accepted. Actual external reroute still belongs to the wiring owner.

`bind_ic_paint_text_only` toggles the angle in an unchanged
`IcSymbolSpec.body` with exact same endpoints. **Four hard D4 tests
(PAINT rotation 90/270 and both mirror choices) still produce
`IC_TEXT_OVERFLOW: main.0 function`** against renderer snapshot
`db53e0ab89bb23f555badc2def41ea9895a5d64c`.
When PAINT uses a world-rotated cell with only **7500 µm width**
to fit a long source-horizontal word, no amount of source local
resizing can make that cell wider. This is a PAINT local/world
text-metric coordinate bug; never silently move physical pins, skip
tests or relax clearance. Detailed reproducible handoff:
https://github.com/Tridgi/gost-schematic/issues/88#issuecomment-6875922497

## P3 handoff evidence

Joint owner workflow:
`.github/workflows/ic-paint-cross-cycle7.yml`, Python 3.12/3.13,
real OpenGost Type A SHA256
`f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`.
The expected export is one manifest with DA8, DD14/40/64 physical
`PinRef→Point`, Net, type, unit and connectability plus **14 unit-angle
views × clean/diagnostic = 28 actual SVG/28 PNG**.
Check `scripts/verify_ic_editor_raster_cycle7.py` for RGB and no-color
assertions. All gallery files remain **DRAFT** and source-provenance
**SYNTHETIC** until independent QA #92/#99 and normative ESKD signoff.

**No E1 / main / integration / PAINT or NET branch changes. No merge.**
