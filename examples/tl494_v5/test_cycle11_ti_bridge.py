"""Cycle11: real 23/15/62 reference->TI manufacturer reversible binding."""
from dataclasses import replace
from pathlib import Path

import pytest

from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.cycle11_ti_bridge import (
    PHYSICAL_REF,
    SOURCE_PART_ID,
    VerifiedCompactTiBinding,
    bind_verified_compact_ti,
)
from examples.tl494_v5.route_candidate_driver import (
    load_original_owner_fixture,
    restore_original_named_nets,
)
from gost_schematic.core.geometry import Point
from gost_schematic.electrical.tl494cn import TI_DEVICE_ID
from gost_schematic.model.circuit import Circuit, Net, PinRef


def _real():
    assembly = compact_source_assembly()
    fixture, _ = load_original_owner_fixture()
    raw = restore_original_named_nets(assembly, fixture)
    return assembly, raw


def test_real_source_reversible_ti_part_id_no_net_or_nominal_drift():
    assembly, source = _real()
    signed = bind_verified_compact_ti(assembly, source)
    signed.verify()
    assert signed.source_circuit is source
    assert signed.reverse_source() is source
    assert signed.source_part_id == SOURCE_PART_ID
    assert signed.signed_part_id == TI_DEVICE_ID
    assert signed.part.identifier == TI_DEVICE_ID
    assert signed.signed.circuit.nets is source.nets
    assert signed.signed.circuit.nets == source.nets
    assert len(signed.signed.circuit.components) == 23
    assert len(signed.signed.circuit.nets) == 15
    assert sum(len(n.members) for n in source.nets) == 62
    assert len(signed.signed.contacts) == 16
    before = {p.reference: p for p in source.components}
    after = {p.reference: p for p in signed.signed.circuit.components}
    assert before["DA1"].part_id == SOURCE_PART_ID
    assert after["DA1"].part_id == TI_DEVICE_ID
    assert before["DA1"].origin == after["DA1"].origin == Point(135000, 90000)
    assert all(before[p] == after[p] for p in before if p != "DA1")
    for physical_pin in ("3", "13"):
        contact = signed.signed.contact(PinRef("DA1", physical_pin))
        assert contact.electrical_type.value == "input"
    assert {n.name for n in source.nets} == {
        "a_INPUT_PLUS", "SWITCH", "TRANSFER", "OUT_BEFORE_FUSE",
        "b_NEGATIVE_OUTPUT", "GATE_DRIVE", "CONTROL_REFERENCE",
        "SOFT_START", "ERROR_INPUT", "RC_CORRECTION", "FEEDBACK",
        "ADJUSTED_DIVIDER", "OSCILLATOR_CT", "OSCILLATOR_RT", "COMMON",
    }


def test_negative_changed_physical_pinref_with_same_total_62_is_rejected():
    assembly, source = _real()
    altered = tuple(
        Net(n.name, (
            PinRef("DA1", "3"), *n.members[1:]
        )) if n.name == "a_INPUT_PLUS" else n
        for n in source.nets
    )
    with pytest.raises(ValueError, match="TL494_PHOTO_REBIND_NET_IDENTITY"):
        bind_verified_compact_ti(assembly, Circuit(source.components, altered))


def test_negative_foreign_da1_placement_rejected():
    assembly, source = _real()
    old = assembly.owner_ic_record
    wrong = replace(
        old, placements=tuple(
            replace(p, origin=Point(137500, p.origin.y))
            for p in old.placements
        ),
    )
    other = replace(assembly, owner_ic_record=wrong)
    with pytest.raises(ValueError, match="TL494_PHOTO_REBIND_DA1_PART_OR_POSE"):
        bind_verified_compact_ti(other, source)


def test_negative_no_authority_from_similar_string_or_modified_part():
    assembly, source = _real()
    correct = bind_verified_compact_ti(assembly, source)
    forged = replace(correct, signed_part_id="ti.fake.pdip16")
    with pytest.raises(ValueError, match="SIGNED_MANUFACTURER_PART"):
        forged.verify()
    forged = replace(correct, source_part_id="reference.tl494cn_v2")
    with pytest.raises(ValueError, match="SIGNED_MANUFACTURER_PART"):
        forged.verify()
    altered = tuple(
        replace(p, part_id="reference.tl494cn_wrong")
        if p.reference == PHYSICAL_REF else p
        for p in source.components
    )
    with pytest.raises((AssertionError, ValueError)):
        bind_verified_compact_ti(
            replace(assembly, circuit=Circuit(altered, assembly.circuit.nets)),
            Circuit(altered, source.nets),
        )


def test_negative_swapped_signed_ic_circuit_is_not_reversible():
    assembly, source = _real()
    verified = bind_verified_compact_ti(assembly, source)
    fake_source = Circuit(
        source.components,
        tuple(
            Net(
                n.name,
                tuple(
                    PinRef("DA1", "12") if pin == PinRef("DA1", "11") else pin
                    for pin in n.members
                ),
            ) if n.name == "a_INPUT_PLUS" else n
            for n in source.nets
        ),
    )
    with pytest.raises(ValueError, match="SOURCE_NET_TUPLE_CHANGED"):
        replace(verified, source_circuit=fake_source).verify()


def test_real_16_pin_signed_paint_overlay_and_wrong_record_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
    from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
    from gost_schematic.standards.type_a_font import inspect_type_a_font

    import os

    font = os.getenv("TL494_TYPE_A_FONT")
    if not font:
        pytest.skip("Requires owner-pinned OpenGOST Type A CI")
    assembly, source = _real()
    verified = bind_verified_compact_ti(assembly, source)
    style = inspect_type_a_font(
        Path(font), h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    ).style
    paint = propose_ic_paint_binding(
        assembly.owner_ic_record, style, PillowTextMeasurer(),
    )
    witness = verified.seal_paint(paint)
    witness.verify_against(verified.signed, paint)
    assert len(witness.per_unit_targets) == 1
    assert len(witness.per_unit_targets[0]) == 16
    targets = {t.pin_ref: t for t in witness.per_unit_targets[0]}
    assert len(targets) == 16
    for number in range(1, 17):
        item = verified.signed.contact(PinRef("DA1", str(number)))
        assert targets[item.pin_ref].anchor == item.world_anchor
        assert targets[item.pin_ref].net_id == item.net_id
    # Never accept a changed full source Circuit as authority for a cached seal.
    bad = replace(
        verified, source_circuit=Circuit(source.components, source.nets[:-1])
    )
    with pytest.raises(ValueError, match="SOURCE_NET_TUPLE_CHANGED"):
        bad.seal_paint(paint)
