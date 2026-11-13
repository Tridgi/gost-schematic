# Issue #58 — foreign-net interior contact at an already attached pin

## Verified source
- Integration/stage0-12 parent: `2052e9d3a903edea860c100e00609ceee3c9062b`.
- Predecessor fix: Issue #40 / merged PR #48, guarding `interior_contact and not attachments[ref]`.
- Independent QA report: Issue #58 and QA PR #42: 16 D4 orientation/reversal xfails, 16 1µm controls.

## The original failure (reproduced before editing)
Four actual `resistor.fixed` physical passport + catalog symbol instances:
- R1.1 = (0,0) assigned to net A;
- R2.1 = (-20000,0) assigned to A;
- R3.1 = (0,-10000) assigned to net B;
- R4.1 = (0,10000) assigned to B.

The authored, junction-free graph contains A from (-20000,0) to (0,0), **ending at R1.1**, plus B from (0,-10000) to (0,10000), **passing R1.1 in its interior**. `attachments[R1.1]` includes A, so the old guard skipped `WIRE_PIN_CONTACT_UNDECLARED` even though the foreign B route touched that physical terminal. Baseline reproduction produced `diagnostics == ()`, and an added negative regression failed as expected.

## Minimal correction
Keep the public `validate_external_wires` signature, `WireSegment`, `ExternalWireGraph`, and existing topology untouched. Replace only the per-pin aggregate boolean `interior_contact` by a set `interior_nets` of the actual net labels of **non-junction wire-interior contacts**.

Issue an existing `WIRE_PIN_CONTACT_UNDECLARED` ERROR if an interior exists **and** (a) the physical pin has no attached conductor at all (retains #40 behavior) **or** (b) any interior wire belongs to a net not listed in the physical pin's owners. A legitimate A endpoint attachment can never suppress an unmarked B interior crossing. This does not union the wire islands, add the physical pin to B, synthesize junctions, mutate the circuit, or claim an electrical short on a visual X.

If the graph **explicitly** contains a junction at the foreign-net crossing, its established `WIRE_NET_SHORT` detection still runs. Unmarked X crossings elsewhere away from real contacts remain electrically separated. Normal same-net T junction with an authored node remains valid; without the node, existing connectivity diagnostics remain.

The detection is exact at the physical pin coordinate (µm): a B route translated 1µm sideways is a valid unmarked X and yields **no false electrical short**. Existing visual thickness, pin escape corridors and stroke clearance are outside this per-coordinate validator and require independent DRC.

## Tests
`tests/test_external_wire_foreign_pin_contact.py` uses the real versioned `resistor.fixed` catalog and D4 composition:
- 4 rotations × 2 mirror states × 2 reversed segment directions = **16 negative cases**, all expecting exactly the existing `WIRE_PIN_CONTACT_UNDECLARED` ERROR for R1.1;
- another **16 controls** at 1 µm exact perpendicular displacement expecting zero diagnostics;
- exact four-resistor repro and input segment permutation; explicit foreign junction requires real short, no junction must never infer short; untouched #40 free physical pin regression; same-net T junction and missing T marker, immutable inputs.
- All existing electrical, unassigned contact and full project regression suites remain enabled without xfail.

## Reproduce
```sh
ruff check .
pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
```

All catalog symbols remain DRAFT. This independent safety PR contains no change to original Draft PR #39, no placement/example changes (#44 separate), no public API, no shared models, no renderer and no changes to main. Coordinator owns review and merge.
