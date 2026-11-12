"""Structural symbol checks; normative conformity must be separately certified.

A graphic connector must terminate on a drawn inward-facing lead. The
electrical circuit is separate: touching drawings do not establish a net.
"""

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import SIDE_VECTORS, Line, Point, Side, StyledLine
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus
from gost_schematic.validation.conductor_checks import inspect_conductor_topology


def _lead_endpoints(symbol: SymbolDefinition) -> dict[Point, tuple[Point, ...]]:
    """Index line terminal endpoints once: O(primitives + pins), not O(P × G)."""
    contacts: dict[Point, list[Point]] = {}
    for item in symbol.graphics:
        if isinstance(item, (Line, StyledLine)):
            contacts.setdefault(item.start, []).append(item.end)
            contacts.setdefault(item.end, []).append(item.start)
    return {point: tuple(targets) for point, targets in contacts.items()}


def validate_symbol(symbol: SymbolDefinition) -> tuple[Diagnostic, ...]:
    issues: list[Diagnostic] = []
    bounds = symbol.body_keepout
    terminals = _lead_endpoints(symbol)
    for pin in symbol.pins:
        wrong_side = {
            Side.LEFT: pin.at.x >= bounds.min_x,
            Side.RIGHT: pin.at.x <= bounds.max_x,
            Side.TOP: pin.at.y >= bounds.min_y,
            Side.BOTTOM: pin.at.y <= bounds.max_y,
        }[pin.side]
        if wrong_side:
            issues.append(Diagnostic(
                "PIN_NOT_EXPOSED", Severity.ERROR,
                f"Pin {pin.number} is not outside its declared {pin.side.value} side",
                symbol.identifier,
            ))
        neighbors = terminals.get(pin.at, ())
        if not neighbors:
            issues.append(Diagnostic(
                "PIN_GRAPHIC_DISCONNECTED", Severity.ERROR,
                f"Pin {pin.number} at {pin.at} has no drawn lead endpoint",
                symbol.identifier,
            ))
            continue
        outward = SIDE_VECTORS[pin.side]
        if not any(
            (target.x - pin.at.x) * outward.x +
            (target.y - pin.at.y) * outward.y < 0
            for target in neighbors
        ):
            issues.append(Diagnostic(
                "PIN_LEAD_NOT_INWARD", Severity.ERROR,
                f"Pin {pin.number} has lead geometry but none points into the symbol",
                symbol.identifier,
            ))
    if symbol.conductor_topology is not None:
        issues.extend(inspect_conductor_topology(symbol).diagnostics)
    if symbol.status != SymbolStatus.APPROVED:
        issues.append(Diagnostic(
            "UNAPPROVED_SYMBOL", Severity.WARNING,
            f"Symbol {symbol.identifier} is {symbol.status.value}, not approved",
            symbol.identifier,
        ))
    return tuple(issues)
