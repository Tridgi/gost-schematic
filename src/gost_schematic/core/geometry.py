"""Immutable, unit-safe 2D geometry in integer micrometres."""
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int

    def __post_init__(self) -> None:
        if type(self.x) is not int or type(self.y) is not int:
            raise TypeError("Point coordinates must be integer micrometres")

    def __add__(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y)


@dataclass(frozen=True, slots=True)
class Box:
    min_x: int
    min_y: int
    max_x: int
    max_y: int

    def __post_init__(self) -> None:
        if any(type(n) is not int for n in
               (self.min_x, self.min_y, self.max_x, self.max_y)):
            raise TypeError("Box coordinates must be integer micrometres")
        if self.min_x >= self.max_x or self.min_y >= self.max_y:
            raise ValueError("Box must have strictly positive area")

    def includes(self, point: Point) -> bool:
        return (self.min_x <= point.x <= self.max_x
                and self.min_y <= point.y <= self.max_y)

    def contains_interior(self, point: Point) -> bool:
        return (self.min_x < point.x < self.max_x
                and self.min_y < point.y < self.max_y)

    def overlaps(self, other: "Box") -> bool:
        """Touching only at a shared edge is not an area overlap."""
        return (self.min_x < other.max_x and self.max_x > other.min_x
                and self.min_y < other.max_y and self.max_y > other.min_y)

    def expanded(self, margin: int) -> "Box":
        if type(margin) is not int or margin < 0:
            raise ValueError("Margin must be a non-negative integer")
        return Box(self.min_x - margin, self.min_y - margin,
                   self.max_x + margin, self.max_y + margin)

    def translated(self, delta: Point) -> "Box":
        return Box(self.min_x + delta.x, self.min_y + delta.y,
                   self.max_x + delta.x, self.max_y + delta.y)


class Side(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


SIDE_VECTORS = {
    Side.LEFT: Point(-1, 0),
    Side.RIGHT: Point(1, 0),
    Side.TOP: Point(0, -1),
    Side.BOTTOM: Point(0, 1),
}


@dataclass(frozen=True, slots=True)
class Line:
    start: Point
    end: Point

    def __post_init__(self) -> None:
        if self.start == self.end:
            raise ValueError("Zero-length line is not allowed")


@dataclass(frozen=True, slots=True)
class Rectangle:
    box: Box


@dataclass(frozen=True, slots=True)
class Circle:
    center: Point
    radius: int

    def __post_init__(self) -> None:
        if type(self.radius) is not int or self.radius <= 0:
            raise ValueError("Circle radius must be positive micrometres")


@dataclass(frozen=True, slots=True)
class Semicircle:
    """True 180-degree arc; bulge determines the visible half of the circle."""

    center: Point
    radius: int
    bulge: Side

    def __post_init__(self) -> None:
        if type(self.radius) is not int or self.radius <= 0:
            raise ValueError("Semicircle radius must be positive integer micrometres")
        if not isinstance(self.bulge, Side):
            raise TypeError("Arc bulge must be a Side")


@dataclass(frozen=True, slots=True)
class StyledLine:
    """Core material strokes can differ in width or dash pattern from winding."""

    start: Point
    end: Point
    stroke_width_um: int
    dash_pattern_um: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.start == self.end:
            raise ValueError("Zero-length styled line")
        if type(self.stroke_width_um) is not int or self.stroke_width_um <= 0:
            raise ValueError("Styled line width must be positive")
        if any(type(item) is not int or item <= 0 for item in self.dash_pattern_um):
            raise ValueError("Dash pattern must be positive integer micrometres")
        if len(self.dash_pattern_um) % 2 != 0:
            raise ValueError("Dash pattern must have even number of entries")


Primitive = Line | Rectangle | Circle | Semicircle | StyledLine


def primitive_stroke_width(primitive: Primitive, default_um: int) -> int:
    """Physical stroke width for collision margins and SVG rendering."""
    return primitive.stroke_width_um if isinstance(primitive, StyledLine) else default_um



def primitive_bounds(primitive: Primitive) -> Box:
    if isinstance(primitive, Rectangle):
        return primitive.box
    if isinstance(primitive, Circle):
        x, y, radius = primitive.center.x, primitive.center.y, primitive.radius
        return Box(x - radius, y - radius, x + radius, y + radius)
    if isinstance(primitive, Semicircle):
        x, y, r = primitive.center.x, primitive.center.y, primitive.radius
        if primitive.bulge == Side.TOP:
            return Box(x - r, y - r, x + r, y + 1)
        if primitive.bulge == Side.BOTTOM:
            return Box(x - r, y, x + r, y + r)
        if primitive.bulge == Side.LEFT:
            return Box(x - r, y - r, x + 1, y + r)
        return Box(x, y - r, x + r, y + r)
    if isinstance(primitive, StyledLine):
        return primitive_bounds(Line(primitive.start, primitive.end))
    if isinstance(primitive, Line):
        a, b = primitive.start, primitive.end
        # A degenerate dimension is legal for a line, unlike a Box.
        return Box(min(a.x, b.x), min(a.y, b.y),
                   max(a.x, b.x) + 1, max(a.y, b.y) + 1)
    raise TypeError(f"Unsupported primitive type: {type(primitive)!r}")


def enclosing_box(boxes: tuple[Box, ...]) -> Box:
    if not boxes:
        raise ValueError("At least one box is required")
    return Box(min(box.min_x for box in boxes), min(box.min_y for box in boxes),
               max(box.max_x for box in boxes), max(box.max_y for box in boxes))
