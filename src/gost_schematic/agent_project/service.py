"""Typed ProjectService P1.1; controlled import, immutable read, real ERC and images.

No component mutations or arbitrary JSON writes are exposed at this gate.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gost_schematic.model.circuit import Circuit
from gost_schematic.model.potentials import PotentialScenario
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    validate_external_wires,
)

from .catalog import CatalogResolver, ProjectError
from .contracts import SchematicProject
from .repository import LocalProjectStore, ProjectHead, ProjectRepository
from .view import ProjectView, render


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    head: ProjectHead
    project: SchematicProject


class ProjectService:
    """Only in-process trusted import is writable in P1.1."""

    def __init__(self, repository: ProjectRepository, catalog: CatalogResolver | None = None):
        self.repository = repository
        self.catalog = catalog if catalog is not None else CatalogResolver()

    @classmethod
    def for_workspace(cls, trusted_root: Path) -> "ProjectService":
        return cls(LocalProjectStore(trusted_root))

    def import_circuit(
        self, circuit: Circuit, graph: ExternalWireGraph, *,
        project_id: str, idempotency_key: str, title: str,
        strokes_um: tuple[int, ...], scenario: PotentialScenario | None = None,
        source_tag: str = "trusted-inprocess-e3",
    ) -> ProjectSnapshot:
        """Trusted in-process use only; not bound as a public MCP tool."""
        project = SchematicProject.from_circuit(
            project_id, title, circuit, graph, self.catalog,
            strokes_um=strokes_um, scenario=scenario, source_tag=source_tag,
        )
        report = self._report(project, generation=1)
        if any(item["severity"] == "error" for item in report["diagnostics"]):
            raise ProjectError("VALIDATION_REJECTED", "Source Circuit/Graph has ERC errors")
        head = self.repository.create_initial(project, idempotency_key)
        return ProjectSnapshot(head, project)

    def open_project(self, project_id: str, revision: str | None = None
                     ) -> ProjectSnapshot:
        head, record = self.repository.read(project_id, revision)
        project = SchematicProject.from_record(record, self.catalog)
        requested = revision if revision is not None else head.revision
        if project.revision != requested:
            raise ProjectError("STORAGE_CORRUPT", "Loaded project identity disagrees with revision")
        if any(item["severity"] == "error" for item in self._report(
            project, generation=head.generation
        )["diagnostics"]):
            raise ProjectError("VALIDATION_REJECTED", "Stored model ERC failed")
        return ProjectSnapshot(head, project)

    def get_snapshot(self, project_id: str, revision: str | None = None
                     ) -> ProjectSnapshot:
        return self.open_project(project_id, revision)

    def validate_project(self, project_id: str, revision: str | None = None
                         ) -> dict[str, Any]:
        snapshot = self.open_project(project_id, revision)
        return self._report(snapshot.project, snapshot.head.generation)

    @staticmethod
    def _summary(snapshot: ProjectSnapshot) -> dict[str, Any]:
        project = snapshot.project
        return {
            "schema_version": 1,
            "project_kind": "E3",
            "project_id": project.project_id,
            "project_revision": project.revision,
            "head_revision": snapshot.head.revision,
            "generation": snapshot.head.generation,
            "title": project.title,
            "component_count": len(project.circuit.components),
            "net_count": len(project.circuit.nets),
            "wire_segment_count": len(project.graph.segments),
            "junction_count": len(project.graph.junctions),
            "catalog_part_count": len(project.catalog_lock),
            "read_only": True,
        }

    def open_project_info(self, project_id: str,
                          revision: str | None = None) -> dict[str, Any]:
        """Typed summary; actual model is loaded and independently validated."""
        return self._summary(self.open_project(project_id, revision))

    def list_projects(self, project_ids: tuple[str, ...]) -> dict[str, Any]:
        """Discover ONLY operator-allowed UUIDs, never scan workspace files."""
        if not isinstance(project_ids, tuple) or len(project_ids) > 32:
            raise ProjectError("PROJECT_ACCESS_DENIED", "Invalid bounded project scope")
        projects: list[dict[str, Any]] = []
        for project_id in sorted(set(project_ids)):
            try:
                projects.append(self.open_project_info(project_id))
            except ProjectError as exc:
                if exc.code != "PROJECT_NOT_FOUND":
                    raise
        return {"schema_version": 1, "project_kind": "E3",
                "read_only": True, "count": len(projects), "projects": projects}

    def describe_project(self, project_id: str,
                         revision: str | None = None) -> dict[str, Any]:
        """Exact original model, physical contacts, actual net/wire geometry."""
        from .evidence import model_manifest

        snapshot = self.open_project(project_id, revision)
        manifest = model_manifest(snapshot.project, self.catalog)
        return {**self._summary(snapshot), "model": manifest}

    def get_connection_targets(
        self, project_id: str, revision: str, *,
        source_target_id: str | None = None,
    ) -> dict[str, Any]:
        """Read authentic PinRefs and authored conductor endpoints by exact SHA.

        Source-pair results are only provisional for editor visualization:
        neither a safe physical route nor transaction authorization exists.
        """
        from .connection_targets import build_connection_targets

        if revision is None:
            raise ProjectError("REVISION_REQUIRED", "Editor targets need immutable SHA")
        snapshot = self.open_project(project_id, revision)
        result = build_connection_targets(
            snapshot.project, self.catalog,
            source_target_id=source_target_id,
        )
        return {**result, "generation": snapshot.head.generation}

    def render_project(
        self, project_id: str, revision: str, *, mode: str = "clean",
        reference: str | None = None, target_dpi: int = 500,
    ) -> ProjectView:
        if revision is None:
            raise ProjectError("REVISION_REQUIRED", "Render must use an immutable SHA")
        snapshot = self.open_project(project_id, revision)
        visual = render(snapshot.project, self.catalog, mode=mode,
                        reference=reference, target_dpi=target_dpi)
        return ProjectView(visual.svg, visual.png, {
            **visual.metadata, "generation": snapshot.head.generation,
            "diagnostics_revision": snapshot.project.revision,
        })

    def export_project_view(
        self, project_id: str, revision: str, *, mode: str = "clean",
        reference: str | None = None, target_dpi: int = 500,
    ) -> dict[str, Any]:
        """Trusted local export; no user-selected filesystem path.

        The saved SVG/PNG are derived artifacts of the exact immutable
        revision, never an alternative source of electrical topology.
        No general MCP write endpoint exposes this operation.
        """
        view = self.render_project(
            project_id, revision, mode=mode, reference=reference,
            target_dpi=target_dpi,
        )
        artifacts = self.repository.write_view(
            project_id, revision, view.metadata["view_id"], view.svg, view.png,
        )
        return {**view.metadata, "artifacts": artifacts}

    def _report(self, project: SchematicProject, generation: int) -> dict[str, Any]:
        parts, symbols = self.catalog.verify(list(project.catalog_lock))
        diagnostics = [
            {"code": d.code, "severity": d.severity.value, "source": label,
             "subject": d.subject, "message": d.message}
            for label, found in (
                ("ExternalWireGraph", validate_external_wires(
                    project.circuit, project.graph, parts, symbols)),
                ("Circuit", validate_circuit(
                    project.circuit, parts, symbols, scenario=project.scenario)),
            )
            for d in found
        ]
        diagnostics.sort(key=lambda d: (
            d["source"], d["code"], str(d["subject"]), d["message"]
        ))
        return {
            "schema_version": 1, "project_id": project.project_id,
            "project_revision": project.revision, "project_kind": "E3",
            "generation": generation,
            "component_count": len(project.circuit.components),
            "net_count": len(project.circuit.nets),
            "wire_segment_count": len(project.graph.segments),
            "junction_count": len(project.graph.junctions),
            "status": ("ERROR" if any(d["severity"] == "error" for d in diagnostics)
                       else "WARN" if diagnostics else "PASS"),
            "diagnostics": diagnostics,
            "labels_check_status": "NOT_IMPLEMENTED",
            "normative_status": "DRAFT / NOT ESKD APPROVED",
        }
