# PAINT — shared SVG and paper layer for Э1 and Э3 (proposal only)

**Status:** DESIGN-ONLY / DRAFT. No structural renderer, model, fake electrical catalog parts, or new common API is implemented in this PR.

**Inputs consulted:** ESKD Issue #69 (ГОСТ 2.702-2011 §5.1, ГОСТ 2.701-2008 and ГОСТ 2.304-81), QA Issue #72, and current rendering code. This proposal awaits the ELEKTRIK/YGO2 typed structural contract.

## Reusable versus inapplicable modules

| Existing module | Reuse decision | Required boundary |
| --- | --- | --- |
| core.geometry: Point/Box/Line/Rectangle/stroked bounds; core.units; core.transforms | Reuse | Integer µm, geometric strokes only. Never infer electrical or process connectivity from an intersection |
| engines.annotation.metrics: PillowTextMeasurer, TextStyle, font SHA-256 | Reuse single-line metrics | Cyrillic cap-height measured in physical mm, distinct from SVG CSS em-size. Multiline block labels need a NEW E1-owned line-layout contract |
| rendering.primitives.draw_primitive | Reuse geometric primitives | A generic line is not an ElectricalWire; E1 process arrows/flow lines need their own semantics and arrowhead shape profiles |
| rendering.form_one | Candidate shared page decoration | 185×55mm, empty by default, explicit values only, 2.5-mm glyph ink and fail-on-overflow. Still unapproved until ESKD final sign-off |
| rendering.formatted_sheet.PageProfile | Candidate shared geometric page profile | A4/A3 sizes, physical margins/safe zone and 1:1 translation. Do not directly reuse compose_formatted_sheet: its ExternalWireSheet input and E3 audit are electrical-specific |
| engines.sheet_layout/layout | Share collision algorithms, NOT current binder | Current annotations bind ComponentInstance/PartDefinition/PinRef and protect electrical pin corridors. Structural ports require typed logical model and different obstruction policy |
| rendering.sheet_svg | NOT directly reusable | Iterates electrical Circuit components, real Part/Symbol definitions and wires. Functional rectangles are not fake electrical part definitions |

## Ownership after agreement

**ELEKTRIK** owns the typed immutable StructuralDiagram: FunctionalBlock with ID and ordered BlockPorts (side, precise attachment coordinate, direction), directed FunctionalLinks between named ports and explicit logical forks/crossings. It does not generate an electrical Circuit, PinRef or conductive net.

**YGO 2** owns the functional rectangle/UGO presentation definitions, multiline title inside each block, port graphics and arrowhead catalog, transformed graphic keepouts, multiport spacing and optional label style. The single port at side midpoint and ordered equal spacing are *editorial defaults*, NOT mandatory ГОСТ coordinates.

**PAINT** would later own a neutral RenderedDiagram scene envelope (not an implemented class): SVG physical width/height/viewBox in mm, exact ink/label extents, source-provenance, diagram-kind Э1/Э3, font SHA and DRAFT status. PAINT could split a common SVG-on-page 1:1 composer from the E3-only ExternalWireSheet compatibility adapter. A4/A3 remain opt-in; clean bare SVG remains default; no clipping, scaling, synthetic signatures or silent re-routing.

**ESKD** independently validates actual normative requirements, separating MUST from editorial choices. Accepted Issue #69 evidence permits functional rectangles or UGO and requires each rectangle to have a name. 3mm ink clearance applies to neighboring parallel lines, not a universal port pitch; at stroke 0.35mm each, parallel centreline spacing is at least 3.35mm. Input-left/output-right is not universal. Arrow meanings and inter-sheet connectors have distinct applicability.

**QA** independently checks preservation of the directed logical graph, block name overflow, glyph/stroke clearances, crossings without connection, explicit fan-out, transform stability, text size, original print dimensions and font provenance. E3 electrical validators are forbidden from becoming E1 logical validators.

## Proposed future pipeline (no code)

1. ELEKTRIK validates E1 source blocks, ports, link directions and logical forks.
2. YGO 2 provides geometric functional block definitions and approved link arrow/branch drawing style.
3. PAINT computes actual stroked bounds and measured Type A h=3.5mm (project preference) multiline title rectangles, rejects overflow rather than shrinking.
4. E1 connection polylines are rendered as separate process-link layers; an unconnected crossing never becomes a physical junction.
5. PAINT exports bare SVG with e.g. functional-blocks, functional-links, arrowheads, block-titles layers; data-block-id and data-link-id preserve identities.
6. Optional A4/A3 composition only translates full ink bounds at 1:1 into a safe page area with independent empty form-1 decoration; avoids implicit E3 source reinterpretation.
7. Contract tests render the independent normative 7-block/9-link example from docs/standards/issue-69-e1-example.json without changing its logical meaning; then seek actual visual ESKD review.

## Blocking hazards / explicit decisions needed

- compose_formatted_sheet currently requires an ExternalWireSheet and verifies authored electrical SVG; it is NOT an E1-ready generic wrapper. Its accepted source SVG grammar permits line/rect/circle/limited arc paths and rejects general polyline/polygon, so new E1 arrows/multiline need a safe shared audit design first. Never bypass clipping checks.
- PillowTextMeasurer measures one line only: E1 multi-line text needs per-line ascent/descent, baseline calculation, inner padding and true glyph-ink overrun handling.
- A conservative body_keepout may be far from visible UGO strokes (L1 Issue #68). Separate painted strokes, selection hitboxes, text zones and connection corridors for E1 blocks.
- OpenGost Type A font must match measured font SHA at render/view time; fallback invalidates label metrics. 300DPI PNG is a raster-math proof, not a certified physical 1:1 plotter or KOMPAS paper test.
- A source rectangle may be a functional block, device contour or standard UGO; do not force every E1 rectangle dashed and do not use electrical catalog fake PartDefinition.

**Gate before any implementation:** ELEKTRIK signs off E1 typed IDs/directed ports/fan-out, YGO2 approves rendering geometry and arrowheads, ESKD signs off the applicable normative requirements, and MAIN 2 authorizes a specific shared API. This document makes no migration and changes no production E1 source.
