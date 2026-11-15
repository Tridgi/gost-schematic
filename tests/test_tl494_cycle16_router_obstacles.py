"""True frozen 23 installed obstacle/portal Cycle16 regression tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.export_tl494_cycle16_router_obstacles import (
    router_obstacle_contract,
)


REPORT = (
    Path(__file__).resolve().parents[1]
    / "reports/tl494-cycle15-true-23-ink.json"
)


@pytest.fixture
def source() -> dict:
    return json.loads(REPORT.read_text(encoding="utf-8"))["control"]


def test_full_true_source_ink_is_not_box_only(source):
    output = router_obstacle_contract(source)
    assert output["pin_portal_count"] == 62
    assert output["type_a_measured_text_count"] == 73
    assert output["primitive_ink_obstacle_count"] > 23
    assert len(output["visual_ink_stroke_obstacles"]) == output[
        "primitive_ink_obstacle_count"
    ]
    assert output["route_pass"] is False
    assert output["full_drc_pass"] is False


def test_16_true_da1_portals_and_no_foreign_net_clearance(source):
    output = router_obstacle_contract(source)
    da1 = [x for x in output["physical_pinref_portals"]
           if x["owner_reference"] == "DA1"]
    assert {p["pin_ref"] for p in da1} == {
        f"DA1.{i}" for i in range(1, 17)
    }
    for port in output["physical_pinref_portals"]:
        assert not port["foreign_net_crossing_allowed"]
        assert port["electrical_connection_only_at_exact_pinref"]
        assert port["escape_unit_vector"] in (
            [-1, 0], [1, 0], [0, -1], [0, 1],
        )


@pytest.mark.parametrize("ref,numbers,roles", (
    ("VD1", {"1", "2"}, {"A", "K"}),
    ("VT1", {"1", "2", "3"}, {"G", "D", "S"}),
    ("R5", {"1", "2", "3"}, {"A", "B", "W"}),
))
def test_true_physical_polarity_and_mos_not_four_pin(
    source, ref, numbers, roles,
):
    output = router_obstacle_contract(source)
    pins = [p for p in output["physical_pinref_portals"]
            if p["owner_reference"] == ref]
    assert {p["pin_ref"].rsplit(".", 1)[1] for p in pins} == numbers
    assert {p["manufacturer_role"] for p in pins} == roles


@pytest.mark.parametrize("kind", ("missing_ink", "fake_mos", "false_net", "no_text"))
def test_invalid_portal_or_unmeasured_ink_fails_closed(source, kind):
    broken = copy.deepcopy(source)
    if kind == "missing_ink":
        broken["parts"]["L1"]["individual_stroked_primitives_um"] = []
    elif kind == "fake_mos":
        extra = copy.deepcopy(
            broken["parts"]["VT1"]["real_physical_contacts"][-1]
        )
        extra["pin_ref"] = "VT1.4"
        extra["number"] = "4"
        broken["parts"]["VT1"]["real_physical_contacts"].append(extra)
    elif kind == "false_net":
        broken["parts"]["R5"]["real_physical_contacts"][0][
            "canonical_source_net"
        ] = "COMMON"
    else:
        broken["actual_PAINT_TypeA_text_guards"][0][
            "collision_box_um"
        ] = None
    with pytest.raises(AssertionError, match="UGO_C16_"):
        router_obstacle_contract(broken)


def test_source_true_lead_portals_are_not_connections_on_search_intersections(source):
    output = router_obstacle_contract(source)
    assert not output["crossed_visibility_portal_creates_electrical_node"]
    refs = {p["pin_ref"] for p in output["physical_pinref_portals"]}
    assert len(refs) == 62
    assert output["obstacle_model"] == "REAL_STROKES_NO_REMOTE_COORDINATE_VETO"
