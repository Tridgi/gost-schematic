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
