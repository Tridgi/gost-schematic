"""One-command TL494 original-source → native read-only MCP → typed CLI evidence.

Runs WITHOUT owner checkout, Codex model credentials or project-write access.
Generated SVG/PNG are seven real *catalog UGO specimens*, NOT routed sheet.
All output is deliberately BLOCKED until authentic 15/15 route and full DRC.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.agent_project.generation_handoff import build_readonly_tl494_handoff
from gost_schematic.agent_project.owner_api_locks import load_pinned_owner_lock_manifest
from gost_schematic.agent_project.owner_source_contract import verify_frozen_owner_fixture

from .agent_tl494_cycle11_pipeline import _cli, _native_mcp_catalog, _request


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def _safe_new_output(path: Path) -> Path:
    """Operator-owned NEW path. Never overwrite evidence or follow old symlinks."""
    if not path.is_absolute():
        path = Path.cwd() / path
    for parent in (path, *path.parents):
        if parent.is_symlink() or (
            hasattr(parent, "is_junction") and parent.is_junction()
        ):
            raise ValueError("OUTPUT_SYMLINK_FORBIDDEN")
    if path.exists():
        raise ValueError("OUTPUT_ALREADY_EXISTS")
    if not path.parent.is_dir():
        raise ValueError("OUTPUT_PARENT_MISSING")
    path.mkdir(mode=0o700)
    return path


def _mutation_matrix(original: dict[str, Any]) -> list[dict[str, Any]]:
    """Meaningful real CLI refusal codes, not hardcoded pretend negatives."""
    cases = []

    def add(name: str, edit, expected: str) -> None:
        mutated = copy.deepcopy(original)
        edit(mutated)
        code, report = _cli(mutated)
        if code != 3 or report.get("code") != expected:
            raise AssertionError(
                f"Invalid source request not denied: {name}: {code} / {report}"
            )
        cases.append({"case": name, "exit_code": code,
                      "diagnostic_code": report["code"],
                      "diagnostic": report["diagnostic"], "rejected": True})

    def component(request: dict[str, Any], reference: str) -> dict[str, Any]:
        return next(c for c in request["components"] if c["reference"] == reference)

    def net(request: dict[str, Any], name: str) -> dict[str, Any]:
        return next(n for n in request["nets"] if n["name"] == name)

    add("wrong_R5_UGO", lambda req: component(req, "R5").update(
        part_id="resistor.fixed"), "SOURCE_UGO_VARIANT_MISMATCH")
    add("unknown_catalog_UGO", lambda req: component(req, "R5").update(
        part_id="resistor.not_real"), "SOURCE_UGO_VARIANT_MISMATCH")
    add("unexpected_source_R1_resistor_alias", lambda req: component(
        req, "R1"
    ).update(source_part_id="resistor.variable"), "SOURCE_PART_ID_MISMATCH")
    add("changed_R5_nominal", lambda req: component(
        req, "R5"
    ).update(nominal_si="9999"), "SOURCE_NOMINAL_MISMATCH")
    add("silent_original_b_net_rename", lambda req: net(
        req, "b_NEGATIVE_OUTPUT"
    ).update(name="OUTPUT_NEG"), "SOURCE_NET_MEMBERSHIP_MISMATCH")
    add("foreign_physical_reference", lambda req: net(
        req, "b_NEGATIVE_OUTPUT"
    )["members"][0].update(reference="FAKE"), "REQUEST_FOREIGN_PINREF")
    add("repeated_pin_in_another_net", lambda req: req["nets"][1][
        "members"
    ].append(copy.deepcopy(req["nets"][0]["members"][0])), "REQUEST_PINREF_REUSED")
    add("stale_uncommitted_revision", lambda req: req.update(
        expected_revision="f" * 64), "SOURCE_LOCK_INVALID")
    add("write_intent_denied", lambda req: req.update(
        intent="commit_transaction"), "REQUEST_INTENT_UNSUPPORTED")
    add("unsupported_print_output", lambda req: req.update(
        outputs=["write_project"]), "REQUEST_OUTPUT_INVALID")
    add("unbounded_route_retries", lambda req: req.update(
        max_route_attempts=99), "REQUEST_RETRY_INVALID")
    return cases


async def build_readonly_evidence(out: Path, source: dict[str, Any]) -> dict[str, Any]:
    """Actual native ClientSession verifies real installed catalogue."""
    return await _native_mcp_catalog(out, source)


def run(output: Path) -> dict[str, Any]:
    root = _safe_new_output(output)
    source = verify_frozen_owner_fixture(
        files("gost_schematic").joinpath(
            "agent_project", "data", "tl494_ic97_frozen_source.json"
        ).read_bytes(), CatalogResolver(),
    )
    lock = load_pinned_owner_lock_manifest()
    if source["source_fixture_git_blob_sha1"] != (
        lock["file_locks"]["ic_frozen_fixture"]["git_blob_sha1"]
    ):
        raise AssertionError("Packaged origin differs from current owner lock")
    request = _request(source)
    exit_code, report = _cli(request)
    if (
        exit_code != 2
        or report.get("status") != "BLOCKED_SOURCE_NOT_IMPORTABLE"
        or report.get("component_count") != 23
        or report.get("net_count") != 15
        or report.get("submitted_pinref_count") != 62
        or not report.get("frozen_original_pinref_membership_verified")
        or not report.get("frozen_original_nominals_verified")
        or not report.get("frozen_original_bom_part_ids_verified")
        or report.get("ready_to_generate") is not False
        or report.get("mutated") is not False
    ):
        raise AssertionError("Source typed review did not fail safely")
    negatives = _mutation_matrix(request)
    parts = asyncio.run(build_readonly_evidence(root, source))
    if len(parts) != 7:
        raise AssertionError("Expected seven true installed source UGO specimens")

    handoff = build_readonly_tl494_handoff(request, report, parts)
    (root / "source-generation-handoff.json").write_bytes(_json_bytes(handoff))
    (root / "source-typed-request.json").write_bytes(_json_bytes(request))
    (root / "source-validation.json").write_bytes(_json_bytes(report))
    (root / "refusal-tests.json").write_bytes(_json_bytes(negatives))

    artifacts = {}
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.is_symlink():
            raise AssertionError("Expected only local unredirected regular evidence files")
        raw = path.read_bytes()
        artifacts[path.name] = {
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
        }

    result = {
        "schema_version": 1,
        "status": "BLOCKED_PARTIAL",
        "source_git_sha": source["source_commit"],
        "source_git_blob_sha1": source["source_fixture_git_blob_sha1"],
        "source_manifest_sha256": source["source_typed_manifest_sha256"],
        "physical_component_count": 23,
        "original_net_count": 15,
        "original_pinref_member_count": 62,
        "physical_da1_all_16_pins": True,
        "historical_source_wires": 91,
        "historical_source_junctions": 37,
        "non_electrical_b_continuation_markers": ["b-X2", "b-R5"],
        "source_verified_against_frozen_original": True,
        "source_netlist_user_approval": "USER_REVIEW_REQUIRED",
        "source_netlist_has_been_reauthored": False,
        "actual_native_mcp_client_session": True,
        "actual_codex_cli_llm_session": False,
        "actual_catalog_ugo_type_count": len(parts),
        "actual_catalog_ugo_glyphs_svg_png": len(parts) * 2,
        "catalog_normative_status": "DRAFT_NOT_APPROVED",
        "catalog_parts_sha256": {
            name: {
                "part_sha256": row["part_sha256"],
                "symbol_sha256": row["symbol_sha256"],
            }
            for name, row in parts.items()
        },
        "owner_head_snapshot": lock["owner_heads"],
        "owner_source_files_fetched_in_this_run": False,
        "original_source_only_no_new_route_attempted": True,
        "new_routed_net_count": 0,
        "full_15_net_route_available": False,
        "source_print_drc_negative_fixture": {"errors": 9, "warnings": 32},
        "full_print_drc_executed": False,
        "complete_print_clean_svg_available": False,
        "complete_print_png_300dpi_available": False,
        "new_bom_or_netlist_committed_to_e3": False,
        "atomic_write_transactions_available": False,
        "mcp_write_tool_enabled": False,
        "cli_verified_read_only_exit_code": exit_code,
        "refusal_tests_passed": len(negatives),
        "refusal_tests_total": len(negatives),
        "generation_handoff_status": handoff["status"],
        "generation_handoff_source_request_sha256": handoff["source_request_sha256"],
        "blocked_stage_diagnostics": report["diagnostics"],
        "artifacts": artifacts,
        "next_unmet_gate": (
            "Separate trusted full manufacturer Circuit import with reviewed "
            "23/15/62; NET full 15/15 route; PAINT/ESKD full ink DRC; "
            "native SVG/300 DPI PNG and independent QA"
        ),
    }
    (root / "source-quickstart-report.json").write_bytes(_json_bytes(result))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", required=True, type=Path,
        help="New empty, non-symlink output directory (trusted local user only)",
    )
    args = parser.parse_args(argv)
    result = run(args.out)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
