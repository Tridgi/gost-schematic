"""Shared, typed geometric obstacles for annotation and routing engines."""

from dataclasses import dataclass

from gost_schematic.core.geometry import Box, Line
from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.model.circuit import PinRef


@dataclass(frozen=True, slots=True)
class BoxObstacle:
    identifier: str
    box: Box
    kind: str = "symbol"
    owner: str | None = None


@dataclass(frozen=True, slots=True)
class WireObstacle:
    identifier: str
    line: Line
    stroke_um: int = 300
    attached_pin: PinRef | None = None
    net_name: str | None = None

    def __post_init__(self) -> None:
        if type(self.stroke_um) is not int or self.stroke_um < 0:
            raise ValueError("Wire stroke must be non-negative micrometres")
        if self.net_name is not None and not self.net_name:
            raise ValueError("A wire net name must be non-empty when supplied")


def wire_intersects_box(wire: WireObstacle, box: Box) -> bool:
    # Expand by ceil(stroke / 2) to avoid missing odd-width stroke edges.
    return segment_intersects_box(wire.line, box.expanded((wire.stroke_um + 1) // 2))
