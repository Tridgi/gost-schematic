# ADR-0003: Text layout and collision-safe annotations

Status: implemented experimentally — **awaiting user visual approval** (2026-11-12).

## Decision

Text and its collision geometry are independent, first-class entities. Do not store
one manually fixed "label hitbox" on a symbol as if it remains correct for every
reference designator, value, font, or rotation.

Each annotation has:
- semantic role: refdes, value, pin_name, pin_number, device_name, note;
- anchor relative to its owning symbol/graphic unit, plus preferred positions
  and priority for fallback placement;
- text content (literal or binding to an instance/part field);
- typography style ID, height, orientation, alignment and line spacing;
- measured ink bounds (actual rendered glyphs, once font metrics are available);
- collision bounds = ink bounds + configured physical clearance;
- an optional *reserved region* for deterministic future text placement;
- a visibility flag and a lock/manual-override flag.

`SymbolDefinition` stores only reusable annotation slots and pin-label rules.
`ComponentInstance` supplies context-specific text such as "R1" and "10 kΩ".
The annotation/layout engine measures text with the exact font chosen for export
and creates `AnnotationPlacement` with immutable calculated bounds. If the text,
font or component pose changes, bounds MUST be recomputed and the affected routes
invalidated.

## Collision policy

- Text collision regions block unrelated symbols, foreign wires and other labels,
  subject to explicitly configured exception rules.
- A component's own leader line, its relevant pin stub, or deliberately adjacent
  symbol geometry may be exempt only by *named, localized* rules (not disabling
  all collisions for objects with the same owner).
- Pin escape corridors are protected separately so enlarged label regions cannot
  silently make a pin unroutable.
- Fixed labels and manually locked placements are hard constraints; optional
  labels may try alternate anchor slots before reporting conflicts.
- Diagnostic overlay displays separately: symbol body, body keepout, annotation
  ink bounds, annotation collision bounds, reserved text regions, and pin escape.
- Clean drawing must NEVER include diagnostic overlays.
- A layout that cannot meet its declared separation requirements reports a
  diagnostic, not a silent font shrink, overlap, or clipped label.

## Implementation boundaries

`model/annotations.py`: intent, roles, slot declarations.
`engines/annotation/`: font measurement, candidate positions, collision solving.
`core/geometry.py`: geometric bounds & transforms.
`standards/`: versioned font metrics and clearance requirements.
`rendering/`: display only resolved placements.
`validation/`: text-to-text, text-to-symbol and text-to-wire collision rules.

For multi-pin ICs, pin numbers and pin labels are measured before body sizing.
A global R-tree/STRtree-style index can accelerate collision candidates; exact
geometry determines final overlaps. Labels on rotated symbols maintain reading
orientation according to the active document/standards profile.

## Acceptance criteria

1. Changing R1 to R1234 changes measured bounds and triggers a collision check.
2. Changing a value from "1 Ω" to "100 kΩ" cannot silently overlap a neighbour.
3. Rotate/mirror operations preserve intended anchors and readable orientation.
4. Different allowed GOST font resources produce separately measured bounds.
5. Unroutable pin escape and unresolved label overlaps produce explicit errors.
6. Tests cover text-text, text-UGO, text-wire and reserved-region overlaps.

Initial implementation: semantic slots, user-provided font measuring, deterministic
candidate placement, text/symbol/pin-escape/wire collision checks, router-facing
obstacles, clean SVG and review-overlay SVG. Whole-sheet incremental layout,
licensed GOST font embedding, verified ГОСТ rules and end-to-end autorouting
remain separate future stages. No font or symbol has received GOST approval.
