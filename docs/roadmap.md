# Roadmap and user review gates

## Stage 0 — foundation (in progress)
- Typed immutable models, exact geometry, JSON catalog schema v1.
- Symbol SVG inspection, explicit diagnostic codes, CI tests and architecture ADRs.
- Review architecture with the user before declaring stage 0 approved.

## Stage 0.5 — annotation collision subsystem (experimental)
- Separate text ink, collision and reserved rectangles, exact font measuring.
- Collision tests versus symbols, wire segments and protected pin corridors.
- Reference/name/value slots with candidate placement and debug SVG overlays.
- User visual review and real ГОСТ font verification still pending.

## Stage 0.6 — typed nominal formatting (experimental)
- SI Decimal values, GOST 2.702-2011 §5.3.20 compact resistor/capacitor notation.
- Full-unit mode and visibility setting with document/per-component overrides.
- Explicit warnings for unsupported ranges and unverified literal text.
- Rebinding labels, hitboxes and routing obstacles when text display changes.
- JSON persistence and CLI/CI sample SVGs; review and licensed GOST font pending.

## Stage 0.7 — sheet-level annotation placement (experimental)
- Refdes above UGO or, if obstructed, to its right (ГОСТ 2.702-2011 §5.3.11).
- Visible nominal below by configurable drafting preference; text remains upright
  under orthogonal symbol rotation and mirror transforms.
- Avoid labels overlapping foreign component keepouts, pin exits or existing wires.
- Diagnose overlapping symbols, duplicated references and blocked escape corridors.
- Provide clean/review multi-element SVG regression fixtures and manual review gate.

## Stage 0.8 — external Type A and capacitor drafts (experimental)
- Read ГОСТ 2.304-81 type A standard metrics, calibrate true capital letter h.
- Store SHA-256 of loaded font, detect changes and document renderer fallback risk.
- Support upright + true italic input faces without synthetically skewing fonts.
- Install actual SIL OFL licensed OpenGOST font for CI preview, without vendoring binary.
- Draft fixed and polarized capacitor UGO with exact plate size/gap, unique pins,
  independent bodies, label zones and rotation/collision tests.
- Rasterize font-accurate clean/diagnostic SVG samples for user approval.
- Block annotation collisions with **all drawn UGO strokes**, including terminal leads.
- Still pending: user approval and formal glyph/width/slant validation.

## Stage 0.9 — physical terminal polarity and conservative ERC
- Immutable, typed physical terminal polarity, separate from graphic labels.
- Versioned part JSON for fixed and polarized capacitors.
- Opt-in voltage orientation rule, not applied to diodes implicitly.
- Static operating-point checks with signed Decimal voltages and explicit
  common references; reversed=error, unknown=warning, zero=informational.
- Test rotation/mirror invariance and mismatched +/- labels.
- CI publishes a reviewable JSON with forward/reversed/unknown examples.
- Not implemented: circuit simulation, multi-scenario transient proof,
  capacitor voltage rating checks, or wiring autorouting.

## Stage 0.10 — parametric inductors/chokes (experimental)
- 15 separately versioned JSON family profiles based on ГОСТ 2.723-68.
- Real semicircle and per-core styled line primitives across all renderers.
- Air / ferro / ferrite / gapped / magnetodielectric, Cu, trims,
  taps, sliders, variable modifiers and related choke profiles.
- Physical contacts START, END and actual TAP/SLIDER pins in same factory.
- Font-audited type A SVG clean/review gallery and JSON manifest.
- Still draft: exact KOMPAS/ГОСТ symbol approval, transformer coupling,
  multi-phase reactors, variometers, goniometers and coaxial choke topology.

## Stage 1 — approved standard UGO
- Resistor family, capacitor family, precise stroke/lettering constraints.
- Reference comparisons from KOMPAS and normative verification.
- Individual golden-vector tests and manually signed approvals.

## Stage 2 — parameterized IC generator
- Pin/port definitions, functional grouping, dynamic body dimensions, typography,
  routing escape lanes, multiple graphic units per physical device.

## Stage 3 — electrical network engine
- Strong electrical rule checking, references, connectivity and persistent netlist.

## Stage 4 — placement/routing
- Constraint-based placement, orthogonal routes, branch trees, crossing and junction
  rules, geometry vs netlist equivalence, incremental recomputation.

## Stage 5 — production documents
- SVG/PDF outputs, GOST font licensing/embedding, sheets, element lists and BOM,
  document templates, KOMPAS interoperability where supported.

Every stage is gated by tests and explicit user inspection; no auto-approval.
