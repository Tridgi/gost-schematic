# ADR-0009 — Explicit graphic pin attachment and stroke-aware extents

**Status:** experimental implementation, pending user review, 2026-11-12.

## Problem

Previously a `GraphicPin` could sit outside the UGO's `body_keepout`
but not terminate on any drawn lead. The validator checked its location,
not the connection to a graphic stroke. In addition, `SymbolDefinition.bounds`
and component-overlap checks did not include the widths of unusually thick
magnetic-core strokes. The ferrite line could therefore render beyond a
reported bounding box.

The adjustable sliding-contact indicator additionally contained a visible
gap between its line and arrow tip. That is a concrete rendering defect,
not a normative choice.

## Decision

1. The external graphic pin must coincide exactly with an endpoint of a
   `Line` or `StyledLine`. At least one incident line must proceed in the
   direction opposite the declared `GraphicPin.side`. Otherwise
   `PIN_GRAPHIC_DISCONNECTED` or `PIN_LEAD_NOT_INWARD` is an **error**.
   Endpoints are indexed once per symbol for linear-time validation.
2. Pin numbering, circuit membership and physical `TerminalFunction`
   are not deduced from drawn geometry. This validator only checks visible
   contact attachment.
3. Expose a new `SymbolDefinition.stroked_bounds` that accounts for
   every primitive's actual line width. Keep legacy `bounds` unchanged for
   compatibility. Use `stroked_bounds` for physical extent inspection,
   symbol collision checks and sheet label placement.
4. The sliding-contact arrow's stem now runs all the way to its tip
   (which meets the winding apex). Add a regression test.
5. Only the worst-case axis-aligned bounding rectangle is used for now.
   It intentionally errs on the side of false-positive collision warnings
   rather than risk overlapping printed strokes.

## Limitations / follow-ups

- This does not prove every line inside a symbol is electrically connected
  to its intended circuit element, and it must not transform a drawing into
  a netlist. A future semantic primitive/layer topology is needed for that.
- A bare pin whose coordinates touch a body outline without an explicit
  graphical lead is rejected in the current external-pin contract. Should
  future device UGO need boundary contacts, add a distinct validated contact
  attachment type, not a silent exception.
- No systematic exact curve-to-curve collision solver is claimed.
- Approval against source ГОСТ drawings and user KOMPAS reference remains
  mandatory before changing the catalog status to `approved`.

## Tests

See `tests/test_graphic_integrity.py`, and the deterministic
`scripts/audit_symbol_catalog.py` CI artifact.
