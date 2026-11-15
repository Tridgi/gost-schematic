# Cycle9 / MAIN 3 — agent catalog selection + transaction boundary

Status: REAL READ-ONLY MCP IN PR #111; P1.2 WRITE = BLOCKED.
Scope: Issue #74, Epic #107, frozen reference commit
`e695c415fdced164b0e0c39c5249d030795a0aa6`;
source manifest Git blob `b2375feb43ad18b8a8e5a515bfc007d169b26908`.
The reference is a 23-component, 15-Net, 91-authored-segment, 37-junction,
16-DA1-physical-pin **negative print baseline**, not an approved sheet.
It is NOT available in the installed P1.1 persisted IC catalog.

## 1. Executable client discovery / trust boundary

The real MCP server exposes **seven** read-only engineering tools from
this PR in addition to existing P1.1 project and P0 Vision readers:
`schematic_catalog_search`, `schematic_catalog_select`,
`schematic_catalog_preview`, `schematic_tl494_selection_profile`,
`schematic_tl494_pin_alias`, `schematic_preflight_project`,
`schematic_preview_placement`.

All seven annotate `readOnlyHint=true`, `destructiveHint=false` and
perform **no repository/workspace modification**. Fixed installed package
catalog cards are not private project data. The last two read exact
persisted ProjectService projects and need explicit host
`GSE_P11_READONLY_ENABLED=1`, trusted workspace and an **exact canonical
UUID project allowlist**. Never accept arbitrary filesystem paths in
MCP and never display a restored private project to unauthorized IDs.
The project SHA and catalog lock are independently verified on open.
All versioned new endpoints reject wrong schema `api_version` with
`API_VERSION_UNSUPPORTED`; bool/float/string are invalid even if
numerically equal to 1.

The query resolver accepts a small finite, reviewed Russian/English
semantic vocabulary, or a canonical installed physical part ID/family.
It does not infer a generic `capacitor`, `inductor`, or `mosfet`
into one final variant. No arbitrary language-to-GOST classifier.
Search responses are **candidates** only and require an explicit selection.

`schematic_catalog_select(part_id, part_sha256, symbol_sha256, api_version=1)`
requires exact current lowercase SHA256 for *both* `PartDefinition`
and `SymbolDefinition`. A changed source yields
`CATALOG_REVISION_MISMATCH`, malformed SHA => `INVALID_CATALOG_SHA`,
unsupported part => `CATALOG_PART_MISSING`, malformed selector =>
`INVALID_CATALOG_SELECTOR`. The selected response is a **catalog pin
template**, NOT a placed instance, with
`physical_pin_templates[].pin_ref=null` and
`is_instantiated_pin_ref=false`. Never synthesize unique physical pin
IDs based on a semantic query. Actual PinRef is the existing
`(ComponentInstance.reference, PhysicalPin.number)` from the saved
Circuit. D4 transforms are mathematically supported but not
normatively approved by that fact.

`schematic_catalog_preview` returns actual installed catalog UGO
`render_symbol_svg` and a rasterized PNG, with reproducible SHA; these
are appearance samples not a source-photo-aligned sheet. Never write
new SVG paths as an electrical or normative source of truth.

Source-specific profile `issue107-tl494-ugo-source-v2` includes the
previous 12 exact choices **plus R5 = resistor.variable (3 physical
contacts, including W wiper)** as documented in handoff and PR #113.
The frozen model counts are provenance only, not automatic proof of
full TL494 parity. FEEDBACK => FB (physical 3), OUTPUT CTRL => OC
(physical 13) remain view-only editorial abbreviations. Unknown
manufacturer labels are not automatically shortened.

## 2. Saved-project preflight and hypothetical placement

`schematic_preflight_project` returns true saved Circuit physical
contacts and Net members, exact physical symbol SHA/status, authored
wires/junctions, original ERC, partial printed-wire DRC and detected
source BOM wrong variants. The gap rule applies to **neighboring
parallel orthogonal wires with overlapping projected spans**, not to
all orthogonal crossings, legitimate T-junctions or nearby unsupported
diagonal cases. It reports exact printed-edge gap and authored wire
UUIDs, never hides original negative failures. Existing print checks:
0.2–1mm wire width, applicable 3mm parallel-edge clearance, a
conservative keepout AABB 2mm review. Distinct UGO glyph-to-glyph 2mm,
adjacent graphic strokes 1mm, all text/font ink, wire-to-symbol,
misleading X/T, manufacturer glyph correctness, A3 sheet fit and
global 15-Net router remain BLOCKED. `print_ready=false` always.

`schematic_preview_placement(project_id,revision,reference,x_um,y_um,
rotation=0,mirror_x=false,api_version=1)` is a *non-mutating*
what-if probe for an **existing** component, returning its original
and proposed world-µm anchor for each TRUE saved PinRef, existing Net
owners, actual catalog SHA, candidate body/ink bbox and diagnostics.
There is no auto-reassignment or new component ID.
It reports `CONNECTED_PIN_RELOCATION_BLOCKED` for any relocation of
an attached physical pin: the current router cannot prove a connected
multi-Net reroute. It separately catches conservative body overlap,
body-spacing review and authored conductor/body intersection.
It cannot approve or render a new valid candidate E3, and returns
`connection_authorized=false`,
`candidate_render=BLOCKED_UNTIL_VIEW_PLUS_ROUTING_CONTRACT`,
`commit_authorized=false`, `model_or_head_mutated=false`.
A retained label, unchanged x/y, or pretty preview is not a proof
that the original print sheet is valid.

## 3. Future typed writes: independently gated P1.2 design, not implementation

See the separate existing [Draft RFC #102](https://github.com/Tridgi/gost-schematic/pull/102).
Future commands, pending authorization: `AddComponent`,
`SetComponentView`, `SetFunctionTextOrientation`,
`ConnectPins`, `AttachNetContinuation`,
`ValidateTransaction`, `CommitTransaction`, and a typed undo via
verified *new* reverse transaction. No arbitrary JSON patch, shell,
user-selected output path, SVG edit or inferred Net merge.

### Mandatory atomic request envelope

```text
schema_version: exact 1
project_id: canonical UUID + host allowlist
expected_revision: exact immutable SHA256, not optional
expected_generation: strictly positive int
idempotency_key: canonical UUID
catalog_profile_revision: source-bounded digest (not a free alias)
commands: bounded tagged union, each with exact field set and size limit
command_count: bounded; unknown command => fail
```

In a future separate implementation:

1. Host authorization and project identity checked before any
   project contents or drawing are disclosed. Unsupported schema or
   malformed request fails with stable, non-leaking codes.
2. Validate physical `PinRef` against manufacturer device and
   actual installed part/package lock. Reject NC, conflicting
   POWER_OUTPUT sources, impossible INPUT/OUTPUT mismatches, duplicate
   physical pin ownership and mismatched expected Net UUID. A text
   label `VCC` or `GND` never joins separate Nets.
3. Make an isolated immutable candidate, never mutate the active
   graph. Exact `Circuit.Net` before/after inventory and audited
   junction/continuation changes are mandatory. The same physical
   package may have multiple graphical `IcUnit`s but only **one**
   physical component and full pin inventory.
4. Complete global routing/print-DCR with true stroke/text guard,
   title block, sheet format, source-locked exact UGO and provenance.
   A source-profile mismatch, unapproved symbol or partial DRC is
   never converted into PASS by improving a PNG.
5. `ValidateTransaction` has zero disk side effects; returns
   candidate digest, exact pin/Net deltas, all failure codes and
   `eligible_to_commit` only if **all** gates are satisfied.
6. Under a cross-process project-specific lock,
   `CommitTransaction` re-checks both expected revision and
   generation CAS, catalog/source lock, idempotency request digest,
   full physical/print DRC. Only then stage and atomically publish
   new immutable blobs and HEAD with durable fsync.
7. A repeated request key + byte-identical command returns original
   verified immutable receipt; same key and different payload yields
   `IDEMPOTENCY_CONFLICT`. Failed preflight or crash cannot expose
   half-published HEAD, missing revision artifact or changed topology.
   Perform recovery from a durable journal, verify receipt and
   safely rollback incomplete staging.
8. A future `UndoTransaction` is a new explicit reverse operation
   against the CURRENT generation, not silent history rewriting.
   It must revalidate source, physical PinRef, Net, print DRC and CAS.
9. Independent QA must test stale revisions, races, replay,
   unauthorized project, path traversal/symlinks, malformed input,
   wrong physical role/NC, foreign Net short, ambiguous cross,
   disconnected multi-pin reroute and power-source conflicts before
   any MCP mutation registration.

## 4. Reproducibility and honest blockers

Focused unit + native stdio MCP tests in
`tests/agent_project/test_tl494_ai_selection_cycle9.py`, plus
unchanged previous catalog/preview/saved-project tests. CI uses
Python 3.12/3.13, Ruff, wheel, catalog audit, native project SHA,
no disk mutation proof and true `ImageContent` SVG/PNG from the
installed physical catalog.

An executable C3 what-if test must identify that C3's saved physical
contacts are already assigned to a Net and DENY relocation without
rerouting them. A correctly source-locked `resistor.variable`
selection exposes physical A/B/W pin *templates*, not a fabricated
R5 from the user original. The user source's 23/15/91/37 baseline
is **not** recreated by this six-part MCP proof and is not silently
replaced by a synthetic success. A fresh autonomous Codex CLI run
is not claimed. Keep PR #111 Draft, no merge or main change.
