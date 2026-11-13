"""Actual JSON-RPC-over-stdio MCP transport, discovery, PNG ImageContent."""

import asyncio
import base64
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ImageContent, TextContent


def test_mcp_stdio_image_content_and_tool_discovery(tmp_path):
    async def exercise():
        env = {**os.environ, "GSE_MCP_WORKSPACE": str(tmp_path)}
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "gost_schematic.mcp_server"], env=env,
        )
        async with stdio_client(params) as (read, write):  # noqa: SIM117
            async with ClientSession(read, write) as session:
                await session.initialize()
                available = await session.list_tools()
                names = {tool.name for tool in available.tools}
                required = {
                    "schematic_render_overview", "schematic_inspect_region",
                    "schematic_inspect_component", "schematic_inspect_connection",
                    "schematic_get_diagnostics",
                }
                assert required <= names
                calls = (
                    ("schematic_render_overview", {"project_ref": "six-part"}),
                    ("schematic_inspect_component", {
                        "project_ref": "six-part", "reference": "C3",
                    }),
                    ("schematic_inspect_region", {
                        "project_ref": "six-part", "selector": {"bbox_mm": [65, 35, 75, 45]},
                    }),
                    ("schematic_inspect_connection", {
                        "project_ref": "six-part",
                        "a": {"component": "R1", "number": "2"},
                        "b": {"component": "C3", "number": "1"},
                    }),
                )
                for name, args in calls:
                    result = await session.call_tool(name, args)
                    assert not result.isError, (name, result)
                    images = [item for item in result.content if isinstance(item, ImageContent)]
                    assert len(images) == 1, name
                    image = images[0]
                    assert image.mimeType == "image/png"
                    assert base64.b64decode(image.data).startswith(b"\x89PNG\r\n\x1a\n")
                    meta = [item for item in result.content if isinstance(item, TextContent)]
                    assert len(meta) == 1
                    data = json.loads(meta[0].text)
                    assert data["project_ref"] == "six-part"
                    assert data["mime_type"] == "image/png"
                    assert len(data["pixels"]) == 2
                diagnostic = await session.call_tool(
                    "schematic_get_diagnostics", {"project_ref": "six-part", "check": "all"},
                )
                assert not diagnostic.isError
                combined = " ".join(
                    item.text for item in diagnostic.content if isinstance(item, TextContent)
                )
                assert "ExternalWireGraph" in combined
                rejected = await session.call_tool(
                    "schematic_inspect_component", {
                        "project_ref": "six-part", "reference": "DOES_NOT_EXIST",
                    },
                )
                assert rejected.isError
                assert not any(isinstance(c, ImageContent) for c in rejected.content)

    asyncio.run(exercise())
