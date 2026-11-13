"""Scoped immutable read/store boundary for the first controlled E3 import.

P1.1 has only exclusive project creation; no arbitrary JSON edits or HEAD updates.
Publication is one same-volume directory rename after durable staging.
"""
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .catalog import ProjectError, canonical_bytes, digest
from .contracts import DOMAIN, SchematicProject, project_uuid


@dataclass(frozen=True, slots=True)
class ProjectHead:
    project_id: str
    revision: str
    generation: int


class ProjectRepository(Protocol):
    def create_initial(self, project: SchematicProject, idempotency_key: str) -> ProjectHead: ...
    def read(self, project_id: str, revision: str | None = None
             ) -> tuple[ProjectHead, dict]: ...


def _write_sync(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 3_000_000:
        raise ProjectError("STORAGE_CORRUPT", "Missing, redirected or oversized file")
    try:
        document = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectError("STORAGE_CORRUPT", "Invalid persisted JSON") from exc
    if type(document) is not dict:
        raise ProjectError("STORAGE_CORRUPT", "Expected a persisted object")
    return document


class LocalProjectStore:
    """Only UUID-derived filenames under a trusted root; no caller filesystem path."""

    def __init__(self, trusted_root: Path):
        if trusted_root.is_symlink():
            raise ProjectError("WORKSPACE_DENIED", "Workspace root cannot be a symlink")
        self.root = trusted_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ProjectError("WORKSPACE_DENIED", "Invalid workspace directory")
        self.projects = self.root / "projects"
        self.projects.mkdir(exist_ok=True)
        if self.projects.is_symlink():
            raise ProjectError("WORKSPACE_DENIED", "Projects directory is redirected")

    def _directory(self, project_id: str) -> Path:
        project_uuid(project_id)
        path = self.projects / project_id
        if path.is_symlink() or not path.resolve().is_relative_to(self.projects.resolve()):
            raise ProjectError("WORKSPACE_DENIED", "Project escapes trusted root")
        return path

    @staticmethod
    def _revision_path(folder: Path, sha: str) -> Path:
        if type(sha) is not str or len(sha) != 64 or any(
            letter not in "0123456789abcdef" for letter in sha
        ):
            raise ProjectError("REVISION_NOT_FOUND", "Invalid SHA256 revision")
        container = folder / "revisions"
        if container.is_symlink():
            raise ProjectError("WORKSPACE_DENIED", "Revision directory is redirected")
        return container / (sha + ".gseproj")

    def read(self, project_id: str, revision: str | None = None
             ) -> tuple[ProjectHead, dict]:
        directory = self._directory(project_id)
        if not directory.is_dir():
            raise ProjectError("PROJECT_NOT_FOUND", project_id)
        head = _read_json(directory / "HEAD.json")
        if set(head) != {"project_id", "revision", "generation",
                         "idempotency_key", "request_sha256"} or (
            head["project_id"] != project_id or type(head["generation"]) is not int
            or head["generation"] != 1
        ):
            raise ProjectError("STORAGE_CORRUPT", "Invalid HEAD record")
        selected = revision if revision is not None else head["revision"]
        source = self._revision_path(directory, selected)
        content = source.read_bytes() if source.is_file() and not source.is_symlink() else None
        if content is None or len(content) > 3_000_000:
            raise ProjectError("REVISION_NOT_FOUND", "Missing immutable revision")
        if digest(DOMAIN + content) != selected:
            raise ProjectError("STORAGE_CORRUPT", "Revision bytes do not match SHA")
        try:
            record = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProjectError("STORAGE_CORRUPT", "Invalid immutable JSON") from exc
        if type(record) is not dict or canonical_bytes(record) != content:
            raise ProjectError("STORAGE_CORRUPT", "Noncanonical persisted project")
        if record.get("project_id") != project_id:
            raise ProjectError("STORAGE_CORRUPT", "Project ID mismatch")
        current = ProjectHead(project_id, head["revision"], head["generation"])
        return current, record

    def create_initial(self, project: SchematicProject, idempotency_key: str) -> ProjectHead:
        project_uuid(idempotency_key)
        directory = self._directory(project.project_id)
        payload = project.canonical
        revision = project.revision
        request_sha = digest(canonical_bytes({"revision": revision, "project": project.project_id}))
        if directory.exists():
            self.read(project.project_id)
            existing = _read_json(directory / "HEAD.json")
            if existing["idempotency_key"] == idempotency_key:
                if existing["request_sha256"] == request_sha:
                    return ProjectHead(project.project_id, existing["revision"], 1)
                raise ProjectError("IDEMPOTENCY_CONFLICT", "Key reused for different data")
            raise ProjectError("PROJECT_ALREADY_EXISTS", project.project_id)
        stage = self.projects / (".stage-" + str(uuid.uuid4()))
        stage.mkdir(mode=0o700)
        try:
            (stage / "revisions").mkdir()
            _write_sync(self._revision_path(stage, revision), payload)
            head = {
                "project_id": project.project_id, "revision": revision,
                "generation": 1, "idempotency_key": idempotency_key,
                "request_sha256": request_sha,
            }
            _write_sync(stage / "HEAD.json", canonical_bytes(head))
            # No incomplete project is published: new nonexisting directory only.
            if directory.exists() or directory.is_symlink():
                raise ProjectError("PROJECT_ALREADY_EXISTS", project.project_id)
            os.rename(stage, directory)
        except Exception:
            if stage.exists():
                shutil.rmtree(stage)
            raise
        return ProjectHead(project.project_id, revision, 1)
