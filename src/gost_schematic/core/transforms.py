"""Discrete orthogonal transforms; rotation is clockwise on SVG-like y-down axes."""
from dataclasses import dataclass

from gost_schematic.core.geometry import (
    SIDE_VECTORS,
    Box,
    Circle,
    Line,
    Point,
    Primitive,
    Rectangle,
    Semicircle,
    Side,
    StyledLine,
)


@dataclass(frozen=True, slots=True)
class Transform:
    rotation: int = 0
    mirror_x: bool = False

    def __post_init__(self) -> None:
        if type(self.rotation) is not int or self.rotation not in (0, 90, 180, 270):
            raise ValueError("Rotation must be exactly 0, 90, 180 or 270 degrees")
        if type(self.mirror_x) is not bool:
            raise TypeError("mirror_x must be a boolean")

    def apply(self, point: Point) -> Point:
        x, y = (-point.x if self.mirror_x else point.x), point.y
        if self.rotation == 90:
            return Point(-y, x)
        if self.rotation == 180:
            return Point(-x, -y)
        if self.rotation == 270:
            return Point(y, -x)
        return Point(x, y)

    def side(self, side: Side) -> Side:
        transformed = self.apply(SIDE_VECTORS[side])
        return next(name for name, vector in SIDE_VECTORS.items() if vector == transformed)

    def box(self, box: Box) -> Box:
        corners = (Point(box.min_x, box.min_y), Point(box.max_x, box.min_y),
                   Point(box.min_x, box.max_y), Point(box.max_x, box.max_y))
        points = tuple(self.apply(p) for p in corners)
        return Box(min(p.x for p in points), min(p.y for p in points),
                   max(p.x for p in points), max(p.y for p in points))


    def primitive(self, primitive: Primitive, origin: Point | None = None) -> Primitive:
        """Transform graphic primitives centrally, including arc bulge direction."""
        origin = origin if origin is not None else Point(0, 0)

        def at(point: Point) -> Point:
            return self.apply(point) + origin

        if isinstance(primitive, Line):
            return Line(at(primitive.start), at(primitive.end))
        if isinstance(primitive, StyledLine):
            return StyledLine(
                at(primitive.start), at(primitive.end),
                primitive.stroke_width_um, primitive.dash_pattern_um,
            )
        if isinstance(primitive, Rectangle):
            return Rectangle(self.box(primitive.box).translated(origin))
        if isinstance(primitive, Circle):
            return Circle(at(primitive.center), primitive.radius)
        if isinstance(primitive, Semicircle):
            return Semicircle(
                at(primitive.center), primitive.radius, self.side(primitive.bulge)
            )
        raise TypeError(f"Unsupported geometry primitive: {type(primitive)!r}")
