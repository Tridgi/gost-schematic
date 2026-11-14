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
    def write_view(self, project_id: str, revision: str, view_id: str,
                   svg: str, png: bytes) -> dict[str, str]: ...


def _is_redirect(path: Path) -> bool:
    # Windows NTFS directory junctions are not always reported as symlinks.
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _safe_mkdir(path: Path) -> None:
    if _is_redirect(path):
        raise ProjectError("WORKSPACE_DENIED", "Redirected storage directory")
    path.mkdir(exist_ok=True)
    if _is_redirect(path) or not path.is_dir():
        raise ProjectError("WORKSPACE_DENIED", "Invalid storage directory")


def _strict_json(blob: bytes) -> dict:
    """Reject duplicate keys, floating numbers and JSON extensions before schema validation."""
    def pairs(items: list[tuple[str, object]]) -> dict:
        record = {}
        for key, value in items:
            if key in record:
                raise ProjectError("STORAGE_CORRUPT", f"Duplicate JSON key {key!r}")
            record[key] = value
        return record

    def reject_number(value: str) -> None:
        raise ProjectError("STORAGE_CORRUPT", f"Non-integer JSON number {value!r}")

    try:
        document = json.loads(
            blob.decode("utf-8"), object_pairs_hook=pairs,
            parse_float=reject_number, parse_constant=reject_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectError("STORAGE_CORRUPT", "Invalid persisted JSON") from exc
    if type(document) is not dict:
        raise ProjectError("STORAGE_CORRUPT", "Expected a persisted object")
    return document


def _write_sync(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _read_limited(path: Path, limit: int) -> bytes:
    if _is_redirect(path) or not path.is_file() or path.stat().st_size > limit:
        raise ProjectError("STORAGE_CORRUPT", "Invalid persisted file or redirect")
    return path.read_bytes()


def _read_json(path: Path) -> dict:
    if _is_redirect(path) or not path.is_file() or path.stat().st_size > 3_000_000:
        raise ProjectError("STORAGE_CORRUPT", "Missing, redirected or oversized file")
    return _strict_json(path.read_bytes())


class LocalProjectStore:
    """Only UUID-derived filenames under a trusted root; no caller filesystem path."""

    def __init__(self, trusted_root: Path):
        if _is_redirect(trusted_root):
            raise ProjectError("WORKSPACE_DENIED", "Workspace root cannot be a symlink")
        self.root = trusted_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if _is_redirect(self.root) or not self.root.is_dir():
            raise ProjectError("WORKSPACE_DENIED", "Invalid workspace directory")
        self.projects = self.root / "projects"
        self.projects.mkdir(exist_ok=True)
        if _is_redirect(self.projects):
            raise ProjectError("WORKSPACE_DENIED", "Projects directory is redirected")

    def _directory(self, project_id: str) -> Path:
        project_uuid(project_id)
        if _is_redirect(self.root) or _is_redirect(self.projects):
            raise ProjectError("WORKSPACE_DENIED", "Workspace was redirected after initialization")
        path = self.projects / project_id
        if _is_redirect(path) or not path.resolve().is_relative_to(self.projects):
            raise ProjectError("WORKSPACE_DENIED", "Project escapes trusted root")
        return path

    @staticmethod
    def _revision_path(folder: Path, sha: str) -> Path:
        if type(sha) is not str or len(sha) != 64 or any(
            letter not in "0123456789abcdef" for letter in sha
        ):
            raise ProjectError("REVISION_NOT_FOUND", "Invalid SHA256 revision")
        container = folder / "revisions"
        if _is_redirect(container):
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
        # The HEAD itself is untrusted bytes: validate its SHA and request identity.
        self._revision_path(directory, head["revision"])
        project_uuid(head["idempotency_key"])
        self._revision_path(directory, head["request_sha256"])
        selected = revision if revision is not None else head["revision"]
        source = self._revision_path(directory, selected)
        if _is_redirect(source) or not source.is_file():
            raise ProjectError("REVISION_NOT_FOUND", "Missing immutable revision")
        if source.stat().st_size > 3_000_000:
            raise ProjectError("STORAGE_CORRUPT", "Oversized immutable revision")
        content = source.read_bytes()
        if digest(DOMAIN + content) != selected:
            raise ProjectError("STORAGE_CORRUPT", "Revision bytes do not match SHA")
        record = _strict_json(content)
        if canonical_bytes(record) != content:
            raise ProjectError("STORAGE_CORRUPT", "Noncanonical persisted project")
        if record.get("project_id") != project_id:
            raise ProjectError("STORAGE_CORRUPT", "Project ID mismatch")
        current = ProjectHead(project_id, head["revision"], head["generation"])
        return current, record

    def write_view(self, project_id: str, revision: str, view_id: str,
                   svg: str, png: bytes) -> dict[str, str]:
        """Publish an immutable pair of derived visual files via the trusted store.

        The view is non-authoritative; only the caller's typed ProjectService
        can request this operation. Never accept an arbitrary output path.
        """
        self.read(project_id, revision)
        if type(view_id) is not str or len(view_id) != 24 or any(
            char not in "0123456789abcdef" for char in view_id
        ):
            raise ProjectError("INVALID_VIEW_ID", "Expected a 24-character hex view ID")
        if not isinstance(svg, str) or not svg.startswith("<") or not isinstance(png, bytes):
            raise ProjectError("IMAGE_INVALID", "Expected genuine SVG and PNG bytes")
        if len(svg.encode("utf-8")) > 4_000_000 or len(png) > 8_000_000 or not (
            png.startswith(b"\x89PNG\r\n\x1a\n")
        ):
            raise ProjectError("IMAGE_INVALID", "Visual evidence exceeds bounds or PNG invalid")
        artifacts = self.root / "artifacts"
        _safe_mkdir(artifacts)
        for name in (project_id, revision):
            artifacts = artifacts / name
            _safe_mkdir(artifacts)
        final = artifacts / view_id
        if _is_redirect(final):
            raise ProjectError("WORKSPACE_DENIED", "Redirected view path")
        svg_bytes = svg.encode("utf-8")
        if final.exists():
            if (_read_limited(final / "view.svg", 4_000_000) != svg_bytes
                    or _read_limited(final / "view.png", 8_000_000) != png):
                raise ProjectError("ARTIFACT_CONFLICT", "Existing immutable view differs")
        else:
            stage = artifacts / (".stage-" + str(uuid.uuid4()))
            stage.mkdir(mode=0o700)
            try:
                _write_sync(stage / "view.svg", svg_bytes)
                _write_sync(stage / "view.png", png)
                if final.exists() or _is_redirect(final):
                    raise ProjectError("ARTIFACT_CONFLICT", "Concurrent view publication")
                os.rename(stage, final)
            except Exception:
                if stage.exists():
                    shutil.rmtree(stage)
                raise
        return {"svg": str(final / "view.svg"), "png": str(final / "view.png")}

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
