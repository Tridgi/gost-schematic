"""Structural symbol checks; standard conformity must be separately certified."""
from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.geometry import Side
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus


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
    if symbol.status != SymbolStatus.APPROVED:
        issues.append(Diagnostic(
            "UNAPPROVED_SYMBOL", Severity.WARNING,
            f"Symbol {symbol.identifier} is {symbol.status.value}, not approved",
            symbol.identifier,
        ))
    return tuple(issues)
