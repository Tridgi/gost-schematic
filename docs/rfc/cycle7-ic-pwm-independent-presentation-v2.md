# ELEKTRIK IC Cycle 7: independent graphical function angle (Draft RFC v2)

**Owner:** Issue #87, existing Draft PR #97, only branch
`parallel/electrical-ic-contract-cycle7`. Independent PAINT #93 current source
pin **`0bc38290db8729c0cd152c0d8d2ed955fae2dd31`**.
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

## PAINT compatibility and limitation

Actual PAINT PR #93 at pinned source
`0bc38290db8729c0cd152c0d8d2ed955fae2dd31` supports
`IcOrientation.LEFT_RIGHT`, `IcOrientation.TOP_BOTTOM`, its own
`function_rotation` and `field_text_rotation`, and the latter
TOP_BOTTOM fig.3-like 0/90 ink style.

**Known missing rendering feature:** PAINT currently throws
`IC_TEXT_ROTATION_REQUIRES_TOP_BOTTOM_PROFILE` for
LEFT_RIGHT + function_rotation=90. Our bridge deliberately raises the
more specific `IC_PAINT_LEFT_RIGHT_TEXT_ROTATION_BLOCKED` without
silently moving pins to TOP/BOTTOM. The **MODEL and lossless v2
serialization PASS**, actual portrait LEFT_RIGHT + PWM90 **production
SVG BLOCKED**. The existing renderer's 90-degree follow-symbol text
mode must not be treated as independent 90-degree local function text.
Coordinate with PAINT to author a separate function-only rotated glyph
bbox, center it within a source-backed main function region (possibly
multiple protected rows), check stroke/zone/page collisions with actual
OpenGost Type A glyph metrics, preserve all external line ends, and fail
with `IC_FUNCTION_ROTATED_OVERFLOW` rather than squeezing fonts or
automatically changing Circuit/Net.

**Genuine TOP_BOTTOM** is now a separate typed owner presentation,
reflowed by PAINT #93 via `vertical_as_canonical` only after explicit
source TOP/BOTTOM anchors. TOP/BOTTOM function angle 0/90 can be rendered
by PAINT's current Draft source subject to individual ink-space
rejections. §2.743-91 figure 3 cannot be cited to certify
LEFT_RIGHT + independent 90° function alone. A separate ESKD decision
is required for actual production export and pin number layout.

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
| DA8 | One physical 8-pin part | Both v2 same pins/Net | 0° LEFT_RIGHT; 90° blocked | DRAFT |
| DD14 | One part, two units | Both v2 same pins/Net | 0° LEFT_RIGHT; 90° blocked | DRAFT |
| DD40 | One part, two units | Both v2 same pins/Net | 0° LEFT_RIGHT; 90° blocked | DRAFT |
| DD64 | One part, two units | Both v2 same pins/Net | 0° LEFT_RIGHT; 90° blocked | DRAFT |
| True TOP_BOTTOM | Different local source sides | Independent 0/90 function | Separate PAINT mode / ink guards | DRAFT/BLOCKED |

QA is to inspect both retained source profiles, real Circuit membership,
font-bound measured clearance, no same-number wiring duplication,
OpenGost Type A per-glyph bbox and physical 300-DPI actual raster
evidence. Never call a model-only text angle a PAINT-verified SVG.

**Not touched:** public `Circuit` API, E1 `StructuralDiagram`,
NET #98, PAINT #93 branch, MCP #96 branch, main, integration/stage0-12.
No auto-merge.
