# NET-C8-002 — source-bound wire endpoints and editor-only diagnostics

**Status:** DRAFT / implementation for independent QA only. Issues [#90](https://github.com/Tridgi/gost-schematic/issues/90) and [#100](https://github.com/Tridgi/gost-schematic/issues/100). Based on the **merged** prior PR #98 in `integration/stage0-12`. No old net continuation architecture is rewritten. No merge, UI, electrical write API, unreviewed data migration or normative certification.

## Electrical truth is not an SVG pixel

The pre-existing `Circuit.Net` (exact `PinRef` members) is the **sole electrical membership authority**. The pre-existing `ExternalWireGraph` owns the **authored graphical segments and explicit junctions**. `NetIdentity` supplies stable semantic Net IDs tied to an exact whole-Circuit net/member inventory. A visible text label, a coincident screen point, two overlapping strokes, or a green editor square cannot create/rename/merge any Net.

### Six distinct entities

| Entity | Source of truth | Diagnostic behavior | Can itself merge Nets? |
|---|---|---|---|
| Physical component/IC pin | Verified `PartDefinition` physical number + `SymbolDefinition`/instance D4 world Point, `PinRef` | Separate exact physical-pin target; connected or NC/blocked differentiated | **No** |
| Free authored wire end | `ExternalWireGraph.segments[index]` exact start/end, caller's stable `wire_id`, existing `NetIdentity` and anchored wire island | **Green outlined square** only when free, sourced and not policy-blocked; red/neutral reason if forbidden | **No** |
| Actual junction (T or 3+ conductors) | Explicit `ExternalWireGraph.junctions` Point | Existing **black** junction dot; NO extra green free-end square | **No** |
| Ordinary unconnected X / unmarked touch | Exact geometry + **absence** of explicit junction | `NonJoiningCrossing` metadata (for true interior/interior X), no green target/no black node; unmarked endpoint T blocked | **No** |
| Named off-sheet continuation | Existing strict validated `NetContinuationProject` endpoint/pair/stub tied to exact `net_id` | `WireTermination.CONTINUATION`, `NONPHYSICAL`; never a free target or a connector | **No** |
| XP/XS physical connector | Real `PartDefinition.reference_prefix` XP/XS plus genuine mapped `PinRef` and resolved world point | `CONNECTOR_CONTACT` / distinct `physical-connector-contact`; no counterfeit from a text prefix | **No** |

An explicitly connected common endpoint of two wires is `WireTermination.JOINED_WIRE`, not a free end. A graphic endpoint touching the **interior** of another wire without `graph.junctions` is `UNMARKED_TOUCH` / `BLOCKED`, not a silently created T. Foreign-net collinear overlap is rejected. A proper X may be drawn across two Net IDs without joining them; putting an actual junction on the foreign-net X is an error.

### P0 typed model and provenance

New isolated `gost_schematic.electrical.wire_endpoints` includes immutable:

- `WireEndpoint(id, wire_id, wire_index, side, net_id, point: Point, termination: WireTermination, state: TargetState, can_accept_connection: bool, attached_pin?: PinRef, continuation_id?, reason_code)`.
- `PhysicalContactTarget(id, pin: PinRef, point, net_id?, connector: bool, state, can_accept_connection, reason_code)` — distinct from a wire end.
- `NonJoiningCrossing(id, point, first_wire_id, second_wire_id, first_net_id, second_net_id)` — graphic-only and never a conductor.
- `WireEndpointSnapshot(circuit, graph, nets, wire_ids, wire_endpoints, physical_contacts, nonjoining_crossings, continuation_ids, schema_version=1)`.

All coordinates are integral **µm**; all enumerations are typed, not freehand strings. `WireEndpoint.id` is `<authored-wire-id>:<start|end>`. `wire_index` and exact `Point` are independently checked against the same source segment; `net_id` is checked against the genuine NetIdentity. Full actual physical Part+Symbol pin maps are required; 1-µm mismatches fail. `collect_wire_endpoints` is **read-only** and `validate_wire_endpoint_snapshot` additionally fails on modified coordinates/net IDs/indexes or a forged eligible endpoint. The rendering adapter recomputes the **entire** snapshot from the actual passed Circuit, graph, physical parts/symbols and policy before emitting debug marks. No SVG parsing supplies physical identity.

**Important integration limit:** the existing `ExternalWireGraph` does not yet persist independent wire UUIDs; the caller must persist `wire_ids` alongside the exact graph **and authoritative project revision**. A collection of wire IDs must never be reused with a reordered graph without an explicit reviewed rebind/compare-and-swap of the saved project revision. This module exposes validated source-side indexing but does not implement a complete persistent segment-ID registry or a safe connection transaction. Do not mistake caller-assigned IDs for a proof of historical segment identity across revisions.

The model verifies a segment belongs to a known real `Circuit.Net`, but even that is insufficient to authorize attaching a new circuit: an **unanchored wire island** (no authored path to a real physical PinRef on the same Net via existing endpoint/overlap/explicit-junction rules) is `FREE/BLOCKED: UNANCHORED_CONDUCTOR_ISLAND`. Corresponding green squares are prohibited. `can_accept_connection=True` only means a **candidate for a future validated operation**, not authority to modify a net, bypass electrical type checks or connect two nets.

### P1 SVG and PNG (static diagnostic, not interactive UI)

New `gost_schematic.rendering.wire_end_overlay.wire_endpoint_svg` takes a clean existing `render_sheet_svg` document, verifies that its wire lines match the same authored `ExternalWireGraph` exactly and refuses mismatched/colored/already-editor-enabled input. Clean mode returns the **original string byte-for-byte**. With `diagnostic=True`, it adds a dedicated `<g data-layer="editor-connection-targets" data-print="false" data-approval="EDITOR_ONLY_NOT_GOST">` with green squares for actually eligible free wire tips, red/neutral squares with reason codes for explicit blocked tips and verified physical NC contacts. Occupied pins, genuine authored junctions, nonphysical continuations and unconnected X **do not** acquire free-end squares. A separate `<metadata data-layer="diagnostic-electrical-endpoint-inventory">` retains all typed identities and reasons, including X and the authored junctions.

The square is a **1200 µm editorial static debug visual** (configurable), NOT a CSS-pixel hit-test or a ГОСТ physical dimension. Color is accompanied by stable text/ID/title/reason for accessibility. Future editor hit zones should be ~8–12 CSS px at 0.25×–20× zoom, independently transformed into world coordinates and keyboard-selectable where two targets are close; this is **not implemented**. There is no hover, snap, writable MCP command, route preview, CAS, or mutation of Circuit.

### P2 normative boundary — ESKD #91

- **ГОСТ 2.709-89 §5.13**: identifiers of connections are placed relative to horizontal/vertical conductors under their local rules.
- **ГОСТ 2.709-89 §5.14**: the address of **actual connected elements/devices/functional groups** may be mutual (including mixed address+net references). A simple project zone like `1/D4` is only editorial sheet navigation, never the universal mandatory contact address.
- **ГОСТ 2.721-74 table 6в pos.8**: authored break/continuation symbol, distinct from a free physical wire tip, X crossing or connector. Exact dimensions/placement remain subject to ESKD source-to-SVG acceptance.
- **ГОСТ 2.721-74 table 6в pos.5/6**: graphic crossing/branching rules. Only specifically authored electrical junctions can be treated as such; the diagnostic green hotspot is **not** a ГОСТ mark. See ESKD #91's comment in Issue #100.

The new package **does not alter or redraw existing standards continuation geometry**. It delegates strict reciprocal addresses and true NetIdentity pairing to merged PR #98. The new example is explicitly synthetic; its physical pin names/numbers do not represent a real chip or connector datasheet. Clean prints are monochrome and contain no editor squares or invisible interactive zones.

### P3 reproducible evidence and future ProjectService

`python -m examples.review_wire_endpoints_cycle8 --output-dir output/wire-ends` generates:

- `wire-endpoints-clean.svg`: real source segment artwork + one existing black authored T marker, zero debug squares.
- `wire-endpoints-diagnostic.svg`: separately verified visible eligible/blocked wire-end/pin targets and inventory with exact integer µm.
- `wire-endpoints.json`: 3 distinct physical Nets (`CTRL`, `AUX`, `SHIELD`), 5 explicit local wires, 1 authored T, 1 proper unconnected foreign-net X, 4 free wire tips (3 available, 1 policy denied), one blocked synthetic NC, 2 genuine physical connector contacts.
- Dedicated Python 3.12/3.13 GitHub workflow with Ruff, negative tests, pinned OpenGost Type A, strict one-`xmlns` XML import permutations, **real PNG 300 DPI** with measured green pixels in debug only, uploaded artifacts.

Future `ProjectService` must store *the entire source-authorized graph plus stable author-supplied wire IDs and exact revision hash*; an optimistic transaction would carry `wire_id`, endpoint side, expected source segment digest, actual `NetIdentity`, exact `Point`, expected revision/generation and explicit routing/junction intent. A subsequent `ConnectWireEndpoint` (not provided here) must revalidate the current physical catalog, T/X rule, electrical types, NC, external wire topology, net merge policy and collision safety, then atomically CAS or reject with no mutation. **Never patch `Circuit.Net` on color/hover/address text or by finding SVG shapes.**

### Independent QA gates

- `test_wire_endpoints_cycle8.py`: real/physical/connector/free/junction/crossing/continuation types, strict authority, same/foreign Net overlap, no false X/T, unattached orphan blocking, exact 1 µm, duplicate and stale IDs, missing pin map, D4 eight transforms, XML import-order, and raster green-only-when-opted-in.
- **Future release blocks:** joint PAINT #88 physical IC 4/8/14/40/64 pin galley; QA #92 combined source branch; P0 PWM D4 90°/270° text overflow; actual manufacturer XP/XS pin map; interactive edit logic, accessibility and CAS ProjectService. No merge from this owner branch until MAIN2/QA approval.
