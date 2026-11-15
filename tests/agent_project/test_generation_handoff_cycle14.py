"""Future-generator handoff tests: strict source, synthetic glyph metadata only.

The smoke uses synthetic image SHA metadata to exercise a contract; this is
NOT an accepted TL494 render. Actual native glyph bytes are independently
verified by the Cycle13 ClientSession quickstart and installed-wheel CI.
"""
import copy
import hashlib
from importlib.resources import files

import pytest

from examples.agent_tl494_cycle11_pipeline import _request
from gost_schematic.agent_project.agent_readiness import review_request
from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.agent_project.design_assistant import TL494_REQUIRED_PARTS
from gost_schematic.agent_project.generation_handoff import build_readonly_tl494_handoff
from gost_schematic.agent_project.owner_source_contract import verify_frozen_owner_fixture


def _proof():
    catalog = CatalogResolver()
    source = verify_frozen_owner_fixture(files("gost_schematic").joinpath(
        "agent_project", "data", "tl494_ic97_frozen_source.json",
    ).read_bytes(), catalog)
    request = _request(source)
    report = review_request(request)
    gallery = {}
    for part in set(TL494_REQUIRED_PARTS.values()):
        sha = catalog.lock(part)
        gallery[part] = {
            "part_sha256": sha["part_sha256"],
            "symbol_sha256": sha["symbol_sha256"],
            "normative_approval": False,
            # Synthetic-only test data; never presented as native MCP image.
            "real_svg_sha256": hashlib.sha256(("test-svg:" + part).encode()).hexdigest(),
            "real_png_sha256": hashlib.sha256(("test-png:" + part).encode()).hexdigest(),
        }
    return request, report, gallery


def test_exact_source_handoff_is_honestly_blocked():
    request, report, gallery = _proof()
    result = build_readonly_tl494_handoff(request, report, gallery)
    assert result["status"] == "BLOCKED_GENERATOR_NOT_INTEGRATED"
    assert result["contract"] == "tl494.future_generator_handoff.read_only.v1"
    assert result["source_component_count"] == 23
    assert result["source_net_count"] == 15
    assert result["source_pinref_memberships"] == 62
    assert result["source_da1_pin_count"] == 16
    assert len(result["required_exact_ugo_refs"]) == 13
    assert result["required_exact_ugo_refs"] == TL494_REQUIRED_PARTS
    assert len(result["locked_catalog_glyphs"]) == 7
    assert len(result["source_net_names"]) == 15
    assert len(result["stages"]) == 7
    assert all(s["verified_complete"] is False for s in result["stages"])
    assert result["source_netlist_user_approval"] == "USER_REVIEW_REQUIRED"
    assert result["ready_to_generate"] is False
    assert result["print_ready"] is False
    assert result["all_15_nets_routed"] is False
    assert result["global_print_drc_verified"] is False
    assert result["mcp_write_tools_enabled"] is False
    assert result["trusted_commit_authorized"] is False
    assert result["mutated"] is False


@pytest.mark.parametrize("fake_field,fake_value", [
    ("ready_to_generate", True),
    ("mutated", True),
    ("status", "READ_ONLY_MODEL_MATCH"),
    ("source_git_sha", "f" * 40),
    ("frozen_original_pinref_membership_verified", False),
])
def test_handoff_rejects_counterfeit_readiness_report(fake_field, fake_value):
    request, report, gallery = _proof()
    report[fake_field] = fake_value
    with pytest.raises(ProjectError, match="CLI result differs"):
        build_readonly_tl494_handoff(request, report, gallery)


def test_handoff_rejects_missing_or_forged_catalog_and_approval():
    request, report, gallery = _proof()
    missing = copy.deepcopy(gallery)
    del missing["fuse.general"]
    with pytest.raises(ProjectError, match="Seven exact"):
        build_readonly_tl494_handoff(request, report, missing)
    for field, value in (
        ("part_sha256", "a" * 64),
        ("symbol_sha256", "f" * 64),
        ("real_png_sha256", "not-a-digest"),
        ("normative_approval", True),
    ):
        wrong = copy.deepcopy(gallery)
        wrong["fuse.general"][field] = value
        with pytest.raises(ProjectError, match="Ungrounded UGO"):
            build_readonly_tl494_handoff(request, report, wrong)


def test_handoff_refuses_rebinding_physical_net_and_wrong_part_id():
    request, report, gallery = _proof()
    wrong = copy.deepcopy(request)
    wrong["nets"][0]["members"][0]["number"] = "99"
    with pytest.raises(ProjectError):
        build_readonly_tl494_handoff(wrong, report, gallery)
    wrong = copy.deepcopy(request)
    next(x for x in wrong["components"] if x["reference"] == "R5")[
        "part_id"
    ] = "resistor.fixed"
    with pytest.raises(ProjectError):
        build_readonly_tl494_handoff(wrong, report, gallery)


def test_handoff_rejects_truncated_output_or_changed_source_request():
    request, report, gallery = _proof()
    wrong = copy.deepcopy(request)
    wrong["outputs"].remove("png_300dpi")
    wrong_report = review_request(wrong)
    with pytest.raises(ProjectError, match="Six bounded outputs"):
        build_readonly_tl494_handoff(wrong, wrong_report, gallery)
    wrong = copy.deepcopy(request)
    wrong["source_sha"] = "0" * 40
    with pytest.raises(ProjectError):
        build_readonly_tl494_handoff(wrong, report, gallery)
