"""Cycle 7 P1.1: real agent-like composition, safe artifact export and strict inputs."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from examples.agent_project_p11 import prepare_circuit, run
from gost_schematic.agent_project import CatalogResolver, ProjectError, ProjectService
from gost_schematic.agent_project.repository import _strict_json
from gost_schematic.agent_project.trusted_import import import_six_part

PID = "b7bc54bd-dd27-4c09-890d-ef7305e61c20"
KEY = "5ad80970-d291-4fbc-a741-896f52d93f65"


def test_agent_like_project_is_true_circuit_safe_route_and_cold_process(tmp_path: Path):
    result = run(tmp_path / "trusted", PID, KEY)
    assert result["kind"] == "E3"
    assert result["source_and_cold_model_match"]
    assert result["geometry_repair"] == {
        **{k: v for k, v in result["geometry_repair"].items()
           if k not in ("before_overlap", "after_overlap")},
        "before_overlap": True, "after_overlap": False,
    }
    assert result["geometry_repair"]["repair_stage"].startswith("BEFORE_INITIAL_IMPORT")
    assert result["cold_diagnostics"]["status"] in ("PASS", "WARN")
    assert not any(d["severity"] == "error" for d in result["cold_diagnostics"]["diagnostics"])
    authoritative = result["source_model"]["canonical_typed_project"]
    assert len(authoritative["components"]) == 3
    assert len(authoritative["nets"]) == 1
    assert len(authoritative["wires"]) >= 1
    assert len(authoritative["junctions"]) == 0
    assert authoritative["nets"][0]["members"] == [
        {"component_id": authoritative["components"][0]["id"], "pin": "2"},
        {"component_id": authoritative["components"][1]["id"], "pin": "1"},
    ]
    assert all(wire["net_id"] == authoritative["nets"][0]["id"]
               for wire in authoritative["wires"])
    assert authoritative["components"][2]["origin_um"] == [60000, 50000]
    art = result["overview_image"]["artifacts"]
    assert Path(art["svg"]).is_file()
    assert Path(art["png"]).is_file()
    assert hashlib.sha256(Path(art["svg"]).read_bytes()).hexdigest() == (
        result["overview_image"]["view_svg_sha256"]
    )
    assert hashlib.sha256(Path(art["png"]).read_bytes()).hexdigest() == (
        result["overview_image"]["png_sha256"]
    )
    assert Path(art["png"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result["overview_image"]["project_revision"] == result["revision_sha256"]


def test_agent_layout_pre_import_is_non_mutating():
    catalog = CatalogResolver()
    first, original_graph, info = prepare_circuit(catalog)
    second, another_graph, second_info = prepare_circuit(catalog)
    assert first == second and original_graph == another_graph
    assert info == second_info
    assert first.nets[0].members[0].reference == "R1"
    assert first.nets[0].members[1].reference == "R2"
    assert all(ref.reference != "C1" for net in first.nets for ref in net.members)


@pytest.mark.parametrize("bad", [
    b'{"a":1,"a":2}', b'{"nested":{"x":1,"x":3}}',
    b'{"x":1.0}', b'{"x":NaN}', b'{"x":Infinity}',
    b'{"x":-Infinity}', b'[1,2]', b'{"x":1} trailing',
])
def test_strict_json_loader_refuses_ambiguous_or_noninteger_data(bad: bytes):
    with pytest.raises(ProjectError, match="STORAGE_CORRUPT"):
        _strict_json(bad)


def test_server_controls_export_path_and_repeated_view_bytes(tmp_path: Path):
    workspace = tmp_path / "workspace"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    service = ProjectService.for_workspace(workspace)
    first = service.export_project_view(PID, snap.head.revision, reference="C3")
    second = service.export_project_view(PID, snap.head.revision, reference="C3")
    assert first == second
    root = workspace / "artifacts" / PID / snap.head.revision / first["view_id"]
    assert Path(first["artifacts"]["png"]) == root / "view.png"
    assert Path(first["artifacts"]["svg"]) == root / "view.svg"
    assert len(list(root.iterdir())) == 2
    assert not any(root.parent.glob(".stage-*"))
    assert service.open_project(PID).head.generation == 1


def test_cli_revision_bound_exports_avoid_arbitrary_path(tmp_path: Path):
    workspace = tmp_path / "workspace"
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    proc = subprocess.run([
        sys.executable, "-m", "gost_schematic.agent_project",
        "--workspace", str(workspace),
        "render", PID, snap.head.revision, "--component", "C3",
    ], check=True, capture_output=True, text=True, timeout=30)
    data = json.loads(proc.stdout)
    assert data["project_revision"] == snap.head.revision
    assert data["diagnostics_revision"] == snap.head.revision
    assert set(data["artifacts"]) == {"svg", "png"}
    assert Path(data["artifacts"]["svg"]).is_file()
    assert Path(data["artifacts"]["png"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_symlinked_artifact_root_fails_closed(tmp_path: Path):
    workspace = tmp_path / "allowed"
    other = tmp_path / "elsewhere"
    other.mkdir()
    snap = import_six_part(workspace, project_id=PID, idempotency_key=KEY)
    redirect = workspace / "artifacts"
    try:
        redirect.symlink_to(other, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable")
    with pytest.raises(ProjectError, match="WORKSPACE_DENIED"):
        ProjectService.for_workspace(workspace).export_project_view(
            PID, snap.head.revision,
        )
    assert list(other.iterdir()) == []


def test_p11_fails_closed_on_uninstalled_cycle7_draft_vendor_pinout():
    # PR #97 is a separate nonmerged draft; do not fabricate a vendor part ID.
    with pytest.raises(ProjectError, match="CATALOG_PART_MISSING"):
        CatalogResolver().resolve("TEST_IC_DIGITAL_64")
