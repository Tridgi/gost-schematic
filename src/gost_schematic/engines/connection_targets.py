"""Editor-only physical connection targets for any E3 component, including XP/XS.

No green marker is part of SymbolDefinition.graphics or a clean SVG/PDF.
PAINT may draw targets in a separate interactive/debug layer ONLY.
Coordinates and sides are derived from the real GraphicPin after D4, not from
text, visual labels, net names or a speculative manufacturer package.
"""

from dataclasses import dataclass

from gost_schematic.core.geometry import Point, Side
from gost_schematic.model.circuit import ComponentInstance, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition


@dataclass(frozen=True, slots=True)
class DiagnosticConnectionTarget:
    """One real physical contact, at an exact transformed endpoint (µm)."""

    pin_ref: PinRef
    symbol_id: str
    point: Point
    side: Side
    physical_name: str


def connection_targets(
    instance: ComponentInstance,
    part: PartDefinition,
    symbol: SymbolDefinition,
) -> tuple[DiagnosticConnectionTarget, ...]:
    """Return ALL physical pins, preserving numbers/roles through D4.

    Raises rather than silently inventing a missing terminal or merging
    multiple contacts that happen to carry the same net label.
    """
    if instance.part_id != part.identifier or part.symbol_id != symbol.identifier:
        raise ValueError("Instance/part/symbol identity mismatch")
    real = {item.number: item for item in part.pins}
    depicted = {item.number: item for item in symbol.pins}
    if len(real) != len(part.pins) or set(real) != set(depicted):
        raise ValueError("PhysicalPin and GraphicPin inventory mismatch")
    origin = instance.origin
    transform = instance.transform
    results = tuple(
        DiagnosticConnectionTarget(
            pin_ref=PinRef(instance.reference, number),
            symbol_id=symbol.identifier,
            point=transform.apply(depicted[number].at) + origin,
            side=transform.side(depicted[number].side),
            physical_name=physical.name,
        )
        for number, physical in ((pin.number, pin) for pin in part.pins)
    )
    if len({target.point for target in results}) != len(results):
        raise ValueError("Multiple physical contacts overlap after D4")
    return results
