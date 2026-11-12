"""A physical pin number is not a drawing coordinate or an electrical net."""
from dataclasses import dataclass
from enum import Enum

from gost_schematic.core.geometry import Point, Side


class ElectricalType(str, Enum):
    PASSIVE = "passive"
    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    POWER_INPUT = "power_input"
    POWER_OUTPUT = "power_output"
    OPEN_COLLECTOR = "open_collector"
    UNSPECIFIED = "unspecified"


class TerminalPolarity(str, Enum):
    """Physical terminal meaning, separate from the schematic pin's visual label."""

    NONE = "none"
    POSITIVE = "positive"
    NEGATIVE = "negative"


class TerminalFunction(str, Enum):
    """Physical pin function, independent of label, polarity and driver type."""

    GENERAL = "general"
    WINDING_START = "winding_start"
    WINDING_END = "winding_end"
    WINDING_TAP = "winding_tap"
    WINDING_SLIDER = "winding_slider"


@dataclass(frozen=True, slots=True)
class PhysicalPin:
    number: str
    name: str
    electrical_type: ElectricalType
    polarity: TerminalPolarity = TerminalPolarity.NONE
    function: TerminalFunction = TerminalFunction.GENERAL

    def __post_init__(self) -> None:
        if not isinstance(self.number, str) or not self.number.strip():
            raise ValueError("Physical pin number must be non-empty")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Physical pin name must be non-empty")
        if not isinstance(self.electrical_type, ElectricalType):
            raise TypeError("electrical_type must be an ElectricalType")
        if not isinstance(self.polarity, TerminalPolarity):
            raise TypeError("polarity must be a TerminalPolarity")
        if not isinstance(self.function, TerminalFunction):
            raise TypeError("function must be a TerminalFunction")


@dataclass(frozen=True, slots=True)
class GraphicPin:
    number: str
    at: Point
    side: Side
    label: str = ""

    def __post_init__(self) -> None:
        if not self.number.strip():
            raise ValueError("Graphic pin needs a physical pin number")
