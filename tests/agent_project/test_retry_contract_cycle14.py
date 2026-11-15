"""Real readiness CLI diagnostics are machine-readable but never a write grant."""
import json
import subprocess
import sys
from importlib.resources import files

from examples.agent_tl494_cycle11_pipeline import _request
from gost_schematic.agent_project.agent_readiness import review_request
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.agent_project.owner_source_contract import verify_frozen_owner_fixture
from gost_schematic.agent_project.retry_contract import (
    blocked_generation_diagnostics,
    readonly_error_diagnostic,
)


def test_retry_codes_fail_closed_and_only_stale_saved_snapshot_may_be_refetched():
    allowed = readonly_error_diagnostic("REQUEST_STALE_REVISION")
    assert allowed["retryable_read_only"] is True
    assert allowed["retry_mode"] == "REFETCH_AUTHORIZED_SNAPSHOT"
    assert allowed["max_retry_attempts"] == 1
    assert allowed["requires_full_source_revalidation"] is True
    for code in (
        "SOURCE_NET_MEMBERSHIP_MISMATCH", "SOURCE_NOMINAL_MISMATCH",
        "REQUEST_FOREIGN_PINREF", "REQUEST_PINREF_REUSED",
        "SOURCE_UGO_VARIANT_MISMATCH", "CATALOG_REVISION_MISMATCH",
        "REQUEST_INTENT_UNSUPPORTED", "REQUEST_RETRY_INVALID",
        "REQUEST_FAILED", "UNRECOGNIZED_ERROR_CODE",
    ):
        row = readonly_error_diagnostic(code)
        assert row["retry_mode"] == "NO_RETRY"
        assert row["retryable_read_only"] is False
        assert row["max_retry_attempts"] == 0
        assert row["source_model_mutation_allowed"] is False
        assert row["net_or_pinref_mutation_allowed"] is False
        assert row["mcp_write_allowed"] is False
    assert all(allowed[key] is False for key in (
        "source_model_mutation_allowed", "net_or_pinref_mutation_allowed",
        "mcp_write_allowed",
    ))


def test_actual_cli_invalid_request_emits_typed_no_retry():
    result = subprocess.run(
        [sys.executable, "-m", "gost_schematic.agent_project.agent_readiness"],
        input='{"schema_version":1}', capture_output=True, text=True, check=False,
    )
    assert result.returncode == 3
    data = json.loads(result.stdout)
    assert data["status"] == "REJECTED"
    assert data["code"] == "REQUEST_SCHEMA_INVALID"
    assert data["read_only"] is True and data["mutated"] is False
    assert data["diagnostic"]["code"] == "REQUEST_SCHEMA_INVALID"
    assert data["diagnostic"]["retryable_read_only"] is False
    assert data["diagnostic"]["mcp_write_allowed"] is False


def test_real_frozen_tl494_remains_blocked_with_explicit_pipeline_stages():
    frozen = files("gost_schematic").joinpath(
        "agent_project", "data", "tl494_ic97_frozen_source.json"
    ).read_bytes()
    source = verify_frozen_owner_fixture(frozen, CatalogResolver())
    report = review_request(_request(source))
    assert report["status"] == "BLOCKED_SOURCE_NOT_IMPORTABLE"
    assert report["ready_to_generate"] is False and report["mutated"] is False
    assert (report["component_count"], report["net_count"],
            report["submitted_pinref_count"]) == (23, 15, 62)
    diagnostics = report["diagnostics"]
    assert {d["code"] for d in diagnostics} == set(report["reasons"])
    assert {d["stage"] for d in diagnostics} == {
        "SOURCE_MODEL", "ROUTING", "ERC_DRC", "COMMIT_GATE",
    }
    assert all(not d["retryable_read_only"] and not d["mcp_write_allowed"]
               and d["max_retry_attempts"] == 0 for d in diagnostics)


def test_unknown_blockers_never_enable_unsafe_retry():
    result = blocked_generation_diagnostics(["UNKNOWN_FUTURE_OWNER", "GLOBAL_15_NET_ROUTER_NOT_ACCEPTED"])
    assert result[0]["stage"] == "SOURCE_MODEL"
    assert result[1]["stage"] == "ROUTING"
    assert all(not x["retryable_read_only"] and not x["mcp_write_allowed"] for x in result)
