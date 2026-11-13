"""Isolated experimental functional structural scheme (Э1) graph.

No physical electrical parts, conductive nets or public application API.
"""

from gost_schematic.structural.model import (
    BlockPort,
    FunctionalBlock,
    FunctionalLink,
    PortDirection,
    PortRef,
    StructuralDiagram,
)
from gost_schematic.structural.serialization import structural_from_json, structural_to_json
from gost_schematic.structural.validation import (
    resolve_port_positions,
    validate_port_clearances,
    validate_structural_diagram,
)

__all__ = [
    "BlockPort",
    "FunctionalBlock",
    "FunctionalLink",
    "PortDirection",
    "PortRef",
    "StructuralDiagram",
    "resolve_port_positions",
    "structural_from_json",
    "structural_to_json",
    "validate_port_clearances",
    "validate_structural_diagram",
]
