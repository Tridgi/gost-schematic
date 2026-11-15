# ELEKTRIK IC Cycle 7: independent graphical function angle (Draft RFC v2)

**Owner:** Issue #87, existing Draft PR #97, only branch
`parallel/electrical-ic-contract-cycle7`. Independent PAINT #93 current source
pin **`db53e0ab89bb23f555badc2def41ea9895a5d64c`**.
ESKD #91/source approval and QA #92 acceptance are independent.

## The actual user contract

The intended new E3 editor preset is a **tall, portrait rectangle** with
physical **LEFT input / RIGHT output** pins and the entire function word **PWM
rotated 90°** *inside* that unchanged rectangle. Only the central function
glyph run rotates. The operator can then toggle **PWM 0°** while all
physical `PinRef` numbers, `Circuit.Net`, port sides, drawn frame,
other field labels, physical pin numbers and unit identities remain fixed.
**Portrait is NOT top/bottom connectivity.** None of this is a PCB package
footprint, proof of the GOST-validity of "PWM", or a claim that fig.3 permits
arbitrary function-only rotation in a LEFT/RIGHT figure.

`IcGraphicProfile.experimental_portrait_pwm()` supplies this **opt-in
new-E3 preset**. Historic v1 `IcGraphicProfile()` remains left/right,
AUTO body and 0° function, preserving the old serializer and golden file
identity until an explicit migration. Geometry must be authored as a
genuinely tall `Box`, otherwise `IC_BODY_AXIS_GEOMETRY_MISMATCH`.

## Eight orthogonal source-owned properties

| Property | Owning typed record | May rotate when user toggles PWM? |
|---|---|---|
| Physical part + manufacturer / synthetic provenance | `IcDeviceDefinition` + `IcPackage` | **No** |
| One real device with N sections and numbered pins | `IcDeviceDefinition.units/pins` | **No** |
| Absolute external contact identity | `PinRef(component_ref, physical_number)` | **No** |
| Local pin placement/semantic side + row/group | `IcPinRow(side, anchor, visual_row, row_key, field)` | **No** |
| Graphical rectangular dimensions | `IcSymbolSpec.body` | **No** (text-only toggle) |
| Source profile of ports: LEFT_RIGHT or genuine TOP_BOTTOM | `IcGraphicProfile.port_layout` | **No** |
| Body aspect: AUTO/PORTRAIT/LANDSCAPE | `IcGraphicProfile.body_axis` | **No** |
| Central function and other text angles, independently | `IcGraphicProfile.function_angle/other_text_angle` | **Only function_angle** |

Local graphical placement D4 is separately recorded in
`IcUnitPlacement.transform`. D4 of the *whole view* never substitutes for
a true TOP_BOTTOM `IcPinRow` model, and it does not redefine the
glyph angle relative to the local body.

## Two strict wire-safe revision classes

1. `revise_ic_text_orientation(original, IcTextAngle.VERTICAL)` makes a
   NEW `IcSymbolSpec.revision+1`, leaving its box, sections, rows, labels,
   `origin` and `transform` identical. The source is not mutated. Verify
   zero moved `PinRef` using `validate_ic_graphic_revision`. This is
   genuinely independent of `port_layout` and `body_axis`.
2. A PAINT-proposed resizing of `Box`, port side or lead length is a
   candidate revised source, **never an implicit edit** to existing wires.
   `validate_ic_graphic_revision(old, new, circuit=..., consent=...)`
   calculates all exact old/new world `Point` values, and requires
   source-fingerprint-bound `IcGeometryConsent` explicitly listing EVERY
   moved `PinRef`. Any connected moved pin additionally requires its name
   in `connected_reroute_pinrefs`. A missing/extra ref, stale source SHA,
   reused unit, changed pin label/number, NC membership, device/placement
   switch, unchanged revision or unknown Net fails closed. Even a valid
   consent **does not reroute** `ExternalWireGraph` or commit a project:
   the layout owner must separately verify/re-author all physical wire ends.

The real PAINT font-measured field/lead requirements are exposed as typed
`IcPaintFieldRequirement` on `IcPaintBinding.requirements`. The actual
Type A run/glyph ink envelopes are exposed as
`IcPaintProtectedTextArea` via `protected_text_areas`. Guards are
the selected project's **editorial** micrometre padding, not asserted
GOST universal dimensions. Exact per-lead world `Point` equals its
source `PinRef` with zero tolerance.

## PAINT compatibility and independent word-only rotation

Actual PAINT #93 implementation for this integration is pinned at
`db53e0ab89bb23f555badc2def41ea9895a5d64c` (later PAINT CI-only
commits retain the same `ic_rectangular.py` source blob). PAINT now
has independent `IcOrientation.LEFT_RIGHT/TOP_BOTTOM`,
`IcTypographyProfile.LEGACY_V1/PORTRAIT_FUNCTION_V2_DRAFT`, and
`IcResolvedUnit.function_rotation=0/90` selected *without changing
the physical port profile*. 90° rotates the **whole PWM text run**,
not individual stacked letters. Actual ink bounds follow the explicit
text transform, protected field and lead strokes, rather than string
character count or a silently shrunken font.

The owner bridge `propose_ic_paint_binding` passes the measured
`function_rotation` to PAINT's `propose_ic_dimensions` and records
`function_row_span` together with main/aux dimension demands. For
the user's exact case, `bind_ic_paint_text_only(old_binding, new_record)`
changes the PAINT function rotation in the **same typed original body,
physical PinRef points and externally resolved leads**. It must pass
`validate_ic_graphic_revision` with **zero moved pins** before any
render. It is intentionally not allowed to call PAINT for a new body
size when toggling 0/90, because that could mutate wired endpoints.

The new E3 opt-in profile is `IcGraphicProfile.experimental_portrait_pwm()`.
This sources **PORTRAIT + LEFT_RIGHT + word90 + other0**. Historic
v1 saved records remain AUTO/LEFT_RIGHT/0. In a scene too small for
the rotated word/other field runs, PAINT may reject with a precise
`IC_TEXT_OVERFLOW`, `IC_INK_COLLISION` or
`IC_REFDES_UNPLACEABLE`: a separate new geometry revision and
explicit `IcGeometryConsent` are required before moving a wired
pin. A graphical test pass does **not** imply GOST approval for
the independent LEFT_RIGHT word-only rotation. §2.743-91 fig.3
alone depicts a *different* TOP/BOTTOM source layout, not this
unmodified LEFT_RIGHT special case; ESKD #91 must decide
whether clean production export may enable it.

**Actual pinned two-owner DRAFT gallery:** DA8, DD14, DD40 and
DD64 each have portrait LEFT_RIGHT function 0° and 90° on the
same `Circuit`, unchanged local body and same exact world
`PinRef` contacts. Actual clean SVG and 300DPI PNG outputs
include 14 rendered unit views in all (1+2+2+2 per angle).
All images/manifest carry source hashes. An explicitly
different real `TOP_BOTTOM` typed source is also generated
for each part and each function angle; currently some of those
views are fail-closed `IC_TEXT_OVERFLOW` because source-compliant
orientation of labels and width/height cannot fit together,
rather than downgrading to fake rotated LEFT_RIGHT or silently
changing PinRef/Nets. Their release remains BLOCKED until a
source-backed font/layout solution and independent QA review.

## Strict persistence and MCP P1.1

Old E3 `PartDefinition` lacks multi-unit graphical ownership and
fails NC fidelity: `to_legacy_part()` refuses split units or NC.
Agent ProjectService #96 P1.1 still locks and verifies the legacy
`PartDefinition/SymbolDefinition` inventory. **Do NOT import an IC
by downcasting it or generating image-only pin metadata.**

`ic_to_json/ic_from_json` preserve historical **exact schema v1** for
old default-profile records; new nondefault graphical profiles are
strictly **v2** with exact `graphic_profile` fields (port layout,
body axis, function and other-text angles). No unknown fields,
duplicate keys, noninteger/NaN values, unknown physical numbers, or
unowned unit rows accepted.

`IcAgentSnapshot` in `electrical/ic_agent_snapshot.py` adds a
lossless read-only archive containing the complete canonical v1/v2
`IcLibraryRecord`, physical component ID and actual `Circuit.Net`
membership with SHA256 verification. Loading requires the **caller's
real Circuit** and validates NC/physical pin identities. This is a
typed **staging contract**, NOT an installed ProjectService endpoint.
Future MCP integration requires a separately versioned project schema,
catalog lock semantics and transactional/rollback policy approved by
MAIN 2 and QA. No edits to PR #96 are performed here.

## Review matrix for QA

| Case | Physical source | Text 0/90 identity | PAINT | Normative |
|---|---|---|---|---|
| DA8 | One physical 8-pin part | Both v2 same pins/Net | 0° and 90° LEFT_RIGHT DRAFT SVG PASS | DRAFT |
| DD14 | One part, two units | Both v2 same pins/Net | 0° and 90° LEFT_RIGHT DRAFT SVG PASS | DRAFT |
| DD40 | One part, two units | Both v2 same pins/Net | 0° and 90° LEFT_RIGHT DRAFT SVG PASS | DRAFT |
| DD64 | One part, two units | Both v2 same pins/Net | 0° and 90° LEFT_RIGHT DRAFT SVG PASS | DRAFT |
| True TOP_BOTTOM | Different local source sides | Independent 0/90 function | Separate PAINT mode / ink guards | DRAFT/BLOCKED |

QA is to inspect both retained source profiles, real Circuit membership,
font-bound measured clearance, no same-number wiring duplication,
OpenGost Type A per-glyph bbox and physical 300-DPI actual raster
evidence. Never call a model-only text angle a PAINT-verified SVG.

**Not touched:** public `Circuit` API, E1 `StructuralDiagram`,
NET #98, PAINT #93 branch, MCP #96 branch, main, integration/stage0-12.
No auto-merge.
