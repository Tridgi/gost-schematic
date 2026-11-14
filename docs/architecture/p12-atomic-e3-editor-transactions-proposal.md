# P1.2 PROPOSAL / Issue #74 — atomic typed E3 edit transactions (no code)

**Status:** DESIGN ONLY / NOT APPROVED / NO ACTIVE WRITE API.
**Branch:** parallel/ai-project-p12-transaction-rfc. This proposal is
deliberately **separate** from P1.1 immutable read-only ProjectService
[Draft PR #96](https://github.com/Tridgi/gost-schematic/pull/96).
No code for mutation, general CAS, Net manipulation, router changes,
or MCP write endpoint is implemented in this proposal.

## Prerequisites and release boundary

P1.1 validates a real `Circuit`, exact physical `PinRef` inventory,
`Circuit.Net`, `ExternalWireGraph`, persisted canonical SHA,
catalog locks, stable UUIDs and rendered SVG/PNG. Its only write is
trusted **create-if-absent** with generation=1. It cannot atomically
update an existing HEAD, cannot reroute C3 on TOP/RIGHT multi-member
nets and cannot safely downcast PR #97 multi-unit/NC physical IC types.

This P1.2 design does **not** authorize development. MAIN 2 must
explicitly approve Issue/branch/transaction scope and appoint ELEKTRIK,
PAINT, ESKD and independent QA review gates **before any write tool is
registered in MCP**. Until then all proposed commands return BLOCKED.

## 1. Exact transaction API envelope (proposed)

~~~text
TransactionRequest:
  api_version: 1
  project_id: canonical UUID
  expected_revision: exact SHA256 of current immutable E3 snapshot
  expected_generation: positive integer
  idempotency_key: canonical UUID
  command_list: nonempty bounded array of tagged typed commands
  catalog_manifest_sha256: exact installed catalog lock digest

Tagged commands:
  AddComponent:
    physical_part_id, exact part_sha, instance_uuid, refdes,
    origin_um, transform, nominal
  SetComponentView:
    component_uuid, view_uuid/unit_id, origin_um, rotation/mirror,
    exact pin_anchor_contract_sha
  SetFunctionTextOrientation:
    component_uuid, view_uuid/unit_id, angle 0|90,
    exact glyph/font/layout revision, anchors_unchanged_required
  ConnectPins:
    target_existing_net_uuid, tuple of exact physical PinRefs,
    expected_net_members_sha, merge_policy = DENY
  AttachNetContinuation:
    existing_net_uuid, explicit sheet marker UUID, anchor_um,
    display label, cross-sheet target; no physical connector
  DisconnectPins / MergeNet:
    NOT INCLUDED in first write gate

ValidateTransaction(request) ->:
  side_effects: NONE
  before_physical_net_inventory: full verifiable digest
  proposed_after_net_inventory: full verifiable digest
  proposed_geometry_digest and explicit route change list
  independent Circuit + ExternalWireGraph ERC diagnostics
  changed_pinrefs_before_after: complete typed sets
  route_status: PASS | BLOCKED | ERROR
  candidate_project_revision: SHA of the validated dry-run
  preview_digest: deterministic full request+candidate digest
  eligible_to_commit: bool

CommitTransaction(request, preview_digest) ->:
  success: bool
  old_revision, new_revision
  old_generation, new_generation
  diagnostics and exact changed physical Net member sets
  idempotent_replay: bool
  mutated: bool
~~~

No arbitrary JSON Patch, Python code string, shell, user-selected
workspace/file path, image pixel manipulation, arbitrary SVG edit,
imperative "connect all matching names", or unknown tagged command.

## 2. Concurrency, crash safety and idempotency

Mandatory explicit acceptance tests, not an informal promise:

1. Normalize and strictly parse the complete typed command set.
   Reject duplicate JSON keys, floats/NaN in integer-um fields,
   unknown keys/command types, invalid UUIDs and unverifiable
   physical part catalog sha. Bound command and final object size.
2. Resolve the canonical idempotency key to a durable request digest.
   Identical replay returns the original immutable receipt even
   if HEAD has advanced (under authorized policy); same key with
   different canonical bytes fails IDEMPOTENCY_CONFLICT. Durable
   receipt cannot be published ahead of the authoritative HEAD.
3. Lock **one project HEAD** using cross-process verified atomic
   exclusivity (not only an in-memory Python thread lock). Check
   **both expected_revision and expected_generation** under this
   lock. Mismatch => REVISION_CONFLICT, unchanged files and head.
   Include two independent processes and forced races in QA.
4. Start a **new immutable candidate** from the exact stored
   original. Apply typed commands to a candidate in memory only,
   with all unchanged stable UUIDs preserved. No partial live
   mutation of the original domain objects or PNG.
5. Re-run full independent electrical/net/graphic validation on
   **entire** proposed Circuit and conductor graph. Check exactly
   intended Net membership delta, all unrelated physical PinRefs,
   power/NC roles, 1-µm external endpoint equality, T/X junctions,
   other-net crossings and keepout clearance.
6. Stage candidate canonical `.gseproj`, versioned manifest,
   action journal and recovery receipt on same trusted filesystem.
   fsync staged data; implement/verify durable parent-directory
   metadata sync or platform equivalent. Test crash just before
   each publication step.
7. Perform **one atomic compare-and-swap HEAD publication** with
   verified update generation. Recovery after process termination
   must choose either entire OLD model + OLD HEAD, or entire NEW
   model + NEW HEAD and matching durable receipt. Never expose
   a revised image with stale diagnostics.
8. On validation/route/IO exception or stale generation: publish
   nothing, preserve original HEAD and all old snapshot images,
   report BLOCKED + mutated=false + machine-readable diagnostics.
   Orphaned staged content may be GC'd only under a separate
   safe recovery protocol.

P1.1's existing atomic **first create** is not evidence that these
multi-generation CAS, journal or rollback properties work.

## 3. Electrical integrity and route gates

- `Circuit.Net` and its complete physical member PinRefs are the
  authority; SVG appearance and equal printed text are never
  electrical evidence. Reconnecting two existing distinct nets
  without a separately authorized explicit Net merge is rejected
  NET_MERGE_DENIED. Overlapping orthogonal conductor strokes do
  not create an inferred junction.
- Resolve each physical pin by version-locked `PartDefinition` or
  future `IcDeviceDefinition` passport; preserve actual pin number,
  name, function and electrical type. Reject NC, duplicate physical
  numbers, hidden power pins, ambiguous unit ownership or
  manufacturer/revision mismatch.
- PR #97/PAINT #93 split-unit IC views share **one** package UUID,
  one instance in physical Circuit and disjoint `IcUnit` view
  subsets. Rotation of central `PWM` function text 90° to 0°
  changes the **view** only when PAINT glyph reflow preserves
  every external physical PinRef world anchor exactly. If refit
  would move connected pins, fail with
  VIEW_REFLOW_REQUIRES_ROUTING_REVIEW, never silently reroute.
- A graphical continuation from Issue #90 refers to **exact
  existing Net UUID**. It cannot generate a hidden XP/XS physical
  component, new electrical PinRef or implicit Net union.
- Existing `route_circuit_two_pins` handles only exactly two
  connected members. It **cannot** reroute C3 on TOP=4 members
  and RIGHT=3 members. No connected-component move or arbitrary
  40/64-pin autorouting is accepted until a branch-aware router
  independently proves each old/moved pin, tee/junction, route
  clearance and unchanged unrelated nets. Return
  ROUTE_UNSUPPORTED_MULTIPIN_NET + mutated=false.

## 4. Read/write permissions

P1.1 read-only stdio tools default DENY, opt in via explicit trusted
host workspace and canonical UUID allowlist. A future write MCP
capability must use an **independent disabled-by-default gate**, a
separate authorization check on **every** proposed transaction and
auditable grant/expiry, not inherit read access. Do not serve it
from an unauthenticated shared network MCP endpoint. No client
can pass a filesystem path or override host catalog authority.

## 5. Deterministic independent QA acceptance before any write enable

- Two processes race same expected HEAD; exactly one commit wins;
  other gets REVISION_CONFLICT, not a silent new net.
- Identical idempotent retry after kill/restart; changed body with
  same key blocked, old/new blobs and receipts recovered intact.
- Crash injection before/after every fsync and HEAD publication;
  no half-updated HEAD, diagnostics, images or Net inventory.
- Exact physical 8/14/40/64-pin source-verified IC package;
  synthetic fixtures labelled SYNTHETIC, not manufacturer approved.
- Disjoint logical sections DD1.1 and DD1.2 map to one DD1
  physical component and stable package PinRefs.
- NC, POWER_INPUT, POWER_OUTPUT, OPEN_COLLECTOR and unverified
  manufacturer revisions fail correctly.
- PWM 90°→0° changes only visual digest if anchors stable; existing
  Circuit Net/PinRef/physical-package digest byte-identical.
- C3 connected move in TOP/RIGHT remains BLOCKED until independent
  multipin router passes actual electrical and 300-DPI visual QA.
- False T/X crossing, 1 µm near miss, hidden short and duplicated
  display label never create an unauthorized real contact.
- Invalid JSON, stale catalog, malicious UUID/path/symlink/junction,
  oversized transactions and read-only client attempts fail closed.
- Original six-part P1.1 immutable revision reopens and renders
  identically on Python 3.12 and 3.13; no v1 migration regression.
- End-to-end **real** stdio MCP ClientSession tests are required
  before registering any write command. A mock client or static
  Python function call is not sufficient.

## 6. Proposed implementation sequence (separate approved PRs)

P1.2a: introduce in-process typed validation-only candidate engine,
strict command schemas and comprehensive side-effect-free preview
tests; **still no MCP write endpoint**.

P1.2b: implement project-specific cross-process CAS, durable
idempotency receipts, multi-generation immutable history, crash
recovery and atomic rollback, including Windows NTFS + Linux.

P1.2c: enable only **safe unconnected** component view edits and
validated non-topological annotation commands behind a separate
write capability, after QA approval.

P1.2d: integrate physical IC source/PAINT view and separately
accepted branch-aware router; only then consider ConnectedMove,
ConnectPins or AttachNetContinuation with full independent QA.

This proposal must not be merged into production or interpreted as
implementation authorization without MAIN 2 acceptance.


## 7. Issue #100: real editor target → safe prospective transaction bridge

**Status: normative design only in this RFC.** The independent
[read-only Draft PR #103](https://github.com/Tridgi/gost-schematic/pull/103)
proposes an executable bounded query, but it is not part of a committed
writer, not a rendered green hotspot UI and not permission to create Nets.
This section is a P1.2 **contract** layered over already merged P1.1.

### Authoritative target record (schema v1 read-only projection)

Every target is derived from a previously verified immutable E3
\`SchematicProject\`: exact catalog-locked \`PhysicalPin\` and transformed
\`GraphicPin\`, or an authored \`ExternalWireGraph.WireSegment.start/end\`,
**never from SVG pixels, OCR, text labels or a mouse click**.

~~~json
{
  "schema_version": 1,
  "project_id": "canonical-project-uuid",
  "project_revision": "sha256-of-immutable-project",
  "target_id": "stable-target-uuid",
  "kind": "physical_pin",
  "component_id": "canonical-component-uuid",
  "pin_ref": {"reference": "DD1", "number": "27"},
  "physical_number": "27",
  "pin_name": "actual-installed-catalog-pin-name",
  "electrical_role": "POWER_INPUT",
  "pin_function": "general",
  "polarity": "none",
  "net_identity": {"id": "authoritative-net-uuid", "name": "VCC"},
  "wire_segment_id": null,
  "wire_end": null,
  "world_um": [102000, 64000],
  "selection_allowed": true,
  "preview_candidate_allowed": false,
  "connection_allowed": false,
  "reason_code": "SOURCE_REQUIRED",
  "commit_blocker": "WRITE_TRANSACTION_NOT_IMPLEMENTED",
  "coincident_target_ids": [],
  "requires_disambiguation": false
}
~~~

The above is **illustrative**, not an actual DD1/27 manufacturer package
assignment. The coordinate is exact integer µm; the physical pin number
is from a pinned **real** catalog part, never row order. The graphic
position and physical reference are paired but conceptually distinct.
An authored wire endpoint uses \`kind="wire_endpoint"\`,
\`wire_segment_id=<immutable UUID>\`, \`wire_end="start"|"end"\`,
and **null** \`pin_ref\`, \`component_id\`, \`physical_number\`, etc.
Its \`net_identity\` comes from the wire's declared Net UUID, not nearby
ink. No UI "pseudo-pin" is created at a body edge or text field.

The returned \`net_identity.id\` is authoritative; \`name\` is only a
display string, **never a same-Net proof**, even for VCC/GND. A
source-target pair with distinct assigned Net UUIDs must yield
\`NET_MERGE_DENIED\` until a separate, explicitly authorized semantic
Net merge exists. \`PinRef\` and owner component UUID are stable;
the returned SHA guards against stale pointer coordinates after future
view/layout edits.

The **three independent booleans** must not be conflated:

- \`selection_allowed\`: editor can focus/select a model-proven endpoint.
  Does not imply an electrical change.
- \`preview_candidate_allowed\`: current *pair* is provisionally
  admissible as a proposed route candidate, subject to all electrical
  type/Net gates; no routing computation is guaranteed.
- \`connection_allowed\`: false until a separately accepted
  \`ValidateTransaction\` + \`CommitTransaction\` performs authoritative
  full-domain ERC, route and CAS validation. Read-only MCP **always false**.

\`source_target_id\` is optional. With no selected source, the API must
return \`SOURCE_REQUIRED\` for ordinary targets, and explicit BLOCKED
reasons for NC/unverified roles. With a source, the policy is evaluated
again against its exact physical role and NetIdentity.

### Electrical role matrix / no inferred source

| Physical role | Discovery / pairing policy before write gate |
| --- | --- |
| PASSIVE | Candidate may be previewed with separately selected compatible source; not an approved connection |
| INPUT / OUTPUT | Candidate may be inspected; OUTPUT→OUTPUT needs independent driver conflict review |
| BIDIRECTIONAL | Block a proposed join pending bidirectional/driver policy review; role may be selected for inspection |
| POWER_INPUT | Selectable physical target; pair BLOCKED until power direction/source check |
| POWER_OUTPUT | Selectable physical target; pair BLOCKED until supply/driver check; two drivers never auto-approved |
| NC / NO_CONNECT | Not selectable as electrical connection target; never part of a Net; fail closed |
| UNSPECIFIED / UNKNOWN | Block until physical catalog role verified, not guessed from a printed name |
| CONDUCTOR (wire endpoint) | Selectable real authored endpoint, existing Net UUID; not a physical pin or new Net |

Current ordinary \`PhysicalPin.ElectricalType\` has no \`NC\` enum
variant. The draft IC model on #87/#97 has independent NC semantics.
**No claim is made that the merged v1 part catalog can load NC**
or vendor-verified 40/64 pinouts yet. The policy reserves NC handling
for a future approved lossless IC adapter; until then unsupported IC
records must fail closed rather than become "passive" fabricated pins.

### Editor interaction and nonprinting hit-zone design

1. Open project by UUID and revision SHA; verify project is explicitly
   authorized to the **host-scoped** local MCP reader.
2. Request \`get_connection_targets\` at that exact immutable SHA; return
   all exact \`world_um\` targets, stable IDs and explicit NetIdentity.
3. Transform world µm → screen CSS px using **camera zoom and pan**;
   distinguish \`devicePixelRatio\` for canvas backing-store rasterization.
   A provisional 8–12 CSS-px pointer hit radius is a UX parameter,
   **not schematic mm nor ГОСТ geometry**.
4. For dense 40/64-pin units and coincident terminal+wire endpoints,
   resolve \`coincident_target_ids\` through keyboard focus/cycling
   or an explicit popup listing *physical number, pin role, Net*.
   Never choose an arbitrary nearest terminal silently.
5. With no source, use selection/hover indication; after selecting a
   source, requery pair policy by source target ID. **Green** shows only
   a selectable/provisional preview target, while rejected targets
   show reason text and a non-color-only indicator.
6. Requested orthogonal dashed route is a **future** independently
   reviewed route-preview engine. Merely having candidate eligibility
   is NOT proof that a physically valid route was found; do not
   paint a misleading safe route. No changes in Circuit/Net on hover.
7. Future ValidateTransaction must verify both PinRefs, source +
   candidate exact positions, unchanged source revision, complete
   physical Net-member sets, every T/X crossing, foreign-Net clearance
   and electrical roles. Return typed diagnostics without side effects.
8. Future CommitTransaction requires exact expected_revision and
   expected_generation CAS, durable idempotency, atomic new HEAD and
   rollback, producing a **new** revision. UI discards old target IDs/
   coordinates after commit and reloads from the new SHA.

**No green zones, translucent hover hit areas, proposed route dashes,
RGB status colors or diagnostic rectangles in normative CLEAN SVG/PDF.**
The existing P1.1 \`schematic_render_project(mode="diagnostic")\`
is a static diagnostic SVG/PNG, **not** a fully interactive editor.
An opt-in editor-only display layer can be defined later; it must be
nonprinting and must not affect electrical topology.

### Fail-closed practical QA checks

- Return original six-part **6 components / 5 real Net / 16 authored
  segments / 3 junctions**, 32 wire **endpoint identities** and actual
  physical C3 pin 1 PLUS at (91000,80000)µm and pin 2 MINUS at
  (109000,80000)µm from the *restored model*.
- Native MCP stdio ClientSession opens the saved revision, enumerates
  targets, receives independent diagnostics, authentic SVG and PNG,
  and compares their SHA. No mock or hand-painted output.
- Different C3 NetIdentity UUIDs => NET_MERGE_DENIED. Printed
  matching VCC/GND never changes that outcome.
- NC, UNVERIFIED, POWER_INPUT, POWER_OUTPUT, BIDIRECTIONAL,
  OUTPUT/OUTPUT and cross-net pairs fail closed; PASSIVE only
  provisionally previewable, **never** approved for commit.
- Unauthorized UUID, path traversal, stale SHA, redirected workspace,
  modified catalog lock, oversized result and duplicate target ID
  fail closed and reveal no other user's project paths.
- Assert the full persisted \`.gseproj\` and HEAD bytes are identical
  before/after *every* read-only operation, with no generated editor
  SVG layer in CLEAN export.
- The P1.2 writer remains **BLOCKED** pending a separate independent
  MAIN 2/QA approval and crash-safe multi-generation CAS tests.
