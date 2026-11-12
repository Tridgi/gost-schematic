"""Small public facade for the experimental model and annotation subsystem."""

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.engines.annotation.layout import (
    bind_component_annotations,
    obstacles_for_component,
    place_annotations,
    requests_for_component,
)
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.ports import PinEscapeCorridor, pin_corridors_for_component
from gost_schematic.engines.routing.clearance import (
    validate_port_reservations,
    validate_wire_clearance,
)
from gost_schematic.engines.sheet_layout import (
    SheetLabelProfile,
    SheetLayout,
    layout_sheet,
    sheet_label_requests,
)
from gost_schematic.model.annotations import TextStyle
from gost_schematic.model.document import SchematicDocument
from gost_schematic.model.nominal_display import (
    ComponentNominalOverride,
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.quantities import Quantity, QuantityKind, Unit
from gost_schematic.rendering.annotation_svg import render_annotation_svg
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.standards.nominals import FormattedNominal, NominalRangeError, format_nominal
from gost_schematic.validation.annotation_checks import (
    annotation_obstacles,
    validate_annotation_scene,
)
from gost_schematic.validation.symbol_checks import validate_symbol

__all__ = [
    "ComponentNominalOverride",
    "FormattedNominal",
    "NominalDisplayConfiguration",
    "NominalDisplayMode",
    "NominalDisplaySettings",
    "NominalRangeError",
    "PillowTextMeasurer",
    "PinEscapeCorridor",
    "Quantity",
    "QuantityKind",
    "SchematicDocument",
    "SheetLabelProfile",
    "SheetLayout",
    "TextStyle",
    "Unit",
    "annotation_obstacles",
    "bind_component_annotations",
    "format_nominal",
    "layout_sheet",
    "load_symbol",
    "obstacles_for_component",
    "pin_corridors_for_component",
    "place_annotations",
    "render_annotation_svg",
    "render_sheet_svg",
    "render_symbol_svg",
    "requests_for_component",
    "sheet_label_requests",
    "validate_annotation_scene",
    "validate_port_reservations",
    "validate_symbol",
    "validate_wire_clearance",
]
