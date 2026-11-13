"""Experimental E1 functional graph; not Circuit, PinRef or a conductive net."""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from gost_schematic.core.geometry import Box, Point, Side


def _identifier(value: str, label: str) -> None:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be a nonempty, trimmed string")


class PortDirection(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"


@dataclass(frozen=True, slots=True)
class FunctionalBlock:
    """Immutable functional rectangle in integral micrometres, not electrical UGO."""

    id: str
    name: str
    origin: Point
    width_um: int
    height_um: int

    def __post_init__(self) -> None:
        _identifier(self.id, "block ID")
        _identifier(self.name, "block name")
        if "\r" in self.name or "\n" in self.name:
            raise ValueError("Block name is a semantic single line; presentation owns linebreaks")
        if not isinstance(self.origin, Point):
            raise TypeError("block origin must be an integer-micrometre Point")
        if (type(self.width_um) is not int or self.width_um <= 0
                or type(self.height_um) is not int or self.height_um <= 0):
            raise ValueError("block dimensions must be positive integer micrometres")

    @property
    def bounds(self) -> Box:
        return Box(
            self.origin.x, self.origin.y,
            self.origin.x + self.width_um, self.origin.y + self.height_um,
        )


@dataclass(frozen=True, slots=True)
class PortRef:
    """Stable structural endpoint, never a physical electrical PinRef."""

    block_id: str
    port_id: str

    def __post_init__(self) -> None:
        _identifier(self.block_id, "port reference block ID")
        _identifier(self.port_id, "port reference port ID")


@dataclass(frozen=True, slots=True)
class BlockPort:
    """Declared side anchor, automatic ordered slot or exact relative Fraction."""

    block_id: str
    id: str
    side: Side
    direction: PortDirection
    position: Fraction | None = None

    def __post_init__(self) -> None:
        _identifier(self.block_id, "port block ID")
        _identifier(self.id, "port ID")
        if not isinstance(self.side, Side):
            raise TypeError("port side must be a Side enum")
        if not isinstance(self.direction, PortDirection):
            raise TypeError("port direction must be PortDirection enum")
        value = self.position
        if type(value) is int:
            value = Fraction(value)
            object.__setattr__(self, "position", value)
        if value is not None:
            if not isinstance(value, Fraction):
                raise TypeError("port position must be Fraction/int/None, not float")
            if not 0 <= value <= 1:
                raise ValueError("relative port position must lie in [0,1]")

    @property
    def ref(self) -> PortRef:
        return PortRef(self.block_id, self.id)


@dataclass(frozen=True, slots=True)
class FunctionalLink:
    """Source-to-target directed function/process connection; no conductive join."""

    id: str
    source: PortRef
    target: PortRef

    def __post_init__(self) -> None:
        _identifier(self.id, "link ID")
        if not isinstance(self.source, PortRef) or not isinstance(self.target, PortRef):
            raise TypeError("links must terminate on declared PortRef values")


@dataclass(frozen=True, slots=True)
class StructuralDiagram:
    """Schema v1, independently versioned; port declaration order is significant."""

    blocks: tuple[FunctionalBlock, ...]
    ports: tuple[BlockPort, ...]
    links: tuple[FunctionalLink, ...]
    schema_version: int = 1
    diagram_type: str = "E1"

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported experimental E1 schema_version")
        if type(self.diagram_type) is not str or self.diagram_type != "E1":
            raise ValueError("Structural diagrams require diagram_type E1")
        if not isinstance(self.blocks, tuple) or any(
            not isinstance(item, FunctionalBlock) for item in self.blocks
        ):
            raise TypeError("blocks must be tuple[FunctionalBlock,...]")
        if not isinstance(self.ports, tuple) or any(
            not isinstance(item, BlockPort) for item in self.ports
        ):
            raise TypeError("ports must be tuple[BlockPort,...]")
        if not isinstance(self.links, tuple) or any(
            not isinstance(item, FunctionalLink) for item in self.links
        ):
            raise TypeError("links must be tuple[FunctionalLink,...]")
