# Issue #19 — catalogue-backed external-wire integration review

**Baseline**: `integration/stage0-12` / `parallel/electrical-next` at `9e9d056e410c8a54dc3c9fc9d5cc56b74e6f225b`.
**Scope**: independently test the external-wire validator shipped by PR #16 using real part/symbol catalog JSON and a winding built from its real JSON profile. No existing model, public API, catalog JSON, renderer or routing engine changed.

## Architecture and test isolation

The example in `examples/review_external_wire_catalog.py` loads:
- `catalog/parts/resistors/fixed.json` + `catalog/symbols/resistors/fixed.json`;
- `catalog/parts/capacitors/{fixed,polarized}.json` + matching symbol JSON;
- `catalog/inductors/inductor.tapped.json` through `load_inductor`, producing real `PartDefinition` and `SymbolDefinition`.

Five real component instances: `R1`, `R2`, `C1`, `C2`, `L1`. The physically declared nets are `TOP`, `LEFT`, `BOTTOM`, `TAP`, `RIGHT`. All real pin references are explicitly attached; `L1` pin **3** is a winding tap, `C2` pin **1** is positive, pin **2** negative. The sheet contains a marked T at (40000, 20000) µm and two **unmarked, unconnected** X crossings at (70000, 40000) and (98000, 27000) µm. Wire endpoints, branches, nets and crossings are authored fixtures, **not** computed routes. The original catalogue files supply pin positions and meanings, not wire connectivity.

`ConductorTopology` for a tapped winding can have one graphical conducting island `(("1","2","3"),)`, while electrical semantics still assign three **distinct external nets**. This is intentional: the winding is not a zero-ohm semantic short between these nets. A resistor's body is likewise not an external wire, and the two capacitor plates have distinct graphic groups. This model has no component-internal Kirchhoff/impedance solver.

## Matrix and expected diagnostics

| Case ID | Mutation relative to valid sheet | Expected unique diagnostic codes |
|---|---|---|
| `valid_catalog_sheet` | None | No diagnostics |
| `missing_t_junction` | Remove explicit T mark | `WIRE_NET_DISCONNECTED`, `WIRE_DANGLING_END` |
| `one_micrometre_break` | Separate segments by exactly 1 µm | `WIRE_NET_DISCONNECTED`, `WIRE_DANGLING_END` |
| `crossing_short_with_junction` | Declare unrelated X as a junction | `WIRE_NET_SHORT` |
| `wrong_bottom_net` | Assign BOTTOM conductor the LEFT label | `WIRE_PIN_NET_MISMATCH`, `WIRE_NET_SHORT` |
| `orphan_conductor` | Add unattached conductor | `WIRE_ORPHAN_CONDUCTOR`, `WIRE_DANGLING_END` |
| `unwired_capacitor_pin` | Remove BOTTOM conductor | `WIRE_PIN_UNWIRED`, `WIRE_NET_DISCONNECTED` |

Additionally test both actual unmarked X crossings, all orthogonal `Transform` rotations and mirror combinations for each real component type, physical pin map invariants, and immutability.

## Machine diagnostic artifact

`examples/review_external_wire_catalog.py` deterministically emits a JSON document with schema version, catalog IDs, per-case real physical-pin positions, semantic nets, segment/junction counts, expected codes and sorted actual machine diagnostics (severity, subject, message, code). No runtime timestamps, generated UUIDs, local paths or nondeterministic ordering. Golden file: `tests/fixtures/external_wire_catalog_review.json` (checked against canonical UTF-8, with checkout CRLF normalized to LF by pytest).

Regenerate explicitly after an authorized catalog or checker change:

```bash
python examples/review_external_wire_catalog.py --output tests/fixtures/external_wire_catalog_review.json
python examples/review_external_wire_catalog.py --output output/external-wire-catalog-review.json
ruff check .
pytest -q
```

The test suite fails if the fixture report differs; it cannot silently absorb a changed outcome by regenerating itself.

## Limits and coordination

Not a real-world electrically simulated circuit, autorouter, drawing clearance verifier, published JSON API, multi-sheet connection model, or ГOСТ/ЕСКД approval. The example's manually authored wires are *electrical connectivity fixtures*, not visually reviewed production layout. All 18 UGO remain DRAFT. The report is an independent diagnostic review of a few test nets, not electrical certification. Any future changes to shared `model/*`, `core/*`, `api.py` or catalog schema require coordinator RFC first.

After local tests, open a Draft PR into `integration/stage0-12`, check GitHub Actions Python 3.12/3.13, audit 18 DRAFT / zero hard errors, and report actual SHA/PR/CI. No merge by this chat.
