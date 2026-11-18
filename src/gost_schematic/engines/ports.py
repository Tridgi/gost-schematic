"""Shared pin-escape reservations for annotation, positioning and routing.

An escape corridor is a RESERVED AREA, not a drawn conductor and not a generic
obstacle exemption. Only the conductor leaving the corresponding connector
outwards along the pin axis can use it.
"""

from dataclasses import dataclass

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.model.circuit import ComponentInstance, PinRef
from gost_schematic.model.symbol import SymbolDefinition


@dataclass(frozen=True, slots=True)
class PinEscapeCorridor:
    """An axis-aligned reservation, referenced by physical connector identity."""

    pin: PinRef
    contact: Point
    side: Side
    box: Box

    @property
    def identifier(self) -> str:
        return f"{self.pin.reference}.pin.{self.pin.number}"

    def admits(self, wire_start: Point, wire_end: Point, attached_pin: PinRef | None) -> bool:
        """Admit only the outward wire segment *physically attached* to this contact.

        A conductor from the same component, or one on the same net, must not
        receive blanket access. The appropriate segment must terminate at the
        precise pin position and leave along the outward normal.
        """
        if attached_pin != self.pin:
            return False
        if wire_start == self.contact:
            target = wire_end
        elif wire_end == self.contact:
            target = wire_start
        else:
            return False

        dx = target.x - self.contact.x
        dy = target.y - self.contact.y
        return {
            Side.LEFT: dy == 0 and dx < 0,
            Side.RIGHT: dy == 0 and dx > 0,
            Side.TOP: dx == 0 and dy < 0,
            Side.BOTTOM: dx == 0 and dy > 0,
        }[self.side]


def pin_corridors_for_component(
    symbol: SymbolDefinition,
    component: ComponentInstance,
    *,
    length_um: int = 1800,
    width_um: int = 800,
) -> tuple[PinEscapeCorridor, ...]:
    """Build connector escape reservations, after orientation and translation."""
    if type(length_um) is not int or length_um <= 0:
        raise ValueError("Port corridor length must be a positive integer in µm")
    if type(width_um) is not int or width_um <= 0:
        raise ValueError("Port corridor width must be a positive integer in µm")

    low_half = width_um // 2
    high_half = width_um - low_half
    result: list[PinEscapeCorridor] = []
    for pin in symbol.pins:
        position = component.transform.apply(pin.at) + component.origin
        side = component.transform.side(pin.side)
        if side == Side.LEFT:
            bounds = Box(position.x - length_um, position.y - low_half,
                         position.x, position.y + high_half)
        elif side == Side.RIGHT:
            bounds = Box(position.x, position.y - low_half,
                         position.x + length_um, position.y + high_half)
        elif side == Side.TOP:
            bounds = Box(position.x - low_half, position.y - length_um,
                         position.x + high_half, position.y)
        else:
            bounds = Box(position.x - low_half, position.y,
                         position.x + high_half, position.y + length_um)
        result.append(PinEscapeCorridor(
            PinRef(component.reference, pin.number), position, side, bounds,
        ))
    return tuple(result)
