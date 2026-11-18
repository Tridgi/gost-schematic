# Issue #26 — six-part electrical vertical slice with electrolytic capacitor

**Baseline:** `integration/stage0-12` and `parallel/electrical-cycle3` at `840576d31ac7ff201fe64144c273e3aefbb1ab83`.

**Status:** experimental, all real catalogue UGO remain DRAFT; no claim of ГОСТ/ЕСКД approval.

## Contract and ownership

The isolated example `examples/review_end_to_end_circuit.py` calls **only existing** APIs:
`load_part`, `load_symbol`, `load_inductor` (through the already merged
`examples.review_external_wire_catalog`), `Circuit`, `Net`, `PinRef`,
`ExternalWireGraph`, `validate_external_wires`, `validate_circuit`, typed
`PotentialScenario`, `WireObstacle`, `SheetLayout`, and `render_sheet_svg`.
No changes to `model/`, `core/`, `validation/`, `rendering/`, `catalog/`,
`api.py` or any shared geometry schema. No auto-router, automatic netlist
inference, electrical simulation or wholesale DRC.

The authored wire graph is the **single source** for the validation geometry
and for the `WireObstacle` objects supplied to the existing sheet renderer.
The tests parse the renderer's SVG `data-layer="wires"` lines and compare **all
18 start/end integer-micrometre coordinates** to the graph in exact order.
Changes to either path cannot silently diverge.

Because the existing renderer draws external segments but does **not** draw
junction dots, this *example only* adds a separate
`data-layer="explicit-junctions"` SVG group, with a dot for each **authored**
junction, and lightweight `specimen-refdes` labels. It never computes
junctions from SVG crossings. Label font is generic `sans-serif` and has not
been calibrated to ГОСТ 2.304; this sample does not call the formal annotation
placement engine or claim approved clearances. The renderer itself remains
completely read-only.

## Six real components and physical terminals

| Ref | Real catalogue part | Connectivity |
|---|---|---|
| `R1`, `R2` | `resistor.fixed` | pins 1 and 2 on distinct nets |
| `C1` | `capacitor.fixed` | separate external networks at two plates |
| `C2` | `capacitor.polarized` | physical 1 PLUS → BOTTOM, 2 MINUS → RIGHT |
| `L1` | `inductor.tapped` | START 1 → TOP, END 2 → RIGHT, TAP 3 → TAP |
| `C3` | **`capacitor.electrolytic`** | physical 1 PLUS → TOP, 2 MINUS → RIGHT |

For C3 placed at (100000, 75000) µm, actual symbol contacts are
(91000, 75000) µm for physical pin 1, and (109000, 75000) µm for pin 2.
There are five semantic nets (`TOP`, `LEFT`, `BOTTOM`, `TAP`, `RIGHT`).
The 18 authored segments include deliberately unjoined X crossings and
three marked junctions at (40000,20000), (40000,40000), (120000,40000) µm.
A separate X at (40000,60000) µm crosses TOP and BOTTOM with no node.

**Important physical distinction:** the graphic conductor islands of a
tapped winding, resistor body and capacitor plates are not direct electrical
external shorts. The netlist does not automatically short L1's three real
terminals or C3's separate plates. External conductivity is established by
authored sheet wire contacts only.

## Operating-point ERC

The test author explicitly assigns, relative to the common reference
`sheet-0V`, TOP=12 V, LEFT=10 V, BOTTOM=6 V, TAP=9 V and RIGHT=0 V.
These are *illustrative asserted potentials* for a single moment, not values
computed by an electrical solver. In the nominal case C2 and C3 pass
the physical terminal polarity rule. The deliberately reversed case sets
TOP=-2 V while RIGHT stays 0 V: only electrolytic C3 must report
`POLARITY_REVERSED`, and the independently validated wire graph is unchanged.

## Regression / negative matrix

| Case | Expected diagnostics |
|---|---|
| `valid` | 0 wire errors, 0 ERC errors (DRAFT warnings retained) |
| `electrolytic_pin_unwired` | `WIRE_DANGLING_END`, `WIRE_NET_DISCONNECTED`, `WIRE_PIN_UNWIRED` |
| `short_at_unmarked_crossing` | `WIRE_NET_SHORT` when an explicit junction is added |
| `one_micrometre_gap` | `WIRE_DANGLING_END`, `WIRE_NET_DISCONNECTED` |
| `missing_t_junction` | `WIRE_DANGLING_END`, `WIRE_NET_DISCONNECTED` |
| `reverse_electrolytic_bias` | `POLARITY_REVERSED`, without new wire errors |

Further tests independently mark each of the three unmarked X crossings
to ensure an actual inter-net short is detected, and check exact transformed
pin identity for all five real part classes × 4 rotations × 2 mirror settings.
They confirm that `C3.1` and `C3.2` and `L1.1/2/3` never merge through
graphics, whether rotated or not.

## Reproduce artifacts

```bash
python -m pip install -e ".[dev]"
python -m examples.review_end_to_end_circuit --output-dir output/electrical-cycle3
ruff check .
pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
```

The example emits:
- `end-to-end-clean.svg` — real UGO strokes, authored wires, explicit junction
  marks and uncalibrated specimen-only reference labels;
- `end-to-end-review.svg` — the same plus existing renderer geometry review
  overlay (pin coordinates and obstacle outlines);
- `end-to-end-diagnostics.json` — sorted machine diagnostics, real physical pin
  positions, netlist, scenarios and exact wire segment endpoints.

Golden copies live at `tests/fixtures/electrical-cycle3/` and are checked
against freshly generated UTF-8 output (CRLF normalized at checkout).
Neither SVG nor JSON includes timestamps, host paths or random identifiers.

## Limits

Not an autorouter, complete circuit ERC, current/voltage simulation, voltage
rating check, network theorem proof, layout clash/clearance approval, GOST
font approval, approved normative electrolytic shape, document exporter or
production-quality ESKD schematic. All source symbols stay DRAFT. Exact
micrometre contact rules are conservative and require manual junction authoring.

Coordinator must review the limited diff and CI for Python 3.12/3.13 before
integration. This workstream does not merge, force-push or close the issue.
