"""QA-only structural E1 acceptance corpus; ELEKTRIK model is NOT integrated.

This file checks that negative vectors are independently reproducible and
well formed; it DOES NOT run/certify a hypothetical production StructuralDiagram.
The owner will bind the vectors to actual typed model/renderer once merged.
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures/qa_structural_e1_negative_vectors.json"
)
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))
CASES = tuple(DATA["cases"])


def materialize_case(case):
    """Apply a strict JSON-pointer mutation to the real baseline data."""
    vector = deepcopy(DATA["base_diagram"])
    for mutation in case["mutations"]:
        path = mutation["path"]
        assert path.startswith("/")
        parts = path[1:].split("/")
        obj = vector
        for key in parts[:-1]:
            obj = obj[int(key)] if isinstance(obj, list) else obj[key]
        last = parts[-1]
        if mutation["op"] == "replace":
            if isinstance(obj, list):
                index = int(last)
                assert 0 <= index < len(obj)
                obj[index] = mutation["value"]
            else:
                assert last in obj
                obj[last] = mutation["value"]
        elif mutation["op"] == "add":
            if isinstance(obj, list):
                assert last == "-"
                obj.append(mutation["value"])
            else:
                assert last not in obj
                obj[last] = mutation["value"]
        elif mutation["op"] == "remove":
            if isinstance(obj, list):
                obj.pop(int(last))
            else:
                assert last in obj
                del obj[last]
        else:
            raise AssertionError(f"Invalid fixture operation: {mutation!r}")
    return vector


def test_e1_manifest_is_explicitly_future_contract_not_current_certification():
    assert DATA["schema_version"] == 1
    assert DATA["status"] == "CONTRACT_ONLY_NOT_EXECUTED_AGAINST_PENDING_MODEL"
    assert "NOT ГОСТ" in DATA["normativity_note"]
    assert DATA["owners"]["model"] == "ELEKTRIK Issue #70"
    assert len(CASES) == 32
    assert {x["expected"] for x in CASES} == {
        "REJECT", "ACCEPT", "ACCEPT_NO_MERGE", "BLOCKED",
    }
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))
    assert ids == [f"E1-NEG-{i:02d}" for i in range(1, 33)]
    assert len({
        x["category"] for x in CASES
    }) >= 26
    assert sum(x["expected"] == "REJECT" for x in CASES) >= 24
    assert sum(x["expected"] == "BLOCKED" for x in CASES) >= 2


def test_e1_baseline_uses_only_functional_ports_not_real_electrical_pins():
    baseline = DATA["base_diagram"]
    assert baseline["schema_version"] == 1
    assert baseline["physical_parts"] == []
    assert baseline["electrical_nets"] == []
    ids = [block["id"] for block in baseline["blocks"]]
    assert len(set(ids)) == len(ids)
    allowed = {"LEFT", "RIGHT", "TOP", "BOTTOM"}
    index = {
        block["id"]: {
            port["id"]: port for port in block["ports"]
        } for block in baseline["blocks"]
    }
    for block in baseline["blocks"]:
        assert block["width_um"] > 0 and block["height_um"] > 0
        assert len(index[block["id"]]) == len(block["ports"])
        for port in block["ports"]:
            assert port["side"] in allowed
            assert 0 <= port["position"] <= 1
    # Two outgoing ports on SAME side at distinct, ordered positions.
    outputs = [
        port for port in baseline["blocks"][0]["ports"]
        if port["side"] == "RIGHT"
    ]
    assert len(outputs) == 2
    assert outputs[0]["position"] < outputs[1]["position"]
    for link in baseline["links"]:
        source, dest = link["source"], link["target"]
        assert index[source["block_id"]][source["port_id"]][
            "direction"
        ] == "OUTPUT"
        assert index[dest["block_id"]][dest["port_id"]][
            "direction"
        ] == "INPUT"
        assert link["arrow"] == "source_to_target"


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[entry["id"] for entry in CASES],
)
def test_all_negative_vectors_apply_without_implicit_model_import(case):
    diagram = materialize_case(case)
    assert diagram != {} and "blocks" in diagram and "links" in diagram
    assert case["expected"] in (
        "REJECT", "ACCEPT", "ACCEPT_NO_MERGE", "BLOCKED",
    )
    assert case["normativity"] == (
        "EDITORIAL_MODEL_CONTRACT_PENDING_ESKD_ISSUE_69"
    )
    if case["expected"] == "REJECT":
        assert case["expected_diagnostic_family"].startswith("E1_")
    else:
        assert case["expected_diagnostic_family"] is None
    assert case["requires"] in {
        "model", "text_measurer", "crossing_router",
        "port_spacing_policy", "renderer", "fanout_policy",
    }
    if case["mutations"]:
        assert diagram != DATA["base_diagram"]
    else:
        assert diagram == DATA["base_diagram"]


def test_future_x_crossing_without_junction_is_not_an_electrical_net():
    cross = next(
        case for case in CASES
        if case["category"] == "CROSSING_NO_IMPLICIT_JOIN"
    )
    diagram = materialize_case(cross)
    assert cross["expected"] == "ACCEPT_NO_MERGE"
    assert diagram["graphics"][-1] == {
        "kind": "crossing",
        "links": ["F1", "F2"],
        "point_um": [45000, 9000],
        "junction": False,
    }
    assert diagram["physical_parts"] == []
    assert diagram["electrical_nets"] == []


def test_structural_negative_corpus_covers_all_requested_threats():
    names = {case["category"] for case in CASES}
    assert {
        "INVALID_PORT_SIDE",
        "PORT_SIDE_OVERLAP",
        "UNDECLARED_SOURCE_ANCHOR",
        "UNDECLARED_TARGET_ANCHOR",
        "ARROW_DIRECTION_MISMATCH",
        "ARROWHEAD_VISUAL_REVERSED",
        "MULTIPORT_SIDE_ORDERED",
        "CROSSING_NO_IMPLICIT_JOIN",
        "INVALID_DIMENSION",
        "TEXT_OUTSIDE_BLOCK",
        "TEXT_INK_OVERFLOW",
        "ELECTRICAL_MODEL_LEAK",
        "DUPLICATE_PORT_ID",
        "MISSING_TARGET_PORT",
        "SELF_LINK",
    }.issubset(names)
