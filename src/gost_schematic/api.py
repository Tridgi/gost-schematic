"""Small public facade for the experimental model and annotation subsystem."""

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.engines.annotation.layout import (
    obstacles_for_component,
    place_annotations,
    requests_for_component,
)
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.routing.clearance import (
    validate_port_reservations,
    validate_wire_clearance,
)
from gost_schematic.engines.routing.ports import (
    PinEscapeCorridor,
    pin_corridors_for_component,
)
from gost_schematic.model.annotations import TextStyle
from gost_schematic.rendering.annotation_svg import render_annotation_svg
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.annotation_checks import (
    annotation_obstacles,
    validate_annotation_scene,
)
from gost_schematic.validation.symbol_checks import validate_symbol

__all__ = [
    "PillowTextMeasurer",
    "PinEscapeCorridor",
    "TextStyle",
    "annotation_obstacles",
    "load_symbol",
    "obstacles_for_component",
    "pin_corridors_for_component",
    "place_annotations",
    "render_annotation_svg",
    "render_symbol_svg",
    "requests_for_component",
    "validate_annotation_scene",
    "validate_port_reservations",
    "validate_wire_clearance",
    "validate_symbol",
]
