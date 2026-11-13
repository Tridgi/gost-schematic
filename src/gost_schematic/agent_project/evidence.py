"""Deterministic, source-model-only evidence for saved engineering E3 projects.

This manifest is not a simulated netlist: it includes the entire typed
canonical project record and independently resolves physical PinRef positions
from real installed catalog definitions. Never derive topology from SVG.
"""
from typing import Any

from .catalog import CatalogResolver
from .contracts import SchematicProject


def model_manifest(project: SchematicProject, catalog: CatalogResolver) -> dict[str, Any]:
    parts, symbols = catalog.verify(list(project.catalog_lock))
    resolved = []
    for component in project.circuit.components:
        part = parts[component.part_id]
        symbol = symbols[part.symbol_id]
        positions = component.pin_positions(symbol)
        resolved.append({
            "component_reference": component.reference,
            "part_id": component.part_id,
            "physical_pins": [{
                "number": pin.number,
                "name": pin.name,
                "electrical_type": pin.electrical_type.value,
                "function": pin.function.value,
                "polarity": pin.polarity.value,
                "world_um": [positions[pin.number].x, positions[pin.number].y],
            } for pin in part.pins],
        })
    return {
        "schema_version": 1,
        "project_revision": project.revision,
        "canonical_typed_project": project.to_record(),
        "resolved_physical_contacts": resolved,
        "component_count": len(project.circuit.components),
        "net_count": len(project.circuit.nets),
        "wire_count": len(project.graph.segments),
        "junction_count": len(project.graph.junctions),
    }
