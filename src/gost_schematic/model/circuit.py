"""Netlist is semantic connectivity, never inferred from line intersections."""
from dataclasses import dataclass, field

from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.symbol import SymbolDefinition


@dataclass(frozen=True, slots=True)
class ComponentInstance:
    reference: str
    part_id: str
    origin: Point = field(default_factory=lambda: Point(0, 0))
    transform: Transform = field(default_factory=Transform)

    def __post_init__(self) -> None:
        if not self.reference or not self.part_id:
            raise ValueError("Reference and part_id must be non-empty")

    def pin_positions(self, symbol: SymbolDefinition) -> dict[str, Point]:
        return {
            pin.number: self.transform.apply(pin.at) + self.origin
            for pin in symbol.pins
        }


@dataclass(frozen=True, slots=True)
class PinRef:
    reference: str
    number: str

    def __post_init__(self) -> None:
        if not self.reference or not self.number:
            raise ValueError("PinRef must name a component and physical pin")


@dataclass(frozen=True, slots=True)
class Net:
    name: str
    members: tuple[PinRef, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.members:
            raise ValueError("Net name and members must be supplied")


@dataclass(frozen=True, slots=True)
class Circuit:
    components: tuple[ComponentInstance, ...]
    nets: tuple[Net, ...]
