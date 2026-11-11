"""Immutable annotation intent, positioning anchors and resolved text collision bounds."""

from dataclasses import dataclass
from enum import Enum

from gost_schematic.core.geometry import Box, Point
from gost_schematic.core.transforms import Transform


class AnnotationRole(str, Enum):
    REFDES = "refdes"
    VALUE = "value"
    PIN_NAME = "pin_name"
    PIN_NUMBER = "pin_number"
    DEVICE_NAME = "device_name"
    NOTE = "note"


class HorizontalAlign(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class VerticalAlign(str, Enum):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


@dataclass(frozen=True, slots=True)
class TextStyle:
    """Physical dimensions and exact resource of the face used for collision checks."""

    font_path: str
    font_family: str
    em_height_um: int = 3500
    clearance_um: int = 500

    def __post_init__(self) -> None:
        if not self.font_path or not self.font_family:
            raise ValueError("An explicit font path and SVG family are required")
        if type(self.em_height_um) is not int or self.em_height_um <= 0:
            raise ValueError("The font em height must be positive integer micrometres")
        if type(self.clearance_um) is not int or self.clearance_um < 0:
            raise ValueError("Clearance must be non-negative integer micrometres")


@dataclass(frozen=True, slots=True)
class Anchor:
    """Preferred location in local symbol coordinates; text remains upright."""

    at: Point
    horizontal: HorizontalAlign = HorizontalAlign.CENTER
    vertical: VerticalAlign = VerticalAlign.BOTTOM


@dataclass(frozen=True, slots=True)
class AnnotationSlot:
    """A symbol-local text placement policy, not the measured text rectangle."""

    key: str
    role: AnnotationRole
    candidates: tuple[Anchor, ...]
    reserved_region: Box | None = None
    required: bool = False

    def __post_init__(self) -> None:
        if not self.key or not self.candidates:
            raise ValueError("Annotation slot needs a key and at least one candidate")


@dataclass(frozen=True, slots=True)
class AnnotationRequest:
    owner: str
    slot: AnnotationSlot
    text: str
    style: TextStyle
    origin: Point = Point(0, 0)
    transform: Transform = Transform()
    locked: bool = False
    visible: bool = True

    def __post_init__(self) -> None:
        if not self.owner:
            raise ValueError("Annotation owner is required")
        if self.visible and not self.text:
            raise ValueError("Visible annotations cannot have empty text")


@dataclass(frozen=True, slots=True)
class MeasuredText:
    """Glyph ink box relative to the SVG baseline origin, in micrometres."""

    ink_box: Box
    advance_um: int


@dataclass(frozen=True, slots=True)
class AnnotationPlacement:
    owner: str
    key: str
    role: AnnotationRole
    text: str
    style: TextStyle
    baseline: Point
    ink_bounds: Box
    collision_bounds: Box
    reservation_bounds: Box | None
    candidate_index: int
