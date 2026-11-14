"""Cycle7 physical IC contract; fixtures are SYNTHETIC, never manufacturer pinouts."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from examples.review_ic_cycle7 import synthetic_ic
from gost_schematic.core.geometry import Box, Point, Side
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
    IcPinType,
    IcPortLayout,
    IcUnit,
    PinoutOrigin,
    resolve_ic_pin_positions,
    resolve_ic_port_sides,
    validate_ic_circuit,
)
from gost_schematic.electrical.ic_serde import (
    IcLibraryRecord,
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


def test_legacy_adapter_fails_closed_on_nc_and_multi_unit():
    for count in (8, 14, 40, 64):
        with pytest.raises(ValueError, match="IC_UNSAFE_LEGACY_ADAPTER"):
            synthetic_ic(count).device.to_legacy_part("DRAFT_ONLY")
    record = synthetic_ic(2)
    part = record.device.to_legacy_part("DRAFT_ONLY")
    assert part.identifier == record.device.identifier
    assert part.reference_prefix == "DD"
    assert [p.number for p in part.pins] == ["1", "2"]
    assert [p.electrical_type.value for p in part.pins] == ["input", "output"]


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


@pytest.mark.parametrize("kind", (IcKind.DIGITAL, IcKind.ANALOG))
@pytest.mark.parametrize("count", (8, 14, 40, 64))
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirrored", (False, True))
def test_explicit_vertical_physical_pinrefs_are_exact_model_only(
    kind, count, rotation, mirrored,
):
    """TOP/BOTTOM is valid physical identity; ESKD ink is separately BLOCKED."""
    source = synthetic_ic(count, kind)
    specs = []
    for spec in source.specs:
        # This is an explicit physical-model demonstration with a 5mm row
        # pitch, NOT an ESKD-approved top/bottom graphical layout.
        width = max(60000, (len(spec.rows) + 2) * 5000)
        new_body = Box(
            spec.body.min_x, spec.body.min_y,
            spec.body.min_x + width, spec.body.max_y,
        )
        rows = []
        for index, row in enumerate(spec.rows):
            role = source.device.pin_map[row.number].electrical_type
            side = Side.TOP if role in (
                IcPinType.INPUT, IcPinType.POWER_INPUT,
            ) else Side.BOTTOM
            rows.append(replace(
                row, side=side,
                anchor=Point(
                    new_body.min_x + (index + 1) * 5000,
                    new_body.min_y - 10000 if side is Side.TOP
                    else new_body.max_y + 10000,
                ),
            ))
        specs.append(replace(
            spec, body=new_body, rows=tuple(rows),
            profile=replace(spec.profile, port_layout=IcPortLayout.TOP_BOTTOM),
            revision=spec.revision + 1,
        ))
    placements = tuple(replace(
        placement, transform=Transform(rotation, mirrored),
    ) for placement in source.placements)
    vertical = IcLibraryRecord(source.device, tuple(specs), placements)
    restored = ic_from_json(ic_to_json(vertical))
    assert restored == vertical
    endpoints = resolve_ic_pin_positions(
        vertical.device, vertical.specs, vertical.placements,
    )
    sides = resolve_ic_port_sides(
        vertical.device, vertical.specs, vertical.placements,
    )
    assert len(endpoints) == count
    assert set(endpoints) == {
        PinRef(kind.reference_prefix + "1", str(number))
        for number in range(1, count + 1)
    }
    for spec, placement in zip(
        vertical.specs, vertical.placements, strict=True,
    ):
        for row in spec.rows:
            ref = PinRef(placement.component_ref, row.number)
            assert endpoints[ref] == (
                placement.transform.apply(row.anchor) + placement.origin
            )
            assert sides[ref] == placement.transform.side(row.side)
            assert row.side in (Side.TOP, Side.BOTTOM)
            assert row.anchor.x != spec.body.min_x
            assert row.anchor.x != spec.body.max_x
    physical = ComponentInstance(
        kind.reference_prefix + "1", source.device.identifier,
    )
    net = Net("NET_A", (PinRef(physical.reference, "1"),))
    circuit = Circuit((physical,), (net,))
    validate_ic_circuit(vertical.device, circuit, physical.reference)
    assert circuit.nets == (net,)
    assert circuit.components == (physical,)


def test_vertical_physical_port_at_frame_corner_fails_closed():
    source = synthetic_ic(8)
    spec = source.specs[0]
    oriented_rows = tuple(replace(
        row,
        side=Side.TOP,
        anchor=Point(
            spec.body.min_x + 5000 * (index + 1),
            spec.body.min_y - 4000,
        ),
    ) for index, row in enumerate(spec.rows))
    wide = Box(
        spec.body.min_x, spec.body.min_y,
        spec.body.min_x + (len(spec.rows) + 2) * 5000, spec.body.max_y,
    )
    with pytest.raises(ValueError, match="IC_ANCHOR_INSIDE"):
        replace(
            spec, body=wide,
            profile=replace(spec.profile, port_layout=IcPortLayout.TOP_BOTTOM),
            rows=(replace(
                oriented_rows[0],
                anchor=Point(wide.min_x, wide.min_y - 4000),
            ), *oriented_rows[1:]),
        )
