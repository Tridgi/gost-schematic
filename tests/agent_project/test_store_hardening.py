"""Atomic create-if-absent and idempotency/durability negative gates."""
import threading
import uuid
from pathlib import Path

import pytest

from gost_schematic.agent_project import ProjectError, ProjectService
from gost_schematic.agent_project import repository as repo_module
from gost_schematic.agent_project.catalog import canonical_bytes, digest
from gost_schematic.agent_project.contracts import DOMAIN, SchematicProject
from gost_schematic.agent_project.trusted_import import import_six_part


def test_two_competing_initial_creates_only_one_published_head(tmp_path: Path):
    same_project = "33333333-3333-4333-8333-333333333333"
    outputs = []
    barrier = threading.Barrier(2)

    def worker(request_id: str) -> None:
        try:
            barrier.wait(timeout=5)
            snap = import_six_part(tmp_path, project_id=same_project,
                                   idempotency_key=request_id)
            outputs.append(("ok", snap.head))
        except (ProjectError, OSError) as exc:
            outputs.append(("blocked", exc))

    workers = [threading.Thread(target=worker, args=(str(uuid.uuid4()),))
               for _ in range(2)]
    for worker_thread in workers:
        worker_thread.start()
    for worker_thread in workers:
        worker_thread.join(timeout=15)
    assert len(outputs) == 2
    assert sorted(item[0] for item in outputs) == ["blocked", "ok"]
    snapshot = ProjectService.for_workspace(tmp_path).open_project(same_project)
    assert snapshot.head.generation == 1
    assert len(snapshot.project.graph.segments) == 16
    assert not any(tmp_path.joinpath("projects").glob(".stage-*"))


def test_staging_failure_does_not_publish_partial_project(tmp_path: Path, monkeypatch):
    def break_rename(_old, _new):
        raise OSError("simulated durable filesystem failure")

    monkeypatch.setattr(repo_module.os, "rename", break_rename)
    project_id = "44444444-4444-4444-8444-444444444444"
    with pytest.raises(OSError, match="simulated"):
        import_six_part(tmp_path, project_id=project_id,
                        idempotency_key="55555555-5555-4555-8555-555555555555")
    assert not (tmp_path / "projects" / project_id).exists()
    assert not any(tmp_path.joinpath("projects").glob(".stage-*"))


def test_symlinked_project_root_refused(tmp_path: Path):
    external = tmp_path / "other"
    external.mkdir()
    trusted = tmp_path / "allowed"
    try:
        trusted.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Windows account is not permitted to create symlinks")
    with pytest.raises(ProjectError, match="WORKSPACE_DENIED"):
        ProjectService.for_workspace(trusted)


def test_canonical_hash_has_domain_separator_and_rejects_extra_json():
    from examples.review_end_to_end_circuit import scenarios
    from gost_schematic.agent_project.catalog import CatalogResolver

    case = scenarios()[0]
    project = SchematicProject.from_circuit(
        "66666666-6666-4666-8666-666666666666", "Canonical model",
        case.circuit, case.graph, CatalogResolver(), strokes_um=(300,) * 16,
        scenario=case.scenario,
    )
    assert project.revision == digest(DOMAIN + canonical_bytes(project.to_record()))
    assert project.revision != digest(canonical_bytes(project.to_record()))
    modified = project.to_record()
    modified["unauthorized_raw_patch"] = {"nets": []}
    with pytest.raises(ProjectError, match="SCHEMA_UNSUPPORTED"):
        SchematicProject.from_record(modified, CatalogResolver())
