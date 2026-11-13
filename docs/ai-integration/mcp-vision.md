# AI Integration: authentic SVG → PNG feedback over MCP (Issue #65)

**Status:** read-only MVP. Built on Issue #64's boundaries, not a general project
editor. The known project is `six-part` (R1, R2, C1, C2, C3, L1). The live
review specimen has C3 origin `(100000, 80000)` µm, **16** authored wire
segments, 5 Circuit nets and 3 explicitly marked junctions.

## Install and launch (Windows PowerShell)

Run from the repository checkout, not an unrelated working directory:

```powershell
cd C:\path\to\gost-schematic
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[mcp,dev]"
.\.venv\Scripts\python.exe -m gost_schematic.mcp_server
```

The final command is a long-lived **stdio** server; it prints no interactive
prompt and reserves stdout for MCP frames. Do not use unauthenticated HTTP.
`mcp>=1.17,<2` supplies the Python SDK; `resvg_py>=0.5,<1` supplies a
Windows-compatible raster backend that needs no Cairo DLL. Optional installed
CairoSVG is a fallback. The first working implementation was smoke-tested with
`mcp 1.30.0`, `resvg_py 0.5.0`, Python 3.13.

## Codex CLI config.toml example

Use the *absolute path to the virtualenv interpreter on the machine running
Codex*, and replace the working directory with the matching repo checkout:

```toml
[mcp_servers.gost_schematic_vision]
command = "C:\\Users\\User\\Documents\\gost-schematic-ai-mcp\\.venv\\Scripts\\python.exe"
args = ["-m", "gost_schematic.mcp_server"]
cwd = "C:\\Users\\User\\Documents\\gost-schematic-ai-mcp"
startup_timeout_sec = 20

[mcp_servers.gost_schematic_vision.env]
GSE_MCP_WORKSPACE = "C:\\Users\\User\\Documents\\gost-schematic-ai-mcp"
```

The working directory makes the fixed `examples.review_end_to_end_circuit`
module available, and `GSE_MCP_WORKSPACE` identifies the server-authorized
artifact directory. Tool callers **cannot** supply file paths. Generated
review artifacts are written only to `artifacts/ai-mcp/view-<hash>.{png,svg}`
inside that workspace. Set this directory to the trusted checkout and protect
it from untrusted modifications. There is no separate network listener.

After configuring, run `codex mcp list`, then open Codex and use `/mcp`
to confirm discovery. Codex's image display behavior can vary by surface;
the same tool response includes the exact local PNG/SVG artifact locations as
fallback. A *real MCP SDK stdio client* is exercised in
`tests/agent_api/test_mcp_stdio.py`; it asserts an actual `ImageContent`,
not a path/base64 string masquerading as a screenshot.

## Tools and response contract

| Tool | Read-only input | Output |
| --- | --- | --- |
| `schematic_render_overview` | project, `clean\|diagnostic`, max 64–4096 px | authentic PNG + JSON metadata |
| `schematic_inspect_region` | selector by reference, physical pin, net or 4 mm coordinates | native SVG viewport PNG at 72–600 DPI |
| `schematic_inspect_component` | reference (e.g. C3), padding, DPI, mode | symbol + physical pins + refdes + nearby wires |
| `schematic_inspect_connection` | two physical PinRefs belonging to same declared net | PNG + net/member/graph diagnostics |
| `schematic_get_diagnostics` | `erc\|geometry\|labels\|all` | model-driven JSON diagnostics |
| `schematic_list_views` | project ref | available view types and SHA revisions |

The four image-returning tools each return two MCP content blocks:
(1) `ImageContent(type=image, mimeType=image/png, data=<base64 PNG bytes>)`;
(2) `TextContent` containing compact JSON with `project_revision`,
`view_id`, `geometry_sha256`, `catalog_sha256`, `bbox_mm`, `pixels`,
`effective_dpi`, rasterizer, provenance and warnings.

Example inputs:

```json
{"project_ref":"six-part","selector":{"reference":"C3"},"padding_mm":4,"target_dpi":500,"mode":"diagnostic"}
```

```json
{"project_ref":"six-part","selector":{"bbox_mm":[65,35,75,45]},"target_dpi":500}
```

```json
{"project_ref":"six-part","a":{"component":"R1","number":"2"},"b":{"component":"C3","number":"1"}}
```

To test an intentional short, use the fixed negative scenario
`six-part:short_at_unmarked_crossing` and
`schematic_get_diagnostics(check="geometry")`. The error
`WIRE_NET_SHORT` must come from `validate_external_wires`, not image
classification. Raw SVG is never treated as netlist authority.

## Rendering and safety

- SVG starts at `render_sheet_svg` with genuine transformed symbol
  primitives and original authored `ExternalWireGraph` segments.
- Exactly specified millimetre viewBox is applied **before** rasterization;
  there is no pixel-space crop of a thumbnail. `resvg_py` 0.5 requires
  pixel-valued width/height in its *temporary raster source*; the saved
  canonical SVG retains millimetre width/height and the same metric viewBox.
- Bounds are integer-micrometre-aligned. Padding is 2–10 mm; image dimensions
  are capped at 4096 per side and 12 million pixels, PNG response 8 MB.
  Refdes, pin, net, and bbox input validation fail closed with stable error codes.
- The current specimen refdes are `sans-serif`; **OpenGost Type A font
  provenance is not established**. The service reports this fact explicitly.
  This is geometry review, not a normative ГОСТ approval or a font conformity test.
- The labels diagnostic is explicitly *unimplemented*, rather than a fabricated
  pass. Certain clearance/label design checks remain outside the MVP.
- The read-only adapter accepts no arbitrary filename, Python expression,
  command or user-supplied SVG. No direct project mutation, persistence or
  network transport is exposed.

## Reproduce PR artifacts and tests

```powershell
python -m examples.review_ai_mcp_vision
python -m pytest tests/agent_api -q
python -m pytest -q
ruff check .
python scripts/audit_symbol_catalog.py
python -m build --wheel
python scripts/verify_wheel_payload.py dist
```

The proof files in `docs/assets/ai-mcp` are from the live renderer:
`six-part-overview.png`, `c3-at-80mm.png`, and
`unmarked-wire-crossing.png`. Each has canonical cropped SVG and JSON
metadata. `diagnostics.json` is authoritative model output.

## Next transaction boundary (Issue #64 / P1, NOT implemented)

Future `ProjectService` should accept only a persisted `SchematicProject`
snapshot with `expected_revision_sha` and a typed command
(`AddComponent`, `MoveComponent`, `ConnectPins`, `DisconnectPins`,
`RouteTwoPins`). Revision mismatch must return `CONFLICT`; validators
must enforce physical pins, nets, keepouts, junctions and symbol editions
atomically and roll back on any failure. Each successful revision would then
feed the existing read-only viewport service and return a before/after diff.

Do not implement raw JSON patching, Python execution or silent routing;
do not claim the mutation half of the agent loop works until the separate
command-service PR is independently reviewed and approved.
