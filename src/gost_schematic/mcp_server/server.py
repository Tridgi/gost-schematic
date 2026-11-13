"""MCP stdio server: native image/png blocks and independent circuit diagnostics."""

import base64
import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent, ToolAnnotations

from gost_schematic.agent_api import vision

mcp = FastMCP("gost-schematic-vision", instructions=(
    "Read-only electrical schematic inspection. Images are authentic SVG-derived PNG. "
    "Use returned diagnostics from Circuit and ExternalWireGraph, never infer nets "
    "from pixels. DRAFT status is not ГОСТ approval. No mutating tools exist."
))


READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
)


def _workspace() -> Path:
    """Environment is controlled by server operator, never by MCP tool arguments."""
    return Path(os.environ.get("GSE_MCP_WORKSPACE", os.getcwd())).resolve()


def _blocks(view: vision.View) -> list[ImageContent | TextContent]:
    return [
        ImageContent(type="image", mimeType="image/png",
                     data=base64.b64encode(view.png).decode("ascii")),
        TextContent(type="text", text=json.dumps(
            view.metadata, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )),
    ]


@mcp.tool(annotations=READ_ONLY)
def schematic_render_overview(
    project_ref: str = "six-part", mode: str = "clean", max_px: int = 1600,
) -> list[ImageContent | TextContent]:
    """Full six-part schematic as real SVG-derived PNG + view metadata."""
    return _blocks(vision.render_overview(project_ref, mode, max_px, _workspace()))


@mcp.tool(annotations=READ_ONLY)
def schematic_inspect_region(
    project_ref: str, selector: dict[str, Any], padding_mm: float = 3,
    target_dpi: int = 300, mode: str = "diagnostic",
) -> list[ImageContent | TextContent]:
    """High-resolution view by reference/pin/net/mm bounding box, re-rasterized from SVG."""
    return _blocks(vision.inspect_region(
        project_ref, selector, padding_mm, target_dpi, mode, _workspace(),
    ))


@mcp.tool(annotations=READ_ONLY)
def schematic_inspect_component(
    project_ref: str, reference: str, padding_mm: float = 3,
    target_dpi: int = 300, mode: str = "diagnostic",
) -> list[ImageContent | TextContent]:
    """Inspect physical symbol, pin positions, refdes and neighboring wires."""
    return _blocks(vision.inspect_component(
        project_ref, reference, padding_mm, target_dpi, mode, _workspace(),
    ))


@mcp.tool(annotations=READ_ONLY)
def schematic_inspect_connection(
    project_ref: str, a: dict[str, str], b: dict[str, str],
    padding_mm: float = 3, target_dpi: int = 250, mode: str = "diagnostic",
) -> list[ImageContent | TextContent]:
    """Inspect declared two-pin net with independent authored-wire diagnostics."""
    return _blocks(vision.inspect_connection(
        project_ref, a, b, padding_mm, target_dpi, mode, _workspace(),
    ))


@mcp.tool(annotations=READ_ONLY)
def schematic_get_diagnostics(
    project_ref: str = "six-part", check: str = "all",
) -> dict[str, Any]:
    """Structured ERC and authored conductor graph diagnostics, not image recognition."""
    return vision.diagnostics(project_ref, check)


@mcp.tool(annotations=READ_ONLY)
def schematic_list_views(project_ref: str = "six-part") -> dict[str, Any]:
    """Discover available read-only specimen views and current project revision."""
    return vision.list_views(project_ref)


def main() -> None:
    # Never log to stdout: reserved for MCP protocol frames.
    mcp.run(transport="stdio")
