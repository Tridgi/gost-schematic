"""P1.1 real read-only MCP tools backed exclusively by typed ProjectService.

All tools require explicit host opt-in and a canonical UUID allowlist.
There are deliberately NO project creation, file write or topology edit tools.
"""
import base64
import json
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent, ToolAnnotations

from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.agent_project.design_assistant import (
    catalog_preview,
    catalog_search,
    tl494_alias,
    tl494_profile,
)
from gost_schematic.agent_project.read_access import ReadOnlyProjectAccess


def _safe_read[T](call: Callable[[], T]) -> T:
    """Only stable machine-readable failure code; no filesystem disclosure."""
    try:
        return call()
    except ProjectError as exc:
        raise ValueError(f"{exc.code}: saved-project read rejected") from None
    except (OSError, ValueError, TypeError):
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
    def schematic_catalog_search(semantic_query: str) -> dict[str, Any]:
        """Return EXACT installed variants, their physical pins, status and guards.

        A broad query returns multiple alternatives and never chooses a
        default capacitor/coil/transistor on the agent's behalf.
        """
        def work() -> dict[str, Any]:
            result = catalog_search(CatalogResolver(), semantic_query)
            if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 700_000:
                raise ProjectError("CATALOG_RESULT_TOO_LARGE", "Catalog cards exceed read budget")
            return result
        return _safe_read(work)

    @mcp.tool(annotations=read_only)
    def schematic_catalog_preview(part_id: str) -> list[ImageContent | TextContent]:
        """Render genuine installed UGO SVG/PNG sample; never fabricate glyph ink."""
        def work() -> list[ImageContent | TextContent]:
            svg, png, metadata = catalog_preview(CatalogResolver(), part_id)
            return [
                ImageContent(type="image", mimeType="image/png",
                             data=base64.b64encode(png).decode("ascii")),
                TextContent(type="text", text=json.dumps(
                    metadata, ensure_ascii=False, sort_keys=True,
                )),
                TextContent(type="text", text=svg),
            ]
        return _safe_read(work)

    @mcp.tool(annotations=read_only)
    def schematic_tl494_selection_profile() -> dict[str, Any]:
        """Exact Issue #107 BOM-to-UGO matrix; DRAFT and missing IC are explicit."""
        return _safe_read(lambda: tl494_profile(CatalogResolver()))

    @mcp.tool(annotations=read_only)
    def schematic_tl494_pin_alias(full_name: str) -> dict[str, Any]:
        """Only editorially pinned full-name to display-alias mapping."""
        return _safe_read(lambda: tl494_alias(full_name))

    @mcp.tool(annotations=read_only)
    def schematic_preflight_project(
        project_id: str, revision: str, profile: str = "none",
    ) -> dict[str, Any]:
        """Inspect immutable E3 physical topology and a *partial* print DRC.

        A printer-ready approval is never inferred from ERC+wire rules.
        """
        def work() -> dict[str, Any]:
            scope = ReadOnlyProjectAccess.from_environment()
            scope.require(project_id)
            report = scope.service.preflight_design(project_id, revision, profile=profile)
            if len(json.dumps(report, ensure_ascii=False).encode("utf-8")) > 700_000:
                raise ProjectError("PREFLIGHT_TOO_LARGE", "Preflight report exceeds MCP read budget")
            return report
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
