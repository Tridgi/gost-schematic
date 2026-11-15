"""Cycle13 end-user *actual* native stdio and strict subprocess quickstart.

All image artifacts are physical source-locked catalogue samples, not a
fabricated fully routed TL494 sheet. No authenticated Codex model is used.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.agent_tl494_cycle11_pipeline import _assert_readonly_tool_registry
from examples.agent_tl494_cycle13_quickstart import _safe_new_output, run


def _check_hashes(root: Path, report: dict) -> None:
    assert len(report["artifacts"]) == 17  # 14 native glyphs + 3 JSON
    assert len([p for p in root.glob("*.svg")]) == 7
    assert len([p for p in root.glob("*.png")]) == 7
    for filename, facts in report["artifacts"].items():
        raw = (root / filename).read_bytes()
        assert facts["sha256"] == hashlib.sha256(raw).hexdigest()
        assert facts["bytes"] == len(raw)
        assert raw
        if filename.endswith(".png"):
            assert raw.startswith(b"\x89PNG\r\n\x1a\n")
        if filename.endswith(".svg"):
            assert b"<svg" in raw
    assert "source-quickstart-report.json" not in report["artifacts"]


def test_real_one_command_source_mcp_and_negatives(tmp_path):
    output = tmp_path / "tl494-user"
    p = subprocess.run(
        [sys.executable, "-m", "examples.agent_tl494_cycle13_quickstart",
         "--out", str(output)],
        capture_output=True, text=True, check=True,
    )
    report = json.loads(p.stdout)
    assert json.loads(
        (output / "source-quickstart-report.json").read_text(encoding="utf-8")
    ) == report
    assert report["status"] == "BLOCKED_PARTIAL"
    assert report["physical_component_count"] == 23
    assert report["original_net_count"] == 15
    assert report["original_pinref_member_count"] == 62
    assert report["physical_da1_all_16_pins"] is True
    assert report["historical_source_wires"] == 91
    assert report["historical_source_junctions"] == 37
    assert report["non_electrical_b_continuation_markers"] == ["b-X2", "b-R5"]
    assert report["source_git_blob_sha1"] == (
        "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65"
    )
    assert report["source_netlist_user_approval"] == "USER_REVIEW_REQUIRED"
    assert report["source_verified_against_frozen_original"] is True
    assert report["actual_native_mcp_client_session"] is True
    assert report["actual_codex_cli_llm_session"] is False
    assert report["actual_catalog_ugo_type_count"] == 7
    assert report["actual_catalog_ugo_glyphs_svg_png"] == 14
    assert report["catalog_normative_status"] == "DRAFT_NOT_APPROVED"
    assert report["owner_source_files_fetched_in_this_run"] is False
    assert report["full_15_net_route_available"] is False
    assert report["new_routed_net_count"] == 0
    assert report["full_print_drc_executed"] is False
    assert report["complete_print_clean_svg_available"] is False
    assert report["complete_print_png_300dpi_available"] is False
    assert report["mcp_write_tool_enabled"] is False
    assert report["atomic_write_transactions_available"] is False
    assert report["source_print_drc_negative_fixture"] == {
        "errors": 9, "warnings": 32,
    }
    assert report["refusal_tests_passed"] == report["refusal_tests_total"] == 11
    assert {d["code"] for d in report["blocked_stage_diagnostics"]} == {
        "TI_TL494_16_PIN_P11_ADAPTER_NOT_INSTALLED",
        "SOURCE_62_PINREF_MEMBERSHIP_NOT_VERIFIED_IN_P11",
        "GLOBAL_15_NET_ROUTER_NOT_ACCEPTED",
        "PRINT_INK_AND_A3_DRC_NOT_ACCEPTED",
        "NO_TRUSTED_TYPED_GENERATOR_OR_CAS_COMMIT",
    }
    assert all(d["mcp_write_allowed"] is False and
               d["retryable_read_only"] is False
               for d in report["blocked_stage_diagnostics"])
    refuses = json.loads((output / "refusal-tests.json").read_text())
    assert {x["case"] for x in refuses} == {
        "wrong_R5_UGO", "unknown_catalog_UGO",
        "unexpected_source_R1_resistor_alias", "changed_R5_nominal",
        "silent_original_b_net_rename", "foreign_physical_reference",
        "repeated_pin_in_another_net", "stale_uncommitted_revision",
        "write_intent_denied", "unsupported_print_output",
        "unbounded_route_retries",
    }
    assert all(x["exit_code"] == 3 and x["rejected"] for x in refuses)
    assert all(x["diagnostic"]["code"] == x["diagnostic_code"]
               and x["diagnostic"]["mcp_write_allowed"] is False
               and x["diagnostic"]["retryable_read_only"] is False
               for x in refuses)
    request = json.loads((output / "source-typed-request.json").read_text())
    assert request["source_sha"] == "e695c415fdced164b0e0c39c5249d030795a0aa6"
    assert len(request["components"]) == 23 and len(request["nets"]) == 15
    assert sum(len(net["members"]) for net in request["nets"]) == 62
    assert "b_NEGATIVE_OUTPUT" in {net["name"] for net in request["nets"]}
    r5 = next(x for x in request["components"] if x["reference"] == "R5")
    assert r5["part_id"] == r5["source_part_id"] == "resistor.variable"
    assert r5["nominal_si"] is not None
    _check_hashes(output, report)


def test_quickstart_rejects_overwriting_and_following_symlinks(tmp_path):
    output = tmp_path / "not-empty"
    output.mkdir()
    (output / "user.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="OUTPUT_ALREADY_EXISTS"):
        _safe_new_output(output)
    assert (output / "user.txt").read_text(encoding="utf-8") == "preserve"
    outside = tmp_path / "external"
    outside.mkdir()
    link = tmp_path / "redirect"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="OUTPUT_SYMLINK_FORBIDDEN"):
        _safe_new_output(link / "new")
    assert not (outside / "new").exists()


def test_quickstart_refuses_missing_parent(tmp_path):
    with pytest.raises(ValueError, match="OUTPUT_PARENT_MISSING"):
        _safe_new_output(tmp_path / "no-parent" / "output")


def test_output_is_source_readonly_even_if_rerun_fails(tmp_path):
    output = tmp_path / "once"
    first = run(output)
    head = hashlib.sha256(
        (output / "source-typed-request.json").read_bytes()
    ).hexdigest()
    with pytest.raises(ValueError, match="OUTPUT_ALREADY_EXISTS"):
        run(output)
    assert hashlib.sha256(
        (output / "source-typed-request.json").read_bytes()
    ).hexdigest() == head
    assert not first["new_bom_or_netlist_committed_to_e3"]


def test_mcp_registry_refuses_future_write_even_if_falsely_marked_readonly():
    def tool(*, read_only=True, destructive=False, open_world=False):
        return SimpleNamespace(annotations=SimpleNamespace(
            readOnlyHint=read_only, destructiveHint=destructive,
            openWorldHint=open_world,
        ))
    good_names = (
        "schematic_catalog_search", "schematic_catalog_select",
        "schematic_catalog_preview", "schematic_tl494_selection_profile",
        "schematic_tl494_pin_alias",
    )
    good = {name: tool() for name in good_names}
    _assert_readonly_tool_registry(good)
    for bad in (
        "schematic_commit_transaction", "schematic_create_component",
        "schematic_connect_pins", "schematic_route_net",
        "schematic_move_component", "schematic_import_project",
    ):
        with pytest.raises(AssertionError, match="write tool"):
            _assert_readonly_tool_registry({**good, bad: tool()})
    for bad_tool in (
        tool(read_only=False), tool(destructive=True), tool(open_world=True),
        SimpleNamespace(annotations=None),
    ):
        with pytest.raises(AssertionError, match="Unsafe MCP tool"):
            _assert_readonly_tool_registry({
                **good, "schematic_read_new": bad_tool,
            })
    with pytest.raises(AssertionError, match="Missing mandatory"):
        _assert_readonly_tool_registry({})
