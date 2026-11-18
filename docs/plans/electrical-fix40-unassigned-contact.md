# Issue #40 — prevent silent wire contact with unassigned physical pin

**Verified baseline:** `integration/stage0-12` and `parallel/electrical-fix40` both at `73bc6f88a814d7b92267326fc1dab8f127e92e77` before edits. This is a MAJOR geometry/electrical safety regression from QA Issue #40.

## Failure mechanism and proof

`validate_external_wires()` resolves the positions of every physical pin of each real `PartDefinition` using the corresponding transformed `SymbolDefinition`. It distinguishes endpoint or explicit-junction attachment from a conductor that merely crosses a pin's coordinate in its interior.

In the original implementation, an unassigned contact lying on a wire interior set `interior_contact=True`, but the only non-junction diagnostic was guarded by `ref in owners`. Because an unassigned contact had no net owner, this guard suppressed `WIRE_PIN_CONTACT_UNDECLARED`. The separate `WIRE_PIN_UNASSIGNED` check requires an *attachment*, so it also missed the interior contact. A QA reproduction using `resistor.fixed` returned **no diagnostics** despite a straight external wire crossing physical R1.2.

A targeted test was executed **before the production change** and failed exactly as reported:

```text
assert set() == {'WIRE_PIN_CONTACT_UNDECLARED'}
FAILED test_original_qa_reproducer_on_real_resistor_json
```

## Minimal production correction (no API change)

Remove only the `and ref in owners` guard from the existing `if interior_contact and not attachments[ref]` branch. Preserve the existing `WIRE_PIN_CONTACT_UNDECLARED` severity ERROR, subject and message, and every other electrical/geometry rule. Physical pin existence does not depend on membership in `Circuit.nets`.

Exact semantics:

| Geometric condition | Diagnosis | Electrical interpretation |
|---|---|---|
| **Any** real physical pin lies strictly in a wire's interior, with no explicit junction and no separate attached segment at that pin | `WIRE_PIN_CONTACT_UNDECLARED` (ERROR) | **No** implicit attachment or net membership |
| Unassigned physical pin is the actual endpoint of a wire or carries an explicitly authored junction | `WIRE_PIN_UNASSIGNED` (ERROR) | Physical contact is represented, but its semantic net was never declared |
| Two independent wires cross at a coordinate that is **not a physical pin** and is not an explicit junction | No new error | They remain distinct external-wire islands; an unmarked X does not connect |
| An explicit junction joins two distinct semantic nets | `WIRE_NET_SHORT` (ERROR) | Existing disjoint-set union and short detection remain authoritative |
| Line misses the exact physical pin coordinate by 1 µm | No new contact warning | The validator is exact-coordinate, not stroke-width physical clearance DRC |

This **does not implement insulated bridges over physical terminals**. In the current one-layer external-wire model, a geometric traversal directly through a real contact is ambiguous/unsafe and must be flagged, even if a human draftsman intended a non-contact visual crossing. Such a representation requires a separate explicit bridge/layer contract and RFC, not automatic reclassification here.

## Regression matrix (real catalog only)

`tests/test_external_wire_unassigned_pin.py` uses real JSON-backed `resistor.fixed`, `capacitor.fixed`, `capacitor.polarized`, `capacitor.electrolytic` and the real catalog `inductor.tapped` winding/physical part. Unassigned **physical pin #2** is positioned directly on one real wire between two *correctly assigned* other catalog resistor pins.

- Every class × 4 rotations × 2 reflections × 4 axial line directions: **160 negative tests**; each asserts ERROR with exact physical pin identity and excludes false-short or inferred membership.
- The same combinations shifted 1 µm perpendicular to the wire: **160 near-miss controls**; each asserts no new contact diagnostic.
- Every class × 4 rotations × 2 reflections with diagonal traversal: **40 additional negative tests**.
- The exact Issue #40 physical resistor reproducer, split endpoint, explicit junction, already-assigned physical pin, and independent real-catalog unmarked X / deliberate junction short tests; verifies input immutability.

No changes to shared `Circuit`, `Net`, `PinRef`, `ExternalWireGraph`, model, catalog, SVG renderer, `api.py`, routing algorithm, or public signatures. Existing algorithm complexity remains O(number of wire segments × number of physical pin locations) for this contact check; no extra geometry lookup or network inference.

## Reproduce

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
python -m pip wheel . --no-deps --wheel-dir dist
python scripts/verify_wheel_payload.py dist
```

CI on both Python 3.12 and 3.13 must be green. All catalogue symbols remain DRAFT: zero hard structural errors are not approval against ГОСТ/ЕСКД.

## Separation from Issue #44

C3 joint-placement/route-cost optimization is documented only in [the separate Issue #44 analysis](https://github.com/Tridgi/gost-schematic/issues/44#issuecomment-6856909816). No layout changes, C3 reposition, route generation, or cost-function implementation are part of this safety PR. The two-pin autorouter PR #39 and its source branch remain untouched.

## Known limits

Only **exact** physical contact coordinates are examined. Passing within the actual symbol stroke or pin stub away from the contact coordinate is not detected by this routine (requires dedicated stroke geometry/clearance DRC). Physical connection at a pin coinciding with multiple external conductors follows the existing endpoint/explicit-junction semantics; this patch does not infer missing non-junction graph connections. Deliberate wire-over-pin bridges are unsupported. A conservative error is intentional until the representation supports safe multi-layer crossings. Do not merge or close this issue from the electrical workstream.
