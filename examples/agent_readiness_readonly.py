"""Actual trusted-local six-part source -> read-only CLI plan and negative evidence.

This fixture is NOT a generated TL494 sheet. Python creates only the
pre-existing known six-part model in a trusted workspace, then calls the
stdin-only separate agent-readiness CLI for exact physical netlist review.
No change to an existing project, no new source routed or autonomous Codex.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from gost_schematic.agent_project import ProjectService
from gost_schematic.agent_project.agent_readiness import build_saved_review_request
from gost_schematic.agent_project.trusted_import import import_six_part


def _invoke(data: dict, env: dict[str, str]) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, "-m", "gost_schematic.agent_project.agent_readiness"],
        input=json.dumps(data, sort_keys=True).encode(),
        capture_output=True, env=env, check=False,
    )
    if result.stderr:
        raise AssertionError("Readiness CLI wrote unexpected stderr")
    try:
        report = json.loads(result.stdout)
    except ValueError as exc:
        raise AssertionError("Readiness CLI must emit a single JSON response") from exc
    return result.returncode, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--project-id", default="d3597e28-c8d8-46f6-8473-a0d03b520c9a")
    parser.add_argument("--idempotency-key", default="e3c1d984-63a3-4859-8b6a-17a3e9ce652c")
    args = parser.parse_args(argv)
    uuid.UUID(args.project_id)
    uuid.UUID(args.idempotency_key)
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    if workspace.is_symlink() or (hasattr(workspace, "is_junction") and workspace.is_junction()):
        raise AssertionError("Redirected workspace forbidden")
    specimen = import_six_part(workspace, project_id=args.project_id,
                               idempotency_key=args.idempotency_key)
    service = ProjectService.for_workspace(workspace)
    request = build_saved_review_request(specimen, service.catalog)
    root = workspace / "projects" / args.project_id
    head = root / "HEAD.json"
    blob = root / "revisions" / (specimen.project.revision + ".gseproj")
    before_head, before_blob = head.read_bytes(), blob.read_bytes()

    env = {key: val for key, val in os.environ.items() if not key.startswith("GSE_P11_")}
    env.update({
        "GSE_P11_READONLY_ENABLED": "1",
        "GSE_P11_WORKSPACE": str(workspace),
        "GSE_P11_ALLOWED_PROJECT_IDS": args.project_id,
    })
    accepted_code, accepted = _invoke(request, env)
    if (accepted_code != 0 or accepted["status"] != "READ_ONLY_MODEL_MATCH"
            or accepted["ready_to_generate"] or not accepted["source_membership_verified"]):
        raise AssertionError("Expected real immutable six-part physical review only")
    missing = json.loads(json.dumps(request))
    missing["nets"].pop()
    refused_code, refused = _invoke(missing, env)
    if refused_code != 3 or refused["code"] != "REQUEST_NET_MEMBERSHIP_MISMATCH":
        raise AssertionError("Partial physical Net plan was not rejected")
    poisoned = json.loads(json.dumps(request))
    poisoned["intent"] = "commit_transaction"
    poison_code, poison = _invoke(poisoned, env)
    if poison_code != 3 or poison["code"] != "REQUEST_INTENT_UNSUPPORTED":
        raise AssertionError("Arbitrary MCP/CLI edit instruction was not rejected")
    forbidden = json.loads(json.dumps(request))
    forbidden["project_id"] = "3c683a93-6ccb-4538-bc09-a589d32d79f6"
    access_code, denied = _invoke(forbidden, env)
    if access_code != 3 or denied["code"] != "PROJECT_ACCESS_DENIED":
        raise AssertionError("Host allowlist leak")
    if head.read_bytes() != before_head or blob.read_bytes() != before_blob:
        raise AssertionError("Read-only CLI changed original P1.1 snapshot")

    proof = {
        "schema_version": 1,
        "generator_implemented": False,
        "mcp_write_tools_enabled": False,
        "cli_transport": "trusted subprocess JSON stdin/stdout, no filesystem argument",
        "project_revision": specimen.project.revision,
        "project_head_sha256": hashlib.sha256(before_head).hexdigest(),
        "project_blob_sha256": hashlib.sha256(before_blob).hexdigest(),
        "project_model_unchanged": True,
        "source_kind": "real-six-part-P1.1-fixture-not-TL494",
        "accepted_review": accepted,
        "incomplete_net_denial": refused,
        "malicious_write_intent_denial": poison,
        "unauthorized_project_denial": denied,
        "exit_statuses": [accepted_code, refused_code, poison_code, access_code],
    }
    # Trusted CLIENT-local evidence, never emitted by the read-only CLI or MCP.
    out = workspace / "readiness-client-evidence"
    if out.is_symlink() or (hasattr(out, "is_junction") and out.is_junction()):
        raise AssertionError("Redirected evidence directory forbidden")
    out.mkdir(exist_ok=True)
    files = {"request.json": request, "proof.json": proof}
    for name, value in files.items():
        (out / name).write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(proof, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
