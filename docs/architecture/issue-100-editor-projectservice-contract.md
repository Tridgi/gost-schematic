# Issue #100 — E3 editor hotspot → ProjectService transaction seam

**Status: PROPOSED CONTRACT ONLY. No interactive CAD editor, green
hotspot renderer or connection-changing API is implemented in P1.1.**

Owner MAIN 2 for prioritization. Dependencies: #74 ProjectService
CAS/transactions, #87 actual multi-pin IC physical endpoint model, #88
PAINT graphical body bounds, #90 nonphysical net continuations, #92 QA.

## Authoritative identities and views

E3 physical contact target is a resolved immutable triple:
`{project_id, revision_sha256, PinRef(component_reference, physical_pin_number)}`.
Its exact integer-micrometre world point derives from the installed
version-pinned physical PartDefinition + graphic SymbolDefinition transform,
or in future PR #97 IcDeviceDefinition + IcUnitPlacement + exact external
IcPinRow.anchor (whose **one** physical part/unit identity is authoritative).

An external-wire endpoint is an **authored WireSegment endpoint ID** and
declared Net ID, not an image pixel, shape contour or nearby arbitrary
crossing. A T-tap requires an explicit junction authored by a future
transaction; an X crossing with no junction never creates conduction.
A named continuation #90 is nonphysical and refers to an existing Net,
not a fabricated PinRef. E1 FunctionalLink and algorithmic FlowNode
are separate graph domains and must not be targeted by E3 connect tools.

## Proposed read-only editor interaction

| Editor event | Request / response / invariant |
| --- | --- |
| Open E3 editor | get_snapshot(project_id, exact SHA); PIN catalog locks + declared Circuit.Net + ExternalWireGraph |
| Request targets | get_connection_targets(project_id, revision, viewport): physical PinRefs, authored wire endpoints, separately allowed junction targets, exact world coordinates, stable IDs |
| Hover/focus | hit-test on screen using CSS-pixel radius (8–12 CSS px provisional), present accessible status; **zero mutation, zero new Net** |
| Select first | freeze exact contact identity, catalog digest, old SHA/generation; reject invalid/NC |
| Select second | ensure unambiguous *electrically compatible* physical PinRef, existing Net identity and no unapproved merge/split |
| Preview route | typed dry-run route against snapshot, source/target world points, actual body/text keepouts and nearby ink, no direct permanent wire writes |
| Request commit | one typed ApplyTransaction with expected_revision + expected_generation + idempotency_key and explicit ConnectPins/Route branch commands |
| Validate | ProjectService independently validates electrical types, physical number, Net membership, crossings, geometric clearance and actual route endpoints |
| Commit success | atomic CAS publishes new immutable revision and exact diagnostics/view IDs; UI refreshes pins and green zones from returned **new** SHA |
| Commit rejection | BLOCKED/ERROR, mutated=false, old HEAD SHA/generation; UI displays reason, no fake glowing connected wire |

The current P1.1 provides **neither get_connection_targets nor
ApplyTransaction**. The above names are proposed future contracts.

### Proposed target record

~~~json
{
  "schema_version": 1,
  "project_id": "canonical-uuid",
  "project_revision": "64-char-hex-sha",
  "target_id": "stable-editor-target-id",
  "kind": "physical_pin",
  "component_id": "stable-e3-component-uuid",
  "pin_ref": {"component_reference": "DD1", "physical_pin_number": "27"},
  "pin_role": "power_input",
  "world_um": [102000, 64000],
  "net_id": "existing-net-uuid-or-null",
  "eligible": false,
  "reason_code": "POWER_POLICY_REVIEW_REQUIRED"
}
~~~

The above is illustrative, not a real vendor 40-pin assignment. Renderer
must never derive a source electrical contact from SVG `x`/`y`
alone; graphic coordinates are only a visual projection of the exact
saved PinRef.

## Screen-space overlay rules

- Camera transform world µm → viewport CSS px is deterministic and
  invertible at known zoom/pan/devicePixelRatio; world anchors **never**
  snap to the pointer pixel or change stored integer geometry.
- Screen hit zone is a UX selection radius, not 8–12 schematic millimetres;
  overlapping targets (40/64 pins) require explicit ambiguity resolution,
  keyboard focus ordering, per-target text labels and non-color-only
  validation cues. No choosing an arbitrary “nearest” when ambiguous.
- Show valid targets in green or accessible neutral patterned markers,
  invalid pins in neutral/error with reason, and a dashed **preview**
  H/V conductor only when a safe route proposal exists.
- Hover/focus/preview never mutates SchematicProject or upgrades DRAFT
  status. Green zones are a **separate editor-only overlay**; clean
  black-and-white E3 SVG/PDF never includes them. A debug preview may
  add an explicit non-normative layer only under a separate opt-in.
- Displayed pin numbers are the *true physical numbers*, not array
  ordinal, logical field row, local Unit ID, or guessed vendor package.

## Fail-closed diagnostics and invariants

- **INVALID_PINREF / CATALOG_REVISION_MISMATCH:** pin number, NC, package
  provenance or graphic endpoint differs from locked catalog.
- **REVISION_CONFLICT:** stale revision OR generation; UI must re-query
  targets and discard old preview; no blind automatic replay.
- **NET_MERGE_DENIED / NET_SPLIT_DENIED:** label similarity or pointer
  collision cannot change physical Net inventory.
- **JUNCTION_REQUIRED / WIRE_NET_SHORT:** crossing without an authored
  junction remains an X; unauthorized new T creates no commit.
- **ROUTE_UNSUPPORTED_MULTIPIN_NET:** TOP (4 members)/RIGHT (3 members)
  in six-part C3 cannot be repaired with existing two-pin autorouter.
- **GEOMETRY_CLEARANCE_BLOCKED:** drawn line collides with symbol body,
  pin-number ink, text keepout or foreign trace at reviewed clearance.
- **IDEMPOTENCY_CONFLICT:** reused operation UUID with different
  command body; old accepted response replay only on identical digest.
- **UNAUTHORIZED_WRITE:** client lacks editor capability; hover/preview
  are read-only; no raw JSON mutation, shell or Python arbitrary exec.

NC and manufacturer pinouts in PR #97 remain DRAFT and **not** available
through the installed fixed PartDefinition catalog until a versioned
adapter is reviewed and merged. Gate to enable the editor is independent
QA of atomic persistence, crash recovery and branch-aware routing.

## QA acceptance matrix

- R/C/L pins and 2/4/8/14/40/64 IC pins, eight D4 poses; exact
  1-µm match from physical PinRef to external world endpoint.
- Split DD1.1/DD1.2 views show **one** package inventory; no repeated
  physical contact or hidden power pin. Top/bottom pin orientation
  remains BLOCKED until separately signed off in Cycle 7.
- 0.25× and 20× zoom, overlapping target focus, keyboard navigation,
  invalid target and access without color.
- Hover over symbol wire ink, label, unconnected component and crossing:
  none can fabricate a valid physical target.
- Select connected PinRef in multipin TOP/RIGHT → BLOCKED, unchanged SHA.
- Preview route, then concurrent commit modifies HEAD → CAS refusal,
  new targets loaded; no silent self-rebase or geometry reuse.
- Synthetic/real manufacturer provenance is explicitly differentiated;
  a fabricated vendor pinout cannot become automatically approved.
- Export clean SVG, debug overlay and PDF, check editor hotspots present
  **only** in explicit debug, never in normative clean artwork.

No MAIN 2 approval for full UI is implied by this contract.
