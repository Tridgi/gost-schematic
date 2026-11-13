"""Trusted local bootstrap: fixed authored six-part E3 source only.

Never expose this function as an MCP command accepting a user-supplied module.
A cold project open MUST NOT import this module or any examples/ source.
"""
import uuid
from pathlib import Path

from .service import ProjectService, ProjectSnapshot


def import_six_part(
    workspace: Path, *, project_id: str, idempotency_key: str,
) -> ProjectSnapshot:
    from examples.review_end_to_end_circuit import definitions, renderer_wires, scenarios

    case = next(item for item in scenarios() if item.identifier == "valid")
    source_parts, source_symbols = definitions()
    service = ProjectService.for_workspace(workspace)
    for component in case.circuit.components:
        source_part = source_parts[component.part_id]
        part, symbol = service.catalog.resolve(component.part_id)
        if part != source_part or symbol != source_symbols[source_part.symbol_id]:
            raise ValueError("CATALOG_REVISION_MISMATCH: imported source is not installed catalog")
    strokes = tuple(item.stroke_um for item in renderer_wires(case.graph))
    return service.import_circuit(
        case.circuit, case.graph, project_id=project_id,
        idempotency_key=idempotency_key, title="Six-part authored E3 specimen",
        strokes_um=strokes, scenario=case.scenario,
        source_tag="fixed-six-part-model-v1",
    )


def new_ids() -> tuple[str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4())
