# Cycle 7 / Epic #86 — agent-facing E3 catalog and named net contract

**Status:** Future catalog/editing commands remain DESIGN/BLOCKED. Issue #74.
P1.1 now also registers five **default-denied host-scoped read-only MCP tools**
that call the real typed ProjectService; live stdio ClientSession tests prove
their behavior. No component, topology or routing mutations are authorized.

## Access matrix (explicit implemented vs future)

| Proposed tool | Gate / availability | Mandatory typed semantics |
| --- | --- | --- |
| schematic_list_catalog | future read-only P1.2 | category, optional search, pagination; actual versioned installed physical part IDs, NOT model guessed names |
| schematic_describe_part | future read-only P1.2 | part_id plus exact lock digest; PartDefinition, related SymbolDefinition and DRAFT status, nominal kinds and provenance |
| schematic_get_pinout | future read-only P1.2 | part_id + catalog SHA; all PhysicalPin number/name/type/polarity/function plus distinct graphical GraphicPin positions; no image OCR |
| schematic_preview_symbol | future read-only P1.2 | exact symbol ID+revision, declared transform, image bounded DPI, real SVG/PNG and explicit DRAFT warnings |
| schematic_list_projects | **implemented read-only MCP**; default DENY | explicit host enable + absolute trusted workspace + canonical UUID allowlist, max 32; never scans foreign IDs |
| schematic_open_project | **implemented read-only MCP**; default DENY | UUID + optional exact SHA; typed physical Circuit restored and independently validated |
| schematic_describe_project | **implemented read-only MCP**; default DENY | full canonical saved E3 and physical PinRef/name/type/functions/coordinates, Net membership, actual authored wire/junction geometry, 700 KB bound |
| schematic_get_snapshot | future separate MCP facade; existing describe exposes typed v1 record | UUID + exact revision; no raw JSON patch |
| schematic_validate_project | **implemented read-only MCP**; default DENY | independent full-model ERC/geometry by revision SHA; absent checks reported NOT_IMPLEMENTED |
| schematic_render_project | **implemented read-only MCP**; default DENY | revision-pinned real PNG ImageContent, metadata and optional exact SVG TextContent, no bitmap edits or filesystem writes |
| schematic_add_component | **BLOCKED until write transaction gate** | part_id+version + explicit UUID/refdes/position/transform; no guessed pinout |
| schematic_connect_pins | **BLOCKED until write transaction gate** | exact two physical PinRefs, explicit target Net ID, expected revision/generation and idempotency key; no hidden net merge |
| schematic_attach_net_continuation | **BLOCKED until topology+presentation gate** | existing Net ID + document/sheet/view anchor; no new physical contact, no Net union |
| schematic_move_component / disconnect_pins / route_connection | **BLOCKED until independent gate** | coordinated safe route adapter; complete atomic rollback on failure |

**P0 MCP Vision** (merged PR #73) remains read-only against the fixed six-part
specimen only: render_overview, inspect_region, inspect_component,
inspect_connection, get_diagnostics, list_views. The **new five P1.1
saved-project MCP reads** operate on exact stored project UUID+SHA through
ProjectService, with independent explicit host allowlist; these do NOT
make fixed P0 tools able to edit or inspect arbitrary stored UUIDs.
The actual list/open/describe/validate/render behavior is covered by native
mcp.ClientSession stdio tests in tests/agent_project/test_mcp_saved_stdio.py.
No write tools exist.

## Catalog list and describe contracts

Request:
~~~
{
  "api_version": 1,
  "category": "IC|TRANSISTOR|DIODE|FUSE|RESISTOR|CAPACITOR|INDUCTOR|CONNECTOR",
  "cursor": null,
  "limit": 50,
  "catalog_manifest_sha256": "exact-pinned-sha"
}
~~~

Response includes canonical catalog snapshot digest, next_cursor, and
items with exact part_id, symbol_id/revision, part SHA, physical_pin_count,
reference prefix and explicit DRAFT status. A change to the pinned catalog
produces CATALOG_REVISION_MISMATCH, never silently substitutes an alternate
revision. Cursor is opaque, bounded and tied to snapshot digest.

describe_part/get_pinout may return a full 40-pin IC as:
~~~
{
  "api_version": 1,
  "part_id": "catalog-provided-real-part-id",
  "part_sha256": "<sha256>",
  "symbol_id": "catalog-provided-real-symbol-id",
  "symbol_revision": 1,
  "approval_status": "DRAFT",
  "physical_pins": [
    {
      "number": "1",
      "name": "data-provided-contact-name",
      "electrical_type": "input",
      "polarity": "none",
      "function": "general",
      "graphic_anchor_um": [0, 1000]
    }
  ],
  "pin_count": 40,
  "datasheet_reference": "verified-source-or-null",
  "warnings": ["unverified-part-or-symbol-if-applicable"]
}
~~~

The single pin shown is a **schema illustration**, NOT a literal 40-pin
datasheet or a fabricated device. In production a 40-pin response must
contain exactly 40 distinct physical numbers from its PartDefinition.
Graphic anchors are separately validated GraphicPin values, transformed
through actual instance pose when presenting instance-specific pinouts.
Pad numbers/roles from a vendor package and the graphical UGO can be
independently versioned. Never use a symbol label or IC designation
to infer an unspecified pin number.

## Future mutation command envelopes

All changes route exclusively through ProjectService.apply_transaction:
~~~
{
  "api_version": 1,
  "project_id": "<uuid>",
  "expected_revision": "<sha256>",
  "expected_generation": 7,
  "idempotency_key": "<uuid>",
  "commands": [
    {
      "type": "ConnectPins",
      "net_id": "<existing-net-uuid>",
      "pins": [
        {"component_id": "<ic-instance-uuid>", "physical_pin_number": "27"},
        {"component_id": "<other-instance-uuid>", "physical_pin_number": "2"}
      ],
      "merge_policy": "never_implicit"
    }
  ]
}
~~~

This is a disabled *contract example*, not executable P1.1 API. The chosen
pin numbers are illustrative and have no real package meaning. For two
physical pins on different named nets, connection must not silently merge
nets. The command either requires an authorized separate net merge or
returns NET_MERGE_DENIED/BLOCKED. A successful connection must validate
complete Circuit/ExternalWireGraph, both endpoints, all connector keepouts
and actual stroke widths before atomic commit. Failed transactions leave
HEAD revision and generation unchanged and produce independent diagnostics.

## Named continuation (no phantom net union)

An E3 continuation is a **graphical annotation referencing the exact
existing Net ID** and target sheet/location. The command:
~~~
{
  "type": "AttachNetContinuation",
  "net_id": "<existing-net-uuid>",
  "sheet_id": "<sheet-uuid>",
  "anchor_um": [110000, 40000],
  "display_name": "POWER_12V",
  "kind": "same_sheet|cross_sheet",
  "target_sheet_id": "<optional-sheet-uuid>",
  "expected_net_revision": "<sha256>"
}
~~~

The display_name is text, **not** an instruction to search all other
label strings and electrically merge them. The input net_id is verified
against existing Circuit.Net ownership. A graphical open conductor may
terminate in a continuation symbol only if its route topology and endpoint
attachment are explicitly validated. Duplicate label names across different
net IDs are an AMBIGUOUS_CONTINUATION diagnostic, **never automatic joining**.
A continuation is not an XP/XS physical connector, radio link or new pin.

Future validation: unresolved references, missing sheet targets, duplicate
aliases, ambiguous names, unconnected route ends and cross-net crossing
must fail closed, and sheet location may not be read as electrical identity.

## Cycle 7 coordination and rollout

- ELEKTRIK owns real multi-terminal physical pin schema, part-to-symbol
  contract, catalog-lock update and safe net topology adapter.
- YGO and ESKD own source-backed DRAFT/approval and graphic pin positions;
  PAINT owns ink metrics, Type A font actual bounds and safe placement.
- QA independently verifies 40 unique pins and transformed graphic
  locations, no pin-number swap, alternative datasheet mapping, no
  DRAFT auto-APPROVED, no phantom junction/alias merge, all stored SHA
  and rollback failure cases.
- AI Integration exposes **only read-only catalog discovery/preview in a
  later explicitly approved MCP adapter**. No write-tools until general
  expected_revision+generation CAS and durable idempotent transactions
  are implemented and independently accepted.

This scope remains E3 only. E1 FunctionalBlock/FunctionalLink and
algorithm/ESPD control-flow Issue #82 have different typed graph domains
and cannot be imported as Circuit or electrical pins.
