"""Cycle11 actual historical b-X2/b-R5 -> compact 23-part typed continuation.

These tests read the real native SOURCE continuation project, not invented
photo pixels, and reject wrong Net, wrong physical PinRef and out-of-page.
"""
from dataclasses import replace
from pathlib import Path

import pytest

from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.cycle11_b_continuation import (
    B_PHYSICAL,
    SOURCE_B_NAME,
    SOURCE_B_STUBS,
    rebind_true_source_b,
)
from examples.tl494_v5.cycle11_ti_bridge import bind_verified_compact_ti
from examples.tl494_v5.route_candidate_driver import (
    load_original_owner_fixture,
    restore_original_named_nets,
)
from gost_schematic.core.geometry import Point
from gost_schematic.electrical.netrefs import (
    NetIdentity,
    validate_net_continuations,
)
from gost_schematic.model.circuit import Circuit, Net, PinRef


@pytest.fixture(scope="module")
def actual_source_and_a3():
    import os

    from examples.tl494_named_photo_sheet import compose_circuit

    font_path = os.getenv("TL494_TYPE_A_FONT")
    if not font_path:
        pytest.skip("Real owner-pinned OpenGOST Type A font required")
    old_photo = compose_circuit(Path(font_path))
    old_project = old_photo[-1]
    a3 = compact_source_assembly()
    frozen, _ = load_original_owner_fixture()
    source = restore_original_named_nets(a3, frozen)
    signed = bind_verified_compact_ti(a3, source)
    return old_project, a3, signed.signed.circuit


def test_real_two_source_b_continuations_rebound_to_typed_new_a3(
    actual_source_and_a3,
):
    old, assembly, signed = actual_source_and_a3
    current = rebind_true_source_b(old, signed, assembly.symbols)
    assert current.circuit.nets is signed.nets
    assert len(current.nets) == 1
    assert current.nets[0].net_name == SOURCE_B_NAME
    assert set(current.nets[0].members) == B_PHYSICAL
    assert {p.id for p in current.endpoints} == set(SOURCE_B_STUBS)
    assert len(current.stubs) == 2
    actual = {s.pin: s.start for s in current.stubs}
    assert validate_net_continuations(
        current, physical_pin_anchors=actual,
    ) == ()
    for original, updated in zip(old.stubs, current.stubs, strict=True):
        assert original.pin == updated.pin
        assert original.end.x - original.start.x == (
            updated.end.x - updated.start.x
        )
        assert original.end.y - original.start.y == (
            updated.end.y - updated.start.y
        )


def test_negative_foreign_b_net_and_member_rejected(actual_source_and_a3):
    old, a3, signed = actual_source_and_a3
    bad_original = replace(old, nets=(NetIdentity(
        old.nets[0].id, old.nets[0].net_name,
        (PinRef("FU1", "2"), PinRef("X2", "1"), PinRef("DA1", "12")),
    ),))
    with pytest.raises(ValueError, match="ORIGINAL_PHYSICAL_NET_UNVERIFIED"):
        rebind_true_source_b(bad_original, signed, a3.symbols)
    changed_nets = tuple(
        Net("OUTPUT_NEG", net.members) if net.name == SOURCE_B_NAME else net
        for net in signed.nets
    )
    with pytest.raises(ValueError, match="SOURCE_23_15_62_IDENTITY_DRIFT"):
        rebind_true_source_b(
            old, Circuit(signed.components, changed_nets), a3.symbols,
        )


def test_negative_wrong_b_marker_provenance_or_double_marker(
    actual_source_and_a3,
):
    old, a3, signed = actual_source_and_a3
    bad = replace(old, address_bindings=old.address_bindings[:-1])
    with pytest.raises(ValueError, match="PROVENANCE_MISSING"):
        rebind_true_source_b(bad, signed, a3.symbols)
    duplicated = replace(old, endpoints=(old.endpoints[0], old.endpoints[0]))
    with pytest.raises(ValueError, match="NOT_TWO_REAL_SOURCE_MARKERS"):
        rebind_true_source_b(duplicated, signed, a3.symbols)
    shifted = replace(
        old, endpoints=tuple(
            replace(ep, anchor=Point(ep.anchor.x + 1000, ep.anchor.y))
            if ep.id == "b-R5" else ep
            for ep in old.endpoints
        ),
    )
    with pytest.raises(ValueError, match="OLD_STUB_NOT_FROM_ACTUAL_PIN"):
        rebind_true_source_b(shifted, signed, a3.symbols)


def test_negative_outside_A3_does_not_reposition_marker_by_guess(
    actual_source_and_a3,
):
    old, a3, signed = actual_source_and_a3
    moved = tuple(
        replace(comp, origin=Point(470000, comp.origin.y))
        if comp.reference == "X2" else comp for comp in signed.components
    )
    # The signed source's electrical identity remains unchanged, but
    # the original b-X2 stub vector would be outside the A3 paper.
    with pytest.raises(ValueError, match="ORIGINAL_VECTOR_OUTSIDE_COMPACT_A3"):
        rebind_true_source_b(
            old, Circuit(moved, signed.nets), a3.symbols,
        )


def test_negative_forged_whole_old_source_ref_or_pin_membership(
    actual_source_and_a3,
):
    old, a3, signed = actual_source_and_a3
    # The two source markers may be intact, but the *rest* of the old
    # source is not then authoritative. Reject a same-count Net mutation.
    modified = tuple(
        Net(net.name, tuple(
            PinRef("DA1", "3") if p == PinRef("DA1", "4") else p
            for p in net.members
        )) if net.name == "SOFT_START" else net
        for net in old.circuit.nets
    )
    with pytest.raises(ValueError, match="HISTORICAL_23_15_62_SOURCE_NOT_AUTHENTIC"):
        rebind_true_source_b(
            replace(old, circuit=Circuit(old.circuit.components, modified)),
            signed, a3.symbols,
        )
    altered = tuple(
        replace(comp, part_id="forged.resistor")
        if comp.reference == "R6" else comp
        for comp in old.circuit.components
    )
    with pytest.raises(ValueError, match="HISTORICAL_23_15_62_SOURCE_NOT_AUTHENTIC"):
        rebind_true_source_b(
            replace(old, circuit=Circuit(altered, old.circuit.nets)),
            signed, a3.symbols,
        )


def test_negative_b_source_address_reciprocity_cannot_be_rewritten(
    actual_source_and_a3,
):
    old, a3, signed = actual_source_and_a3
    incorrect = replace(old, endpoints=tuple(
        replace(ep, target_address="DA1.12")
        if ep.id == "b-X2" else ep
        for ep in old.endpoints
    ))
    with pytest.raises(ValueError, match="SOURCE_B_MARKER_ADDRESS_DRIFT"):
        rebind_true_source_b(incorrect, signed, a3.symbols)

def test_negative_compact_non_b_net_pinref_swap_fails_closed(
    actual_source_and_a3,
):
    old, assembly, signed = actual_source_and_a3
    # b itself is unchanged and the total 23/15/62 still matches; mutating
    # some OTHER Net is nevertheless forbidden by source-authentic routing.
    changed = tuple(
        Net(
            net.name,
            tuple(
                PinRef("DA1", "4") if pin == PinRef("DA1", "3") else pin
                for pin in net.members
            ),
        ) if net.name == "FEEDBACK" else net
        for net in signed.nets
    )
    assert len(changed) == 15
    assert sum(len(net.members) for net in changed) == 62
    assert next(n for n in changed if n.name == SOURCE_B_NAME).members == (
        next(n for n in signed.nets if n.name == SOURCE_B_NAME).members
    )
    with pytest.raises(ValueError, match="ALL_15_PHYSICAL_NETS_NOT_FROZEN"):
        rebind_true_source_b(
            old, Circuit(signed.components, changed), assembly.symbols,
        )


def test_negative_b_pin_member_order_change_not_source_exact(
    actual_source_and_a3,
):
    old, assembly, signed = actual_source_and_a3
    modified = tuple(
        Net(net.name, tuple(reversed(net.members)))
        if net.name == SOURCE_B_NAME else net
        for net in signed.nets
    )
    with pytest.raises(ValueError, match="ALL_15_PHYSICAL_NETS_NOT_FROZEN"):
        rebind_true_source_b(
            old, Circuit(signed.components, modified), assembly.symbols,
        )
