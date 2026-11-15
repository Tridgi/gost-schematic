"""Cycle13 deterministic source-only relocation and fail-closed evidence tests."""
import pytest

from examples.tl494_v5.compact_layout import (
    actual_component_occupied_mm,
    compact_source_assembly,
)
from examples.tl494_v5.cycle11_ti_bridge import bind_verified_compact_ti
from examples.tl494_v5.cycle13_placement_matrix import (
    PLACEMENT_TRIALS,
    summarize_trial,
)
from examples.tl494_v5.route_candidate_driver import (
    load_original_owner_fixture,
    position_only_move,
    restore_original_named_nets,
)


@pytest.mark.parametrize(("name", "moves"), PLACEMENT_TRIALS)
def test_legal_c13_source_preserving_editorial_candidates(name, moves):
    frozen, _ = load_original_owner_fixture()
    base = compact_source_assembly()
    changed = position_only_move(base, moves)
    before = restore_original_named_nets(base, frozen)
    after = restore_original_named_nets(changed, frozen)
    actual = {net.name: net.members for net in after.nets}
    assert name and after.nets == before.nets
    assert changed.circuit.nets is base.circuit.nets
    assert len(actual) == 15
    assert sum(len(pins) for pins in actual.values()) == 62
    assert len(after.components) == 23
    assert {
        pin.number for pins in actual.values() for pin in pins
        if pin.reference == "DA1"
    } == {str(i) for i in range(1, 17)}
    signed = bind_verified_compact_ti(changed, after)
    assert signed.signed.circuit.nets is after.nets
    assert len(signed.signed.contacts) == 16
    for original, moved in zip(
        before.components, after.components, strict=True,
    ):
        assert original.reference == moved.reference
        assert original.part_id == moved.part_id
        assert original.transform == moved.transform
        assert original.nominal == moved.nominal
    footprint = actual_component_occupied_mm(changed, changed.symbols)
    assert len(footprint["bbox_um"]) == 4
    assert footprint["nominal_symbols_scaled"] is False
    assert footprint["printable"] is False


def test_corrected_x1_stroke_is_physically_inside_a3_margin():
    base = compact_source_assembly()
    actual = actual_component_occupied_mm(base, base.symbols)
    assert actual["A3_bbox_within_margins"] is True
    assert actual["A3_capacity_fit"] is True
    assert actual["bbox_um"][0] >= 10000
    assert actual["bbox_um"][2] <= 410000
    assert actual["DRC_pass"] is False


def _partial_trial() -> dict:
    return {
        "source_unchanged": True,
        "a3": {
            "bbox_um": [10850, 14800, 405150, 243151],
            "A3_capacity_fit": True,
            "A3_bbox_within_margins": True,
        },
        "status": "BLOCKED_PARTIAL_ROUTING_NO_PRINT",
        "routed_net_count": 10,
        "routes_attempted": 15,
        "named_net_status": {str(i): {} for i in range(15)},
        "layout_valid": True,
        "technical_route_eligible": False,
        "print_after_released": False,
    }


def test_partial_10_of_15_never_laundered_into_print():
    report = summarize_trial("partial", _partial_trial())
    assert report["completed_nets"] == 10
    assert report["print_after_released"] is False
    assert report["technical_route_eligible"] is False
    assert len(report["named_net_status"]) == 15


@pytest.mark.parametrize(
    ("key", "value", "error"),
    [
        ("source_unchanged", False, "CHANGED_SOURCE"),
        ("routes_attempted", 14, "SILENTLY_SKIPPED_NET"),
        ("routes_attempted", 0, "ROUTE_NOT_ATTEMPTED_UNDISCLOSED"),
        ("routed_net_count", 16, "INVALID_ROUTE_COUNT"),
        ("print_after_released", True, "UNVERIFIED_PRINT_RELEASE"),
    ],
)
def test_matrix_diagnostics_reject_forged_owners(key, value, error):
    source = _partial_trial()
    source[key] = value
    with pytest.raises(ValueError, match=error):
        summarize_trial("forged", source)


def test_layout_block_is_explicit_not_zero_drc_success():
    t = _partial_trial()
    t.update({
        "status": "BLOCKED_LAYOUT_NO_ROUTE_ATTEMPT",
        "routes_attempted": 0,
        "routed_net_count": 0,
        "technical_route_eligible": False,
    })
    t.pop("named_net_status")
    report = summarize_trial("outside", t)
    assert report["status"] == "BLOCKED_LAYOUT_NO_ROUTE_ATTEMPT"
    assert report["completed_nets"] == 0
    assert report["print_after_released"] is False
