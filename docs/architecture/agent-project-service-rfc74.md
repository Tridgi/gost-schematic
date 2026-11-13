# RFC #74 — Agent Project Service: revisioned, transactional schematic editing

**State:** PROPOSED / Gate 1 technical review; documentation only. MCP Vision PR #73 is merged and remains the accepted read-only P0 foundation.
**Parent:** Issue #64. **Target:** `integration/stage0-12`.
**No production model, public API, electrical catalog, physical-pin, or router changes.**
**Decision requested:** MAIN 2, ELEKTRIK, PAINT, YGO and QA architecture approval before any P1 implementation. The separate implementation PR starts with read-only persistence, not arbitrary write MCP.

## Architecture clarification after MAIN 2 review

This parent RFC is complemented by three **normative design annexes**. Where a
preliminary interface, hashing suggestion or storage example below differs,
the explicit Annex A contract controls and must be approved by the coordinator:

- [Annex A — precise v1 type, persistence, CAS, command, error and revision contracts](agent-project-service-contract-v1.md)
- [Annex B — component, import and transaction diagrams](agent-project-service-diagrams.md)
- [Annex C — first *read-only* persisted E3 implementation gate](../plans/agent-project-service-readonly-roundtrip.md)
- [Later, gated connected-C3 editing pilot](../plans/agent-project-service-c3-pilot.md)

Key decision: **the initial P1.1 implementation is controlled import →
canonical save → cold reopen → real Circuit/ExternalWireGraph projection →
revision-bound SVG/PNG → independent diagnostics**. No generic editing.
The inherited P0 computed six-part project_revision is retained only as
migration provenance, not reused as v1 content SHA. Wire stroke is known
from renderer_wires(): 300 µm for the fixed specimen; future imports must
prove their own style provenance.

Domain kind isolation: E3 uses electrical Circuit/ExternalWireGraph;
E1 after its independent model RFC uses StructuralDiagram; algorithmic
control-flow diagrams under Issue #82 use AlgorithmDiagram. Neither
alternative kind is represented as fake electrical PartDefinition/PinRef.

## 1. Non-negotiable data flow

```text
Codex / other MCP agent
  -> typed MCP schemas + capability/scope + idempotency key
    -> ProjectService (sole authority for editing)
      -> workspace repository (immutable snapshots and CAS revision head)
      -> command validator / draft builder / transaction journal
      -> real PartDefinition+SymbolDefinition, Circuit, ExternalWireGraph
      -> physical-pin, routing and annotation validators
      -> atomic commit of new revision OR unchanged old revision on failure
    -> revision-bound render_sheet_svg and diagnostic report
      -> authentic ImageContent image/png + canonical SVG + metadata/diff
```

The image is an observation, **never evidence of electrical net membership**.
`Circuit` is the semantic authority; `ExternalWireGraph` contains explicitly
authored conductor segments and junctions. The MCP server is an adapter, not a
domain model. A skill can recommend commands but cannot override safety gates.

## 2. Storage and canonical project format

Propose a JSON UTF-8 `*.gseproj` with `schema_version: 1`, at most one
project document per allowlisted project ID. JSON schema v1 will be generated
and checked independently before enabling writes. The public format must not
serialize opaque Python `repr`, timestamps, arbitrary Python class names,
or SVG-derived electrical nets. Every coordinate and print stroke is an
**integer micrometre**. No floats or locale-dependent decimal formatting.

| Section | Required persisted content |
| --- | --- |
| `identity` | `project_id` UUID, `diagram_kind` (`E3` for this phase), title, schema version |
| `catalog_lock` | catalog manifest SHA, `part_id`, symbol ID, exact symbol revision, per-definition SHA |
| `components[]` | stable instance ID, unique refdes, part ID, exact origin µm, transform (quarter turns, mirror), nominal as typed unit/quantity |
| `nets[]` | stable semantic net ID/name; exact set of `{component_id,pin_number}` physical PinRefs |
| `routes[]` | stable route/branch ID, declared owner net ID, explicit physical attachment refs, ordered segments with stroke µm |
| `junctions[]` | stable junction ID, exact point µm, net ID; connected only if explicitly declared |
| `annotations` | anchored/free text, explicit text position, collision reservation, font family and actual font SHA |
| `document` | sheet size/profile, drawing units, standards provenance, nominal style, source constraints |
| `provenance` | engine/projection version, font/source manifests, migration record, DRAFT normative status |

**Model projection:** a strict adapter constructs the *existing* immutable
`Circuit` and `ExternalWireGraph` from this format, preserving all physical
pin numbers. Stable wire-path IDs live in ProjectService storage only; the
existing `WireSegment` and `ExternalWireGraph` types are **not modified**.
The projection never creates a junction from an incidental crossing. Unknown
or future schema versions are rejected, not silently rewritten.

Canonical serialization uses sorted object keys, explicit array ordering
(where ordering is semantic), Unicode NFC, no NaN/Infinity, stable integer
units, reproducible line endings and no volatile timestamps in the revision.
`revision_sha256 = SHA256(canonical_domain_document + pinned catalog/font
manifest)`. Signed/provenance events may have timestamps in a separate
append-only audit log, **not** in the content hash. A generation counter and
commit UUID prevent ABA even if identical contents reappear.

The initial persisted specimen must be imported using an explicit,
one-time versioned exporter from the **live** six-part authored model.
Do **not** read/execute arbitrary Python examples specified by clients.
Migration gate: 6 components, 5 semantic nets, 3 explicit junctions, 16
authored wire segments, C3 at (100000,80000) µm; archived 18-wire C3
fixture remains untouched. After an authorized reroute, wire count is not
necessarily 16: invariant is *electrical topology and explicit junction
semantics*, not identical bend count.

## 3. ProjectService boundaries

Proposed interfaces (final names subject to coordinator approval):

```python
ProjectService.create_project(CreateProject, auth_scope) -> ProjectSnapshot
ProjectService.open_project(project_id, revision="head") -> ProjectSnapshot
ProjectService.get_snapshot(project_id, revision) -> ProjectSnapshot
ProjectService.validate(project_id, revision, checks) -> ValidationReport
ProjectService.apply_transaction(
    project_id, expected_revision, expected_generation,
    idempotency_key, commands: tuple[TypedCommand, ...],
    *, dry_run=False, permission: WriteScope,
) -> TransactionResult
ProjectService.save_project(project_id, expected_revision) -> SaveResult
ProjectService.render(project_id, revision, ViewRequest) -> BoundImageArtifact
```

No MCP endpoint exposes a raw `patch_json`, `exec_python`, generic
`write_file`, arbitrary path, SVG data upload, hidden write-on-preview,
or authorless `approved=true`.

### Typed command contracts

| Proposed MCP name | Required validated fields | Semantics / safety |
| --- | --- | --- |
| `schematic_create_project` | workspace scope, diagram kind E3, title, fixed standards/catalog profile, request ID | Allocate stable ID and empty revision, no implicit circuit/net |
| `schematic_open_project` | project ID, optional exact revision | Read-only access; reject path traversal, schema/catalog drift |
| `schematic_get_snapshot` | project ID, revision, optional narrow selectors | Page bounded components/nets/wires, include all revision hashes |
| `schematic_add_component` | part ID + locked revision, unique refdes, typed nominal, origin µm, transform | Physical contacts only from catalog; no automatic connections |
| `schematic_move_component` | component ID/refdes, target origin or exact delta µm, route disposition | Reject detached wires; no implicit reroute; requires safe batch or dry-run |
| `schematic_set_transform` | component ID, quarter turns 0/90/180/270, mirror flag | Recompute *graphic positions* of fixed physical pins; reject disconnected wiring |
| `schematic_set_nominal` | component ID, typed quantity kind/value/unit | Never reinterpret physical electrical net or catalog definition |
| `schematic_connect_pins` | exact physical PinRef pair, explicit target net ID or new net ID, topology policy | Semantic net edit only when explicit; net merge requires separate deliberate command and approval |
| `schematic_disconnect_pins` | exact PinRef, expected owning net/branch ID | No accidental renumber, foreign pin touch or orphan conductor |
| `schematic_route_connection` | net ID, exact source/target PinRef, locked stroke/clearance/grid/bounds, approved route strategy | Only reviewed safe adapter; reject unsupported multi-terminal case |
| `schematic_validate_project` | immutable revision, check scope | Independent ERC + authored-wire + collision + provenance reports |
| `schematic_save_project` | project ID, expected current revision and generation | Durable atomic write; read-after-write proof and content SHA |
| `schematic_apply_transaction` (additional) | project ID, expected revision/generation, idempotency key, ordered typed operations | Single atomic multi-command boundary; no invalid intermediate snapshot leaked |
| `schematic_render_*` | project ID, **exact revision**, selector, mode, dpi | Reuses P0 real ImageContent; never substitutes a new head silently |

Each write is a convenience facade to `apply_transaction` with one
typed command, **not a second mutable backend**. If moving a component
requires jointly updating connected routes, the agent must submit a single
batch. An unaccompanied move that breaks attachment is rejected with
`ROUTE_REPAIR_REQUIRED` and the old snapshot stays authoritative.

### Request / response envelope (v1)

```json
{
  "api_version": 1,
  "project_id": "c4d3d8a1-754f-4eae-9cf9-73fdc58e7c03",
  "expected_revision": "sha256:<64 lowercase hex chars>",
  "expected_generation": 7,
  "idempotency_key": "client-created-unique-uuid",
  "dry_run": false,
  "commands": [
    {"type": "MoveComponent", "component_id": "cmp-c3",
     "delta_um": {"x": 0, "y": 5000}},
    {"type": "RepairRoutes", "strategy": "approved_branch_adapter",
     "affected_route_ids": ["route-top-c3", "route-right-c3"]}
  ]
}
```

`RepairRoutes` is **proposed only** and must remain disabled until the
branch-aware safety adapter is designed, tested and approved. The example is
a contract sketch, not executable API or a claim that rerouting works.

Successful `TransactionResult` carries:
`api_version`, `project_id`, `before_revision`, `after_revision`,
`before_generation`, `after_generation`, `command_ids`,
`idempotency_key`, `semantic_diff`, `geometry_diff`,
`validation_before`, `validation_after`, and revision-bound
`before_view` / `after_view` artifact handles (each with
`ImageContent`, `geometry_sha256`, `png_sha256`, `bbox_mm`,
`pixel_size`, `rasterizer`, exact catalog/font hashes and warnings).
No stale images: every render must load the requested immutable revision
or return `REVISION_NOT_FOUND`. Model revision does not change for
a clean vs diagnostic viewport, but the view hash does.

## 4. Atomicity, concurrency, idempotency and persistence

1. Validate authorization, input schema, diagram kind, workspace scope,
   catalog lock, expected revision+generation and idempotency key before
   allocating or mutating any persisted state.
2. Acquire project-specific serialization lock or database CAS; open immutable
   head; compare request to durable idempotency journal.
3. Replay of the **same key + exact request fingerprint** returns the
   already-committed result with identical revision and artifacts. Same
   key with different payload returns `IDEMPOTENCY_CONFLICT`.
4. Build a **copy-on-write in-memory draft**, apply typed commands in order.
   No shared mutable singleton Circuit, catalog or external graph.
5. Run all preconditions, allowlisted safe routing (where supported), ERC,
   physical pin ownership, graph topology, wire clearance/keepouts,
   missing junction, text reservation and symbol-provenance validators.
6. On a rejected command or validator failure: discard draft and return
   typed `REJECTED` / `BLOCKED`; no partial route, index, revision,
   junction or physical net mutation is published.
7. On success: deterministically serialize immutable blob to a temp file
   *inside* workspace; fsync file; atomically replace head pointer under CAS
   and fsync directory where supported. Reopen and verify canonical SHA,
   Circuit nets, PinRefs, graph, catalog and saved revision.
8. Write a separate audit event with command fingerprint, origin (client
   permission identity), before/after SHA and diagnostic summary. MCP
   session ID is **not** the transaction ID. Rendering can be queued later,
   but the response must never claim a new PNG exists before successful
   materialization.
9. Multiple agents racing on the same expected revision: exactly one wins;
   other receives `REVISION_CONFLICT`, current head summary and refresh
   action, no rebasing of electrical edits automatically.
10. Atomic response with retained `before` snapshot supports exact
    before/after diff; idempotency journal survives process restart.

For OS differences, durability claims and Windows ReplaceFile/rename
semantics need targeted tests. Where atomic directory fsync cannot be
guaranteed, return an explicitly weaker durability level rather than
claim guaranteed crash consistency.

## 5. Explicit safety invariants

- Catalog `PartDefinition` owns *physical* pin number and polarity.
  Transform/rotation changes only graphic positions, not pin identities.
  C3 pin 1 stays PLUS, pin 2 stays MINUS.
- Every semantic PinRef belongs to at most one net; no unrequested net
  rename/merge/split; all existing conductive junctions remain explicit.
- Route endpoints coincide **exactly in µm** with declared physical
  contact coordinates; never snap by tolerance or infer from a screenshot.
- A crossing is not electrically connected without an authorized explicit
  junction. Cross-net contact, pin mismatch, missing T, dangling segment
  and text/keepout collision may be `BLOCKED`; no automatic waiver.
- A new conductor uses real printed stroke width and physical pin escape
  corridors for clearance. Diagonal or arbitrary low-level geometry
  routing is not a safe substitute.
- All elements remain `DRAFT` as catalogued; no MCP tool can promote
  them to `APPROVED`. Font provenance and ESKD review are independent.
- Reject E1 structural diagrams in this E3 ProjectService until a
  **separate** structural-model adapter is accepted.
- No AI inference of topology, no arbitrary script evaluation, no generic
  patch document operation, no wildcard filesystem access.
- `expected_revision` is mandatory for all writes and explicit before/
  after image renders; raw network or client credentials never appear
  in persisted project metadata or logs.

### Real existing safe router limitation

At the current integration baseline, the physical-pin-aware
`engines/routing/two_pin_sheet.py:route_circuit_two_pins` explicitly
requires `len(matching[0].members) == 2`. The live TOP and RIGHT
nets connected to C3 each have **more than two contacts**. Therefore
that adapter CANNOT safely move/reroute C3 by connecting an arbitrary
pair inside TOP/RIGHT.

Required new gate: independently reviewed branch-aware route adapter
which can extend an *existing explicitly authored net* to a moved
physical PinRef without fabricating a junction or splitting/merging
nets, and validates the complete candidate `ExternalWireGraph`.
Until the ELEKTRIK/QA review approves this capability, a real C3
move scenario is **BLOCKED** and no production mutation is allowed.
A P1 implementation may initially support safe two-pin nets only.

## 6. Machine-readable errors (contract v1)

Each rejection is a structured MCP error envelope:

```json
{
  "error_schema_version": 1,
  "code": "ROUTE_UNSUPPORTED_MULTIPIN_NET",
  "severity": "blocked",
  "project_id": "<opaque-id>",
  "expected_revision": "<sha>",
  "current_revision": "<sha>",
  "affected": ["C3.1", "TOP"],
  "evidence": ["net-member-count=4", "router-supports-exactly-2"],
  "remediation": "Use reviewed branch-aware adapter; do not bypass routing guard",
  "retryable": false,
  "mutated": false
}
```

Stable error codes: `SCHEMA_UNSUPPORTED`, `PROJECT_NOT_FOUND`,
`WORKSPACE_DENIED`, `CATALOG_REVISION_MISMATCH`,
`REVISION_CONFLICT`, `IDEMPOTENCY_CONFLICT`, `UNAUTHORIZED_WRITE`,
`UNKNOWN_COMPONENT`, `PHYSICAL_PIN_INVALID`, `NET_MERGE_DENIED`,
`ROUTE_REPAIR_REQUIRED`, `ROUTE_UNSUPPORTED_MULTIPIN_NET`,
`ROUTE_GEOMETRY_BLOCKED`, `WIRE_NET_SHORT`, `JUNCTION_REQUIRED`,
`ANNOTATION_COLLISION`, `VALIDATION_REJECTED`,
`IMAGE_TOO_LARGE`, `REVISION_NOT_FOUND`, `SAVE_FAILED`.
Do not convert an exception into a fake empty-success image/report.
Diagnostics include rule source, specific net/pin IDs and µm locations
when known.

## 7. MCP authorization and filesystem scope

Read-only tools remain default in all clients. Separate explicit
`ProjectReadScope` and `ProjectWriteScope`; write scopes are specific
to exact project IDs and approved workspace root, not to the MCP process
or user text prompt. An authenticated local process is not by itself
proof of a project's write authorization. Optional human approval can
be required per mutation or critical net modification.

Paths in tools are **IDs**, not arbitrary filenames. Save/restore resolves
only under an approved root, with path normalization, traversal and
symlink/reparse-point checks, secure open, size/quota caps and no
untrusted device paths. File uploads and arbitrary JSON modifications
are not supported. `stdio` remains default; HTTP deferred until
authentication, identities, scoped access and rate limiting are reviewed.

## 8. Model and artifact version-locking

A `ProjectSnapshot` is immutable and includes `project_id`,
`revision_sha256`, `generation`, schema version, exact catalog
manifest, exact component/pin/net/route/junction records,
engine/renderer version and font sources.

An image references the exact `snapshot_revision`, renderer commit
or version, canonical SVG SHA, bitmap SHA and requested viewport/zoom.
A diagnostic response references the **same snapshot SHA**, a
validator-version identifier and its own content SHA. A diff references
both before and after revisions. Reject ambiguous `head` rendering
inside a repeatable agent cycle; resolve once, then pin exact SHA.
An agent verifies the image metadata revision equals the diagnostics
revision before recommending a change.

## 9. Testing and acceptance gates

| Gate | Evidence required |
| --- | --- |
| Format | Canonical roundtrip, schema-version rejection, catalog-hash mismatch, physical-pin lookup without `repr` |
| Transactions | Stale CAS, conflicting concurrent agents, durable idempotent replay, replay/key collision, error rollback, disk failure rollback |
| Network semantics | No silent net merge/split, pin renumber/polarity swap, crossing short, missing T-junction, unauthorized orphan wire |
| Geometry | 1 µm precision, rotation/mirror contact positions, symbol+label keepouts, true conductor stroke, bounded routing |
| C3 migration | 6 components, 5 nets, 3 junctions, live 16-wire example and independent frozen 18-wire archive |
| C3 move | Correct delta, safe branch rerouting only after approval, or explicit `BLOCKED` with unchanged SHA |
| Rendering | Source-svg roundtrip, nonblank image/png content, viewport mm bounds, revision-matched before/after, deterministic repeat hash |
| Persistence | Save, fresh-process reopen, exact net+route+annotation+revision hashes, no drift |
| Security | `../`, drive-letter/UNC, symlink/reparse escape, hostile JSON, resource limits, no shell/eval |
| CI | Ruff; pytest Python 3.12+3.13; 21 DRAFT dynamic catalog audit; wheel payload & import |

**Human QA:** no automatic ГОСТ certification. Review by ELEKTRIK
(pin/net/router), PAINT (geometry/annotations), YGO (catalog locking),
and independent QA. Codex CLI smoke test must prove
`ImageContent` reaches the model and drives an *agent-selected*
second zoom tool. SDK-only transport roundtrip is insufficient.

## 10. Rollout sequence and approval decisions

- **Gate 0:** PR #73 real Codex compatibility, C3 source check, P0 clean.
- **Gate 1 (this PR):** approve canonical schema, commands, CAS and
  explicit route safety; docs-only, no runtime writes.
- **Gate 2:** add persistence and in-process ProjectService read-only
  create/open/snapshot/save/export; migration plus true binary roundtrip.
- **Gate 3:** restricted typed add/nominal/transform and single-transaction
  writes for isolated components; rejected unsafe moves.
- **Gate 4:** ELEKTRIK/QA-approved branch-aware repair for multi-member TOP
  and RIGHT; complete C3 5mm move + revision-bound two-image diff.
- **Gate 5:** MCP facade for explicit writes behind project scopes,
  Codex end-to-end loop, fault/restart tests and documentation.

Decisions requested: (a) stable route-branch IDs and migration semantics,
(b) P1 application service package boundary, (c) approved safe branch
routing ownership and QA, (d) revision/generation hash format, (e) scope
and human approval model, (f) retention and artifact lifecycle.

**No changes to `Circuit`, `ExternalWireGraph`, `PartDefinition`,
`PinRef`, catalog JSON, `gost_schematic.api`, or active router
in this RFC. No merge without coordinator authorization.**
