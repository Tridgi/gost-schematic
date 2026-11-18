# Cycle 7 / Issue #74 — lossless physical IC and typed transaction boundary

**Status:** FUTURE CONTRACT ONLY; not a P1.1 serializer extension, write endpoint,
catalog approval or integrated PAINT build. Reviewed inputs are isolated Draft
[physical IC PR #97](https://github.com/Tridgi/gost-schematic/pull/97) and
[rendering PR #93](https://github.com/Tridgi/gost-schematic/pull/93).
The current P1.1 project schema v1 remains strict **ordinary E3 Circuit**
and **ExternalWireGraph** and must reject unsupported multi-unit IC models.
Nothing below authorizes downcasting PR #97 multi-unit/NC packages into
legacy `PartDefinition` or creating independent `DD1.1`/`DD1.2` parts.

## 1. Physical and presentation identities must remain separate

The new PR #97 electrical namespace includes:

- `IcDeviceDefinition(identifier, kind, package, pins, units)`: **one**
  physical component / `Circuit.ComponentInstance(reference="DD1")`.
  `IcPackage(package_id,family,pin_count,origin,manufacturer,datasheet_url,
  revision)` is part of the **version-locked physical passport**.
  For genuine production devices, exact manufacturer, part number,
  manufacturer HTTPS datasheet and document revision + verified source
  checksum are mandatory; `PinoutOrigin.SYNTHETIC` is never promoted.
- `IcPhysicalPin(number,name,function,electrical_type)`: one unique
  physical `number` per package, including POWER and NC. No pin may be
  invented from a graphic row/printed number. The full pin map is locked.
- `IcUnit(id,function,pin_numbers)`: disjoint assigned functional
  subsets **of the same physical package**, no duplicate ownership.
  `PinRef("DD1","27")` is physical regardless of displayed section.
- `IcSymbolSpec(device_id,unit_id,body,rows,profile,revision)` +
  `IcUnitPlacement(component_ref="DD1",unit_id,origin,transform)`:
  presentation only. `IcPinRow.anchor` is an explicit EXTERNAL endpoint
  in integer micrometres, independently verified against PAINT, never
  a convenient body-edge guess.
- `IcGraphicProfile(port_layout,body_axis,function_angle,
  other_text_angle)` carries original PR #97's independent 0°/90°
  function and non-function text intent. PR #93's `IcResolvedUnit`
  has the concrete `function_rotation` and `field_text_rotation`
  that actual measured glyph/ink rendering resolves. All those fields
  belong to **the graphic projection**, not the physical PinRef.

### Versioned future schema sketch (nonexecuting)

`SchematicProjectV2` would have:

~~~text
project_kind: E3
physical_components: [
  {
    component_id: stable UUID,
    reference: DD1,
    device_id: exact immutable versioned catalog ID,
    package_passport: {manufacturer, part_number, package_id,
                       datasheet_url, datasheet_revision, datasheet_sha256,
                       physical_pinout_sha256, provenance: real|synthetic},
    physical_pin_inventory: [PhysicalPin(number, name, function, type, ...)]
  }
]
nets: [
  {net_id: stable UUID, members: [PhysicalPinRef(component_id, number), ...]}
]
unit_views: [
  {view_id: stable UUID, component_id: same DD1 UUID, unit_id: unit A,
   symbol_revision: ..., row_anchors_um: ..., transform: ...,
   graphic_profile: {port_layout,body_axis,
                     function_angle: 90, other_text_angle: 0}}
]
external_wire_graph: {segments: [...], explicit_junctions: [...]}
catalog_manifest_sha256: ...
~~~

This is a **schema sketch**, NOT JSON accepted by v1, NOT real manufacturer
part data and NOT a release claim. A candidate v2 adapter must include all
currently persisted v1 provenance fields, pin positions, drawing labels,
scenarios, net and junction IDs, numeric wire width, and display geometry.
v1→v2 migration is explicit, versioned, fail-closed and independently
verified by QA; a library revision mismatch never silently updates pins.
The existing `ic_to_json/ic_from_json` is Draft `IcLibraryRecord`
serde, not itself the full saved project serializer.

**Lossless invariants:**
1. Exactly **one** physical `component_id`, `DD1` refdes and package
   passport despite N visual units. `DD1.1` is a view/reference suffix,
   not a physical component or a separate Net ownership domain.
2. Every package PinRef is unique; units map disjoint subsets; NC must
   remain explicit and rejected by electrical connection validation.
3. A physical model fingerprint covers package identity, all pins,
   functions/roles, authoritative `Circuit.Net` members and typed
   electrical identity. A separate view fingerprint covers geometry,
   symbol revision, glyph layout, transform and text angles.
4. Changing centered `PWM` **function display 90°→0°** updates only the
   unit view/fingerprint. `Circuit`, `PinRef`, physical package,
   net-membership fingerprint and catalog pinout hash must remain
   **byte-for-byte semantically equal**. The full project revision
   may change because the image content changed.
5. PAINT's measured typography might require resizing the body and
   reauthoring exact external pin anchors. If a requested text change
   would actually move a **connected** physical endpoint, reject as
   `VIEW_REFLOW_REQUIRES_ROUTING_REVIEW`; do not disguise a physical
   move as a harmless label rotation. Exact 1-µm world PinRef→Point
   is the integration acceptance gate.
6. For genuine manufacturer parts, every physical number/function
   traces back to the pinned datasheet edition; 40/64-pin synthetic
   fixtures are type tests, **not verified vendor pinouts**.
7. The original v1 6-component, 5-Net, 16-wire, 3-junction snapshot
   must remain loadable without importing future IC modules.

## 2. Future mutation boundary (NO implementation/activation in PR #96)

Only `ProjectService.apply_transaction()`, never an arbitrary JSON patch,
shell operation, decoded SVG or PNG mutation, may publish a new revision.

~~~text
TransactionRequest {
  project_id: canonical UUID,
  expected_revision: exact 64-char SHA256 of current project,
  expected_generation: positive int,
  idempotency_key: UUID,
  commands: typed, bounded tuple[
    AddComponent(part_id, exact catalog sha, UUID/refdes, ...),
    SetComponentView(component_id, unit_id, pose, ...),
    SetFunctionTextOrientation(component_id, unit_id, angle=0|90),
    ConnectPins(net_id, exact physical PinRefs, net_merge_policy=DENY),
    AttachNetContinuation(existing_net_id, sheet+anchor, ...)
  ]
}
ValidateTransactionResponse {
  preview_id, input_revision, input_generation,
  model_delta_digest, complete diagnostics,
  changed_physical_net_members: explicit full before/after sets,
  eligible_to_commit: bool
}
CommitTransactionResponse {
  committed: bool, old_revision, new_revision,
  old_generation, new_generation, diagnostics,
  idempotent_replay: bool
}
~~~

**Safety gates before write exposure:**

- Strong expected_revision **and** expected_generation CAS against the
  same HEAD; reject stale requests and never silently rebase.
- Unique durable `idempotency_key` plus canonical request-digest journal;
  identical replay returns original receipt; key with changed bytes
  returns `IDEMPOTENCY_CONFLICT`.
- Atomic staging of entire **new** project revision and durable
  HEAD publication, crash recovery of incomplete stages; rollback
  must leave old HEAD and all previous blobs intact. P1.1 implements
  **only** initial expected-absent creation, not this update protocol.
- Resolve physical pin number from verified installed catalog lock,
  reject duplicates, unknown/NC pins, incompatible typed electrical
  roles and swapped sections. Net ownership is one authoritative
  `Circuit.Net`; same text labels never force a merge.
- Independent external-wire and `Circuit` ERC, 1-µm endpoint checks,
  actual printed stroke, all body/text/foreign-pin keepouts and safe
  boundary routing before commit; detect unmarked T/X crossing and
  **hidden shorts** from any proposed geometry intersection.
- Report exact allowed physical PinRef member delta; unauthorized
  member changes, net split/merge, orphaned junctions and changed
  electrical identity block the transaction.
- Connected C3 TOP has four members and RIGHT has three; current
  `route_circuit_two_pins()` handles exactly two contacts. Connected
  `MoveComponent` and route repair remain
  `ROUTE_UNSUPPORTED_MULTIPIN_NET`, `mutated=false`.
- For `AttachNetContinuation` use an existing Net ID and **nonphysical**
  marker from Issue #90; never create real `XP/XS` component, new
  PinRef or implicit Net union.
- Commands have strict discriminated schemas, bounded argument sizes,
  no client paths/raw script execution/general JSON patch, and
  separate operator write capability (none granted in P1.1).

## 3. Next independent implementation gates

**Gate A — current P1.1**: immutable real E3 snapshot, host-scoped
read-only MCP via five tools, cold-process verified image and physical
model. This is the only scope authorized in PR #96.

**Gate B — source-backed multiunit IC read-only migration**: after
independent ELEKTRIK/PAINT/ESKD/QA signoff, pin and vendor/versioned
`IcDeviceDefinition`, exact multi-unit views and two separate text
angles in a *new* schema adapter. Unit graphics may be read and
rendered, while physical nets still belong to one package. No writes.

**Gate C — transaction service**: separate issue, branch and Draft PR,
independent crash/CAS/idempotency/electrical topology tests on
unchanged old HEAD. Only afterward may typed command mutations be
registered as MCP tools behind an explicit writable capability.

A "green" UI snap hotspot Issue #100 is screen-space nonprinting
interaction; it must never appear in clean SVG/PDF or become a
connectivity inference rule.
