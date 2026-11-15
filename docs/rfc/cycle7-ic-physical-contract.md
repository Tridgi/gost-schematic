# RFC IC-C7-001 — physical E3 IC and multi-unit view contract

Status: EXPERIMENTAL DRAFT, no normative approval. Owner Issue #87; PAINT #88; ESKD #91; QA #92.
Design-first proposal: https://github.com/Tridgi/gost-schematic/issues/87#issuecomment-6866650570
PAINT explicitly accepted external endpoint geometry: https://github.com/Tridgi/gost-schematic/issues/87#issuecomment-6866914274
Numeric display row coordination: https://github.com/Tridgi/gost-schematic/issues/88#issuecomment-6866982126

## Physical truth and immutable namespace

- IcDeviceDefinition(identifier,kind,package,pins,units): ONE actual Circuit component, potentially multiple visual units; immutable distinct physical pin numbers.
- IcKind.ANALOG → DA, preliminary ГОСТ 2.759-82; IcKind.DIGITAL → DD, preliminary ГОСТ 2.743-91. Both DRAFT.
- IcPackage(package_id,family,pin_count,origin,manufacturer,datasheet_url,revision): source required for real pinout. All supplied TEST_IC fixtures are SYNTHETIC and must not be used as manufacturer data.
- IcPhysicalPin(number,name,function,electrical_type): number is the physical PinRef key, never the visual label. Typed INPUT, OUTPUT, BIDIRECTIONAL, POWER_INPUT, POWER_OUTPUT, OPEN_COLLECTOR, PASSIVE, NC.
- IcUnit(id,function,pin_numbers): disjoint ownership of all non-NC pins. NC never connects to an electrical Net. Power pins cannot disappear silently.
- IcPinRow(number,side,anchor,row_key,label,field,visual_row): anchor is LOCAL exact integer micrometre EXTERNAL lead endpoint, strictly outside corresponding box side, not at a corner. row_key groups functional meaning; visual_row is a separate unique positive drawing row per side. Number is never derived from label.
- IcSymbolSpec(device_id,unit_id,body,main_field,rows,aux_left,aux_right,revision): explicit rectangle and optional auxiliary fields. No text-width estimation by character count.
- IcUnitPlacement(component_ref,device_id,unit_id,origin,transform): all unit projections refer to ONE physical DA1/DD1. resolve_ic_pin_positions outputs authoritative PinRef→Point, resolve_ic_port_sides outputs transformed side. D4 never changes PinRef identity.
- validate_ic_circuit checks actual Circuit component, NC rejection, missing pin and membership conflicts; never interprets graphical intersection as a short. Legacy to_legacy_part is inventory-only and FAILS CLOSED on any NC or multi-unit package; legacy APIs cannot express that safety information.
- ContactInventory preserves separate transistor gate/source/drain/substrate, BJT base/collector/emitter, potentiometer wiper/end terminals, fuse and physical connector contacts, even if labels match.

## PAINT boundary

PAINT phase 1 measures actual Type A glyph ink and proposes dimensions. Phase 2 uses a NEW IcSymbolSpec with explicitly reauthored body/row anchors, re-resolved by ELEKTRIK. No UI guess and no automatic relocation. The PAINT renderer compares exact external anchor to the drawn lead and fails on 1µm discrepancy (IC_PIN_ANCHOR_MISMATCH). Numbers and names have separate measured ink boxes. Placement is DRAFT until ESKD source-specific norm review; source-note ГОСТ 2.743-91 §2.3.12 numbers above pin lines is PAINT responsibility.

## Experimental JSON and tests

Strict deterministic DRAFT_E3_IC v1 serialization preserves all physical numbers and exact integer coordinates, rejects duplicate/unknown fields, float coordinates, missing unit pins and duplicate anchor/visual row. Twelve SYNTHETIC fixtures: ANALOG/DIGITAL × 2,4,8,14,40,64 physical pins; 14/40/64 split into multiple units, one real component. Tests cover D4 ×8, labels and numbers 1/10/40, NC/POWER/OC, Unicode stress, no Circuit.Net mutation.

Commands: python -m examples.review_ic_cycle7 --output-dir output/ic-cycle7
          pytest -q tests/test_ic_contract_cycle7.py
          ruff check .
          python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
          python -m pip wheel . --no-deps --wheel-dir dist
          python scripts/verify_wheel_payload.py dist

No changes to old E3/E1/public API, renderer, catalog or main. PAINT real font integration and ESKD/QA approval remain separate. DO NOT MERGE.
