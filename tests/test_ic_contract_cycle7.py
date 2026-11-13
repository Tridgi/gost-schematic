"""Cycle7 physical IC contract; fixtures are SYNTHETIC, never manufacturer pinouts."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from examples.review_ic_cycle7 import synthetic_ic
from gost_schematic.core.geometry import Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.contacts import (
    ContactInventory,
    ContactRole,
    ContactSpec,
)
from gost_schematic.electrical.ic import (
    IcField,
    IcKind,
    IcPackage,
    IcPinRow,
    IcUnit,
    PinoutOrigin,
    resolve_ic_pin_positions,
    resolve_ic_port_sides,
    validate_ic_circuit,
)
from gost_schematic.electrical.ic_serde import (
    ic_from_json,
    ic_to_json,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef

FIXTURES = Path(__file__).parent / "fixtures" / "electrical-ic-cycle7"
COUNTS = (2, 4, 8, 14, 40, 64)


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize("kind", list(IcKind))
def test_physical_synthetic_inventory_as_one_part(count, kind):
    record = synthetic_ic(count, kind)
    device = record.device
    assert device.identifier.startswith("TEST_IC_")
    assert device.kind.draft_standard.endswith("(DRAFT)")
    assert device.kind.reference_prefix == ("DA" if kind is IcKind.ANALOG else "DD")
    assert device.package.pin_count == count
    assert device.package.origin is PinoutOrigin.SYNTHETIC
    assert len(device.pins) == count
    assert len({p.number for p in device.pins}) == count
    assert set(device.pin_map) == {str(i) for i in range(1, count + 1)}
    assert len(resolve_ic_pin_positions(device, record.specs, record.placements)) == count
    assert len({p.component_ref for p in record.placements}) == 1
    assert all(x.component_ref == kind.reference_prefix + "1" for x in record.placements)
    assert all(x.device_id == device.identifier for x in record.placements)
    if count >= 14:
        assert len(device.units) == 2
    else:
        assert len(device.units) == 1


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize("kind", list(IcKind))
def test_exact_json_v1_roundtrip_and_golden_synthetic(count, kind):
    record = synthetic_ic(count, kind)
    actual = ic_to_json(record)
    expected = (FIXTURES / f"TEST_IC_{kind.value.upper()}_{count}.json").read_text("utf-8")
    assert expected == actual
    assert ic_from_json(actual) == record
    assert ic_to_json(ic_from_json(actual)) == actual
    assert json.loads(actual)["record_type"] == "DRAFT_E3_IC"
    assert "СИНТЕТИЧЕСКАЯ_ФУНКЦИЯ" in actual if count >= 14 else "ТЕСТ" in actual
    assert "MAIN" not in actual  # visual placement does not become electrical pin type


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
@pytest.mark.parametrize("count", (2, 8, 14, 40, 64))
def test_eight_d4_poses_change_points_not_physical_pinrefs(count, rotation, mirror):
    record = synthetic_ic(count)
    baseline = resolve_ic_pin_positions(record.device, record.specs, record.placements)
    new_placements = tuple(
        replace(p, transform=Transform(rotation, mirror)) for p in record.placements
    )
    transformed = resolve_ic_pin_positions(record.device, record.specs, new_placements)
    assert set(baseline) == set(transformed)
    for p in record.placements:
        normal = next(x for x in new_placements if x.unit_id == p.unit_id)
        assert normal.component_ref == p.component_ref
    assert len(set(transformed.values())) == count
    sides = resolve_ic_port_sides(record.device, record.specs, new_placements)
    assert set(sides) == set(transformed)
    for p, spec in zip(new_placements, record.specs, strict=True):
        for row in spec.rows:
            ref = PinRef(p.component_ref, row.number)
            assert transformed[ref] == p.transform.apply(row.anchor) + p.origin
            assert sides[ref] == p.transform.side(row.side)


def test_one_circuit_component_and_nets_persist_across_multisection_relayout():
    record = synthetic_ic(14)
    component = ComponentInstance("DD1", record.device.identifier)
    other = ComponentInstance("VT1", "TEST_TRANSISTOR")
    nets = (
        Net("CTRL", (PinRef("DD1", "1"), PinRef("VT1", "G"))),
        Net("VDD", (PinRef("DD1", "13"),)),
        Net("GND", (PinRef("DD1", "12"),)),
    )
    circuit = Circuit((component, other), nets)
    before = circuit.nets
    validate_ic_circuit(record.device, circuit, "DD1")
    first = resolve_ic_pin_positions(record.device, record.specs, record.placements)
    rotated = tuple(replace(
        placement,
        origin=Point(placement.origin.x + 100000, placement.origin.y + 200000),
        transform=Transform(270, True),
    ) for placement in record.placements)
    second = resolve_ic_pin_positions(record.device, record.specs, rotated)
    assert set(first) == set(second)
    assert circuit.nets is before and circuit.components[0] is component
    assert len([c for c in circuit.components if c.reference == "DD1"]) == 1
    validate_ic_circuit(record.device, circuit, "DD1")
    assert PinRef("DD1", "1") in circuit.nets[0].members


def test_nc_unknown_and_double_net_membership_are_rejected():
    record = synthetic_ic(8)
    physical = ComponentInstance("DD1", record.device.identifier)
    for net in (
        Net("NC_SHORT", (PinRef("DD1", "8"),)),
        Net("UNKNOWN", (PinRef("DD1", "999"),)),
    ):
        with pytest.raises(ValueError):
            validate_ic_circuit(record.device, Circuit((physical,), (net,)), "DD1")
    repeated = (
        Net("A", (PinRef("DD1", "1"),)),
        Net("B", (PinRef("DD1", "1"),)),
    )
    with pytest.raises(ValueError, match="multiple nets"):
        validate_ic_circuit(record.device, Circuit((physical,), repeated), "DD1")


def test_same_label_never_substitutes_number_even_when_ink_label_collides():
    record = synthetic_ic(8)
    spec = record.specs[0]
    rows = tuple(replace(row, label="G") for row in spec.rows)
    variant = replace(spec, rows=rows)
    points = resolve_ic_pin_positions(record.device, (variant,), record.placements)
    assert len(points) == 8
    assert PinRef("DD1", "1") != PinRef("DD1", "2")
    assert variant.rows[0].label == variant.rows[1].label == "G"


def test_two_pins_same_logical_row_and_same_side_still_have_distinct_anchors():
    record = synthetic_ic(2)
    old = record.specs[0]
    rows = (
        replace(old.rows[0], side=Side.LEFT, row_key="DATA", anchor=Point(-4000, 5000)),
        replace(old.rows[1], side=Side.LEFT, row_key="DATA", anchor=Point(-4000, 9000)),
    )
    assert len({x.anchor for x in rows}) == 2
    spec = replace(old, rows=rows)
    assert len(resolve_ic_pin_positions(record.device, (spec,), record.placements)) == 2


def test_legacy_physical_pin_adapter_preserves_number_and_unknown_nc():
    record = synthetic_ic(8)
    part = record.device.to_legacy_part("DRAFT_ONLY")
    assert part.identifier == record.device.identifier
    assert part.reference_prefix == "DD"
    assert [p.number for p in part.pins] == [str(i) for i in range(1, 9)]
    assert part.pins[-1].electrical_type.value == "unspecified"
    assert part.pins[-1].number == "8"


@pytest.mark.parametrize("role", [
    ContactRole.POT_WIPER, ContactRole.FET_GATE, ContactRole.FET_SUBSTRATE,
    ContactRole.BJT_BASE, ContactRole.BJT_EMITTER, ContactRole.CONNECTOR_CONTACT,
])
def test_role_is_physical_not_ink_label(role):
    inventory = ContactInventory((
        ContactSpec("1", role, "real function", label="SAME"),
        ContactSpec("2", ContactRole.GENERAL, "another", label="SAME"),
    ))
    inventory.require_roles((role,))
    assert inventory.contacts[0].number != inventory.contacts[1].number


def test_pot_wiper_fet_substrate_and_bjt_contacts_not_lost():
    pot = ContactInventory((
        ContactSpec("1", ContactRole.POT_END_A, "end A"),
        ContactSpec("2", ContactRole.POT_WIPER, "moving contact"),
        ContactSpec("3", ContactRole.POT_END_B, "end B"),
    ))
    pot.require_roles((ContactRole.POT_END_A, ContactRole.POT_WIPER,
                       ContactRole.POT_END_B))
    fet = ContactInventory((
        ContactSpec("G", ContactRole.FET_GATE, "gate"),
        ContactSpec("D", ContactRole.FET_DRAIN, "drain"),
        ContactSpec("S", ContactRole.FET_SOURCE, "source"),
        ContactSpec("B", ContactRole.FET_SUBSTRATE, "substrate"),
    ))
    fet.require_roles((
        ContactRole.FET_GATE, ContactRole.FET_DRAIN, ContactRole.FET_SOURCE,
        ContactRole.FET_SUBSTRATE,
    ))
    with pytest.raises(ValueError, match="exactly one"):
        ContactInventory(fet.contacts[:3]).require_roles((ContactRole.FET_SUBSTRATE,))


def test_duplicate_physical_role_identity_and_units_fail_closed():
    record = synthetic_ic(8)
    device = record.device
    with pytest.raises(ValueError, match="Duplicate physical"):
        replace(device, pins=(*device.pins[:-1], replace(device.pins[-1], number="1")))
    with pytest.raises(ValueError, match="ownership"):
        replace(device, units=(
            device.units[0], IcUnit("U2", "duplicate 1", ("1",)),
        ))
    with pytest.raises(ValueError, match="missing"):
        replace(device, units=(replace(device.units[0], pin_numbers=("1", "8")),))
    with pytest.raises(ValueError, match="Duplicate"):
        ContactInventory((
            ContactSpec("1", ContactRole.FET_GATE, "gate"),
            ContactSpec("1", ContactRole.FET_SUBSTRATE, "substrate"),
        ))


def test_undeclared_rows_duplicate_physical_pin_and_corner_rejected():
    record = synthetic_ic(8)
    spec = record.specs[0]
    with pytest.raises(ValueError, match="PIN_NOT_PRESENTED"):
        resolve_ic_pin_positions(record.device, (
            replace(spec, rows=spec.rows[:-1]),
        ), record.placements)
    with pytest.raises(ValueError, match="Duplicate"):
        replace(spec, rows=(*spec.rows[:-1], replace(spec.rows[-1], number="1")))
    with pytest.raises(ValueError, match="IC_ANCHOR_INSIDE"):
        replace(spec, rows=(
            replace(spec.rows[0], anchor=Point(0, 5000)), *spec.rows[1:],
        ))
    with pytest.raises(ValueError, match="IC_ANCHOR_INSIDE"):
        replace(spec, rows=(
            replace(spec.rows[0], anchor=Point(-4000, spec.body.min_y)), *spec.rows[1:],
        ))
    with pytest.raises(ValueError, match="IC_ANCHOR_COLLISION"):
        replace(spec, rows=(
            spec.rows[0], replace(spec.rows[1], anchor=spec.rows[0].anchor),
            *spec.rows[2:],
        ))


def test_analog_and_digital_profiles_do_not_share_prefix_or_assume_gost_approval():
    assert IcKind.ANALOG.reference_prefix == "DA"
    assert IcKind.DIGITAL.reference_prefix == "DD"
    for kind in IcKind:
        record = synthetic_ic(14, kind)
        assert kind.draft_standard.endswith("DRAFT)")
        assert all(p.component_ref.startswith(kind.reference_prefix)
                   for p in record.placements)


def test_unauthenticated_real_pinout_and_unmarked_synthetic_claim_rejected():
    for data in [
        {"manufacturer": None, "datasheet_url": None, "revision": None},
        {"manufacturer": "claimed", "datasheet_url": None, "revision": "1"},
        {"manufacturer": "claimed", "datasheet_url": "http://invalid", "revision": "1"},
    ]:
        with pytest.raises((TypeError, ValueError)):
            IcPackage("PKG", "generic", 8, PinoutOrigin.MANUFACTURER_DATASHEET, **data)
    record = synthetic_ic(8)
    with pytest.raises(ValueError, match="TEST_IC_"):
        replace(record.device, identifier="REAL_IC_WITHOUT_EVIDENCE")


def test_typed_fields_and_auxiliary_fields_invalid_rejected():
    record = synthetic_ic(8)
    spec = record.specs[0]
    with pytest.raises(ValueError):
        replace(spec, rows=(
            replace(spec.rows[0], field=IcField.AUX_LEFT),
            *spec.rows[1:],
        ), aux_left=None)
    with pytest.raises(TypeError):
        IcPinRow("1", "left", Point(-4, 5), "row")
    with pytest.raises(TypeError):
        replace(record.device.pins[0], electrical_type="input")
    bad = replace(record.placements[0], component_ref="R1")
    with pytest.raises(ValueError):
        resolve_ic_pin_positions(record.device, record.specs, (bad,))


@pytest.mark.parametrize("tamper", [
    lambda data: {**data, "schema_version": 2},
    lambda data: {**data, "schema_version": True},
    lambda data: {**data, "record_type": "E1"},
    lambda data: {**data, "unknown_field": 1},
    lambda data: {**data, "device": {
        **data["device"], "package": {
            **data["device"]["package"], "pin_count": 8.0,
        },
    }},
    lambda data: {**data, "specs": [{
        **data["specs"][0], "rows": [
            {**data["specs"][0]["rows"][0], "anchor_um": [1000.1, 5000]},
            *data["specs"][0]["rows"][1:],
        ],
    }]},
    lambda data: {**data, "specs": [{
        **data["specs"][0], "rows": [
            {**data["specs"][0]["rows"][0], "number": "999"},
            *data["specs"][0]["rows"][1:],
        ],
    }]},
])
def test_strict_private_json_rejects_malformed_and_inferred_identity(tamper):
    data = json.loads(ic_to_json(synthetic_ic(8)))
    with pytest.raises((ValueError, TypeError)):
        ic_from_json(json.dumps(tamper(data)))


def test_json_duplicate_keys_and_nonfinite_numbers_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        ic_from_json('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ValueError):
        ic_from_json(ic_to_json(synthetic_ic(8)).replace('"schema_version": 1',
                                                         '"schema_version": NaN'))


def test_mutation_does_not_rewrite_old_circuit_api_or_imply_svg_junction():
    record = synthetic_ic(14)
    component = ComponentInstance("DD1", record.device.identifier)
    circuit = Circuit((component,), (Net("CTRL", (PinRef("DD1", "1"),)),))
    assert circuit.nets[0].members == (PinRef("DD1", "1"),)
    assert not hasattr(record, "nets")
    assert not hasattr(record.device, "electrical_nets")
    assert not hasattr(record, "junctions")
    assert all(p.pin_numbers for p in record.device.units)
