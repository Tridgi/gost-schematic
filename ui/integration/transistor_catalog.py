"""Exact Python transistor profile projection to the current CAD ProjectV2.

V2 supports exact lines, circles and routing keepout fields. The source
lock and body protection are also retained in the staging manifest. This is a staging interface, not permission to place these parts
without enforcing the protection metadata.
"""
import json

from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.core.geometry import Circle, Line


class ProjectionError(ValueError):
    """Stable rejection when the target contract cannot preserve the source."""


def _point(point) -> list[int]:
    return [point.x, point.y]


def _box(box) -> list[int]:
    return [box.min_x, box.min_y, box.max_x, box.max_y]


def project_v2_profile(catalog: CatalogResolver, identifier: str) -> dict:
    if identifier not in catalog.transistor_layout_ids():
        raise ProjectionError("UNKNOWN_TRANSISTOR_PROFILE: " + identifier)
    part, symbol = catalog.resolve(identifier)
    if not all(isinstance(item, (Line, Circle)) for item in symbol.graphics):
        raise ProjectionError("UNSUPPORTED_V2_PRIMITIVE: " + identifier)
    # V2 cannot carry these physical attributes. Refuse non-default values
    # rather than changing the physical meaning in the target document.
    if any(p.polarity.value != "none" or p.function.value != "general" for p in part.pins):
        raise ProjectionError("UNSUPPORTED_V2_PIN_ATTRIBUTE: " + identifier)
    symbol_id = "symbol/" + symbol.identifier
    if any(len(ref) > 256 for ref in symbol.standard_refs):
        raise ProjectionError("UNSUPPORTED_V2_REFERENCE_LENGTH: " + identifier)
    return {
        "part_definition": {
            "id": part.identifier,
            "reference_prefix": part.reference_prefix,
            "symbol_ids": [symbol_id],
            "physical_pins": [
                {"number": p.number, "name": p.name, "electrical_type": p.electrical_type.value}
                for p in part.pins
            ],
        },
        "symbol_definition": {
            "id": symbol_id,
            "part_id": part.identifier,
            "revision": symbol.revision,
            "status": symbol.status.value,
            "standard_refs": list(symbol.standard_refs),
            "routing_keepouts_um": [_box(b) for b in symbol.routing_boxes],
            "pins": [
                {"physical_pin_number": p.number, "at_um": _point(p.at), "side": p.side.value}
                for p in symbol.pins
            ],
            "graphics": [
                ({"kind": "line", "points_um": [_point(g.start), _point(g.end)],
                  "stroke_um": symbol.line_width_um} if isinstance(g, Line) else
                 {"kind": "circle", "points_um": [_point(g.center),
                  [g.center.x + g.radius, g.center.y]], "stroke_um": symbol.line_width_um})
                for g in symbol.graphics
            ],
        },
        "source_lock": catalog.lock(identifier),
        "protection": {
            "body_um": _box(symbol.body_keepout),
            "routing_keepouts_um": [_box(b) for b in symbol.routing_boxes],
        },
        "placement_ready": False,
    }


def export_manifest(catalog: CatalogResolver | None = None) -> dict:
    resolver = CatalogResolver() if catalog is None else catalog
    profiles, blocked = [], []
    for identifier in resolver.transistor_layout_ids():
        try:
            profiles.append(project_v2_profile(resolver, identifier))
        except ProjectionError as exc:
            blocked.append({"id": identifier, "reason": str(exc).split(": ", 1)[0]})
    return {
        "schema_version": 1,
        "target": "gscad-project-v2",
        "placement_ready": False,
        "profiles": profiles,
        "blocked": blocked,
    }


def verify_profile(catalog: CatalogResolver, profile: dict) -> None:
    """Check all projected fields against the exact currently locked source."""
    try:
        identifier = profile["source_lock"]["part_id"]
        expected = project_v2_profile(catalog, identifier)
    except (KeyError, TypeError, ProjectError, ProjectionError) as exc:
        raise ProjectionError("PROFILE_SOURCE_MISMATCH") from exc
    if profile != expected:
        raise ProjectionError("PROFILE_SOURCE_MISMATCH")


if __name__ == "__main__":
    print(json.dumps(export_manifest(), ensure_ascii=False, sort_keys=True, indent=2))
