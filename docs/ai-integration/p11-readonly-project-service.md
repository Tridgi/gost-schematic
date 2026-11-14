# AI Integration P1.1 — immutable saved E3 projects (Issue #74)

**Implemented:** controlled trusted import, immutable saved E3 model, new-process
read, real SVG/PNG and ERC. **Not implemented:** arbitrary editable MCP tools,
multi-command transactions, existing-HEAD revision updates and automatic routing.
This implementation is independent of the accepted RFC PR #81 and P0 MCP PR #73.

## Responsibility boundary

- **SchematicProject:** typed immutable project with the existing real Circuit
  and ExternalWireGraph, exact physical PinRef and versioned canonical records.
- **CatalogResolver:** loads installed real PartDefinition and SymbolDefinition;
  locks each part/symbol SHA, revision, DRAFT status and full physical pin list.
- **ProjectRepository / LocalProjectStore:** read-only immutable revision
  lookup and exclusive atomic initial create; trusted workspace and UUID paths.
- **ProjectService:** sole application write authority. P1.1 exposes only
  import_circuit for trusted in-process engineering models, plus
  open_project/get_snapshot/validate_project/render_project for read-only use.
- **trusted_import.import_six_part:** one approved bootstrap from the authored
  six-part Circuit/ExternalWireGraph, not an MCP-supplied Python module.
  Opening a stored project in a new process imports no example source.
- **view.py:** restores genuine sheet geometry using render_sheet_svg plus
  saved junction markers and label positions, then rasterizes using resvg_py.

### Version identity and storage

Schema v1: SHA256 of domain separator GSE_PROJECT_V1 + NUL + canonical UTF-8
JSON. This persisted project SHA differs intentionally from the P0 fixed
specimen project_revision and is not the Git commit SHA.

Model stores stable component/net/wire/junction UUIDs and preserved wire
ordinal, exact integer micrometre coordinates, semantic member PinRefs,
physical part/symbol catalog digests and pinout, individual wire width,
transforms and nominals, static scenario and text label geometry.
No electrical connectivity is inferred from drawing ink or PNG.

Only initial import is a writable command in P1.1. A complete project
directory (immutable revision and HEAD generation=1) is staged inside the
trusted root with file fsync and atomically renamed to a new UUID path.
An identical idempotency key and source bytes returns the same immutable
receipt. A different payload under the same key returns
IDEMPOTENCY_CONFLICT; a new key for an existing ID returns
PROJECT_ALREADY_EXISTS. There is no existing-HEAD overwrite.

**CAS note:** this is strictly the create-if-absent case, expected HEAD absent.
General expected_revision + generation compare-and-swap, multi-command
transaction/journal, connected MoveComponent, and durability guarantees on
all filesystems are NOT implemented. They require later review and tests.

### Windows 11 smoke (actual checkout)

Workspace: C:\Users\User\Documents\gost-schematic-p11

~~~powershell
cd C:\Users\User\Documents\gost-schematic-p11
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev,mcp]"
.\.venv\Scripts\python.exe -m gost_schematic.agent_project --workspace .\output\p11-demo import-six-part --project-id 00000000-0000-4000-8000-000000000074 --idempotency-key 00000000-0000-4000-8000-000000000075
~~~

The first command prints exact revision SHA and generation=1.
Cold open and rendering in another Python process:

~~~powershell
.\.venv\Scripts\python.exe -m gost_schematic.agent_project --workspace .\output\p11-demo open 00000000-0000-4000-8000-000000000074
.\.venv\Scripts\python.exe -m gost_schematic.agent_project --workspace .\output\p11-demo render 00000000-0000-4000-8000-000000000074 <exact-revision-SHA>
~~~

SVG+PNG are confined to the derived artifacts/project-ID/revision directory.
The --workspace option is host-trusted **local CLI configuration**, never a
user-controlled MCP argument.

### Acceptance: authoritative engineering model

Stored and reconstructed: 6 real E3 components, 5 Circuit.Net definitions,
16 ExternalWireGraph segments, 3 exact explicit junctions, actual transforms,
optional potential scenario and 300-µm wire stroke proven by the original
renderer_wires adapter. C3 is capacitor.electrolytic, revision 1 DRAFT, with
physical PLUS pin 1 at (91000,80000) um and MINUS pin 2 at (109000,80000) um.
The older 18-wire archive is untouched.

Fresh-process validation: warnings UNAPPROVED_SYMBOL x6, no error codes.
Images are real SVG -> PNG, not AI illustrations. Labels remain sans-serif,
not proven GOST Type A; label checker is NOT_IMPLEMENTED.

### Security and future scope

- Open validates strict UUID, exact SHA256, canonical bytes, catalog lock,
  physical pin maps and real independent Circuit + graph diagnostics.
- Corrupted bytes, missing catalogue revision, invalid contacts, ambiguous
  junction ownership, existing project overwrite and path escape refuse.
- No direct JSON patch, arbitrary file paths, shell or Python execution
  through MCP, no invented transistor/IC pin assignments.
- Typed code supports a 40-pin physical definition, but the synthetic
  40-pin unit fixture is **not** an approved vendor package or datasheet.
- E1 StructuralDiagram and algorithm/ESPD Issue #82 remain distinct models.
- Existing P0 read-only six-part MCP tools are unchanged. Their fixed
  project_ref does not yet route to a saved ProjectService project; adding
  a revision-bound read-only MCP adapter is a separate approved gate.

### Verification

Tests in tests/agent_project/test_readonly_p11.py verify exact source/restore
model equality including PinRef/net/wire IDs, fresh Python subprocess with
imports of examples.* actively forbidden, true SVG/PNG and component zoom,
duplicate import idempotency, tampered immutable blobs, invalid 40pin,
physical pin/catalog lock, unmarked crossing and failed import rollback.

CI acceptance: Python 3.12 and 3.13 pytest, Ruff, dynamic DRAFT catalog
audit and wheel payload. The number 21 is Cycle 7's baseline, not a
permanent hard-coded target.


## Post-audit P1.1 hardening and independently reproducible agent pilot

The repository now has a **second engineering experiment independent of the
fixed six-part fixture**: `python -m examples.agent_project_p11
--workspace output/agent-project-p11`. It constructs R1/R2/C1 from the
**installed physical catalog**, looks up the exact real PinRef anchors,
and declares a two-contact `Circuit.Net("SIGNAL")`.

A first **unsaved** candidate accidentally places unconnected C1 on R2.
The script detects its real translated `body_keepout` overlap and
relocates **only the unconnected C1** before initial import, preserving
net membership. It requests a genuine two-pin route through the existing
`route_circuit_two_pins` (physical-pin-aware safe adapter), then imports
the resulting real `Circuit` and `ExternalWireGraph` via ProjectService.
No connected component is moved, no unsupported TOP/RIGHT branch router
is invoked and **no save-time mutation command** is implied.

ProjectService produces revision-bound SVG/PNG, while a fresh Python
interpreter reopens only the saved file, explicitly forbids any
`examples.*` import and produces a second SVG/PNG. The experiment
compares source/cold **complete serialized engineering model** plus
catalog lock and independently resolved physical pin positions, their
actual geometry, diagnostic revision SHA, source SVG SHA and PNG SHA.
The command prints a JSON evidence report; image paths derive exclusively
from ProjectService's trusted store and have no arbitrary output argument.

The source and new-process `model_manifest` in
`src/gost_schematic/agent_project/evidence.py` explicitly includes
the typed `SchematicProject.to_record()` and a separate
catalog-resolved list of every physical pin with its `number`,
`name`, `electrical_type`, `function`, `polarity` and
**exact integer-µm world coordinate**. A matching image alone is
insufficient for acceptance.

### Post-audit corrections

- The original local CLI wrote `output/artifacts/*` directly rather
  than through ProjectService. This was a boundary violation.
  `ProjectService.export_project_view()` now delegates artifact
  publication to scoped `LocalProjectStore.write_view()`. Files are
  staged and published under controlled
  `artifacts/<project-id>/<revision>/<view-id>/view.svg|view.png`;
  symlinks/junctions or mismatching replays refuse.
- The stored JSON parser now rejects duplicate object keys, binary
  floats, NaN and Infinity; reopens continue to require canonical bytes,
  SHA and schema, independently checked original-domain pin/net data.
- Workspace and project directories check for symlinks and Windows
  junctions before scoped lookup and artifact publication.
- A parameterized synthetic single-device 40/64-physical-pin test
  demonstrates serializable pin inventory, **not** vendor-source package
  integration. PR #97's independent `IcDeviceDefinition/IcPackage/IcUnit`
  DRAFT and its NC/multiunit constraints **cannot** be downcast into
  legacy PartDefinition without data loss; a reviewed kind-specific
  adapter and versioned schema migration are prerequisites.

### Actual native MCP inventory (P0 + P1.1 read-only)

The six existing P0 tools still serve ONLY the fixed six-part specimen:
**schematic_render_overview**, **schematic_inspect_region**,
**schematic_inspect_component**, **schematic_inspect_connection**,
**schematic_get_diagnostics**, and **schematic_list_views**. They are not
saved-project UUID tools.

The following five new MCP functions are registered by the P1.1 branch
via the existing stdio FastMCP server, backed only by typed ProjectService.
**All five deny access unless the host operator explicitly grants access.**

| Name | Read-only result |
| --- | --- |
| schematic_list_projects | Only already-saved allowed UUIDs (maximum 32), no arbitrary workspace scan |
| schematic_open_project | Verified project HEAD and exact revision, counts and generation |
| schematic_describe_project | Full canonical E3 model, physical pins and integer-um positions, actual Net/PinRef/wire/junction geometry and catalog SHA locks, bounded at 700 KB |
| schematic_validate_project | Actual independent Circuit and ExternalWireGraph diagnostics |
| schematic_render_project | Real revision-locked image/png ImageContent, SHA metadata, optional full SVG TextContent |

**Host trust and permissions:** These are disabled by default. Starting a
private, operator-controlled MCP stdio server requires these settings:

- GSE_P11_READONLY_ENABLED = 1
- GSE_P11_WORKSPACE = absolute path to an existing trusted workspace
- GSE_P11_ALLOWED_PROJECT_IDS = comma-delimited canonical UUID allowlist

The trusted workspace must contain an existing projects directory; redirected
symlink/junction workspace roots or ancestors are refused. Missing settings,
invalid UUIDs, unauthorized IDs and explicit relative paths fail closed.
No MCP argument can select a filesystem path, shell, script or raw JSON patch.
Unauthorized projects are not enumerated or disclosed as existing/nonexistent.
The MCP stdio server inherits the host OS identity; it is **not** a multi-user
authenticated public network service. Run it only from a trusted application.

Windows PowerShell operator example after the fixed six-part import:

~~~powershell
$env:GSE_P11_READONLY_ENABLED = "1"
$env:GSE_P11_WORKSPACE = (Resolve-Path .\output\p11-demo).Path
$env:GSE_P11_ALLOWED_PROJECT_IDS = "00000000-0000-4000-8000-000000000074"
.\.venv\Scripts\python.exe -m gost_schematic.mcp_server
~~~

The server speaks MCP over stdio; use a real MCP client to call tools.

**Actual transport tests:** tests/agent_project/test_mcp_saved_stdio.py
launches a new stdio MCP server through mcp.ClientSession and stdio_client,
discovers and calls all five saved-project read tools, verifies the
six-part model (6 components, 5 electrical Nets, 16 authored wires,
3 explicit junctions, C3 physical PLUS/MINUS contacts), direct-vs-MCP
SVG/PNG SHA and real image content, unchanged HEAD/blob, inaccessible
foreign UUID and fail-closed default permissions. It also confirms the
six original P0 tool names remain available.

**Independent agent-style experiment:** run

~~~powershell
.\.venv\Scripts\python.exe -m examples.agent_project_p11_mcp --workspace .\output\p11-agent-mcp
~~~

That program first authors a genuine R1/R2/C1 Circuit, PinRef and
two-contact Net using **trusted Python APIs**, performs safe *pre-save*
unconnected-part layout correction and source-backed routing, saves
an immutable E3 revision, reopens it in a cold process, and then uses a
real stdio MCP ClientSession to list, open, describe, validate and render
that stored revision. It checks complete typed physical and geometric
data, plus byte-identical native SVG and PNG hashes. A separate call
to the existing fixed P0 schematic_render_overview proves legacy MCP
Vision still works. It labels codex_cli_used=false: **a live Codex
model-generated tool call was not run or claimed**.

The existing trusted Python ProjectService import_circuit, open_project,
validate_project, render_project, export_project_view and related
operations remain useful, but **there are no MCP write tools**.
Independent MCP catalog browse/pinout/preview and all typed write
commands remain BLOCKED until separately accepted.

Real multi-unit IC and central PWM display angle preservation are only
specified, not enabled for schema v1, in the
[PR97/PAINT93 lossless design](../architecture/p11-ic-lossless-and-transaction-contract.md).

### Interactive editor Issue #100

See [the proposed editor-only hotspot contract](../architecture/issue-100-editor-projectservice-contract.md).
Hover is a pixel-space preview over authoritative real PinRefs/wire
endpoints, not a ГОСТ graphic or a mutation. An actual connection
requires future typed ProjectService transaction with expected revision,
CAS, rollback, independent ERC, and branch-aware safe routing. This
feature remains **not implemented** in P1.1.
