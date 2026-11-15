"""MAIN 3: 23 real photo components, 15 Nets, actual TI 16 physical pins.

No synthetically invented TL494 photo circuit. Independently assert source
topology frozen at e695..., not a claim to approve source-photo interpretation.
"""
import json
from dataclasses import replace

import pytest

from examples.review_ic_cycle7 import synthetic_ic
from examples.tl494_cycle9_circuit_integration import (
    FROZEN_SOURCE_BLOB,
    FROZEN_SOURCE_COMMIT,
    assert_frozen_photo_topology,
    bind_positioned_photo_circuit_from_catalog,
    build_frozen_photo_23,
)
from gost_schematic.core.geometry import Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.ic import (
    IcKind,
    IcPinType,
    IcTextAngle,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_circuit_adapter import (
    IcCircuitBinding,
    bind_ic_circuit,
    bind_ic_circuit_from_catalog,
)
from gost_schematic.electrical.ic_graphic_revision import (
    revise_ic_text_orientation,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord
from gost_schematic.electrical.tl494cn import (
    TI_DEVICE_ID,
    tl494cn_device,
)
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, PhysicalPin
from gost_schematic.validation.symbol_checks import validate_symbol


def _photo():
    binding, source = build_frozen_photo_23()
    return binding, source


def _bind_revised(binding, circuit=None, record=None, inventory=None):
    return bind_ic_circuit(
        binding.record if record is None else record,
        binding.circuit if circuit is None else circuit,
        aliases=binding.aliases,
        external_pin_numbers=(
            dict(binding.external_pin_numbers)
            if inventory is None else inventory
        ),
    )


def _change_net(binding, name, members):
    nets = tuple(
        replace(net, members=members)
        if net.name == name else net
        for net in binding.circuit.nets
    )
    return replace(binding.circuit, nets=nets)


def test_frozen_photo_fixture_checksum_rejects_silent_same_count_net_swap(tmp_path):
    """A source file cannot be rewritten to change topology yet keep counts."""
    from examples.tl494_cycle9_circuit_integration import (
        FROZEN_FIXTURE,
        load_frozen_source,
    )

    original = FROZEN_FIXTURE.read_text(encoding="utf-8")
    # Still 23 components / 15 Nets / 62 members, but wrong real pin.
    mutated = original.replace('"DA1.3"', '"DA1.6"', 1)
    assert mutated != original
    untrusted = tmp_path / "forged.json"
    untrusted.write_text(mutated, encoding="utf-8")
    with pytest.raises(ValueError, match="FIXTURE_BYTES_CHANGED"):
        load_frozen_source(untrusted)
    assert load_frozen_source() == load_frozen_source(FROZEN_FIXTURE)


def test_actual_frozen_photo_source_23_15_62_all_16_vendor_contacts():
    binding, source = _photo()
    assert source["source_commit"] == FROZEN_SOURCE_COMMIT
    assert source["source_blob_sha"] == FROZEN_SOURCE_BLOB
    assert len(binding.circuit.components) == 23
    assert len(binding.circuit.nets) == 15
    assert sum(len(n.members) for n in binding.circuit.nets) == 62
    assert len(binding.contacts) == 16
    assert {p.pin_ref for p in binding.contacts} == {
        PinRef("DA1", str(i)) for i in range(1, 17)
    }
    assert binding.contact(PinRef("DA1", "3")).manufacturer_pin_name == "FEEDBACK"
    assert binding.contact(PinRef("DA1", "3")).electrical_type is IcPinType.INPUT
    assert binding.contact(PinRef("DA1", "3")).schematic_short_label == "FB"
    assert binding.contact(PinRef("DA1", "13")).electrical_type is IcPinType.INPUT
    assert binding.contact(PinRef("DA1", "13")).schematic_short_label == "OC"
    assert binding.part.identifier == TI_DEVICE_ID
    assert binding.part.pins[2].electrical_type is ElectricalType.INPUT
    assert binding.part.pins[12].electrical_type is ElectricalType.INPUT
    assert binding.part.pins[2].name == "FEEDBACK"
    assert binding.symbol_surrogate is not None
    assert binding.symbol_surrogate.status.value == "draft"
    assert binding.circuit.components[-1].part_id == TI_DEVICE_ID
    assert_frozen_photo_topology(binding, source)


def test_external_nominals_are_exact_decimal_and_not_alias_data():
    binding, source = _photo()
    expected = {
        item["ref"]: item["nominal_si"] for item in source["components"]
    }
    assert {
        comp.reference: (
            str(comp.nominal.si_value) if comp.nominal else None
        ) for comp in binding.circuit.components
    } == expected
    assert all(contact.net_id for contact in binding.contacts)
    assert binding.contact(PinRef("DA1", "3")).net_id == "FEEDBACK"
    assert binding.contact(PinRef("DA1", "13")).net_id == "COMMON"


def test_single_native_symbol_has_same_16_world_terminals_and_no_ink_claim():
    binding, _ = _photo()
    native = binding.symbol_surrogate
    assert native is not None
    instance = next(
        comp for comp in binding.circuit.components if comp.reference == "DA1"
    )
    assert instance.pin_positions(native) == {
        contact.pin_ref.number: contact.world_anchor
        for contact in binding.contacts
    }
    assert {
        pin.number: pin.label for pin in native.pins
    } == {
        c.pin_ref.number: c.schematic_short_label
        for c in binding.contacts
    }
    assert {
        pin.number: pin.name for pin in binding.part.pins
    } == {
        pin.number: pin.name for pin in tl494cn_device().pins
    }
    assert not [
        problem for problem in validate_symbol(native)
        if problem.severity.value == "error"
    ]


def _synthetic_catalog_only_for_electrical_inventory(binding):
    """TEST ONLY: #115 must supply real PartDefinitions from source catalog."""
    inventory = dict(binding.external_pin_numbers)
    parts = {}
    for comp in binding.circuit.components:
        if comp.reference == "DA1":
            continue
        nums = inventory[comp.reference]
        if comp.part_id in parts:
            assert {p.number for p in parts[comp.part_id].pins} == set(nums)
            continue
        parts[comp.part_id] = PartDefinition(
            identifier=comp.part_id,
            reference_prefix="T",
            symbol_id="synthetic.geometry.not.printable",
            pins=tuple(
                PhysicalPin(number, f"TEST PIN {number}", ElectricalType.PASSIVE)
                for number in nums
            ),
        )
    return parts


def test_reconstructor_a3_23_part_catalog_adapter_preserves_complete_nets():
    binding, source = _photo()
    parts = _synthetic_catalog_only_for_electrical_inventory(binding)
    candidate = bind_ic_circuit_from_catalog(
        binding.record, binding.circuit, parts,
        aliases=binding.aliases,
    )
    assert candidate == binding
    assert candidate.circuit is binding.circuit
    assert candidate.contacts == binding.contacts
    assert_frozen_photo_topology(candidate, source)
    assert IcCircuitBinding.from_json(candidate.to_json()) == candidate



def test_manufacturer_record_is_authority_without_redundant_vendor_catalog():
    """QA C11 missing vendor row is safe: trusted TI record is the authority."""
    binding, _ = _photo()
    external_catalog = _synthetic_catalog_only_for_electrical_inventory(binding)
    assert TI_DEVICE_ID not in external_catalog
    signed = bind_ic_circuit_from_catalog(
        binding.record, binding.circuit, external_catalog,
        aliases=binding.aliases,
    )
    assert signed == binding
    assert signed.circuit is binding.circuit
    assert {c.pin_ref for c in signed.contacts} == {
        PinRef("DA1", str(index)) for index in range(1, 17)
    }
    assert signed.contact(PinRef("DA1", "3")).electrical_type is IcPinType.INPUT
    assert signed.contact(PinRef("DA1", "13")).electrical_type is IcPinType.INPUT
    assert (
        signed.contact(PinRef("DA1", "14")).electrical_type
        is IcPinType.POWER_OUTPUT
    )
    supplied = {**external_catalog, TI_DEVICE_ID: binding.part}
    explicit = bind_ic_circuit_from_catalog(
        binding.record, binding.circuit, supplied,
        aliases=binding.aliases,
    )
    assert explicit == signed


@pytest.mark.parametrize(
    "attack", (
        "missing_value", "foreign_type", "foreign_id", "wrong_prefix",
        "missing_factory_pin", "wrong_factory_number", "wrong_factory_name",
        "wrong_factory_electrical_type", "reordered_factory_pins",
    ),
)
def test_supplied_manufacturer_partdefinition_must_match_true_ti(attack):
    """No supplied spoofed vendor PartDefinition may certify a signed DA1."""
    binding, _ = _photo()
    catalog = _synthetic_catalog_only_for_electrical_inventory(binding)
    signed_factory = binding.part
    if attack == "missing_value":
        forged = None
    elif attack == "foreign_type":
        forged = "ti.tl494cn.pdip16"
    elif attack == "foreign_id":
        forged = replace(signed_factory, identifier="fraud.tl494.pdip16")
    elif attack == "wrong_prefix":
        forged = replace(signed_factory, reference_prefix="ZZ")
    else:
        pins = list(signed_factory.pins)
        if attack == "missing_factory_pin":
            pins.pop()
        elif attack == "wrong_factory_number":
            pins[0] = replace(pins[0], number="99")
        elif attack == "wrong_factory_name":
            pins[2] = replace(pins[2], name="NOT_FEEDBACK")
        elif attack == "wrong_factory_electrical_type":
            pins[12] = replace(
                pins[12], electrical_type=ElectricalType.OUTPUT,
            )
        else:
            pins[0], pins[1] = pins[1], pins[0]
        forged = replace(signed_factory, pins=tuple(pins))
    catalog[TI_DEVICE_ID] = forged
    with pytest.raises(
        ValueError,
        match="IC_ADAPTER_CATALOG_MANUFACTURER_PINOUT_CONFLICT",
    ):
        bind_ic_circuit_from_catalog(
            binding.record, binding.circuit, catalog,
            aliases=binding.aliases,
        )

def test_reconstructor_catalog_foreign_missing_unknown_pin_rejected():
    binding, _ = _photo()
    parts = _synthetic_catalog_only_for_electrical_inventory(binding)
    absent = dict(parts)
    del absent["resistor.variable"]
    with pytest.raises(ValueError, match="IC_ADAPTER_CATALOG_PART_NOT_FOUND"):
        bind_ic_circuit_from_catalog(
            binding.record, binding.circuit, absent,
            aliases=binding.aliases,
        )
    fake = dict(parts)
    fake["resistor.fixed"] = replace(
        fake["resistor.fixed"], identifier="foreign.resistor.kind",
    )
    with pytest.raises(ValueError, match="IC_ADAPTER_CATALOG_FOREIGN_PART_ID"):
        bind_ic_circuit_from_catalog(
            binding.record, binding.circuit, fake,
            aliases=binding.aliases,
        )
    truncated = dict(parts)
    truncated["resistor.fixed"] = replace(
        truncated["resistor.fixed"],
        pins=truncated["resistor.fixed"].pins[:1],
    )
    with pytest.raises(
        ValueError, match="IC_ADAPTER_FOREIGN_OR_UNKNOWN_EXTERNAL_PIN",
    ):
        bind_ic_circuit_from_catalog(
            binding.record, binding.circuit, truncated,
            aliases=binding.aliases,
        )
    with pytest.raises(TypeError, match="IC_ADAPTER_CATALOG_MAPPING_REQUIRED"):
        bind_ic_circuit_from_catalog(
            binding.record, binding.circuit, None,
            aliases=binding.aliases,
        )


def _source_legacy_part_id(binding):
    return replace(binding.circuit, components=tuple(
        replace(c, part_id="reference.tl494cn")
        if c.reference == "DA1" else c
        for c in binding.circuit.components
    ))


def test_reconstructor_photo_legacy_tl494_model_is_upgraded_without_net_changes():
    signed, original = _photo()
    source = _source_legacy_part_id(signed)
    before_nets = source.nets
    before_components = source.components
    catalog = _synthetic_catalog_only_for_electrical_inventory(signed)
    upgraded = bind_positioned_photo_circuit_from_catalog(
        source, signed.record, catalog, aliases=signed.aliases,
    )
    assert source.nets is before_nets
    assert source.components is before_components
    assert next(
        c for c in source.components if c.reference == "DA1"
    ).part_id == "reference.tl494cn"
    assert next(
        c for c in upgraded.circuit.components if c.reference == "DA1"
    ).part_id == TI_DEVICE_ID
    assert upgraded.circuit.nets is source.nets
    assert upgraded.contacts == signed.contacts
    assert upgraded == signed
    assert_frozen_photo_topology(upgraded, original)
    assert IcCircuitBinding.from_json(upgraded.to_json()) == upgraded


@pytest.mark.parametrize("kind", (
    "wrong_photo_net", "wrong_da1_part", "foreign_part",
    "moved_da1", "wrong_unit_pose", "missing_part", "changed_nominal",
))
def test_reconstructor_photo_catalog_rebind_refuses_forged_source(kind):
    signed, _ = _photo()
    legacy = _source_legacy_part_id(signed)
    parts = _synthetic_catalog_only_for_electrical_inventory(signed)
    record = signed.record
    if kind == "wrong_photo_net":
        change = next(n for n in legacy.nets if n.name == "FEEDBACK")
        legacy = replace(legacy, nets=tuple(
            replace(n, members=tuple(
                PinRef("DA1", "4") if p == PinRef("DA1", "3")
                else PinRef("DA1", "3") if p == PinRef("DA1", "4")
                else p for p in n.members
            )) if n == change else n
            for n in legacy.nets
        ))
    elif kind in ("wrong_da1_part", "foreign_part", "moved_da1", "changed_nominal"):
        component_ref = "DA1" if kind in ("wrong_da1_part", "moved_da1") else "R1"
        legacy = replace(legacy, components=tuple(
            replace(
                c, **(
                    {"part_id": "UNKNOWN_FACTORY"}
                    if kind in ("wrong_da1_part", "foreign_part")
                    else {"origin": Point(c.origin.x + 1, c.origin.y)}
                    if kind == "moved_da1"
                    else {"nominal": None}
                ),
            ) if c.reference == component_ref else c
            for c in legacy.components
        ))
        if kind == "changed_nominal":
            legacy = replace(legacy, components=tuple(
                replace(c, nominal=None) if c.reference == "R1" else c
                for c in legacy.components
            ))
    elif kind == "wrong_unit_pose":
        record = IcLibraryRecord(
            record.device, record.specs,
            tuple(replace(p, origin=Point(p.origin.x + 1, p.origin.y))
                  for p in record.placements),
        )
    else:
        del parts["resistor.variable"]
    expected = {
        "wrong_photo_net": "NET_IDENTITY_OR_MEMBERSHIP_CHANGED",
        "wrong_da1_part": "DA1_PART_OR_POSE_MISMATCH",
        "foreign_part": "NON_IC_PART_CHANGED",
        "moved_da1": "DA1_PART_OR_POSE_MISMATCH",
        "wrong_unit_pose": "DA1_PART_OR_POSE_MISMATCH",
        "missing_part": "IC_ADAPTER_CATALOG_PART_NOT_FOUND",
        "changed_nominal": "BOM_NOMINAL_DRIFT",
    }[kind]
    with pytest.raises(ValueError, match=expected):
        bind_positioned_photo_circuit_from_catalog(
            legacy, record, parts, aliases=signed.aliases,
        )


def test_strict_adapter_serialization_is_exact_idempotent_with_all_23_parts():
    binding, source = _photo()
    payload = binding.to_json()
    loaded = IcCircuitBinding.from_json(payload)
    assert loaded == binding
    assert loaded.to_json() == payload
    assert loaded.circuit.nets == binding.circuit.nets
    assert loaded.circuit.components == binding.circuit.components
    assert loaded.contacts == binding.contacts
    assert_frozen_photo_topology(loaded, source)
    loaded.validate()


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_d4_real_23_part_circuit_native_endpoint_and_net_invariance(rotation, mirror):
    binding, source = _photo()
    pose = Transform(rotation, mirror)
    views = tuple(replace(p, transform=pose) for p in binding.record.placements)
    record = IcLibraryRecord(binding.record.device, binding.record.specs, views)
    circuit = replace(
        binding.circuit,
        components=tuple(replace(
            c, transform=pose,
        ) if c.reference == "DA1" else c for c in binding.circuit.components),
    )
    rotated = _bind_revised(binding, circuit=circuit, record=record)
    assert rotated.circuit.nets == binding.circuit.nets
    assert rotated.symbol_surrogate is not None
    da = next(c for c in circuit.components if c.reference == "DA1")
    assert da.pin_positions(rotated.symbol_surrogate) == {
        p.pin_ref.number: p.world_anchor for p in rotated.contacts
    }
    source_points = resolve_ic_pin_positions(
        binding.record.device, binding.record.specs, binding.record.placements,
    )
    for contact in rotated.contacts:
        initial = source_points[contact.pin_ref]
        delta = initial - binding.record.placements[0].origin
        assert contact.world_anchor == (
            pose.apply(delta) + binding.record.placements[0].origin
        )
    assert_frozen_photo_topology(rotated, source)
    assert IcCircuitBinding.from_json(rotated.to_json()) == rotated


@pytest.mark.parametrize("angle", (
    IcTextAngle.HORIZONTAL, IcTextAngle.VERTICAL, IcTextAngle.BOTTOM_TO_TOP,
))
def test_0_90_270_text_revision_real_photo_nets_and_pins_unchanged(angle):
    binding, source = _photo()
    target = revise_ic_text_orientation(binding.record, angle)
    updated, change = binding.revise(target)
    assert change.moved == ()
    assert change.connected_moved == ()
    assert updated.circuit is binding.circuit
    assert updated.circuit.nets is binding.circuit.nets
    assert updated.contacts == binding.contacts
    assert updated.part.pins == binding.part.pins
    assert updated.record.specs[0].profile.function_angle is angle
    assert_frozen_photo_topology(updated, source)
    assert IcCircuitBinding.from_json(updated.to_json()) == updated


def test_edit_fb_alias_changes_only_svg_display_not_physical_or_net():
    binding, source = _photo()
    aliases = replace(binding.aliases, labels=tuple(
        replace(a, schematic_short_label="FDBK")
        if a.physical_number == "3" else a
        for a in binding.aliases.labels
    ))
    renamed_record = aliases.apply_to_record(binding.record)
    rewritten = bind_ic_circuit(
        renamed_record, binding.circuit, aliases=aliases,
        external_pin_numbers=dict(binding.external_pin_numbers),
    )
    assert rewritten.contact(PinRef("DA1", "3")).schematic_short_label == "FDBK"
    assert rewritten.contact(PinRef("DA1", "3")).manufacturer_pin_name == "FEEDBACK"
    assert rewritten.contact(PinRef("DA1", "3")).electrical_type is IcPinType.INPUT
    assert rewritten.circuit is binding.circuit
    assert rewritten.circuit.nets == binding.circuit.nets
    assert {
        ref: p for ref, p in resolve_ic_pin_positions(
            rewritten.record.device, rewritten.record.specs,
            rewritten.record.placements,
        ).items()
    } == resolve_ic_pin_positions(
        binding.record.device, binding.record.specs, binding.record.placements,
    )
    assert_frozen_photo_topology(rewritten, source)


def test_adapter_missing_foreign_or_duplicate_catalog_and_ic_pin_fail_closed():
    binding, _ = _photo()
    with pytest.raises(ValueError, match="EXTERNAL_PIN_INVENTORY_INCOMPLETE"):
        _bind_revised(binding, inventory={})
    with pytest.raises(ValueError, match="nonexistent physical IC pin"):
        _bind_revised(binding, circuit=_change_net(
            binding, "FEEDBACK", (PinRef("R3", "2"), PinRef("DA1", "99")),
        ))
    with pytest.raises(ValueError, match="FOREIGN_OR_UNKNOWN_EXTERNAL_PIN"):
        _bind_revised(binding, circuit=_change_net(
            binding, "FEEDBACK", (PinRef("R3", "2"), PinRef("Q99", "1")),
        ))
    with pytest.raises(ValueError, match="FOREIGN_OR_UNKNOWN_EXTERNAL_PIN"):
        _bind_revised(binding, circuit=_change_net(
            binding, "FEEDBACK", (PinRef("R3", "99"), PinRef("DA1", "3")),
        ))
    with pytest.raises(ValueError, match="DUPLICATE_NET_MEMBER"):
        _bind_revised(binding, circuit=_change_net(
            binding, "FEEDBACK", (
                PinRef("R3", "2"), PinRef("DA1", "3"), PinRef("DA1", "3"),
            ),
        ))
    with pytest.raises(ValueError, match="MULTIPLE_NET_OWNERSHIP"):
        _bind_revised(binding, circuit=_change_net(
            binding, "FEEDBACK", (
                PinRef("R3", "2"), PinRef("DA1", "3"), PinRef("DA1", "13"),
            ),
        ))
    with pytest.raises(ValueError, match="DUPLICATE_NET"):
        _bind_revised(binding, circuit=replace(
            binding.circuit, nets=(
                *binding.circuit.nets,
                binding.circuit.nets[0],
            ),
        ))
    with pytest.raises(ValueError, match="DUPLICATE_COMPONENT"):
        _bind_revised(binding, circuit=replace(
            binding.circuit, components=(
                *binding.circuit.components,
                binding.circuit.components[0],
            ),
        ))


def test_frozen_photo_gate_detects_missing_net_or_source_reinterpretation():
    binding, source = _photo()
    deleted = replace(
        binding.circuit,
        nets=binding.circuit.nets[:-1],
    )
    candidate = _bind_revised(binding, circuit=deleted)
    with pytest.raises(ValueError, match="COMPONENT_OR_NET_COUNT_DRIFT"):
        assert_frozen_photo_topology(candidate, source)
    # Swap two real DA1 physical contacts while keeping each contact unique:
    # standalone Circuit accepts it, but the frozen original MUST NOT.
    members = {}
    for n in binding.circuit.nets:
        members[n.name] = tuple(
            PinRef("DA1", "5") if p == PinRef("DA1", "3") else
            PinRef("DA1", "3") if p == PinRef("DA1", "5") else p
            for p in n.members
        )
    hostile = replace(binding.circuit, nets=tuple(
        replace(n, members=members[n.name]) for n in binding.circuit.nets
    ))
    rewritten = _bind_revised(binding, circuit=hostile)
    with pytest.raises(ValueError, match="NET_MEMBERSHIP_DRIFT"):
        assert_frozen_photo_topology(rewritten, source)


def test_unmatched_alias_and_wrong_semantics_fail_at_circuit_adapter_boundary():
    binding, _ = _photo()
    wrong = replace(binding.aliases, labels=tuple(
        replace(a, schematic_short_label="BADFB")
        if a.physical_number == "3" else a for a in binding.aliases.labels
    ))
    with pytest.raises(ValueError, match="IC_ALIAS_GRAPHIC_TEXT_MISMATCH"):
        bind_ic_circuit(
            binding.record, binding.circuit, aliases=wrong,
            external_pin_numbers=dict(binding.external_pin_numbers),
        )
    changed_device = replace(binding.record.device, pins=tuple(
        replace(p, electrical_type=IcPinType.OUTPUT)
        if p.number == "3" else p
        for p in binding.record.device.pins
    ))
    changed_record = IcLibraryRecord(
        changed_device, binding.record.specs, binding.record.placements,
    )
    with pytest.raises(ValueError, match="TL494_TI_PIN_FUNCTION_OR_ELECTRICAL_TYPE"):
        bind_ic_circuit(
            changed_record, binding.circuit, aliases=binding.aliases,
            external_pin_numbers=dict(binding.external_pin_numbers),
        )


def test_ti_source_lock_refuses_two_matching_forged_types_and_aliases():
    """A forged pinout + consistently forged short-label metadata still fails."""
    binding, _ = _photo()
    device = replace(binding.record.device, pins=tuple(
        replace(p, electrical_type=IcPinType.OUTPUT)
        if p.number == "3" else p for p in binding.record.device.pins
    ))
    record = IcLibraryRecord(
        device, binding.record.specs, binding.record.placements,
    )
    aliases = replace(binding.aliases, labels=tuple(
        replace(a, electrical_type=IcPinType.OUTPUT)
        if a.physical_number == "3" else a
        for a in binding.aliases.labels
    ))
    aliases.validate_device(device)  # Two forged objects agree; TI table does not.
    with pytest.raises(ValueError, match="TL494_TI_PIN_FUNCTION_OR_ELECTRICAL_TYPE"):
        bind_ic_circuit(
            record, binding.circuit, aliases=aliases,
            external_pin_numbers=dict(binding.external_pin_numbers),
        )


def test_missing_unknown_multisection_pin_unit_and_duplicate_pin_owned_fail():
    source = synthetic_ic(14, IcKind.DIGITAL)
    # Common legacy ElectricalType has no NC; change only synthetic last pin
    # to PASSIVE, never claim this is an actual manufacturer package.
    device = replace(source.device, pins=tuple(
        replace(p, electrical_type=IcPinType.PASSIVE)
        if p.electrical_type is IcPinType.NC else p
        for p in source.device.pins
    ))
    record = IcLibraryRecord(device, source.specs, source.placements)
    circuit = Circuit((ComponentInstance("DD1", device.identifier),), (
        Net("CTRL_A", (PinRef("DD1", "1"), PinRef("DD1", "8"))),
        Net("CTRL_B", (PinRef("DD1", "6"),)),
    ))
    bridge = bind_ic_circuit(record, circuit)
    assert bridge.symbol_surrogate is None
    assert len(bridge.contacts) == 14
    assert {p.unit_id for p in bridge.contacts} == {"U1", "U2"}
    assert {p.net_id for p in bridge.contacts} >= {None, "CTRL_A", "CTRL_B"}
    assert IcCircuitBinding.from_json(bridge.to_json()) == bridge
    with pytest.raises(ValueError, match="unit ownership"):
        replace(device, units=(
            device.units[0],
            replace(device.units[1], pin_numbers=(
                *device.units[1].pin_numbers, "1",
            )),
        ))
    with pytest.raises(ValueError, match="PIN_NOT_PRESENTED"):
        IcLibraryRecord(device, source.specs[:1], source.placements)
    with pytest.raises(ValueError, match="Net references nonexistent physical"):
        bind_ic_circuit(record, replace(
            circuit, nets=(
                Net("WRONG", (PinRef("DD1", "99"),)),
            ),
        ))


def test_nc_fail_closed_not_silently_remapped_to_passive():
    original = synthetic_ic(14)
    circuit = Circuit((
        ComponentInstance("DD1", original.device.identifier),
    ), (Net("LIVE", (PinRef("DD1", "14"),)),))
    with pytest.raises(ValueError, match="IC_NC_CONNECTED"):
        bind_ic_circuit(original, circuit)
    disconnected = replace(
        circuit, nets=(
            Net("SAFE", (PinRef("DD1", "1"),)),
        ),
    )
    with pytest.raises(ValueError, match="IC_ADAPTER_UNSUPPORTED_LEGACY_NC_PIN"):
        bind_ic_circuit(original, disconnected)


@pytest.mark.parametrize("corruption", (
    '{"schema_version":1,"schema_version":1}',
    '{"schema_version":1,"record_type":"DRAFT_IC_CIRCUIT_PINREF_BINDING","ic_record":{},"aliases":null,"external_pin_numbers":{},"components":[],"nets":[],"extra":1}',
))
def test_malformed_json_duplicate_keys_and_foreign_fields_fail(corruption):
    with pytest.raises(ValueError):
        IcCircuitBinding.from_json(corruption)


def test_roundtrip_rejects_forged_alias_foreign_member_and_bool_transform():
    binding, _ = _photo()
    good = json.loads(binding.to_json())
    fake = json.loads(binding.to_json())
    fake["aliases"]["labels"][2]["real_pin_ref"] = ["DA99", "3"]
    with pytest.raises(ValueError, match="IC_ALIAS_FOREIGN_PINREF"):
        IcCircuitBinding.from_json(json.dumps(fake))
    fake = json.loads(binding.to_json())
    fake["nets"][0]["members"][0] = ["DA1", "999"]
    with pytest.raises(ValueError):
        IcCircuitBinding.from_json(json.dumps(fake))
    fake = json.loads(binding.to_json())
    fake["components"][0]["rotation"] = True
    with pytest.raises(ValueError, match="TRANSFORM_TYPED_REQUIRED"):
        IcCircuitBinding.from_json(json.dumps(fake))
    fake = json.loads(binding.to_json())
    fake["external_pin_numbers"].pop("R3")
    with pytest.raises(ValueError, match="EXTERNAL_PIN_INVENTORY_INCOMPLETE"):
        IcCircuitBinding.from_json(json.dumps(fake))
    assert IcCircuitBinding.from_json(json.dumps(good)) == binding


def test_point_and_side_types_are_preserved_without_route_auto_reflow():
    binding, _ = _photo()
    for contact in binding.contacts:
        assert isinstance(contact.world_anchor, Point)
        assert isinstance(contact.world_side, Side)
        assert contact.pin_ref.number in {str(n) for n in range(1, 17)}
        assert contact.manufacturer_pin_name
        assert len(contact.schematic_short_label) <= 6


def test_malicious_contact_dataclass_payload_detected_by_revalidation():
    binding, _ = _photo()
    hostile = replace(binding, contacts=(
        replace(binding.contacts[2], world_anchor=Point(0, 0)),
        *binding.contacts[1:],
    ))
    with pytest.raises(ValueError, match="IC_ADAPTER_INTEGRITY_MISMATCH"):
        hostile.validate()


def test_real_recon115_three_net_labels_are_reversible_only_as_complete_source():
    """Only exact three pinned #115 aliases + same 62 source members are legal."""
    signed, source = _photo()
    legacy = _source_legacy_part_id(signed)
    names = {
        "a_INPUT_PLUS": "INPUT_POS",
        "b_NEGATIVE_OUTPUT": "OUTPUT_NEG",
        "TRANSFER": "ENERGY_TRANSFER",
    }
    reconstructed = replace(legacy, nets=tuple(
        replace(net, name=names.get(net.name, net.name))
        for net in legacy.nets
    ))
    catalog = _synthetic_catalog_only_for_electrical_inventory(signed)
    accepted = bind_positioned_photo_circuit_from_catalog(
        reconstructed, signed.record, catalog, aliases=signed.aliases,
    )
    assert accepted.circuit.nets is reconstructed.nets
    assert accepted.circuit.nets != legacy.nets
    assert len(accepted.circuit.nets) == 15
    assert sum(len(net.members) for net in accepted.circuit.nets) == 62
    assert accepted.circuit.components[-1].part_id == TI_DEVICE_ID
    assert_frozen_photo_topology(accepted, source)
    reverse = {value: key for key, value in names.items()}
    restored = replace(accepted.circuit, nets=tuple(
        replace(net, name=reverse.get(net.name, net.name))
        for net in accepted.circuit.nets
    ))
    assert restored.nets == legacy.nets
    assert restored.components != legacy.components  # only DA1 ID upgraded
    assert IcCircuitBinding.from_json(accepted.to_json()) == accepted

    half = replace(reconstructed, nets=tuple(
        replace(net, name="a_INPUT_PLUS") if net.name == "INPUT_POS"
        else net for net in reconstructed.nets
    ))
    with pytest.raises(ValueError, match="NET_IDENTITY_OR_MEMBERSHIP_CHANGED"):
        bind_positioned_photo_circuit_from_catalog(
            half, signed.record, catalog, aliases=signed.aliases,
        )
    tampered = replace(reconstructed, nets=tuple(
        replace(net, members=tuple(
            PinRef("DA1", "4") if pin == PinRef("DA1", "3") else pin
            for pin in net.members
        )) if net.name == "FEEDBACK" else net
        for net in reconstructed.nets
    ))
    with pytest.raises(ValueError, match="NET_IDENTITY_OR_MEMBERSHIP_CHANGED"):
        bind_positioned_photo_circuit_from_catalog(
            tampered, signed.record, catalog, aliases=signed.aliases,
        )
