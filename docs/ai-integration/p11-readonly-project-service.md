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
