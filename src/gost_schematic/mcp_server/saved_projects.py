"""P1.1 real read-only MCP tools backed exclusively by typed ProjectService.

All tools require explicit host opt-in and a canonical UUID allowlist.
There are deliberately NO project creation, file write or topology edit tools.
"""
import base64
import json
from collections.abc import Callable
from typing import Any, TypeVar

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent, ToolAnnotations

from gost_schematic.agent_project.catalog import ProjectError
from gost_schematic.agent_project.read_access import ReadOnlyProjectAccess

_T = TypeVar("_T")


def _safe_read(call: Callable[[], _T]) -> _T:
    """Only stable machine-readable failure code; no filesystem disclosure."""
    try:
        return call()
    except ProjectError as exc:
        raise ValueError(f"{exc.code}: saved-project read rejected") from None
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("PROJECT_READ_FAILED: saved-project read rejected") from None


def register_saved_project_tools(
    mcp: FastMCP, read_only: ToolAnnotations,
) -> None:
    """Augment the existing six fixed-specimen MCP Vision tools in-place."""

    @mcp.tool(annotations=read_only)
    def schematic_list_projects() -> dict[str, Any]:
        """List only the host-authorized persisted E3 projects (default DENY)."""
        def work() -> dict[str, Any]:
            scope = ReadOnlyProjectAccess.from_environment()
            return scope.service.list_projects(scope.allowed_ids)
        return _safe_read(work)

    @mcp.tool(annotations=read_only)
    def schematic_open_project(
        project_id: str, revision: str | None = None,
    ) -> dict[str, Any]:
        """Open real saved E3 snapshot with verified immutable revision/physical catalog."""
        def work() -> dict[str, Any]:
            scope = ReadOnlyProjectAccess.from_environment()
            scope.require(project_id)
            return scope.service.open_project_info(project_id, revision)
        return _safe_read(work)

    @mcp.tool(annotations=read_only)
    def schematic_describe_project(
        project_id: str, revision: str | None = None,
    ) -> dict[str, Any]:
        """Full physical PinRef/Net/wire/junction and world-µm project evidence."""
        def work() -> dict[str, Any]:
            scope = ReadOnlyProjectAccess.from_environment()
            scope.require(project_id)
            description = scope.service.describe_project(project_id, revision)
            # Never truncate provenance or silently omit physical pins.
            if len(json.dumps(description, ensure_ascii=False).encode("utf-8")) > 700_000:
                raise ProjectError("DESCRIPTION_TOO_LARGE", "Project exceeds MCP read budget")
            return description
        return _safe_read(work)

    @mcp.tool(annotations=read_only)
    def schematic_validate_project(
        project_id: str, revision: str | None = None,
    ) -> dict[str, Any]:
        """Run actual Circuit/ExternalWireGraph ERC on the immutable saved revision."""
        def work() -> dict[str, Any]:
            scope = ReadOnlyProjectAccess.from_environment()
            scope.require(project_id)
            return scope.service.validate_project(project_id, revision)
        return _safe_read(work)

    @mcp.tool(annotations=read_only)
    def schematic_render_project(
        project_id: str, revision: str, mode: str = "clean",
        reference: str | None = None, target_dpi: int = 300,
        include_svg: bool = False,
    ) -> list[ImageContent | TextContent]:
        """Real stored-revision SVG-derived ImageContent and optional source SVG."""
        def work() -> list[ImageContent | TextContent]:
            scope = ReadOnlyProjectAccess.from_environment()
            scope.require(project_id)
            if type(include_svg) is not bool:
                raise ProjectError("INVALID_ARGUMENT", "include_svg must be boolean")
            view = scope.service.render_project(
                project_id, revision, mode=mode, reference=reference,
                target_dpi=target_dpi,
            )
            if include_svg and len(view.svg.encode("utf-8")) > 700_000:
                raise ProjectError("SVG_TOO_LARGE", "Source SVG exceeds MCP read budget")
            return [
                ImageContent(type="image", mimeType="image/png",
                             data=base64.b64encode(view.png).decode("ascii")),
                TextContent(type="text", text=json.dumps(
                    {**view.metadata, "svg_included": include_svg},
                    sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                )),
                *([TextContent(type="text", text=view.svg)] if include_svg else []),
            ]
        return _safe_read(work)
