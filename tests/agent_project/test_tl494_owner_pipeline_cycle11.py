"""Cycle11 original source 23/15/62 -> real typed strict CLI request, blocked router."""
import copy
from pathlib import Path

import pytest

from examples.agent_tl494_cycle11_pipeline import _request
from gost_schematic.agent_project.agent_readiness import review_request
from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.agent_project.owner_source_contract import verify_frozen_owner_fixture

FIXTURE = (Path(__file__).parents[1] / "fixtures"
           / "ai_tl494_ic97_pinned_source.json")


@pytest.fixture
def real_source():
    return verify_frozen_owner_fixture(FIXTURE.read_bytes(), CatalogResolver())


def test_exact_original_23_15_62_r5_pinref_cli_boundary_is_blocked(real_source):
    req = _request(real_source)
    result = review_request(req)
    assert result["component_count"] == 23
    assert result["net_count"] == 15
    assert result["submitted_pinref_count"] == 62
    assert result["status"] == "BLOCKED_SOURCE_NOT_IMPORTABLE"
    assert not result["source_membership_verified"]
    assert not result["ready_to_generate"] and not result["mutated"]
    assert result["route_attempts_executed"] == 0
    assert result["outputs_created"] == []
    assert result["source_git_sha"] == (
        "e695c415fdced164b0e0c39c5249d030795a0aa6"
    )
    original = real_source["source_nets"]
    submitted = {
        n["name"]: [f"{p['reference']}.{p['number']}" for p in n["members"]]
        for n in req["nets"]
    }
    assert submitted == original
    assert "b_NEGATIVE_OUTPUT" in submitted
    assert "a_INPUT_PLUS" in submitted
    assert "PE" not in submitted
    r5 = next(c for c in req["components"] if c["reference"] == "R5")
    assert r5["part_id"] == "resistor.variable"
    assert r5["part_sha256"] and r5["symbol_sha256"]


def test_missing_full_original_net_prevents_acceptance(real_source):
    req = _request(real_source)
    req["nets"].pop()
    with pytest.raises(ProjectError, match="SOURCE_NET_INVENTORY_INCOMPLETE"):
        review_request(req)


def test_reused_real_pinref_and_ugo_sha_fails_closed(real_source):
    req = _request(real_source)
    req["nets"][1]["members"].append(copy.deepcopy(
        req["nets"][0]["members"][0],
    ))
    with pytest.raises(ProjectError, match="REQUEST_PINREF_REUSED"):
        review_request(req)
    req = _request(real_source)
    next(c for c in req["components"] if c["reference"] == "R5")[
        "part_sha256"
    ] = "f" * 64
    with pytest.raises(ProjectError, match="CATALOG_REVISION_MISMATCH"):
        review_request(req)


def test_renamed_and_missing_original_2_continuation_links_denied(real_source):
    req = _request(real_source)
    target = next(n for n in req["nets"] if n["name"] == "b_NEGATIVE_OUTPUT")
    target["name"] = "OUTPUT_NEG"
    # Same count cannot fake changed identity: current source provider lacks
    # verified saved P1.1 correspondence; full TL494 remains BLOCKED.
    assert review_request(req)["status"] == "BLOCKED_SOURCE_NOT_IMPORTABLE"
    assert "b_NEGATIVE_OUTPUT" not in {
        n["name"] for n in req["nets"]
    }
    req = _request(real_source)
    next(n for n in req["nets"] if n["name"] == "b_NEGATIVE_OUTPUT")[
        "members"
    ].pop()
    with pytest.raises(ProjectError, match="SOURCE_PIN_INVENTORY_INCOMPLETE"):
        review_request(req)
