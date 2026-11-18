# CHAT 6 — exact GSCAD v2 → Python E3 projection

**Status:** engineering adapter, not an ESKD-approved catalogue bridge or a print-ready exporter. Owner: #122. Tracking Draft PR: #134. Target app/IPC integrator: #125; Manual Wire: #123; export: #124; desktop: #118.

## Entry point

```python
# From repo root with src and ui/editor/src/model on PYTHONPATH
from contract import strict_loads
from engine_adapter import project_to_engine

file = strict_loads(open("ui/fixtures/tl494-source-e695-v2.gscad.json", "rb").read())
projection = project_to_engine(file)
assert len(projection.circuit.components) == 23
assert len(projection.circuit.nets) == 15
assert not projection.rendering_catalog_verified
assert len(projection.sheets[0].graph.segments) == 0
```

For scripted tests: `PYTHONPATH=ui/editor/src/model python -m pytest -q ui/editor/src/model/tests`, requires the installed repository's `gost_schematic` Python engine and `jsonschema`. GitHub Actions `Visual CAD R1 source gate` exercises the same model suite against actual Python source.

## Identity and contract

`project_to_engine(ProjectFileV2, require_placed=True) -> EngineProjectProjection` returns immutable-ish Python engine dataclasses plus read-only identifier mapping. It **never changes** the v2 document.

| v2 authority | E3 projection |
|---|---|
| Stable `component.id`, `source_refdes` | `component_id_to_refdes`, `source_refdes_by_component_id`; E3 `ComponentInstance.reference` is mutable `refdes` |
| `PartDefinition.id` | `ComponentInstance.part_id` with *unchanged string*; no catalogue inference |
| `Net.name` and `members[PinRef(component_id,physical_pin_number)]` | Literal E3 `Net.name` and `PinRef(reference,number)` via explicit bijection |
| `SymbolInstance.origin_um`, CW y-down quarter-turn/mirror | `Point(x,y)` and `Transform(rotation,mirror_x)` |
| `WirePolyline.vertices/segments` | `ExternalWireGraph.segments`, `authored_segments[(wire_id,segment_id)]` in identical order |
| `Junction` | Exact authored `ExternalWireGraph.junctions` (visible conducting dot) |
| `Splice` | Invisible degree-2 electrical continuation: v2 validator checks; E3 is endpoint-continuous, no dot |
| `Graphic.kind=source_b_continuation` | `source_b_graphic_ids` only; **not a wire/PinRef/Net** |
| `Net.route_status` | `unfinished_net_ids` per Sheet; partial/zero routes preserved |
| `Component.value` | `unparsed_values_by_component_id` retained separately; **no fabricated SI nominal** |
| `workspace` | Excluded from engineering hash |
| One/many sheets | `sheets[]` with separate graphs; identical XY across sheets never connects by itself |

`source_topology_hash` and `project_sha256` are computed by the established CHAT6 `contract.py`. This projection has no write/CAS operation: persistence remains in `contract.History` or MASTER `project_wire_bridge.apply_snapshot` with source revision guards. The two bridges serve **different** boundaries.

## Fail-closed safeguards

The preflight calls **full JSON Schema and semantic v2 validation**, which rejects false physical numbers, wrong net membership, 1µm pin drift, fake Junction, foreign stroke at Junction, unsupported Splice and altered frozen E695 topology. Projection additionally rejects:
- `ENGINE_PLACEMENT_AMBIGUOUS` for unplaced components unless `require_placed=False` explicitly requests **netlist-only** projection;
- `ENGINE_MULTIUNIT_UNSUPPORTED` for multiple SymbolInstances of one physical component, because E3 `ComponentInstance` cannot represent multiple unit placements losslessly;
- `ENGINE_FREE_ENDPOINT_COLLISION` for visually coincident free ends that older E3 wire geometry would automatically join;
- `ENGINE_FOREIGN_ENDPOINT_COLLISION` for different declared Nets meeting at identical authored endpoints;
- `ENGINE_SEGMENT_OVERLAP` for positive-length collinear overlap between distinct polylines (older E3 implicitly joins them);
- `ENGINE_UNAUTHORED_PIN_CONTACT` when **any authored segment** passes through a placed physical symbol pin without the *same segment* explicitly terminating at that PinRef (no imaginary contact from pixels).

The geometry intersection preflight is currently O(P×S + S²) for placed pins P and segments S. For high-volume drawings replace with exact integer spatial index, not fuzzy CSS hit testing. The projection is **more conservative** than future routed CAD and may reject some physically legal authoring arrangements until an explicit per-contact E3 graph API exists.

## Export, source provenance, and blocked interfaces

Projection into `Circuit + ExternalWireGraph` **does not mean** the existing `render_external_wire_sheet` can safely render it. Native E3 needs a **verified full actual `PartDefinition` + `SymbolDefinition` / UGO catalog lock, engine layout and print DRC**. The v2 source fixtures contain explicit DRAFT symbol placeholders; no prior GOST approval is granted and `rendering_catalog_verified=False` remains fixed. A multi-sheet project also needs a per-sheet E3 renderer/authoritative continuation adapter; do **not** render the entire `projection.circuit` on every page. #124 owns clean SVG/PNG and #118 owns IPC; those paths must reject unverified catalog or incomplete export policy. Do not mark historical original E695 91 wires/37 dots (9 ERROR, 32 WARN) repaired: authentic frozen fixture exports **zero authored historical wires**.

**Review request:** #124 integrate and validate the actual catalog lock from Python; test true physical-PinRef-to-rendered-world-µm on one sheet, no source-b-as-wire, no false-X contact, no wrong-Net merge; then return a typed export-ready token only after source, DRC and font checks. #125 integrate conditional GUI adapter with revision compare; #123 validate free/splice/junction semantics against E3 projection; #118 keep IPC strict and allowlisted.
