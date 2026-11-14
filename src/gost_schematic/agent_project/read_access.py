"""Explicit host-authorized read capability for persisted E3 projects.

The stdio MCP transport has no independent per-tool user login: it inherits
the local host operator's OS identity. Therefore saved-project access is
disabled by default, and must be independently scoped to an explicit absolute
workspace and a bounded allowlist of project UUIDs before any files are read.

This module never exposes a user-selected filesystem path or write capability.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from .catalog import ProjectError
from .contracts import project_uuid
from .service import ProjectService

_MAX_PROJECTS = 32


def _redirected(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


@dataclass(frozen=True, slots=True)
class ReadOnlyProjectAccess:
    service: ProjectService
    allowed_ids: tuple[str, ...]

    @classmethod
    def from_environment(cls) -> "ReadOnlyProjectAccess":
        if os.environ.get("GSE_P11_READONLY_ENABLED") != "1":
            raise ProjectError("PROJECT_ACCESS_DENIED", "Saved project tools disabled by host")
        path_str = os.environ.get("GSE_P11_WORKSPACE", "")
        allowed_str = os.environ.get("GSE_P11_ALLOWED_PROJECT_IDS", "")
        if not path_str or not allowed_str:
            raise ProjectError("PROJECT_ACCESS_DENIED", "Workspace and project scope required")
        path = Path(path_str)
        if not path.is_absolute() or not path.is_dir():
            raise ProjectError("PROJECT_ACCESS_DENIED", "Host workspace unavailable")
        # Reject existing redirected ancestors as well as NTFS junctions.
        if any(_redirected(part) for part in (path, *path.parents)):
            raise ProjectError("PROJECT_ACCESS_DENIED", "Redirected workspace forbidden")
        if not (path / "projects").is_dir() or _redirected(path / "projects"):
            raise ProjectError("PROJECT_ACCESS_DENIED", "No pre-existing project store")
        identifiers = [item.strip() for item in allowed_str.split(",")]
        if (len(identifiers) > _MAX_PROJECTS or not all(identifiers)
                or len(set(identifiers)) != len(identifiers)):
            raise ProjectError("PROJECT_ACCESS_DENIED", "Invalid project allowlist")
        try:
            allowed = tuple(sorted(project_uuid(item) for item in identifiers))
        except ProjectError as exc:
            raise ProjectError("PROJECT_ACCESS_DENIED", "Noncanonical project UUID") from exc
        return cls(ProjectService.for_workspace(path), allowed)

    def require(self, project_id: str) -> None:
        try:
            project_uuid(project_id)
        except ProjectError as exc:
            raise ProjectError("PROJECT_ACCESS_DENIED", "Invalid project selector") from exc
        if project_id not in self.allowed_ids:
            # Do not reveal whether a foreign project exists.
            raise ProjectError("PROJECT_ACCESS_DENIED", "Project is not authorized")
