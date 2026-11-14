"""Source-faithful v5 multi-Net candidate positive and negative tests."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from examples.tl494_v5.compact_layout import compact_source_assembly
from examples.tl494_v5.route_candidate_driver import (
    ORIGINAL_BAD_DRC,
    REAL_SOURCE_NAMES,
    candidate_priority,
    drive_candidates,
    load_original_owner_fixture,
    position_only_move,
    restore_original_named_nets,
    score_route,
)
from gost_schematic.model.circuit import Circuit


def test_exact_frozen_owner_netnames_and_all_62_pinrefs():
    frozen, binding = load_original_owner_fixture()
    assembly = compact_source_assembly()
    restored = restore_original_named_nets(assembly, frozen)
    assert len(restored.components) == 23
    assert len(restored.nets) == len(REAL_SOURCE_NAMES) == 15
    assert sum(len(net.members) for net in restored.nets) == 62
    assert {net.name for net in restored.nets} == set(REAL_SOURCE_NAMES)
    assert {net.name for net in restored.nets} == {
        net.name for net in binding.circuit.nets
    }
    assert {
        net.name: net.members for net in restored.nets
    } == {
        net.name: net.members for net in binding.circuit.nets
    }
    assert "a_INPUT_PLUS" in {net.name for net in restored.nets}
    assert "b_NEGATIVE_OUTPUT" in {net.name for net in restored.nets}
    assert "TRANSFER" in {net.name for net in restored.nets}
    assert "PE" not in {net.name for net in restored.nets}
    assert len({
        pin for net in restored.nets for pin in net.members
    }) == 62


def test_source_alias_pin_swap_rejected_even_when_count_unchanged():
    frozen, _ = load_original_owner_fixture()
    altered = deepcopy(frozen)
    item = altered["nets"]["a_INPUT_PLUS"]
    item[0] = "DA1.3"  # valid IC pin but WRONG physical Net
    with pytest.raises(ValueError, match="PHYSICAL_PINREF_NET_DRIFT"):
        restore_original_named_nets(compact_source_assembly(), altered)


def test_same_count_different_source_net_identifier_rejected():
    frozen, _ = load_original_owner_fixture()
    altered = deepcopy(frozen)
    altered["nets"]["INPUT_POS"] = altered["nets"].pop("a_INPUT_PLUS")
    with pytest.raises(ValueError, match="ORIGINAL_NET_NAMES_DRIFT"):
        restore_original_named_nets(compact_source_assembly(), altered)


def test_false_nominal_even_if_net_counts_identical_rejected():
    frozen, _ = load_original_owner_fixture()
    positioned = compact_source_assembly()
    wrong = tuple(
        replace(part, nominal=replace(
            part.nominal, si_value=part.nominal.si_value + 100
        )) if part.reference == "R7" else part
        for part in positioned.circuit.components
    )
    fabricated = replace(
        positioned, circuit=Circuit(wrong, positioned.circuit.nets)
    )
    with pytest.raises(ValueError, match="REAL_NOMINAL_CHANGED:R7"):
        restore_original_named_nets(fabricated, frozen)


def test_move_rejects_unknown_ref_uneven_grid_and_duplicate_moves():
    original = compact_source_assembly()
    for invalid in (
        (("DA9", 5, 0),),
        (("DA1", 1, 0),),
        (("VT1", 5, 0), ("VT1", 5, 0)),
        (("DA1", 35, 0),),
    ):
        with pytest.raises(ValueError, match="V5_CANDIDATE"):
            position_only_move(original, invalid)


def test_real_position_only_move_preserves_electrical_topology_and_ic_pose():
    original = compact_source_assembly()
    moved = position_only_move(
        original, (("DA1", -5, 5), ("VT1", 5, 0)),
    )
    assert original.circuit.nets == moved.circuit.nets
    old_components = {c.reference: c for c in original.circuit.components}
    for after in moved.circuit.components:
        before = old_components[after.reference]
        assert after.part_id == before.part_id
        assert after.nominal == before.nominal
        assert after.transform == before.transform
    assert moved.owner_ic_record.placements[0].origin.x == (
        original.owner_ic_record.placements[0].origin.x - 5000
    )
    assert moved.owner_ic_record.placements[0].origin.y == (
        original.owner_ic_record.placements[0].origin.y + 5000
    )
    moved.verify()


def test_deterministic_15_net_priority_variants_reject_unknown():
    fixture, _ = load_original_owner_fixture()
    for mode in ("source", "short-first", "control-first"):
        ranking = candidate_priority(fixture, mode)
        assert len(set(ranking)) == 15
        assert set(ranking) == set(REAL_SOURCE_NAMES)
    assert candidate_priority(fixture, "source")[0] == "a_INPUT_PLUS"
    with pytest.raises(ValueError, match="UNRECOGNIZED_ROUTE_PRIORITY"):
        candidate_priority(fixture, "auto-fake-priority")


def test_never_rank_partial_zero_drc_as_print_pass():
    p = {
        "net_trees": [{
            "net": "a_INPUT_PLUS", "complete": False,
            "connected_pin_refs": ["X1.1"], "segments": 0,
        }],
        "drc": {"error_count": 0}, "diagnostics": ["NO_CLEAR_PATH"],
    }
    success_count_only = {
        "net_trees": [{
            "net": "a_INPUT_PLUS", "complete": True,
            "connected_pin_refs": ["X1.1", "L1.1"], "segments": 1,
        }],
        "drc": {"error_count": 0}, "diagnostics": [],
    }
    assert score_route(success_count_only) > score_route(p)
    assert ORIGINAL_BAD_DRC == {
        "error_count": 9, "warning_count": 32,
        "segments": 91, "junctions": 37,
    }


def test_negative_source_fixture_integration_does_not_write_outputs(tmp_path: Path):
    fixture, _ = load_original_owner_fixture()
    altered = deepcopy(fixture)
    altered["components"][0]["part_id"] = "fake.part"
    with pytest.raises(ValueError, match="ORIGINAL_PART_ID_CHANGED"):
        restore_original_named_nets(compact_source_assembly(), altered)
    assert list(tmp_path.iterdir()) == []


def test_candidate_driver_real_owners_diagnostics_only(
    tmp_path: Path,
):
    # A real 15-Net owner route; 1000 search nodes bounds CI time. It may
    # complete in the future, but QA/ESKD always remains an independent gate.
    font_env = __import__("os").environ.get("TL494_TYPE_A_FONT")
    if not font_env:
        pytest.skip("Owner-pinned CI provides TL494_TYPE_A_FONT")
    output = tmp_path / "source-all15.json"
    result = drive_candidates(
        Path(font_env), output, variants=("source",), node_cap=1000
    )
    assert output.exists()
    assert result["bom_count"] == 23
    assert result["net_count"] == 15
    assert result["physical_net_membership_count"] == 62
    assert set(result["original_net_names"]) == set(REAL_SOURCE_NAMES)
    assert result["actual_full_sheet_svg_or_png_emitted"] is False
    assert result["qa_print_release"] == "BLOCKED_INDEPENDENT_QA_AND_ESKD"
    record = result["candidates"][0]
    assert record["routes_attempted"] == 15
    assert record["print_after_released"] is False
    assert len(record["named_net_status"]) == 15
    assert set(record["named_net_status"]) == set(REAL_SOURCE_NAMES)
    assert all(
        set(net["connected"]) <= set(net["expected"])
        for net in record["named_net_status"].values()
    )
    assert record["Net_membership_SHA256"] == result["original_nets_SHA256"]
    assert record["layout_valid"] is True
    assert record["a3"]["A3_capacity_fit"] is True
    assert result["negative_original_DRC_expected"] == ORIGINAL_BAD_DRC
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(\n        json.dumps(result, ensure_ascii=False)\n    )
    assert [file.name for file in tmp_path.iterdir()] == ["source-all15.json"]
