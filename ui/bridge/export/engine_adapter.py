"""The actual Python renderer remains the canonical source of UGO and wire ink."""

from __future__ import annotations

from typing import Any

from ui.bridge.export.canonical import ExportRequest, ExportResult, export


def export_existing_external_wire_graph(
    circuit: Any,
    graph: Any,
    symbols_by_part: dict[str, Any],
    style: Any,
    measurer: Any,
    request: ExportRequest,
) -> ExportResult:
    """Render validated explicit authored graph using the existing engine.

    This is the working Python-engine bridge while the ProjectFileV2 → Circuit
    adapter is being developed by #122. The graph validator, not SVG, owns
    physical PinRef and Net topology. Existing layout must pass before export.

    Strict font policy may fail if visible text is not converted to vector
    glyph outlines. Such a failure is intentional for non-preview output.
    """
    from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet

    rendered = render_external_wire_sheet(
        circuit,
        graph,
        symbols_by_part,
        style,
        measurer,
        diagnostic=False,
        strict_layout=True,
    )
    return export(rendered.svg.encode("utf-8"), request)
