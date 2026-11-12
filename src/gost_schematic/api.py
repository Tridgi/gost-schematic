"""Small public facade for the experimental model and annotation subsystem."""

from gost_schematic.catalog.inductors import (
    AdjustmentKind,
    CoreKind,
    InductorDefinition,
    InductorSpec,
    build_inductor,
    load_inductor,
    parse_inductor_spec,
)
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part, parse_part
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
    component_graphic_obstacles,
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
from gost_schematic.model.part import PartDefinition, VoltageOrientationRule
from gost_schematic.model.pins import PhysicalPin, TerminalPolarity
from gost_schematic.model.potentials import NetPotential, PotentialScenario
from gost_schematic.model.quantities import Quantity, QuantityKind, Unit
from gost_schematic.rendering.annotation_svg import render_annotation_svg
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.standards.nominals import FormattedNominal, NominalRangeError, format_nominal
from gost_schematic.standards.type_a_font import (
    TypeAAngle,
    TypeAFontInspection,
    TypeAParameters,
    inspect_type_a_font,
)
from gost_schematic.validation.annotation_checks import (
    annotation_obstacles,
    validate_annotation_scene,
)
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.polarity_checks import (
    PolarityAssessment,
    PolarityStatus,
    assess_polarity,
    polarity_diagnostics,
)
from gost_schematic.validation.symbol_checks import validate_symbol

__all__ = [
    "AdjustmentKind",
    "ComponentNominalOverride",
    "CoreKind",
    "FormattedNominal",
    "InductorDefinition",
    "InductorSpec",
    "NetPotential",
    "NominalDisplayConfiguration",
    "NominalDisplayMode",
    "NominalDisplaySettings",
    "NominalRangeError",
    "PartDefinition",
    "PhysicalPin",
    "PillowTextMeasurer",
    "PinEscapeCorridor",
    "PolarityAssessment",
    "PolarityStatus",
    "PotentialScenario",
    "Quantity",
    "QuantityKind",
    "SchematicDocument",
    "SheetLabelProfile",
    "SheetLayout",
    "TerminalPolarity",
    "TextStyle",
    "TypeAAngle",
    "TypeAFontInspection",
    "TypeAParameters",
    "Unit",
    "VoltageOrientationRule",
    "annotation_obstacles",
    "assess_polarity",
    "bind_component_annotations",
    "build_inductor",
    "component_graphic_obstacles",
    "format_nominal",
    "inspect_type_a_font",
    "layout_sheet",
    "load_inductor",
    "load_part",
    "load_symbol",
    "obstacles_for_component",
    "parse_inductor_spec",
    "parse_part",
    "pin_corridors_for_component",
    "place_annotations",
    "polarity_diagnostics",
    "render_annotation_svg",
    "render_sheet_svg",
    "render_symbol_svg",
    "requests_for_component",
    "sheet_label_requests",
    "validate_annotation_scene",
    "validate_circuit",
    "validate_port_reservations",
    "validate_symbol",
    "validate_wire_clearance",
]
