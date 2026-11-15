# MAIN 3 cycle 9 — TL494CN manufacturer → physical Circuit/Net/PinRef → PAINT

**Owner:** ELEKTRIK IC #87 / PR #97; MAIN 3 [instructions #6884105219](https://github.com/Tridgi/gost-schematic/pull/97#issuecomment-6884105219). **Scope:** DRAFT only. No merge/main/integration mutation.

## Authentic input and immutable source guarantee

- Original photographic TL494 reconstruction HEAD (never edited):
  `e695c415fdced164b0e0c39c5249d030795a0aa6`.
- Original model output:
  `examples/tl494_model_output/TL494_full_typed_netlist.json`,
  Git blob SHA `c4cfd515782bf856a7a44fbe2c2ceacd303208d6`.
- Exact copied but curated **source inventory only**, no moved electrical topology:
  `tests/fixtures/tl494_photo_23_frozen_cycle9.json`.
- Original 23 real `ComponentInstance` refs: `C1…C7, R1…R8, VT1, VD1, L1, L2, FU1, X1, X2, DA1`.
  15 named Nets and **62 exact (reference, physical number) connections**;
  all **DA1.1…DA1.16** have Net memberships. This fixture does not invent
  or assign missing/extra source Nets.
- Original source had the known wrong **DA1.3 FEEDBACK=OUTPUT**. The adapter
  purposely does **not** inherit its role, name or pin orientation; it derives
  all 16 from `tl494cn_device()` and `verify_tl494cn_ti_pinout()`
  (TI `SLVS074J`, [Table 4-1](https://www.ti.com/lit/ds/symlink/tl494.pdf#page=3)).
  **DA1.3 FEEDBACK=INPUT, DA1.13 OUTPUT CTRL=INPUT**, FB/OC are only UI labels.
  No cast of `ElectricalType` may reverse manufacturer I/O role.

This source is not a validated electrical design. E.g. the original image
may have questionable physical connections: the adapter preserves them
unchanged for QA rather than automatically “fixing” the topology or claiming
functional operation. The 23-part JSON contains **no verified placements of
the other 22 parts**, and these `ComponentInstance.origin=(0,0)` placeholders
are explicitly **NON-PRINTABLE**. The reference source's full-sheet routed
segments, source-photo parity and DRC remain owned by #115/#108/#109/#107.
This adapter must NOT be used to build a finished connected full-sheet SVG.

## Typed API intended for QA #99 and reconstructer #115

Source at `src/gost_schematic/electrical/ic_circuit_adapter.py`,
with public, reusable `bind_ic_circuit(record, circuit, *,
aliases=None, external_pin_numbers=None) -> IcCircuitBinding`.

For the exact 23-part fixture:

```python
from examples.tl494_cycle9_circuit_integration import (
    build_frozen_photo_23, assert_frozen_photo_topology,
)
from gost_schematic.electrical.ic_circuit_adapter import IcCircuitBinding
from gost_schematic.model.circuit import PinRef

binding, source = build_frozen_photo_23()
assert len(binding.circuit.components) == 23
assert len(binding.circuit.nets) == 15
assert len(binding.contacts) == 16
assert binding.contact(PinRef("DA1", "3")).electrical_type.value == "input"
assert binding.contact(PinRef("DA1", "3")).schematic_short_label == "FB"
assert binding.contact(PinRef("DA1", "13")).schematic_short_label == "OC"
assert_frozen_photo_topology(binding, source)
saved = binding.to_json()
assert IcCircuitBinding.from_json(saved) == binding
```

The `IcCircuitBinding` owns:
- `record: IcLibraryRecord`, real `IcDeviceDefinition` with immutable full TI
  `IcPhysicalPin.number/name/function/electrical_type`, authoritatively typed
  `IcSymbolSpec` and one or more `IcUnitPlacement`.
- `circuit: Circuit`, **exact** original nets and all external instances,
  `PinRef` objects, true `Quantity` values as SI `Decimal`.
- `part: PartDefinition`, exact legacy `ElectricalType` mapping for *all*
  actual 16 package contacts; full manufacturer pin names are retained.
- `symbol_surrogate: SymbolDefinition | None`, DRAFT geometry-only one-unit
  surrogate for the native sheet's `ComponentInstance.pin_positions()` and
  symbol checker. It is **NEVER** the final IC print artwork; the only graphical
  label allowed here is the separate short alias.
  **Multi-unit:** this field is `None` rather than inventing a single compact
  printed outline or merging physical sections.
- `contacts: tuple[IcCircuitContact,...]`, every real `PinRef` with
  `unit_id`, full manufacturer name, UI short label, `IcPinType`,
  exact **integer µm** `world_anchor`, transformed `world_side`, and true
  `net_id | None`. Never deduce a Net from a label or crossing.
- `external_pin_numbers`, independent named inventory for the other
  22 source parts (`R5` 3 contacts, `VT1` 3 contacts, others 2),
  validated for **every** Circuit component; a foreign or unknown contact
  cannot be added by a renderer or auto-router.

**Strict serializer:** `binding.to_json()` and
`IcCircuitBinding.from_json(text)`; schema v1 explicit fields,
typed transform D4, exact signed coordinates, strict unknown keys, duplicate
JSON keys, duplicate Net names, duplicate/multiple physical membership,
source mismatch, role mismatch, foreign/unknown/NC pins, invalid/incomplete
external inventory, wrong alias, missing functional unit, and 16/16 TI
manufacturer source drift fail **CLOSED**. Roundtrip exact and idempotent.
The canonical original `IcLibraryRecord` private serde remains unchanged.

## World-coordinate and geometry revision contract

`resolve_ic_pin_positions(record.device, record.specs,record.placements)`
is the sole authority for actual physical lead endpoints. No ink,
SVG, character count, crossing position, package footprint or rerouter may
generate a substitute. `IcCircuitBinding.symbol_surrogate` maps them exactly
via the native `ComponentInstance.pin_positions()` at D4 poses.
The inverse matrix uses integer dot products on a D4 orthonormal basis,
**no floats, no rounding, zero µm tolerance**.

For geometry revision, call
`updated, delta = binding.revise(candidate_record, consent=IcGeometryConsent(...))`
with **exact** changed physical `PinRef` set and separately enumerated
connected-moved contacts approved for rerouting. No auto-commit of
old wires. A text-only 0/90/270° revision has `delta.moved == ()` and
`binding.circuit.nets` unchanged; the physical transistor pin directions
and numbers cannot be changed by PWM word orientation.

For genuine PAINT #93, call:

```python
proposal = propose_ic_paint_binding(binding.record, style, measurer)
# Obtain source fingerprint and exact changed PinRefs, including all connected
# moved PinRefs. Approval is explicit, NEVER inferred from this example.
updated, delta = binding.revise(proposal.record, consent=approved_consent)
manifest = updated.bind_paint(proposal)  # 16 typed PAINT editor contacts
# Actual SVG and ink via paint.render_resolved_ic(...), not surrogate art
```

`bind_paint()` independently rechecks `IcPaintBinding.verify_endpoints()`,
full manufacturer source/physical role/Net vs actual `PAINT` contact manifest,
exact endpoints and unit ownership. Stale PAINT revisions or fake contacts
are rejected. GPIO-style green diagnostic rectangles are editor-only, absent
from clean paper output. Current known tested PAINT SHA is pinned in
`.github/workflows/ic-paint-cross-cycle7.yml`; moving PAINT owner HEAD
**requires new cross-PR CI**.

## QA minimum test matrix

- **Actual source (not 13-component substitute):** 23 refs, 15 named Nets,
  62 PinRef memberships, full **16 manufacturer DA1 Pins**, FEEDBACK/OC
  input, FB/OC display-only, unchanged SI `Quantity`.
- D4: 0/90/180/270° × mirror yes/no, `ComponentInstance.pin_positions()`
  matches each PAINT physical endpoint with 0 µm tolerance; source Net
  topology independent of view transform.
- Function text independent 0°/90°/270°, correct SVG word transform for
  signed bottom-to-top 270°, never rotate actual pins; PAINT may
  explicitly BLOCK a collision/overflow but may not silently move a pin.
- Strict JSON roundtrip for 23 components, all typed symbols, 15 named Nets,
  62 member pairs, 16 contacts, full TI aliases/manufacturer metadata,
  transforms & external pin inventory.
- Adversarial: duplicate same-Net contact; one contact in multiple Nets;
  duplicate Net/instance names; missing Net from immutable source; swapped
  physical pin numbers; unknown DA1/foreign external contact; fake external
  inventory; linked contact with NC role; stale or changed factory role;
  **coordinated forgery of pin3 and its alias together**; repeated unit owner;
  missing logical unit; corrupt JSON, duplicate keys and wrong transform.
- Multiple functional sections: two-unit *clearly SYNTHETIC* digital test
  checks 14 physical pins, two PAINT unit views, **one Circuit component**,
  unchanged Nets and exact contact ownership. Real TI TL494CN stays
  **one manufacturer 16-contact device**, not a fake 14-pin substitute.
- Full legacy regression CI both Python 3.12 and 3.13,
  dedicated actual PAINT workflow **without hidden skips**,
  Ruff, wheel, real Type A raster and 0 µm geometry proof.

## Engineering gates

**PASS** is source-role consistency and strict physical topology only
when CI actually succeeds at its final HEAD.

**BLOCKED:** source-photo routing/DRC and whole-sheet printed E3 1:1 (#115,
#108, #109), real ESKD normative approval (#91), any NC-backed
multi-unit **legacy** `PartDefinition` adapter (the common `ElectricalType`
has no NC; error `IC_ADAPTER_UNSUPPORTED_LEGACY_NC_PIN`), and PAINT owner
SHA migration without a newly pinned test. Nothing is merged.


## MAIN 3 Next integration sprint (2026-11-15): trusted PAINT 161c31bd and sheet composer

The new exact PAINT owner dependency is
`161c31bd0b538c6e827341ae465c3b3a59f6637d` (PR #93),
not the older `67b1aaabee45327416bcdea246dd6a3b51118db4`.
The actual `ic_hotspots.verify_ic_connection_targets` intentionally
supports **partial unverified read-only cosmetic previews**. Even when
it validates the physical reference/coordinate, it has **no trusted
`Circuit.Net` input**, cannot determine that an active pin was forged NC,
and does not certify a complete 16-tip overlay. A direct raw PAINT
`IcConnectionTarget` is **UNVERIFIED**, never permission for Net changes.

### Rechecked trust boundary (code, not a future promise)

`IcCircuitBinding.seal_paint_overlay(actual_ic_paint_binding)` now
rebuilds the `IcEditorContactManifest` from full source `Circuit`, confirms
all 16 real manufacturer `PinRef`, unit ownership, full original Net
identities, actual integer-µm tips, NC/active semantics and complete
per-unit targets. It returns frozen `IcVerifiedPaintSnapshot` with a
**non-secret audit SHA256** of the serialized typed source. No user
target list is accepted as a proof. Calling `verify_against(source,
paint_binding)` re-derives all rows before comparing:
`IC_TRUSTED_OVERLAY_PROVENANCE_OR_TARGET_MISMATCH` rejects
forged/missing/duplicate/foreign 16-point targets and wrong networks.
`IcVerifiedPaintSnapshot.render(...,diagnostics=True)` enforces the
check again, renders from **actual PAINT** with fully source-verified
target list, parses the generated SVG to compare **all physical lead
tips and manufacturer roles at 0 µm tolerance**, and verifies all
16 final green diagnostic marks by `data-pin-ref`, original
`data-net-id` and exact integer-µm center. Clean mode omits these
editor-only squares. No operation mutates `Circuit.Net` or wires.

A separate previously-unnoticed source metadata drift was corrected:
`ResolvedIcPin.label` is now the **full immutable manufacturer name**
(`FEEDBACK`, `OUTPUT CTRL`) and `display_alias` is the *editable*
short on-paper label (`FB`, `OC`). The independent
`manufacturer_electrical_type` is now always transmitted to
PAINT and verified. `IcPaintBinding.verify_endpoints` rejects
counterfeit full names, alias swaps or false factory electrical roles
even when number/coordinate/short text still look valid. Actual SVG
`data-full-manufacturer-name`/`data-visible-pin-alias`/
`data-manufacturer-electrical-type` are verified by tests; the visible
glyphs and all physical endpoints remain unchanged.

With PAINT's newly implemented
`rendering.ic_sheet_composition.compose_authoritative_ic_layers`,
the user/QA/reconstructor must supply the **same** `Circuit` and
its matching `PartDefinition/SymbolDefinition` when composing
the full sheet. The composer independently verifies the complete
PAINT `IcRendered.connection_targets` against `Circuit.Net`,
physical world `PinRef`, actual SVG strokes and markers. The
new tests run both **clean** and **diagnostic** composition with
the 23/15/62 locked Circuit and adversarial alterations to
the actual PAINT `IcRendered`. This is an integration boundary
test using a real physical 16-pin rendered symbol plus the actual
`Circuit`, **not** a newly routed complete photo A3 E3 sheet.

```python
# Only after resolving PAINT from its exact owner source and validating
# the revised physical IcSymbolSpec via explicit IcGeometryConsent:
trusted = updated_circuit_binding.seal_paint_overlay(paint_binding)
trusted.verify_against(updated_circuit_binding, paint_binding)
clean_ugo = trusted.render(
    updated_circuit_binding, paint_binding, style, measurer,
    diagnostics=False,
)
debug_ugo = trusted.render(
    updated_circuit_binding, paint_binding, style, measurer,
    diagnostics=True,
)
# The read-only real PAINT composer may now accept the actual 23-part
# Circuit, native symbol surrogate, and the corresponding IcRendered.
# Never infer an electrical Net from a green square, text label or SVG path.
```

**New negative matrix:** `tests/test_ic_trusted_paint_cycle9.py`
checks the actual current PAINT module, source-locked real 23/15/62,
wrong component, wrong Net, active-faked-NC, missing and duplicate
16-point targets, wrong contact number and +1 µm tip, fake source
revision/checksum, mutable manifest forge, illegitimate source-Net
revision, PAINT-sheet compositor forged/partial overlay, tampered
lead SVG/marker and independent PWM 0/90/270° word rotations.

**Important remaining BLOCKED:** New printed A3 layout currently has
failed `DA1.12 INPUT_POS` lead-forest routing and 7 Nets incomplete
according to MAIN 3 audit #6885041804. Neither the typed overlay nor
the current PAINT compositor fixes router #114's physical paths, sheet
ink collisions or old source 9 ERROR/32 WARNING, and no independent
QA #99 acceptance or GOST approval is implied. All output DRAFT.
