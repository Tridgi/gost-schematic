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

The endpoint is computed from **the exact declared fraction, rectangle and absolute document origin**. Quantization follows YGO2's `Decimal(ROUND_HALF_UP)`: perform **one** round of the complete absolute rational coordinate to an integer µm; half ties round **away from zero**, including at negative coordinates. Integer-only implementation: for `n/d`, `sign(n)*((2*abs(n)+d)//(2*d))`. Never round the relative offset before adding the origin and never convert through binary floats. For a 20,000µm side and two auto ports, exact `1/3` and `2/3` remain in the model/JSON and resolve to **6,667µm and 13,333µm**. Different fractions mapping to the same final integer-micrometre Point are a hard `E1_PORT_COLLISION`, including opposite sides/corners. `FunctionalLink` stores only `PortRef`s, never arbitrary coordinates.

**Optional YGO2 editorial guard:** `validate_port_clearances(diagram, min_corner_um=5000, min_pitch_um=6000)` checks the **rounded** anchors against minimum 5mm from either side's corners and minimum 6mm adjacent same-side pitch. These are **project-specific view values, NOT ГОСТ semantic norms**. Graph validity does not impose graphical ink constraints: a logically valid corner fraction `0` may be rejected for the chosen printed view, without rewriting its original Fraction. Negative editorial clearances are invalid. Visual routing/letter metrics need independent YGO2/ESKD evaluation.

## Validation contract and limitations

`validate_structural_diagram(diagram)` returns deterministic sorted ERROR diagnostics; no mutation.

- `E1_DUPLICATE_BLOCK`, `E1_DUPLICATE_PORT`, `E1_DUPLICATE_LINK`, `E1_DUPLICATE_CONNECTION`: IDs and repeated directed port-to-port arc.
- `E1_PORT_BLOCK_UNKNOWN`, `E1_LINK_PORT_UNKNOWN`: no orphan declaration or missing directed endpoint.
- `E1_SOURCE_DIRECTION`, `E1_TARGET_DIRECTION`, `E1_SELF_LINK`, `E1_ZERO_LENGTH_LINK`: contradictory process direction, trivial self-link, zero-length connector.
- `E1_PORT_COLLISION`: distinct declared ports resolve to the same **post-rounding** absolute point (including mixed sides/corners). `E1_PORT_OFF_GRID` is retired; fractional-micrometre results are deterministically quantized instead.
- `E1_PORT_CORNER_CLEARANCE`, `E1_PORT_PITCH`: optional editorial YGO2 view-profile diagnostics, not automatically evidence of a ГОСТ violation.
- `E1_BLOCK_OVERLAP`: two rectangles overlap in **positive area**, touching at the edge not claimed to be an overlap.
- `E1_LINK_THROUGH_BLOCK`: a temporary **straight geometric inspection chord** between port points enters any functional block interior. This is only a conservative static layout check, **not a real path router**.
- `E1_LINK_THROUGH_PORT`: an inspection chord passes through an unrelated declared anchor without creating a logical connection.
- `E1_LINK_CROSSING`: two straight inspection chords geometrically cross, touch or collinearly overlap without exactly sharing a declared port endpoint. Shared declared output port fan-out is allowed when the only intersection is that port and the lines do not overlap in positive length. **This is a provisional legibility ERROR, not a physical/electrical short, not a claim that GOST bans all X crossings.**

Straight lines are *inspection chords*, not finalized directed multi-segment drawing paths; routed visual links may need bends, arrowheads, stroke clearance, text reservations and layout constraints. Future YGO2/ESKD review may change whether a detected crossing is an ERROR, WARNING, or rendered without logical junction, but must never create an electrical `Net` from a visual crossing. The prototype has no geometric data for text clipping, font metrics, prescribed arrowheads, sheet/frame/title block or approved ГОСТ dimensional inspection.

## Exact JSON v1

`structural_to_json` serializes **validated** structures deterministically; `structural_from_json` strictly validates typed fields, exact keys, duplicate JSON keys, version and actual graph. Arrays preserve declared block/port/link order. Every link endpoint is a named JSON object `{"block_id": "...", "port_id": "..."}`, matching YGO2's provisional semantic projection (rather than a positional two-string array). Integers are **post-rounding** absolute µm in resolved coordinates; original relative positions remain `null` for automatic slots or exact canonical `[numerator,denominator]` fractions. No floats, NaN, loss of Fraction precision or silent anchor snapping. Example:

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
  "links": [{"id": "L1", "source": {"block_id": "A", "port_id": "out"}, "target": {"block_id": "B", "port_id": "in"}}]
}
```

Top-level `diagram_type="E1"` distinguishes this JSON from E3. This JSON is **experimental private internal schema v1**, not a shared/public API. Frozen `Point`, `Box` and `Side` primitives are only imported, not modified.

## Seven-block proof and reproducibility

`examples/review_structural_e1.py::specimen()`: B1..B7 (7 real functional rectangles, semantic Russian names and separate view-only two-line titles), 18 declared side ports, 9 directed links including B2.RIGHT/B3.LEFT three-port bundles and a lower visual feedback detour B7→B6. The 7-block model is **the source of truth**; `ygo2_visual_seed()` derives matching names, ids, ports and link endpoints, then adds view-only `title_lines`, code `ФБ*`, `arrow_at=target`, and `via_um` for L9. It passes the independent PR78 `validate_design` on real code and generates two real DRAFT SVG fixtures, not an approved ГОСТ sheet. `report()` lists resolved `PortRef→Point` anchors, functional inspection chords, no electrical nets.

```sh
python -m examples.review_structural_e1 --output-dir output/structural-e1
ruff check .
pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
```

Regressions cover 1 through 8 auto ports on each side, all eight D4 test-only transformations, **absolute half-away-from-zero** for positive and negative origins, width/height including 1µm and odd dimensions, exact `1/3,2/3` preservation, rounded collisions including mixed-side corners, 5mm corner/6mm pitch visual fail-closed, declared port-only endpoints, YGO2 view JSON parity and the actual pinned SVG diagnostic port markers, duplicates, dangling links, wrong flow direction, cycles, immutable JSON and no electrical nets. YGO2 / ESKD independent approval is required before turning this prototype into a stable product contract.

## Cross-branch real YGO2 integration evidence (QA #83)

Verified against **actual standalone Python code from YGO2 Draft PR #78** at head
`c49b7632cac33eafd77b29cc746a37978838f3e4`,
source blob `85fcf7bc5aff7057f5c489d3f5b697d10c36f119`.
No fake renderer was substituted or copied into production; the source was loaded
**temporarily** for the independent verification script.

A new 7-block / 18-port / 9-link view seed in
`tests/fixtures/structural-e1/ygo2-seven-view.json` was generated from typed
`specimen()`, *not* treated as the semantic master.
`examples/verify_structural_e1_ygo2.py` loads PR78 source with an explicit
`--ygo-source` CLI argument and executes:
`validate_design`, `semantic_projection`, `render_svg` (clean and diagnostic),
all 18 exact `PortRef→Point` comparisons and all 9 directed path endpoints,
and byte-identical regeneration of the two committed SVG fixtures.
The manifest `tests/fixtures/structural-e1/ygo2-seven-interop-report.json`
records source and output SHA256 hashes; no electrical short or implied
functional junction appears at graphical crossings.

**One outstanding owner-branch schema delta:** actual PR78
`semantic_projection()` omits the *mandatory* top-level constant
`diagram_type:"E1"`. The cross-branch verification explicitly injects this
*one test-only adapter key* before sending JSON to our **strict** structural
decoder; no other field is modified and no schema gate disabled.
YGO2 should add the constant in its own workstream. There is no implicit
loss of semantic Fraction for the shared example: all its fractions have
terminating decimal representations (0.25, 0.5, 0.75).
For **general** auto positions `1/3`, the current view's finite decimal
string can give identical rounded ink coordinates, but cannot carry the
original infinite-repeating rational value; a future view adapter must use a
rational `[numerator,denominator]` or preserve the semantic JSON separately.

Use:
```sh
git show c49b7632cac33eafd77b29cc746a37978838f3e4:examples/review_structural_e1_design.py > output/ygo2_design_qa.py
python -m examples.review_structural_e1 --output-dir tests/fixtures/structural-e1
python -m examples.verify_structural_e1_ygo2 --ygo-source output/ygo2_design_qa.py --output-dir output/e1-interop
```

The sample is **DRAFT** only. YGO2's text sizing is an approximate preview,
not a measured GOST Type A metric. Bends and arrows are view overlays; the
electrical E3 model remains untouched.

## Open architecture questions for coordinator / teams

1. **Resolved for experimental v1:** preserve original exact Fraction, quantize **absolute** document endpoints once with ROUND_HALF_UP, and reject rounded collisions. Keep `null` for automatic slots in semantic JSON; future view may choose to emit exact rational fractions to avoid repeating-decimal drift. No public API stability promise.
2. Should graph-level repeated directed arcs and overlapping inspection chords be hard errors or explicit UI warnings? Prototype opts fail-closed.
3. Should link ports support named semantic interface types or capacity constraints? Deferred; no physical `PinRef` allowed.
4. Visual routing, arrowhead geometry and notation shall follow future YGO2 #71 / ESKD #69 signed-off constraints, never be inferred from this unapproved experimental model.
5. No merge until coordinator validates private schema, ESKD normative matrix and YGO2 rendering interface. All existing electrical UGO remain DRAFT, including any new catalog counts from other workstreams.
