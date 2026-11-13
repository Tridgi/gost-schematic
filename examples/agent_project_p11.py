"""Reproducible P1.1 agent-style E3 composition with *real* catalog and routing.

This is a trusted Python API scenario (NOT a writable MCP or Codex execution).
It places components from installed physical definitions, detects and fixes an
UNCONNECTED part's keepout overlap BEFORE committing a project, uses the
reviewed two-PinRef router, persists through ProjectService, cold-opens in a
fresh interpreter, compares engineering data, and returns SVG/PNG SHA evidence.

Run:
  python -m examples.agent_project_p11 --workspace output/agent-project-p11
"""
import argparse
import builtins
import json
import subprocess
import sys
import uuid
from dataclasses import replace
from pathlib import Path

from gost_schematic.agent_project import CatalogResolver, ProjectService
from gost_schematic.agent_project.evidence import model_manifest
from gost_schematic.core.geometry import Point
from gost_schematic.engines.routing.two_pin_sheet import route_circuit_two_pins
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef


def _keepout(component: ComponentInstance, catalog: CatalogResolver):
    _, symbol = catalog.resolve(component.part_id)
    return component.transform.box(symbol.body_keepout).translated(component.origin)


def prepare_circuit(catalog: CatalogResolver):
    """Use only physically proven native parts and a two-contact named Net."""
    r1 = ComponentInstance("R1", "resistor.fixed", Point(20_000, 20_000))
    r2 = ComponentInstance("R2", "resistor.fixed", Point(60_000, 20_000))
    # Deliberately unsafe initial placement: capacitor overlaps R2's body.
    original_c1 = ComponentInstance("C1", "capacitor.fixed", Point(60_000, 20_000))
    if not _keepout(r2, catalog).overlaps(_keepout(original_c1, catalog)):
        raise AssertionError("Experimental overlap must be independently detected")
    # C1 has NO PinRef in any Net: correcting its pose cannot detach a wire.
    relocated_c1 = replace(original_c1, origin=Point(60_000, 50_000))
    if any(_keepout(c, catalog).overlaps(_keepout(relocated_c1, catalog))
           for c in (r1, r2)):
        raise AssertionError("Replacement layout still violates component keepouts")
    net = Net("SIGNAL", (PinRef("R1", "2"), PinRef("R2", "1")))
    circuit = Circuit((r1, r2, relocated_c1), (net,))
    # Actual physical data / PartDefinition are the routing authority.
    parts = {}
    symbols = {}
    for comp in circuit.components:
        part, symbol = catalog.resolve(comp.part_id)
        parts[part.identifier] = part
        symbols[symbol.identifier] = symbol
    route = route_circuit_two_pins(
        circuit, parts, symbols, PinRef("R1", "2"), PinRef("R2", "1"),
        net_name="SIGNAL", stroke_um=300,
    )
    if not route.ok:
        raise AssertionError("Existing safe router rejected route: "
                             + ", ".join(d.code for d in route.diagnostics))
    return circuit, route.external_graph("SIGNAL"), {
        "before_overlap": True,
        "after_overlap": False,
        "moved_unconnected": "C1",
        "before_origin_um": [60_000, 20_000],
        "after_origin_um": [60_000, 50_000],
        "route_points_um": [[p.x, p.y] for p in route.points],
        "repair_stage": "BEFORE_INITIAL_IMPORT_NOT_SAVED_PROJECT_EDIT",
    }


# The child does not import this or another examples/ fixture, and does not
# mutate the source project. No retry from source Python can disguise a broken
# persistence layer.
COLD_OPEN_SCRIPT = """
import builtins, json, sys
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == 'examples' or name.startswith('examples.'):
        raise AssertionError('Cold-open attempted to import an examples fixture')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
from pathlib import Path
from gost_schematic.agent_project import ProjectService
service = ProjectService.for_workspace(Path(sys.argv[1]))
snapshot = service.open_project(sys.argv[2], sys.argv[3])
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.agent_project.evidence import model_manifest
manifest = model_manifest(snapshot.project, CatalogResolver())
report = service.validate_project(sys.argv[2], sys.argv[3])
image = service.render_project(sys.argv[2], sys.argv[3])
print(json.dumps({'manifest': manifest,
                  'diagnostics': report,
                  'image': image.metadata}, sort_keys=True))
"""


def run(workspace: Path, project_id: str, idempotency_key: str) -> dict:
    catalog = CatalogResolver()
    circuit, graph, correction = prepare_circuit(catalog)
    service = ProjectService.for_workspace(workspace)
    snapshot = service.import_circuit(
        circuit, graph, project_id=project_id, idempotency_key=idempotency_key,
        title="Agent composition of real catalog parts",
        strokes_um=(300,) * len(graph.segments),
        source_tag="trusted-python-agent-layout-demo",
    )
    before_manifest = model_manifest(snapshot.project, catalog)
    # Controlled artifact export, no arbitrary file chosen by an MCP caller.
    view = service.export_project_view(project_id, snapshot.project.revision)
    observed = subprocess.run(
        [sys.executable, "-c", COLD_OPEN_SCRIPT, str(workspace.resolve()),
         project_id, snapshot.project.revision],
        capture_output=True, text=True, check=True, timeout=35,
    )
    cold = json.loads(observed.stdout)
    if cold["manifest"] != before_manifest:
        raise AssertionError("Cold project physical model/geometry changed")
    if cold["diagnostics"]["project_revision"] != snapshot.project.revision:
        raise AssertionError("Cold diagnostics do not belong to original revision")
    if cold["image"]["png_sha256"] != view["png_sha256"]:
        raise AssertionError("Cold rasterization changed for identical source")
    if cold["image"]["view_svg_sha256"] != view["view_svg_sha256"]:
        raise AssertionError("Cold SVG changed for identical source")
    if any(d["severity"] == "error" for d in cold["diagnostics"]["diagnostics"]):
        raise AssertionError("Independent electrical ERC rejected the stored model")
    return {
        "kind": "E3", "work_mode": "trusted_python_api_not_MCP_write",
        "project_id": project_id, "revision_sha256": snapshot.project.revision,
        "generation": snapshot.head.generation,
        "source_and_cold_model_match": True,
        "geometry_repair": correction,
        "cold_diagnostics": cold["diagnostics"],
        "source_model": before_manifest,
        "overview_image": view,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--idempotency-key", default=None)
    args = parser.parse_args()
    data = run(
        args.workspace, args.project_id or str(uuid.uuid4()),
        args.idempotency_key or str(uuid.uuid4()),
    )
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
