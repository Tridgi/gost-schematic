# RFC E1-001 — isolated typed functional structural scheme (Э1)

**Status:** CONDITIONALLY GO for isolated experimental prototype per [coordinator decision](https://github.com/Tridgi/gost-schematic/issues/70#issuecomment-6862999265), but NOT APPROVED / NOT MERGE; independent QA, ESKD and YGO review remain mandatory.
**Issue:** [#70](https://github.com/Tridgi/gost-schematic/issues/70).
**Pre-implementation review:** [Issue #70 RFC comment](https://github.com/Tridgi/gost-schematic/issues/70#issuecomment-6862724943).
**Requested other-team reviews:** [YGO2 #71](https://github.com/Tridgi/gost-schematic/issues/71#issuecomment-6862725531); [ESKD #69](https://github.com/Tridgi/gost-schematic/issues/69#issuecomment-6862726058). YGO2 has [confirmed the provisional model/view seam](https://github.com/Tridgi/gost-schematic/issues/70#issuecomment-6863099192), keeping title_lines, code, arrow_at and via geometry exclusively in view.
**Starting integration:** `45d4451eb06e7e469aa4e3c26e728ac8a5bdf3c5`; original task branch `e2b280d91957ff678c90b792e2c94fa9e73e27ae` was exactly one commit behind and was fast-forwarded without rewriting history.
**Implementation scope:** `src/gost_schematic/structural/`, `examples/review_structural_e1.py`, new tests and fixture. Never change E3 `Circuit`, `PinRef`, `ExternalWireGraph`, public `api.py`, electrical UGO, printer/renderer, physical `PartDefinition`, JSON catalog or normative rules.

## Semantic contract

| Entity | Exactly what it means | Explicitly NOT |
| --- | --- | --- |
| `FunctionalBlock(id,name,origin,width_um,height_um)` | Named functional rectangle with integer-micrometre bounds; immutable | Physical electrical part or symbol UGO |
| `BlockPort(block_id,id,side,direction,position)` | Named logical anchor on one rectangle side, assigned to its stable block and ID | Physical metal pin or `PinRef` |
| `PortRef(block_id,port_id)` | Typed exact endpoint locator, requiring a declared `BlockPort` | Graphical arbitrary coordinate |
| `FunctionalLink(id,source,target)` | **Directed** functional/process relationship source → target; no inferred orientation | Conductive `Net` / wire with electrical node semantics |
| `StructuralDiagram(blocks,ports,links,schema_version=1,diagram_type="E1")` | One immutable structural graph snapshot with independently versioned JSON | `Circuit` / `ExternalWireGraph` |

All IDs and block names must be nonblank trimmed strings (semantic names have no line breaks); block sizes positive integer µm; no floats or non-finite numerics. Structural snapshots are immutable; graph-level invalid references and topology produce `Diagnostic(code, Severity.ERROR, ...)` without changing any source object. Ordinary functional feedback loops are **permitted** (potential regulation loop), not inferred electric shorts or a cycle error. Automatic electrical simulation and connection through intersections are excluded.

## Side ports (editorial defaults, **not GOST mandates**)

`Side.LEFT/RIGHT/TOP/BOTTOM` matches existing immutable core enum; `PortDirection.INPUT/OUTPUT/BIDIRECTIONAL` is strictly typed. Port direction is a **semantic source/sink constraint**:
- source is `OUTPUT` or `BIDIRECTIONAL`;
- target is `INPUT` or `BIDIRECTIONAL`.

`position = None`: placement by ordered declaration rank among **all ports on this block side**. With N ports, slot i (zero-indexed) is exactly `Fraction(i+1,N+1)`. N=1 → exactly `1/2`. Left/right fractions increase top-to-bottom; top/bottom increase left-to-right. Explicit `position = Fraction(n,d)` (or integral 0/1) replaces that port's automatic fraction. Mixing explicit and automatic is allowed only if no position collides; distinct ports cannot share an exact anchor, including at neighboring-side corners. Fractional position range is inclusive [0,1]; invalid types, booleans, out-of-range, and duplicate final coordinates fail.

The point is computed from **that exact declared side and rectangle**. YGO2's optional visual profile adds independent editorial minimums (5mm from corners, 6mm between ports); these are **not** hardcoded in the semantic model and must be checked by a future view/renderer. Integer µm are an invariant. If e.g. `Fraction(1,3) * 10000 µm` cannot be represented exactly, `E1_PORT_OFF_GRID` is an ERROR: **never silently round or slide an endpoint**. `FunctionalLink` stores only `PortRef`s, no raw `Point` fields. The model guarantees every representable endpoint terminates **on a declared port**.

## Validation contract and limitations

`validate_structural_diagram(diagram)` returns deterministic sorted ERROR diagnostics; no mutation.

- `E1_DUPLICATE_BLOCK`, `E1_DUPLICATE_PORT`, `E1_DUPLICATE_LINK`, `E1_DUPLICATE_CONNECTION`: IDs and repeated directed port-to-port arc.
- `E1_PORT_BLOCK_UNKNOWN`, `E1_LINK_PORT_UNKNOWN`: no orphan declaration or missing directed endpoint.
- `E1_SOURCE_DIRECTION`, `E1_TARGET_DIRECTION`, `E1_SELF_LINK`, `E1_ZERO_LENGTH_LINK`: contradictory process direction, trivial self-link, zero-length connector.
- `E1_PORT_OFF_GRID`, `E1_PORT_COLLISION`: fractional-µm endpoints, two anchors at one coordinate.
- `E1_BLOCK_OVERLAP`: two rectangles overlap in **positive area**, touching at the edge not claimed to be an overlap.
- `E1_LINK_THROUGH_BLOCK`: a temporary **straight geometric inspection chord** between port points enters any functional block interior. This is only a conservative static layout check, **not a real path router**.
- `E1_LINK_THROUGH_PORT`: an inspection chord passes through an unrelated declared anchor without creating a logical connection.
- `E1_LINK_CROSSING`: two straight inspection chords geometrically cross, touch or collinearly overlap without exactly sharing a declared port endpoint. Shared declared output port fan-out is allowed when the only intersection is that port and the lines do not overlap in positive length. **This is a provisional legibility ERROR, not a physical/electrical short, not a claim that GOST bans all X crossings.**

Straight lines are *inspection chords*, not finalized directed multi-segment drawing paths; routed visual links may need bends, arrowheads, stroke clearance, text reservations and layout constraints. Future YGO2/ESKD review may change whether a detected crossing is an ERROR, WARNING, or rendered without logical junction, but must never create an electrical `Net` from a visual crossing. The prototype has no geometric data for text clipping, font metrics, prescribed arrowheads, sheet/frame/title block or approved ГОСТ dimensional inspection.

## Exact JSON v1

`structural_to_json` serializes **validated** structures deterministically; `structural_from_json` strictly validates typed fields, exact keys, duplicate JSON keys, version and actual graph. Arrays preserve declared block/port/link order. Integers are µm; relative positions are `null` for auto or `[numerator,denominator]` in canonical lowest terms; no binary float/NaN or rounding. Example:

```json
{
  "schema_version": 1,
  "diagram_type": "E1",
  "blocks": [
    {"id": "A", "name": "Управление", "origin_um": [0, 0], "width_um": 20000, "height_um": 12000},
    {"id": "B", "name": "Индикация", "origin_um": [40000, 0], "width_um": 20000, "height_um": 12000}
  ],
  "ports": [
    {"block_id": "A", "id": "out", "side": "right", "direction": "output", "position": null},
    {"block_id": "B", "id": "in", "side": "left", "direction": "input", "position": [1, 2]}
  ],
  "links": [{"id": "L1", "source": ["A", "out"], "target": ["B", "in"]}]
}
```

Top-level `diagram_type="E1"` distinguishes this JSON from E3. This JSON is **experimental private internal schema v1**, not a shared/public API. Frozen `Point`, `Box` and `Side` primitives are only imported, not modified.

## Seven-block proof and reproducibility

`examples/review_structural_e1.py::specimen()`: POWER, ENTRY, CTRL, SENSOR, ADAPT, ACT, DISPLAY (7 real functional regions), 18 declared side ports, 9 source→target functional links, two ordered ports on ENTRY.RIGHT / CTRL.LEFT, outputs, inputs, arrows and an upstream feedback branch. `report()` lists every precisely computed declared port and the straight inspection chord endpoints. The outputs are **JSON only**, deliberately no improvised or normatively unverified SVG/ГОСТ sheet.

```sh
python -m examples.review_structural_e1 --output-dir output/structural-e1
ruff check .
pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
```

Regression checks cover 1 through 8 auto ports on each side and all eight D4 example-only transformations, mixed explicit fractions, unique corners, exact 1µm representation/invalid fractions, duplicates, unresolved ports, wrong direction, block overlaps, chord/block intersection, tangency, X crossing without electric tie, common-port fan-out, directed cycles, invalid JSON and immutable objects. YGO2 / ESKD independent approval is required before turning this prototype into a stable product contract.

## Open architecture questions for coordinator / teams

1. Should production accept fractions at sub-µm granularity (reject vs render-time rounding), and should auto-slot order be persisted as explicit fractions in JSON? This RFC chooses reject non-integral µm, keep null auto for minimal deterministic payload.
2. Should graph-level repeated directed arcs and overlapping inspection chords be hard errors or explicit UI warnings? Prototype opts fail-closed.
3. Should link ports support named semantic interface types or capacity constraints? Deferred; no physical `PinRef` allowed.
4. Visual routing, arrowhead geometry and notation shall follow future YGO2 #71 / ESKD #69 signed-off constraints, never be inferred from this unapproved experimental model.
5. No merge until coordinator validates private schema, ESKD normative matrix and YGO2 rendering interface. All existing electrical UGO remain DRAFT, including any new catalog counts from other workstreams.
