"""Real typed AI CLI-readiness contract: accepted saved E3 vs forbidden TL494 write.

This test never uses SVG pixels as source or bypasses ProjectService.
"""
import copy
import json
import os
import subprocess
import sys

import pytest

from gost_schematic.agent_project import ProjectService
from gost_schematic.agent_project.agent_readiness import (
    build_saved_review_request,
    decode_request,
    review_request,
)
from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.agent_project.design_assistant import (
    TL494_FROZEN_SOURCE_SHA,
    TL494_GROUPS,
    TL494_REQUIRED_PARTS,
)
from gost_schematic.agent_project.trusted_import import import_six_part

PID = "96bc492b-1635-493c-855e-3f6470a57548"
KEY = "75c5b15e-7053-49e8-a059-4ffdf0a8760a"


@pytest.fixture
def saved(tmp_path, monkeypatch):
    workspace = tmp_path / "trusted"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    service = ProjectService.for_workspace(workspace)
    request = build_saved_review_request(snap, service.catalog)
    monkeypatch.setenv("GSE_P11_READONLY_ENABLED", "1")
    monkeypatch.setenv("GSE_P11_WORKSPACE", str(workspace))
    monkeypatch.setenv("GSE_P11_ALLOWED_PROJECT_IDS", PID)
    head = workspace / "projects" / PID / "HEAD.json"
    blob = workspace / "projects" / PID / "revisions" / (
        snap.project.revision + ".gseproj"
    )
    return request, snap, workspace, head, blob


def _payload(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _reject(obj, code):
    with pytest.raises(ProjectError, match=code):
        review_request(decode_request(_payload(obj)))


def _source_candidate():
    """Artificial *negative* contract fixture, NEVER called original source."""
    catalog = CatalogResolver()
    refs = sorted({ref for group in TL494_GROUPS.values() for ref in group})
    components = []
    pins = []
    for ref in refs:
        part_id = TL494_REQUIRED_PARTS.get(ref)
        lock = catalog.lock(part_id) if part_id else None
        components.append({
            "reference": ref, "part_id": part_id,
            "part_sha256": lock["part_sha256"] if lock else None,
            "symbol_sha256": lock["symbol_sha256"] if lock else None,
        })
        if part_id:
            part, _ = catalog.resolve(part_id)
            pins.extend({"reference": ref, "number": p.number} for p in part.pins)
        elif ref == "DA1":
            pins.extend({"reference": ref, "number": str(n)} for n in range(1, 17))
        else:
            pins.extend({"reference": ref, "number": str(n)} for n in range(1, 8))
    pins = pins[:62]
    assert len(pins) == 62
    return {
        "schema_version": 1, "intent": "tl494_reconstruction",
        "source_sha": TL494_FROZEN_SOURCE_SHA,
        "project_id": None, "expected_revision": None, "expected_generation": None,
        "components": components,
        "nets": [
            {"name": f"NET_{i+1:02d}",
             "members": [p for j, p in enumerate(pins) if j % 15 == i]}
            for i in range(15)
        ],
        "outputs": [
            "bom", "netlist", "drc",
            "svg_clean", "svg_diagnostic", "png_300dpi",
        ],
        "max_route_attempts": 3,
    }


def test_positive_real_saved_review_is_source_equal_and_not_writable(saved):
    request, snap, workspace, head, blob = saved
    h, b = head.read_bytes(), blob.read_bytes()
    report = review_request(decode_request(_payload(request)))
    assert report["status"] == "READ_ONLY_MODEL_MATCH"
    assert report["project_revision"] == snap.project.revision
    assert report["component_count"] == 6
    assert report["net_count"] == 5
    assert report["physical_pin_membership_count"] > 0
    assert report["source_membership_verified"]
    assert not report["mutated"] and not report["ready_to_generate"]
    assert not report["print_ready"]
    assert report["outputs_created"] == []
    assert report["route_attempts_executed"] == 0
    assert report["print_drc"] == "PARTIAL_ONLY_NOT_CERTIFIED"
    assert head.read_bytes() == h and blob.read_bytes() == b
    assert not (workspace / "artifacts").exists()


def test_complete_shaped_tl494_is_still_blocked_not_claimed_original():
    request = _source_candidate()
    report = review_request(decode_request(_payload(request)))
    assert report["status"] == "BLOCKED_SOURCE_NOT_IMPORTABLE"
    assert report["source_git_sha"] == TL494_FROZEN_SOURCE_SHA
    assert report["component_count"] == 23
    assert report["net_count"] == 15
    assert report["submitted_pinref_count"] == 62
    assert not report["source_membership_verified"]
    assert not report["ready_to_generate"]
    assert not report["mutated"]
    assert report["route_attempts_executed"] == 0
    assert report["outputs_created"] == []
    assert "GLOBAL_15_NET_ROUTER_NOT_ACCEPTED" in report["reasons"]


def test_tl494_missing_net_is_exact_error_not_silent_invention():
    request = _source_candidate()
    request["nets"].pop()
    _reject(request, "SOURCE_NET_INVENTORY_INCOMPLETE")


def test_tl494_missing_physical_pin_is_exact_error():
    request = _source_candidate()
    request["nets"][0]["members"].pop()
    _reject(request, "SOURCE_PIN_INVENTORY_INCOMPLETE")


def test_tl494_missing_part_and_wrong_ugo_are_rejected():
    req = _source_candidate()
    req["components"].pop()
    _reject(req, "SOURCE_COMPONENT_INVENTORY_INCOMPLETE")
    req = _source_candidate()
    r5 = next(r for r in req["components"] if r["reference"] == "R5")
    r5["part_id"] = "resistor.fixed"
    _reject(req, "SOURCE_UGO_VARIANT_MISMATCH")


def test_tl494_wrong_source_reference_or_fake_p11_revision_rejected():
    req = _source_candidate()
    req["source_sha"] = "0" * 40
    _reject(req, "SOURCE_LOCK_INVALID")
    req = _source_candidate()
    req["project_id"] = PID
    _reject(req, "SOURCE_LOCK_INVALID")


@pytest.mark.parametrize("part_ref", ("NOPE", "DA1", "R5"))
def test_tl494_wrong_physical_pin_and_foreign_ref_rejected(part_ref):
    req = _source_candidate()
    target = req["nets"][0]["members"][0]
    target["reference"] = part_ref
    target["number"] = "999"
    with pytest.raises(ProjectError, match=(
        "REQUEST_FOREIGN_PINREF|REQUEST_INVALID_PHYSICAL_PIN"
        "|REQUEST_PINREF_REUSED"
    )):
        review_request(decode_request(_payload(req)))


def test_real_saved_missing_net_or_changed_pin_ref_blocks(saved):
    request, _, _, _, _ = saved
    removed = copy.deepcopy(request)
    removed["nets"].pop()
    _reject(removed, "REQUEST_NET_MEMBERSHIP_MISMATCH")
    changed = copy.deepcopy(request)
    changed["nets"][0]["members"][0]["number"] = "not_a_real_pin"
    _reject(changed, "REQUEST_INVALID_PHYSICAL_PIN")


def test_real_saved_wrong_generation_or_part_sha_is_denied(saved):
    request, _, _, _, _ = saved
    stale = copy.deepcopy(request)
    stale["expected_generation"] += 1
    _reject(stale, "REQUEST_STALE_REVISION")
    wrong = copy.deepcopy(request)
    wrong["components"][0]["symbol_sha256"] = "f" * 64
    _reject(wrong, "CATALOG_REVISION_MISMATCH")


@pytest.mark.parametrize("field,value,code", [
    ("schema_version", True, "API_VERSION_UNSUPPORTED"),
    ("schema_version", 2, "API_VERSION_UNSUPPORTED"),
    ("max_route_attempts", 4, "REQUEST_RETRY_INVALID"),
    ("max_route_attempts", True, "REQUEST_RETRY_INVALID"),
    ("outputs", ["full_print_approved"], "REQUEST_OUTPUT_INVALID"),
    ("intent", "commit_transaction", "REQUEST_INTENT_UNSUPPORTED"),
    ("intent", "write_project", "REQUEST_INTENT_UNSUPPORTED"),
    ("intent", "execute_python", "REQUEST_INTENT_UNSUPPORTED"),
])
def test_malicious_or_unsupported_plan_never_becomes_write(saved, field, value, code):
    request = copy.deepcopy(saved[0])
    request[field] = value
    _reject(request, code)


def test_duplicate_keys_nan_unknown_fields_and_oversize_rejected(saved):
    with pytest.raises(ProjectError, match="REQUEST_DUPLICATE_KEY"):
        decode_request(b'{"schema_version":1,"schema_version":2}')
    with pytest.raises(ProjectError, match="REQUEST_JSON_INVALID"):
        decode_request(b'{"schema_version":NaN}')
    with pytest.raises(ProjectError, match="REQUEST_JSON_INVALID"):
        decode_request(b'{"schema_version":1.\u0000}')
    with pytest.raises(ProjectError, match="REQUEST_SIZE_INVALID"):
        decode_request(b" " * 131073)
    wrong = copy.deepcopy(saved[0])
    wrong["shell"] = "rm -rf /"
    _reject(wrong, "REQUEST_SCHEMA_INVALID")
    wrong = copy.deepcopy(saved[0])
    wrong["components"][0]["reference"] = "C3; DROP NET"
    _reject(wrong, "INVALID_COMPONENT_REFERENCE")
    wrong = copy.deepcopy(saved[0])
    wrong["nets"][0]["name"] = "../PE"
    _reject(wrong, "INVALID_NET_NAME")


def test_duplicate_component_net_pinref_and_wrong_neutral_name_rejected(saved):
    req = copy.deepcopy(saved[0])
    req["components"].append(copy.deepcopy(req["components"][0]))
    _reject(req, "REQUEST_DUPLICATE_COMPONENT")
    req = copy.deepcopy(saved[0])
    req["nets"].append(copy.deepcopy(req["nets"][0]))
    _reject(req, "REQUEST_DUPLICATE_NET")
    req = copy.deepcopy(saved[0])
    req["nets"][1]["members"].append(copy.deepcopy(req["nets"][0]["members"][0]))
    _reject(req, "REQUEST_PINREF_REUSED")
    req = copy.deepcopy(saved[0])
    req["nets"][0]["name"] = "PE"
    _reject(req, "REQUEST_NET_MEMBERSHIP_MISMATCH")


def test_denied_host_scope_and_foreign_uuid_leak_no_p11_project(saved, monkeypatch):
    request, _, _, _, _ = saved
    monkeypatch.delenv("GSE_P11_READONLY_ENABLED")
    _reject(request, "PROJECT_ACCESS_DENIED")
    monkeypatch.setenv("GSE_P11_READONLY_ENABLED", "1")
    monkeypatch.setenv("GSE_P11_ALLOWED_PROJECT_IDS", "7e2af9f2-86f0-441e-ad0e-616f5d53444a")
    _reject(request, "PROJECT_ACCESS_DENIED")


def test_real_cli_stdin_only_outputs_json_no_p11_mutation(saved):
    request, _, workspace, head, blob = saved
    initial_head, initial_blob = head.read_bytes(), blob.read_bytes()
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, "-m", "gost_schematic.agent_project.agent_readiness"],
        input=_payload(request), capture_output=True, env=env, check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    report = json.loads(proc.stdout)
    assert report["status"] == "READ_ONLY_MODEL_MATCH"
    assert report["read_only"] and not report["ready_to_generate"]
    assert b"TRACEBACK" not in proc.stdout.upper()
    assert head.read_bytes() == initial_head and blob.read_bytes() == initial_blob
    assert not (workspace / "artifacts").exists()


def test_real_cli_tl494_blocked_and_injection_fail_with_stable_exit():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GSE_P11_")}
    proc = subprocess.run(
        [sys.executable, "-m", "gost_schematic.agent_project.agent_readiness"],
        input=_payload(_source_candidate()),
        capture_output=True, env=env, check=False,
    )
    assert proc.returncode == 2
    report = json.loads(proc.stdout)
    assert report["status"] == "BLOCKED_SOURCE_NOT_IMPORTABLE"
    assert report["outputs_created"] == []
    proc = subprocess.run(
        [sys.executable, "-m", "gost_schematic.agent_project.agent_readiness"],
        input=b'{"schema_version":1,"intent":"__import__(os).system()"}',
        capture_output=True, env=env, check=False,
    )
    assert proc.returncode == 3
    assert json.loads(proc.stdout)["code"] == "REQUEST_SCHEMA_INVALID"
    assert b"Traceback" not in proc.stderr
