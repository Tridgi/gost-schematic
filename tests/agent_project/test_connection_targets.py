"""Read-only saved E3 target proof: physical pins, real wire ends, roles and Net IDs."""
from dataclasses import replace
from pathlib import Path

import pytest

from gost_schematic.agent_project import ProjectError, ProjectService
from gost_schematic.agent_project.connection_targets import (
    ConnectionTarget,
    _candidate_reason,
    build_connection_targets,
)
from gost_schematic.agent_project.trusted_import import import_six_part
from gost_schematic.electrical.netrefs import NetIdentity
from gost_schematic.model.circuit import PinRef

PID = "a8fb3921-48e3-43a4-8ce3-4a0b82e345ec"
KEY = "7f6f78ac-d43e-48c2-b6c2-236bffec949e"


def _source(tmp_path: Path):
    workspace = tmp_path / "saved"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    service = ProjectService.for_workspace(workspace)
    return service, snap, workspace


def test_real_saved_pin_and_wire_end_identity_and_no_image_inference(tmp_path):
    service, snapshot, workspace = _source(tmp_path)
    revision = snapshot.project.revision
    report = service.get_connection_targets(PID, revision)
    assert report["project_revision"] == revision
    assert report["project_id"] == PID
    assert report["generation"] == 1
    assert report["read_only"] is True
    assert report["hover_creates_net"] is False
    assert report["route_preview_available"] is False
    assert report["transaction_available"] is False

    pins = [t for t in report["targets"] if t["kind"] == "physical_pin"]
    ends = [t for t in report["targets"] if t["kind"] == "wire_endpoint"]
    assert len(ends) == 32  # 16 original authored wire segments; neither pixels nor body ink.
    assert report["target_count"] == len(pins) + 32
    assert len({t["target_id"] for t in report["targets"]}) == report["target_count"]
    assert len({t["wire_segment_id"] for t in ends}) == 16
    assert all(t["connection_allowed"] is False for t in report["targets"])
    assert all(t["reason_code"] == "SOURCE_REQUIRED" for t in report["targets"])

    original = snapshot.project.to_record()
    by_wire = {wire["id"]: wire for wire in original["wires"]}
    for end in ends:
        wire = by_wire[end["wire_segment_id"]]
        assert end["world_um"] == wire[end["wire_end"] + "_um"]
        assert end["net_identity"]["id"] == wire["net_id"]
        assert end["physical_number"] is None and end["pin_ref"] is None
        assert end["electrical_role"] == "CONDUCTOR"
        assert end["component_id"] is None
    component_id = next(
        row["id"] for row in original["components"] if row["reference"] == "C3"
    )
    c3 = [t for t in pins if t["pin_ref"]["reference"] == "C3"]
    assert len(c3) == 2
    assert {(p["physical_number"], p["pin_name"], tuple(p["world_um"]))
            for p in c3} == {
        ("1", "PLUS", (91000, 80000)), ("2", "MINUS", (109000, 80000)),
    }
    assert all(p["component_id"] == component_id for p in c3)
    assert all(p["pin_function"] and p["polarity"] for p in c3)
    assert len({p["net_identity"]["id"] for p in c3}) == 2
    assert all(p["selection_allowed"] for p in c3)
    assert all(t["project_revision"] == revision for t in report["targets"])
    # Candidate data is non-authoritative: the saved E3 bytes remain unchanged.
    assert not (workspace / "artifacts").exists()
    assert service.open_project(PID, revision).project.to_record() == original
    second = service.get_connection_targets(PID, revision)
    assert report == second


def test_cross_net_is_blocked_by_uuid_not_name_or_svg(tmp_path):
    service, snapshot, _ = _source(tmp_path)
    first = service.get_connection_targets(PID, snapshot.project.revision)
    pin1 = next(t for t in first["targets"]
                if t["kind"] == "physical_pin"
                and t["pin_ref"] == {"reference": "C3", "number": "1"})
    pin2 = next(t for t in first["targets"]
                if t["kind"] == "physical_pin"
                and t["pin_ref"] == {"reference": "C3", "number": "2"})
    pair = service.get_connection_targets(
        PID, snapshot.project.revision, source_target_id=pin1["target_id"],
    )
    other = next(t for t in pair["targets"] if t["target_id"] == pin2["target_id"])
    assert other["preview_candidate_allowed"] is False
    assert other["connection_allowed"] is False
    assert other["reason_code"] == "NET_MERGE_DENIED"
    self_pin = next(t for t in pair["targets"] if t["target_id"] == pin1["target_id"])
    assert self_pin["reason_code"] == "SAME_TARGET"
    with pytest.raises(ProjectError, match="SOURCE_TARGET_UNKNOWN"):
        service.get_connection_targets(PID, snapshot.project.revision,
                                       source_target_id="f" * 36)
    with pytest.raises(ProjectError, match="REVISION_NOT_FOUND"):
        service.get_connection_targets(PID, "f" * 64)


def _target(target_id: str, role: str, net: NetIdentity | None = None):
    return ConnectionTarget(
        target_id=target_id, project_id=PID, project_revision="a" * 64,
        kind="physical_pin", world_um=(10000, 20000),
        component_id="d8a47665-90c2-4f42-9cf1-7e9b3516ef55",
        pin_ref=PinRef("DD1", "2"), physical_number="2", pin_name="VCC",
        electrical_role=role, pin_function="general", polarity="none",
        net_identity=net, wire_segment_id=None, wire_end=None,
    )


@pytest.mark.parametrize(("role", "reason"), [
    ("NC", "NC_CONTACT_FORBIDDEN"),
    ("NO_CONNECT", "NC_CONTACT_FORBIDDEN"),
    ("UNSPECIFIED", "ELECTRICAL_ROLE_UNVERIFIED"),
    ("POWER_INPUT", "POWER_POLICY_REVIEW_REQUIRED"),
    ("POWER_OUTPUT", "POWER_POLICY_REVIEW_REQUIRED"),
    ("BIDIRECTIONAL", "BIDIRECTIONAL_POLICY_REVIEW_REQUIRED"),
])
def test_explicit_electrical_role_blocks_without_peer_approval(role, reason):
    source = _target("s", "PASSIVE")
    candidate = _target("t", role)
    assert _candidate_reason(source, candidate) == (False, reason)
    assert _candidate_reason(None, candidate)[0] is False


@pytest.mark.parametrize("role", ("PASSIVE", "INPUT", "OUTPUT"))
def test_passive_and_directional_roles_are_only_provisional(role):
    source = _target("s", "PASSIVE")
    candidate = _target("t", role)
    assert _candidate_reason(source, candidate) == (True, "PROVISIONAL_PREVIEW_ONLY")


def test_same_printed_vcc_name_never_merges_distinct_net_uuids():
    pins = (PinRef("DD1", "2"),)
    net1 = NetIdentity("ea01e706-fbd3-40a8-801a-af3acb132930", "VCC", pins)
    net2 = NetIdentity("4b7c5e33-b129-4f70-aee0-68c174f2868f", "VCC", pins)
    assert _candidate_reason(
        _target("s", "POWER_INPUT", net1),
        _target("t", "PASSIVE", net2),
    ) == (False, "NET_MERGE_DENIED")
    # Also deny output vs output (even if both appear on an existing Net).
    assert _candidate_reason(
        _target("s", "OUTPUT", net1),
        _target("t", "OUTPUT", net1),
    ) == (False, "DRIVER_CONFLICT_REVIEW_REQUIRED")
    same = _candidate_reason(
        _target("s", "PASSIVE", net1),
        _target("t", "PASSIVE", net1),
    )
    assert same == (True, "ALREADY_SAME_NET_PREVIEW_ONLY")


def test_coincident_point_requires_disambiguation(tmp_path):
    service, snapshot, _ = _source(tmp_path)
    report = build_connection_targets(snapshot.project, service.catalog)
    assert report["target_count"] >= 32
    coincident = [t for t in report["targets"] if t["requires_disambiguation"]]
    assert coincident
    for target in coincident:
        assert len(target["coincident_target_ids"]) > 1
        assert target["target_id"] in target["coincident_target_ids"]
        assert target["connection_allowed"] is False


def test_source_policy_for_unknown_role_or_nc_is_failsafe():
    blocked_source = _target("s", "NC")
    destination = _target("t", "PASSIVE")
    assert _candidate_reason(blocked_source, destination) == (
        False, "SOURCE_NC_CONTACT_FORBIDDEN",
    )
    assert _candidate_reason(
        replace(blocked_source, electrical_role="UNSPECIFIED"), destination,
    ) == (False, "SOURCE_ELECTRICAL_ROLE_UNVERIFIED")
