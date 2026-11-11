# Stage 0 architecture — contracts

## Dependency direction

- `core` has no dependencies on higher-level packages.
- `model` depends only on `core`.
- `catalog` maps versioned files to immutable `model` definitions.
- `validation` reads the `model`; it does not modify the drawing or electrical netlist.
- `rendering` projects immutable geometry into a target format; it never routes wires.
- Future `generators`, `engines/placement`, and `engines/routing` consume the same contracts and do not embed symbol-specific drawing code.
- Future `standards` rules are explicit, versioned, auditable inputs; a filename or text citation alone does not constitute compliance.

## Distinct identities

1. `PartDefinition`: a physical or logical device, identified by part ID, with a list of physical pin numbers and electrical functions.
2. `SymbolDefinition`: a reusable graphic representation and its physical pin mappings. A single physical part can eventually have several multi-unit graphic views.
3. `ComponentInstance`: a placed occurrence with a reference designator, position and transform.
4. `Net`: the semantic electrical connectivity of physical pin references; its membership cannot be inferred from wire crossings.
5. `Route` (future): the computed wire geometry, validated against net membership.

**Current limitation:** exactly one graphic symbol unit per part. Multi-unit components are deferred until a dedicated mapping model is specified and tested. Do not work around this by duplicating physical pins.

## Geometry contract

- Internal unit: exact integer micrometres.
- Public catalog length unit: millimetres, representable to 0.001 mm.
- Local origin belongs to each reusable symbol; instance translation and 90-degree transforms are applied once, centrally.
- `body_keepout` prevents routing through the body; it is not the same as the visual bounds, text extent or pin-escape geometry.
- Catalog drawing primitives are immutable value objects. Complex arc/text primitives, exact glyph metrics, stroked collision bounds, escape corridors and spatial indexes are not implemented yet.
- `GraphicPin.at` is the external connection coordinate; `GraphicPin.side` is its expected approach direction.
- Rotations are clockwise in the downward-positive Y coordinate convention used by SVG.

## Stable public boundary

`gost_schematic.api` is the entrypoint intended for future compatibility.
Other modules are internal, and their contracts remain experimental until version 1.0.

## Explicit non-goals for stage 0

- A*-based routing, layout optimization, ERC beyond basic reference/net consistency.
- ГОСТ-certified symbol dimensions.
- Fonts, PDF export, CAD import, full documentation templates.
- Automatically approving user-submitted drawings.
