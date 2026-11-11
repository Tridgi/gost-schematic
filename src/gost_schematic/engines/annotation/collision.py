"""Compatibility re-exports for shared geometry and obstacle contracts."""

from gost_schematic.core.intersections import segment_intersects_box
from gost_schematic.model.obstacles import BoxObstacle, WireObstacle, wire_intersects_box

__all__ = [
    "BoxObstacle",
    "WireObstacle",
    "segment_intersects_box",
    "wire_intersects_box",
]
