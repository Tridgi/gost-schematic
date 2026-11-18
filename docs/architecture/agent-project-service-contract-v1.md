# RFC #74 Annex A — normative Agent Project Service v1 contracts

Status: **PROPOSED FOR ARCHITECTURE ACCEPTANCE; documentation only**. This annex
clarifies and takes precedence over ambiguous examples in
agent-project-service-rfc74.md. Implementation still requires an independent
approved PR. Current integrated MCP Vision (PR #73) is **read-only P0**.

## A1. Boundary and type discipline

- **ProjectService** is the sole application boundary for create/import, open,
  validate, render, commit, checkpoint and later typed mutations. All storage
  actions (including initial import) are issued by the service and enforced
  by policy. MCP, CLI, Agent Skill and renderer are not storage authorities.
- **ProjectRepository** is an interface exposing immutable object loading,
  persisted HEAD lookup, atomic CAS commit and idempotency retrieval. No
  domain validation belongs in the repository.
- **LocalProjectStore** is the initial ProjectRepository implementation,
  with an explicit trusted workspace root. It never accepts caller-selected
  absolute paths, symlink traversal or arbitrary JSON patches.
- **SchematicProject** is a typed immutable application snapshot: shared
  ProjectEnvelope plus one tagged diagram payload. Its E3 payload projects
  *without semantic loss* to real Circuit and ExternalWireGraph and pinned
  PartDefinition/SymbolDefinition; it is not a replaceable simplified netlist.
- **ProjectSnapshot** is a value tuple of project_id, revision SHA, generation,
  immutable canonical content and verified exact catalog/font/engine locks.
  Opening an old snapshot never edits HEAD or migrates it in place.
- **ProjectRevision** is SHA256 of unambiguous canonical schema-versioned
  project content, including diagram payload and locked definitions. It is
  distinct from the Git commit SHA, UI view hash and HEAD generation.
- **ProjectHead** is (project_id, generation, revision_sha256), an independently
  durable pointer. Generation increments on every accepted *new* commit.
  If identical content reoccurs, the SHA may be identical; generation defeats
  ABA in optimistic concurrency. The accepted import creates generation 1.
- **ProjectKind** is an explicit closed discriminator: "E3", "E1" or "ALGORITHM".
  Only E3 has an accepted projection to Circuit in P1.1. Unknown kinds fail
  closed; no implicit conversion or shared electrical fields for E1/ALGORITHM.

## A2. Project file format v1 (design contract)

Format is canonical UTF-8 JSON with extension .gseproj, no locale-specific
numbers or serialized Python classes. Coordinates, wire widths, clearances
and text anchors use exact **integer micrometres**. Documented fields:

| Contract path | Type / rule |
| --- | --- |
| format_id | literal "gse-project" |
| format_version | positive int, v1 only in initial implementation |
| project_id | canonical lowercase UUID string; never a path |
| project_kind | closed discriminator E3 / E1 / ALGORITHM |
| title | NFC Unicode string, bounded length; descriptive, non-identity |
| payload | tagged union discriminated strictly by project_kind |
| catalog_lock | exact manifest SHA + immutable part/symbol IDs, revisions, definition SHAs |
| document_profile | page geometry/provenance; norm status cannot be promoted by MCP |
| renderer_lock | engine/renderer version, font files' content digests or explicit missing-font warning |
| imported_from | fixed source reference/version and import recipe digest, if import |
| extension_data | absent in v1; unknown keys rejected rather than ignored |

E3 payload requires distinct arrays (no raster-derived records):

| E3 record | Typed mandatory fields |
| --- | --- |
| components | stable component_id (UUID), unique reference designator, part_id, pinned symbol ID/revision, origin_x_um/origin_y_um (int), quarter-turn enum, mirror flag, typed nominal and units, optional annotation anchor IDs |
| nets | stable net_id (UUID), unique display name, canonical sorted unique members (component_id, physical_pin_number as opaque string) |
| wire_segments | stable wire_id (UUID), source_ordinal (int, unique and contiguous per imported graph), declared net_id, exact start/end integer-µm points, printed stroke_um (int > 0); preserve source order |
| junctions | stable junction_id (UUID), owner net_id, x_um/y_um; no implicit T or X junctions |
| branches | optional future route_id/branch_id and participating segment IDs; migration must not invent connectivity from bends |
| annotations | stable ID, text, exact anchor, layer, text layout constraints, font provenance |
| sheet | dimensions, profile, text metrics version, explicit bounds in integer µm |
| analysis_scenarios | optional **typed** PotentialScenario with net voltages/conditions, source digest and certainty flag; absence never implies polarity PASS |

The existing Circuit Net / ExternalWireGraph WireSegment projection currently
stores names, member PinRefs, line endpoints and net names; it **does not**
store stable UUIDs or per-line stroke widths. The v1 importer creates
persistent IDs in a deterministic, namespace-qualified fashion based on
original semantic identities and original array indices, and freezes them
thereafter. Printed stroke width MUST be recovered from a known actual
source/style profile, NEVER guessed from a PNG. If it cannot be proven,
report IMPORT_PROVENANCE_BLOCKED, do not invent a value. Repeated equal
geometry may legitimately consist of multiple authored segments: unique
wire_id includes the source ordinal and net, while geometry is preserved.

The initial persisted E3 source is the integrated live "six-part" fixture
obtained through a *fixed, allowlisted importer* that calls the actual
Circuit and ExternalWireGraph; it must not use any arbitrary user-supplied
Python path or synthesize electrical net ownership from an SVG. A project
may be imported only once under a new project_id, with an exact recipe
and source hashes retained.

### Canonical hashing

1. Validate UTF-8, NFC strings, schema version, ranges, duplicates, exact
   physical pin identity and catalog locks **before** hashing.
2. Canonicalize object keys lexicographically, use no whitespace, no NaN,
   no float or exponent, canonical escaped Unicode, and normalized arrays:
   components/networks/junctions sorted by explicit stable IDs;
   **wire_segments ordered by persisted source_ordinal** (and disallow missing
   ordinals), route point order and intentional annotation order preserved
   where semantic. The canonicalization version itself is pinned in the schema.
3. Revision SHA = lowercase hex SHA256 over a fixed domain-separator byte
   sequence ("GSE_PROJECT_V1" + null byte) followed by canonical UTF-8
   project bytes. This guards against cross-type digest confusion.
4. A revision is immutable and addressed by (project_id, revision_sha256).
   The catalog and font locks are included within those bytes. No timestamp,
   random idempotency key, process ID or transient raster output participates.
5. UI view_id = hash of revision SHA, rendering version, exact bbox, mode,
   DPI, layer selection, and source SVG hash; output SVG SHA/PNG SHA are
   separate. Repeatability applies under identical pinned renderer/fonts/
   rasterizer. Without those inputs a PNG byte comparison is not a valid
   cross-environment invariant.

Do not confuse the earlier P0 specimen's computed project_revision with
the new v1 SHA. The **migration mapping** must record both and document
the intentional change of hash domain. Never silently rewrite older SHAs.

## A3. Storage layout and crash consistency

Approved workspace root is configured by the host, not from an MCP request.
Proposed layout:

~~~
<root>/
  projects/
    <project-uuid>/
      HEAD.json                       # generation, revision SHA, checksum
      revisions/<revision>.gseproj    # immutable content-addressed canonical bytes
      requests/<idempotency-id>.json  # committed request fingerprint/result
      journal/<txn-id>.json           # recoverable transaction intent and outcome
  artifacts/
    <project-uuid>/<revision>/<view-id>.svg
    <project-uuid>/<revision>/<view-id>.png
~~~

ProjectRepository methods (readers never mutate):

~~~
get_head(project_id) -> ProjectHead
read_revision(project_id, revision_sha) -> CanonicalProjectBytes
list_project_ids(scope, cursor, limit) -> page
compare_and_swap(project_id, expected_head, new_revision,
                 request_fingerprint, idempotency_key) -> CommitReceipt
get_committed_request(project_id, idempotency_key) -> CommitReceipt | None
recover(project_id) -> RecoveryResult
~~~

The service owns schema validation, projection, diagnostics, authorization,
and command semantics; the repository owns durable data and concurrency.
ProjectStore is the local disk adapter. A later database implementation
must implement the same CAS and immutable object semantics.

A project-specific mutex is a local *optimization*, not the only guarantee.
CAS at commit must atomically compare **both generation and revision**.
Blob and idempotency journal are staged durably before the HEAD pointer
commit; HEAD update is the only publication/linearization point. After a
crash, recover from the journal and verify blob SHA. A journal with no
committed HEAD is not reported as an accepted transaction. A committed
HEAD without its referenced blob is storage corruption, never silent
recovery to an unrelated revision. Cross-file atomicity is not claimed;
crash/rename/fsync behavior on Windows and Linux requires explicit tests.

For read-only P1.1 import, the service may import a fixed, proven source
into a *new* project_id only; it must never silently overwrite an
existing id or replace a previously imported authored fixture.

## A4. Exact service and MCP contracts

One application service; separate transport facade. All operations carry
api_version=1 and project_id when a project already exists. Read actions
accept optional exact revision (default HEAD is resolved **once** and returned).
Mutating actions require expected_revision, expected_generation, UUID
idempotency_key and a granted capability scoped to the project ID.

| Service operation | MCP tool / readiness | Read/write, semantic precondition |
| --- | --- | --- |
| import_fixed_source | P1.1 internal-only, controlled bootstrap | new project_id, fixed importer version; commits generation 1 |
| create_project | schematic_create_project / future | privileged initialization, E3 only initially |
| open_project | schematic_open_project / P1.1 | read snapshot exact rev / validated catalog lock; no mutation |
| get_snapshot | schematic_get_snapshot / P1.1 | immutable typed E3 data and digest; bounded/paged |
| list_projects | schematic_list_projects / P1.1 | authorized IDs only, no filesystem path |
| validate | schematic_validate_project / P1.1 | project revision, independent model check, no edits |
| render_overview/inspect_region | P0 names extended in P1.1 | explicit project ID + snapshot revision, real ImageContent |
| save_project | schematic_save_project / future | durable checkpoint/export of already committed revision; **never an unvalidated edit** |
| add_component | schematic_add_component / later | typed known catalog ID/revision, new stable ID, no network side effect |
| move_component | schematic_move_component / later | exact delta/target; connected pin repair MUST be same validated transaction |
| set_transform | schematic_set_transform / later | rotate/mirror graphic position only, NEVER reassign physical polarity |
| connect_pins | schematic_connect_pins / later | exact physical PinRefs and explicit net selection; merger separate authorized command |
| disconnect_pins | schematic_disconnect_pins / later | explicit expected member/route; reject orphaned net or wire |
| route_connection | schematic_route_connection / later | only reviewed physical-pin-aware safe adapter; unsupported multi-member net BLOCKED |
| apply_transaction | schematic_apply_transaction / later | ordered typed commands + CAS + dry-run + idempotency; one atomic boundary |

**Save semantics:** every successful write is already a committed immutable
revision in the repository. A future "save_project" flushes/verifies that
revision or creates a separately named/exported checkpoint via ProjectService;
it MUST NOT imply hidden dirty mutable state or create a new revision for
an unchanged snapshot. A read-only "open" may never auto-migrate in place.

Commands use discriminated schemas, no arbitrary key/value mutation:

~~~
{
 "api_version": 1,
 "project_id": "<uuid>",
 "expected_revision": "<64-lowercase-sha256>",
 "expected_generation": 7,
 "idempotency_key": "<uuid>",
 "dry_run": false,
 "commands": [
    {"type": "MoveComponent", "component_id": "<uuid>",
     "delta_um": {"x": 0, "y": 5000}}
 ]
}
~~~

The standalone MoveComponent example is intentionally **rejected** when
the target has attached wires and no approved safe route repair in the
same transaction; example data here is an interface sketch, not a
working mutation. The service validates whole-transaction final state
without leaking invalid intermediate drafts.

All successful mutation replies contain before_revision/generation,
after_revision/generation, idempotency_key, command receipt, canonical
typed diff, before/after independent diagnostics and revision-bound view
handles. A failed mutation returns a structured refusal and unchanged
authoritative HEAD, with no partial file/graph write.

## A5. Atomic edit and idempotency rules

A command transaction is a single ProjectService call:
authorize -> check schema -> consult committed idempotency record ->
obtain exact HEAD/CAS inputs -> copy-on-write draft -> apply typed commands
-> independent validators -> persist immutable staged blob -> CAS publish
HEAD -> journal complete -> return before/after revision receipts.

A retry with identical idempotency key AND canonical request fingerprint
must return the previously committed receipt, even across process
restart, with no second generation bump. Reuse of the same key for a
different request fails IDEMPOTENCY_CONFLICT. A previously unknown key
with stale expected_revision fails REVISION_CONFLICT (no auto rebase).
The idempotency replay check precedes stale revision detection so that
a successful retry is not misreported as conflict.

Validation rejects all new unauthorized topological edits including
silent net split/merge, changing C3 physical PLUS/MINUS identity, moving
a connected part without repairing attached wires, spuriously marking
a crossing, crossing a foreign net, or text/keepout intrusion. DRAFT
catalog symbols remain DRAFT. Unsupported branch repair fails BLOCKED
and emits no revision.

## A6. Diagnostic/error envelope v1

Responses are always machine-readable; warnings and true errors are
distinguished. Successful model validation can report warnings, but
missing/unimplemented checks are **not** represented as PASS.

~~~
{
 "schema_version": 1,
 "api_version": 1,
 "project_id": "<uuid>",
 "revision_sha256": "<sha>",
 "validator_id": "electrical-erc",
 "validator_version": "<exact-version>",
 "status": "PASS|WARN|BLOCKED|ERROR|NOT_IMPLEMENTED",
 "diagnostics": [
   {
     "code": "WIRE_NET_SHORT",
     "severity": "ERROR",
     "source": "ExternalWireGraph",
     "subject": {"kind": "wire", "id": "<wire-uuid>"},
     "location_um": {"x": 70000, "y": 40000},
     "related_ids": ["<net-uuid>"],
     "message": "Human-readable detail",
     "suggested_action": "Check authored junctions and net ownership"
   }
 ]
}
~~~

A transaction rejection has a separate error envelope: api_version,
error_schema_version, code, status=BLOCKED|ERROR, retryable, mutated=false,
project_id, expected_revision/generation, current_revision/generation
when authorized, affected_ids, independent_diagnostics and remediation.

| Stable error code | Meaning | Typical status / mutation |
| --- | --- | --- |
| SCHEMA_UNSUPPORTED | incompatible format version or unknown discriminator | BLOCKED / none |
| PROJECT_NOT_FOUND | authorized ID absent | ERROR / none |
| WORKSPACE_DENIED | path traversal/symlink/reparse/wrong scope | BLOCKED / none |
| UNAUTHORIZED_WRITE | missing write capability or approval | BLOCKED / none |
| CATALOG_REVISION_MISMATCH | pinned definition missing or changed | BLOCKED / none |
| REVISION_NOT_FOUND | referenced immutable SHA absent | ERROR / none |
| REVISION_CONFLICT | stale expected_revision or expected_generation | BLOCKED, retryable / none |
| IDEMPOTENCY_CONFLICT | key replay with different request | BLOCKED / none |
| PHYSICAL_PIN_INVALID | unknown or mismapped physical pin | BLOCKED / none |
| NET_MERGE_DENIED | unrequested merge or polarity swap | BLOCKED / none |
| ROUTE_REPAIR_REQUIRED | existing wires would detach on move/transform | BLOCKED / none |
| ROUTE_UNSUPPORTED_MULTIPIN_NET | current safe adapter cannot route TOP/RIGHT | BLOCKED / none |
| WIRE_NET_SHORT / JUNCTION_REQUIRED | invalid authored electrical connectivity | BLOCKED / none |
| GEOMETRY_CLEARANCE_BLOCKED | body/text/trace exclusion zone violated | BLOCKED / none |
| IMAGE_TOO_LARGE | viewport exceeds configured output limits | ERROR / none |
| IMPORT_PROVENANCE_BLOCKED | cannot prove source part/pin/stroke/route metadata | BLOCKED / none |
| STORAGE_CORRUPT | content SHA disagrees with immutable revision/HEAD | ERROR / none |
| PERSISTENCE_FAILURE | durable commit cannot be proven | ERROR / none |

Codes retain stable meanings across MCP transports. Display messages
are not parsed to infer success. If check is not implemented, return
status=NOT_IMPLEMENTED with explicit validator_id, not an empty list
claiming zero errors.

## A7. Revision-bound visual evidence

MCP tools work against **one** immutable SchematicProject instance
at an explicitly resolved revision; render and diagnostics are computed
from that instance, never from unrelated current HEAD or a stale
six-part Python specimen. For image tools return MCP ImageContent with
mimeType="image/png", plus TextContent JSON:

~~~
{
 "api_version": 1,
 "project_id": "<uuid>",
 "project_revision": "<sha>",
 "generation": 7,
 "diagram_kind": "E3",
 "source_model_sha256": "<sha>",
 "catalog_sha256": "<sha>",
 "svg_sha256": "<sha>",
 "png_sha256": "<sha>",
 "view_id": "<sha>",
 "bbox_mm": ["87.999","64.5","112.001","87.5"],
 "pixels": [472,453],
 "target_dpi": 500,
 "mode": "diagnostic",
 "diagnostics_revision": "<same-project-sha>",
 "warnings": []
}
~~~

The bbox and pixels above are **P0 C3 specimen values**, not values
guaranteed for an arbitrary future project. Every diagnostic report
and its image share the same snapshot revision. If either cannot be
produced, do not invent a before/after success. The response is a
typed project result, not a promise of completed ГОСТ approval.

## A8. Per-kind isolation and future extension

| Kind | Primary domain model | Graph edges | Not allowed |
| --- | --- | --- | --- |
| E3 electrical principle | Circuit + ExternalWireGraph + physical PartDefinition/PinRef | semantic electrical Net with explicit conductor geometry | image-derived nets |
| E1 electrical structural | StructuralDiagram / FunctionalBlock / BlockPort / FunctionalLink (Issues #69–#72) | directional functional relationship | fake Circuit/Net/PinRef or physical conduction |
| ALGORITHM / ESPD (#82) | AlgorithmDiagram + FlowNode + ControlFlowEdge + Entry/Exit | named control-flow branches, loops and source trace | fake E1 blocks or fake electrical pins |

Envelope, project ID, immutable revisions, workspace policy, commit
journal, SVG/PNG artifact metadata and generic MCP read surfaces may
be reused across the three kinds **only through a typed domain adapter**.
Validators, commands, normative profiles and semantic graphs remain
separate, selected strictly by diagram_kind. P1.1 accepts only E3;
E1 support is gated on its independent RFC/model; algorithmic diagrams
on Issue #82 and ESPD review. Unknown kinds return SCHEMA_UNSUPPORTED.
Do not promise cross-kind conversion or generic graph mutation.

## A9. Decisions recorded vs approval still needed

Architecture decision candidates in this annex are explicit and ready
for MAIN 2 review:
1. Immutable canonical snapshot versus mutable editor document.
2. ProjectService sole edit boundary; ProjectRepository interface and
   disk-backed ProjectStore implementation.
3. Content revision plus HEAD generation CAS, durable idempotency and
   authored geometry preserving UUIDs.
4. Exact revision-bound image and diagnostic payload, independent from
   image segmentation.
5. E3-only initial projector; segregated E1 and #82 models.

Approvals still required before implementation: canonical serializer
tests and schema v1 sign-off; catalog and stroke-width provenance
(ELEKTRIK/YGO); file atomicity across Windows/Linux (QA); branch-aware
safe routing and connected C3 mutation (ELEKTRIK/QA); diagram-kind
extension adapters (E1/#82 owners).

No production code, public API, catalog definitions, read-only P0 tools
or protected main branch are changed in this annex.