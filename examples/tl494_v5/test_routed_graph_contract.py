"""PAINT hand-off contract: only source-locked accepted typed graphs, no art."""
from copy import deepcopy

import pytest

from examples.tl494_v5.route_candidate_driver import load_original_owner_fixture
from examples.tl494_v5.routed_graph_contract import (
    rehydrate_verified_route_graph,
)


def _serialization_only_toy():
    """Synthetic wire for serialization tests, NOT a real TL494 route proof."""
    frozen, _ = load_original_owner_fixture()
    netlist = frozen["nets"]
    winner = "RC_CORRECTION"
    states = {
        name: {
            "expected": list(members),
            "connected": list(members) if name == winner else [],
            "complete": name == winner,
        }
        for name, members in netlist.items()
    }
    trial = {
        "source_unchanged": True,
        "source_nets": deepcopy(netlist),
        "print_after_released": False,
        "named_net_status": states,
        "owner_router_report": {
            "graph_segments": 1, "graph_junctions": 0,
            "routed_net_count": 1,
        },
        "accepted_graph_nonprintable": {
            "status": "DIAGNOSTIC_ONLY_NOT_PRINT_AFTER",
            "segments_um": [{
                "net": winner, "start": [0, 0], "end": [1000, 0],
            }],
            "junctions_um": [],
            "total_segment_count": 1,
            "total_manhattan_length_mm": 1.0,
            "source_original_wire_count": 91,
            "historical_negative_not_overwritten": True,
        },
    }
    return trial, netlist


def test_exact_integer_typed_graph_roundtrip_is_not_printable():
    toy, source = _serialization_only_toy()
    graph = rehydrate_verified_route_graph(toy, source)
    assert len(graph.segments) == 1
    assert graph.segments[0].net_name == "RC_CORRECTION"
    assert graph.segments[0].start.x == 0
    assert graph.segments[0].end.x == 1000
    assert graph.junctions == ()
    assert toy["print_after_released"] is False


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("fake_pe", "UNACCEPTED_OR_FOREIGN_NET"),
        ("diagonal", "DIAGONAL_OR_ZERO_STROKE"),
        ("zero_wire", "DIAGONAL_OR_ZERO_STROKE"),
        ("bad_count", "WIRE_OR_NEGATIVE_SNAPSHOT_DRIFT"),
        ("foreign_junction", "FOREIGN_OR_FAKE_T_X_JUNCTION"),
        ("fake_release", "DIAGNOSTIC_ONLY_REQUIRED"),
        ("wrong_pinref", "SOURCED_PINREF_MISMATCH"),
        ("lost_net_name", "NAMED_NET_MISMATCH"),
    ],
)
def test_wire_graph_rejects_all_fabricated_data(mutation, error):
    trial, source = _serialization_only_toy()
    if mutation == "fake_pe":
        trial["accepted_graph_nonprintable"]["segments_um"][0]["net"] = "PE"
    elif mutation == "diagonal":
        trial["accepted_graph_nonprintable"]["segments_um"][0]["end"] = [
            1000, 2000,
        ]
    elif mutation == "zero_wire":
        trial["accepted_graph_nonprintable"]["segments_um"][0]["end"] = [0, 0]
    elif mutation == "bad_count":
        trial["accepted_graph_nonprintable"]["total_segment_count"] = 2
    elif mutation == "foreign_junction":
        trial["accepted_graph_nonprintable"]["junctions_um"].append([500, 0])
    elif mutation == "fake_release":
        trial["print_after_released"] = True
    elif mutation == "wrong_pinref":
        trial["source_nets"]["a_INPUT_PLUS"][0] = "DA1.3"
    elif mutation == "lost_net_name":
        trial["source_nets"]["INPUT_POS"] = trial["source_nets"].pop(
            "a_INPUT_PLUS"
        )
    with pytest.raises(ValueError, match=error):
        rehydrate_verified_route_graph(trial, source)
