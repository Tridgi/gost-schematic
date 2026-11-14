"""Read-only AI decision boundary: exact catalog SHA locks and placement proposals.

No persisted modifications, routing, connected PinRef reassignment or approval of
GOST DRAFT symbols. ProjectService is authoritative for saved physical snapshots.
"""
import re
from typing import Any

from gost_schematic.core.geometry import Point, primitive_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import PinRef
from gost_schematic.model.obstacles import WireObstacle, wire_intersects_box
from gost_schematic.core.geometry import Line

from .catalog import CatalogResolver, ProjectError
from .contracts import SchematicProject
from .design_assistant import _bounds, catalog_card

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PART = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\Z")
_REF = re.compile(r"[A-Z][A-Z0-9]{0,15}\Z")


def require_api_version(value: int) -> None:
    """Disallow bool, 1.0, version strings, unknown response semantics."""
    if type(value) is not int or value != 1:
        raise ProjectError("API_VERSION_UNSUPPORTED", "Only typed API version 1 is implemented")


def require_sha(value: str, *, name: str) -> None:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise ProjectError("INVALID_CATALOG_SHA", f"{name} must be lowercase SHA256")


def select_physical_part(
    catalog: CatalogResolver, part_id: str, *,
    part_sha256: str, symbol_sha256: str, api_version: int = 1,
) -> dict[str, Any]:
    """Explicitly selected catalog candidate; no synonym, alias, or stale SHA."""
    require_api_version(api_version)
    if type(part_id) is not str or _PART.fullmatch(part_id) is None or len(part_id) > 80:
        raise ProjectError("INVALID_CATALOG_SELECTOR", "Exact installed physical part ID required")
    require_sha(part_sha256, name="part_sha256")
    require_sha(symbol_sha256, name="symbol_sha256")
    lock = catalog.lock(part_id)
    if lock["part_sha256"] != part_sha256 or lock["symbol_sha256"] != symbol_sha256:
        raise ProjectError("CATALOG_REVISION_MISMATCH", "Selected part/symbol changed")
    card = catalog_card(catalog, part_id)
    return {
        "schema_version": 1, "read_only": True, "selection_status": "EXACT_CATALOG_LOCK_MATCH",
        "selected_part_id": part_id,
        "part_sha256": lock["part_sha256"], "symbol_sha256": lock["symbol_sha256"],
        "symbol_revision": lock["symbol_revision"], "symbol_status": lock["symbol_status"],
        "physical_pin_templates": [
            {
                "number": p["number"], "name": p["name"],
                "electrical_role": p["electrical_role"], "polarity": p["polarity"],
                "function": p["function"], "local_anchor_um": p["symbol_anchor_um"],
                "is_instantiated_pin_ref": False, "pin_ref": None,
            } for p in card["physical_pin_refs"]
        ],
        "placement_requires_real_project_component": True,
        "d4_geometric_transforms": card["allowed_by_geometry_engine"],
        "normative_status": "NOT_APPROVED",
        "connection_authorized": False,
    }


def preview_placement(
    project: SchematicProject, catalog: CatalogResolver, *,
    reference: str, x_um: int, y_um: int, rotation: int,
    mirror_x: bool, api_version: int = 1,
) -> dict[str, Any]:
    """Probe a change to an EXISTING component without editing a snapshot.

    Fail closed for any moved electrically connected pin: a fully independent
    multi-Net router must resolve and validate the potential new conductors.
    """
    require_api_version(api_version)
    if type(reference) is not str or _REF.fullmatch(reference) is None:
        raise ProjectError("INVALID_COMPONENT_REFERENCE", "Exact existing reference required")
    if any(type(v) is not int or abs(v) > 100_000_000 for v in (x_um, y_um)):
        raise ProjectError("INVALID_COORDINATE", "Expected bounded integer micrometre point")
    if type(rotation) is not int or rotation not in (0, 90, 180, 270):
        raise ProjectError("INVALID_TRANSFORM", "Only D4 exact rotations supported")
    if type(mirror_x) is not bool:
        raise ProjectError("INVALID_TRANSFORM", "mirror_x must be boolean")
    component = next((c for c in project.circuit.components
                      if c.reference == reference), None)
    if component is None:
        raise ProjectError("UNKNOWN_COMPONENT", "Requested physical instance not saved")
    parts, symbols = catalog.verify(list(project.catalog_lock))
    part = parts[component.part_id]
    symbol = symbols[part.symbol_id]
    selected = Transform(rotation=rotation, mirror_x=mirror_x)
    origin = Point(x_um, y_um)
    existing_positions = component.pin_positions(symbol)
    proposed_positions = {
        pin.number: selected.apply(pin.at) + origin for pin in symbol.pins
    }
    changed = proposed_positions != existing_positions
    original_nets = {
        (ref.reference, ref.number): net.name
        for net in project.circuit.nets for ref in net.members
    }
    attached = [{
        "pin_ref": {"reference": reference, "number": pin.number},
        "original_net_name": original_nets[(reference, pin.number)],
    } for pin in part.pins if (reference, pin.number) in original_nets]
    conflict = []
    if changed and attached:
        conflict.append({
            "code": "CONNECTED_PIN_RELOCATION_BLOCKED", "severity": "error",
            "reference": reference,
            "message": "Connected physical terminals cannot be moved without verified rerouting",
            "affected_pinrefs": attached,
        })
    target_body = selected.box(symbol.body_keepout).translated(origin)
    target_ink = selected.box(symbol.stroked_bounds).translated(origin)
    for other in project.circuit.components:
        if other.reference == reference:
            continue
        other_part = parts[other.part_id]
        other_sym = symbols[other_part.symbol_id]
        body = other.transform.box(other_sym.body_keepout).translated(other.origin)
        dx = max(0, body.min_x - target_body.max_x, target_body.min_x - body.max_x)
        dy = max(0, body.min_y - target_body.max_y, target_body.min_y - body.max_y)
        if dx == 0 and dy == 0:
            conflict.append({
                "code": "PLACEMENT_BODY_OVERLAP", "severity": "error",
                "reference": reference, "other_reference": other.reference,
                "message": "Component body keepouts overlap or touch",
                "gap_um": [dx, dy],
            })
        elif dx < 2000 and dy < 2000:
            conflict.append({
                "code": "PLACEMENT_BODY_CLEARANCE_REVIEW", "severity": "warning",
                "reference": reference, "other_reference": other.reference,
                "message": "Conservative body AABB separation <2mm; exact glyph DRC required",
                "gap_um": [dx, dy],
            })
    if changed:
        for i, wire in enumerate(project.graph.segments):
            if wire_intersects_box(
                WireObstacle(project.wire_ids[i], Line(wire.start, wire.end),
                             stroke_um=project.stroke_widths_um[i], net_name=wire.net_name),
                target_body,
            ):
                conflict.append({
                    "code": "PLACEMENT_CONDUCTOR_BODY_INTERSECTION", "severity": "error",
                    "reference": reference, "wire_id": project.wire_ids[i],
                    "net_name": wire.net_name,
                    "message": "Authored conductor stroke intersects proposed body keepout",
                })
    return {
        "schema_version": 1, "read_only": True,
        "project_id": project.project_id, "project_revision": project.revision,
        "reference": reference, "part_id": component.part_id,
        "catalog_lock": {"part_sha256": catalog.lock(part.identifier)["part_sha256"],
                         "symbol_sha256": catalog.lock(part.identifier)["symbol_sha256"]},
        "component_geometry_changed": changed,
        "original_pin_anchors_um": [
            {"pin_ref": {"reference": reference, "number": pin.number},
             "at_um": [existing_positions[pin.number].x, existing_positions[pin.number].y]}
            for pin in part.pins
        ],
        "proposed_pin_anchors_um": [
            {"pin_ref": {"reference": reference, "number": pin.number},
             "at_um": [proposed_positions[pin.number].x, proposed_positions[pin.number].y]}
            for pin in part.pins
        ],
        "original_net_membership": attached,
        "proposed_origin_um": [x_um, y_um],
        "proposed_transform": {"rotation": rotation, "mirror_x": mirror_x},
        "body_keepout_um": _bounds(target_body),
        "ink_bounds_um": _bounds(target_ink),
        "diagnostics": conflict,
        "placement_geometry_eligible_for_review": not any(
            d["severity"] == "error" for d in conflict
        ),
        "connection_authorized": False, "print_ready": False,
        "candidate_render": "BLOCKED_UNTIL_VIEW_PLUS_ROUTING_CONTRACT",
        "commit_authorized": False,
        "model_or_head_mutated": False,
    }
