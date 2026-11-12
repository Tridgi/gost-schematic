"""Structural symbol checks; normative conformity must be separately certified.

The graphical connector must genuinely terminate on a drawn inward-facing
lead. Physical/semantic connection is separately represented by the netlist.
"""

from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import SIDE_VECTORS, Line, Side, StyledLine
from gost_schematic.model.pins import GraphicPin
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus


def _inward_lead_projection(pin: GraphicPin, lead: Line | StyledLine) -> int | None:
    """Projection of the lead leaving a contact onto its outward normal.

    A negative result means the drawn stub enters the symbol; zero is
    tangent. A contact strictly inside a primitive is not a valid terminal
    endpoint: the catalogue must express a real connector stub.
    """
    if lead.start == pin.at:
        other = lead.end
    elif lead.end == pin.at:
        other = lead.start
    else:
        return None
    outward = SIDE_VECTORS[pin.side]
    return (other.x - pin.at.x) * outward.x + (other.y - pin.at.y) * outward.y


def validate_symbol(symbol: SymbolDefinition) -> tuple[Diagnostic, ...]:
    issues: list[Diagnostic] = []
    bounds = symbol.body_keepout
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
        projections = [
            direction
            for item in symbol.graphics
            if isinstance(item, (Line, StyledLine))
            if (direction := _inward_lead_projection(pin, item)) is not None
        ]
        if not projections:
            issues.append(Diagnostic(
                "PIN_GRAPHIC_DISCONNECTED", Severity.ERROR,
                f"Pin {pin.number} at {pin.at} has no drawn lead endpoint",
                symbol.identifier,
            ))
        elif min(projections) >= 0:
            issues.append(Diagnostic(
                "PIN_LEAD_NOT_INWARD", Severity.ERROR,
                f"Pin {pin.number} has lead geometry but none points into the symbol",
                symbol.identifier,
            ))
    if symbol.status != SymbolStatus.APPROVED:
        issues.append(Diagnostic(
            "UNAPPROVED_SYMBOL", Severity.WARNING,
            f"Symbol {symbol.identifier} is {symbol.status.value}, not approved",
            symbol.identifier,
        ))
    return tuple(issues)
