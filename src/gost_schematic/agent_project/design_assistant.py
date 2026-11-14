"""Strict source-backed catalog selection and non-mutating TL494 preflight.

Not a placement optimizer, a complete printed-sheet DRC, a routing engine or
a manufacturer-verified TL494 IC catalog adapter. All E3 references and
connections are loaded from the exact immutable ProjectService revision.
"""
from typing import Any

from gost_schematic.core.geometry import Line, enclosing_box, primitive_bounds
from gost_schematic.core.transforms import Transform
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.dimensional_checks import check_verified_dimensions
from gost_schematic.validation.sheet_wire_rules import validate_sheet_wire_rules

from .catalog import CatalogResolver, ProjectError
from .contracts import SchematicProject

# User's source-specific selection; NEVER an assertion of GOST approval.
TL494_REQUIRED_PARTS = {
    "C1": "capacitor.polarized", "C2": "capacitor.polarized",
    "C3": "capacitor.polarized", "C5": "capacitor.polarized",
    "C6": "capacitor.polarized", "C4": "capacitor.fixed",
    "C7": "capacitor.fixed", "L1": "inductor.ferromagnetic",
    "L2": "inductor.ferromagnetic",
    "VT1": "transistor.mosfet_n_enh",
    "VD1": "diode.schottky", "FU1": "fuse.general",
}
TL494_EDITORIAL_ALIASES = {
    "FEEDBACK": ("FB", "3"),
    "OUTPUT CTRL": ("OC", "13"),
}
# A small, reviewed phrase dictionary, not fuzzy/LMM-generated synonyms.
# Ambiguous semantics deliberately return the whole catalog family.
SEMANTIC_QUERY_TERMS = {
    "capacitor": "capacitor",
    "конденсатор": "capacitor",
    "polarized capacitor": "capacitor.polarized",
    "полярный конденсатор": "capacitor.polarized",
    "fixed capacitor": "capacitor.fixed",
    "неполярный конденсатор": "capacitor.fixed",
    "electrolytic capacitor": "capacitor.electrolytic",
    "катушка": "inductor",
    "inductor": "inductor",
    "катушка с сердечником": "inductor",
    "ferromagnetic inductor": "inductor.ferromagnetic",
    "катушка с ферромагнитным сердечником": "inductor.ferromagnetic",
    "mosfet": "transistor",
    "n channel enhancement mosfet": "transistor.mosfet_n_enh",
    "diode": "diode",
    "диод": "diode",
    "диод шоттки": "diode.schottky",
    "schottky diode": "diode.schottky",
    "fuse": "fuse.general",
    "предохранитель": "fuse.general",
}
TL494_GROUPS = {
    "input_and_L1": ("X1", "L1"),
    "feedback_and_control": (
        "R1", "R2", "R3", "R4", "R5", "R6", "R7", "C3", "C4", "C7",
    ),
    "tl494_control": ("DA1",),
    "mosfet_drive": ("R8", "VT1", "VD1"),
    "output_and_L2": ("C1", "C2", "L2", "C5", "C6", "FU1", "X2"),
}
_D4 = tuple(
    {"rotation": deg, "mirror_x": mirror}
    for mirror in (False, True) for deg in (0, 90, 180, 270)
)


def _bounds(box: Any) -> list[int]:
    return [box.min_x, box.min_y, box.max_x, box.max_y]


def catalog_card(catalog: CatalogResolver, part_id: str) -> dict[str, Any]:
    part, symbol = catalog.resolve(part_id)
    lock = catalog.lock(part_id)
    # Geometric transform capability != normative clearance of orientation.
    for pose in _D4:
        Transform(pose["rotation"], pose["mirror_x"])
    return {
        **lock,
        "physical_pin_refs": [
            {"number": pin.number, "name": pin.name,
             "electrical_role": pin.electrical_type.value,
             "function": pin.function.value, "polarity": pin.polarity.value,
             "symbol_anchor_um": [next(p.at.x for p in symbol.pins
                                       if p.number == pin.number),
                                  next(p.at.y for p in symbol.pins
                                       if p.number == pin.number)]}
            for pin in part.pins
        ],
        "body_keepout_um": _bounds(symbol.body_keepout),
        "stroked_graphic_bounds_um": _bounds(symbol.stroked_bounds),
        "line_width_um": symbol.line_width_um,
        "nominal_kind": part.nominal_kind.value if part.nominal_kind else None,
        "standard_refs": list(symbol.standard_refs),
        "allowed_by_geometry_engine": list(_D4),
        "normative_transform_approval": "NOT_VERIFIED_PER_POSE",
        "preview_tool": "schematic_catalog_preview",
        "preview_source": "real installed SymbolDefinition, not source photo",
        "not_manufacturer_part_number": True,
    }


def catalog_search(catalog: CatalogResolver, query: str) -> dict[str, Any]:
    """Never pick one variant from a broad category; show exact loaded options."""
    if type(query) is not str or not 1 <= len(query) <= 64:
        raise ProjectError("INVALID_SEMANTIC_QUERY", "Expected a bounded category or part ID")
    word = query.strip().lower()
    if word != query.lower() or not word or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789._- " for char in word
    ):
        raise ProjectError("INVALID_SEMANTIC_QUERY", "Use a canonical catalog category/ID")
    group = SEMANTIC_QUERY_TERMS.get(word, word)
    if group in catalog.parts:
        ids = [group]
    else:
        ids = [key for key in sorted(catalog.parts)
               if key.startswith(group + ".")]
    if len(ids) > 64:
        raise ProjectError("CATALOG_QUERY_TOO_BROAD", "Refine to a specific category")
    if not ids:
        return {
            "schema_version": 1, "read_only": True, "query": query,
            "status": "NO_EXACT_CATALOG_MATCH", "candidates": [],
            "selection_required": True,
        }
    return {
        "schema_version": 1, "read_only": True, "query": query,
        "status": "OPTIONS_REQUIRE_EXPLICIT_PART_ID", "candidate_count": len(ids),
        "candidates": [catalog_card(catalog, key) for key in ids],
        "selection_required": True,
    }


def catalog_preview(catalog: CatalogResolver, part_id: str) -> tuple[str, bytes, dict[str, Any]]:
    """Genuine SVG source and PNG derived from the resolved installed part."""
    if type(part_id) is not str or not 1 <= len(part_id) <= 80:
        raise ProjectError("INVALID_CATALOG_SELECTOR", "Exact part ID required")
    _, symbol = catalog.resolve(part_id)
    svg = render_symbol_svg(symbol, review_overlay=False)
    box = symbol.stroked_bounds.expanded(3000)
    width = box.max_x - box.min_x
    height = box.max_y - box.min_y
    width_px = max(64, 512 * width // max(width, height))
    height_px = max(64, 512 * height // max(width, height))
    try:
        import resvg_py
        png = resvg_py.svg_to_bytes(
            svg_string=svg, width=width_px, height=height_px,
        )
    except ImportError as exc:
        raise ProjectError("RASTERIZER_UNAVAILABLE", "Install mcp extra") from exc
    if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) > 2_000_000:
        raise ProjectError("RASTERIZATION_FAILED", "Catalog PNG preview invalid")
    import hashlib
    return svg, png, {
        **catalog_card(catalog, part_id),
        "preview_width_px": width_px, "preview_height_px": height_px,
        "svg_sha256": hashlib.sha256(svg.encode()).hexdigest(),
        "png_sha256": hashlib.sha256(png).hexdigest(),
        "not_a_printed_sheet": True,
    }


def tl494_profile(catalog: CatalogResolver) -> dict[str, Any]:
    rows = []
    for ref, part_id in TL494_REQUIRED_PARTS.items():
        card = catalog_card(catalog, part_id)
        rows.append({
            "reference": ref, "required_part_id": part_id,
            "part_sha256": card["part_sha256"],
            "symbol_sha256": card["symbol_sha256"],
            "symbol_status": card["symbol_status"],
            "choice": "EXACT_USER_SOURCE_PROFILE",
        })
    return {
        "schema_version": 1, "profile_id": "issue107-tl494-ugo-source-v1",
        "source": "Issue #107 authored 2026-11-14, editorial requirements",
        "read_only": True, "not_normatively_approved": True,
        "required_variants": rows,
        "unlisted_components": "REQUIRE_INDEPENDENT_EXACT_PART_SELECTION",
        "tl494_device_catalog": (
            "NOT_IN_INSTALLED_P11_CATALOG"
            if "reference.tl494cn" not in catalog.parts else
            "INSTALLED_REQUIRES_DATASHEET_PINOUT_LOCK"
        ),
        "aliases": [{
            "full_name": full, "display_alias": alias,
            "physical_number": number,
            "provenance": "Issue #107 + physical TI TL494 pin-number mapping (draft)",
            "manufacturer_passthrough_preserved": True,
            "normative_status": "EDITORIAL_DRAFT",
        } for full, (alias, number) in TL494_EDITORIAL_ALIASES.items()],
        "aliases_not_in_dictionary": "BLOCKED_DO_NOT_ABBREVIATE",
    }


def tl494_alias(full_name: str) -> dict[str, Any]:
    if type(full_name) is not str or not 1 <= len(full_name) <= 64:
        raise ProjectError("INVALID_PIN_LABEL", "Require exact full pin name")
    pair = TL494_EDITORIAL_ALIASES.get(full_name)
    if pair is None:
        return {"status": "ALIAS_UNVERIFIED", "full_name": full_name,
                "abbreviation_allowed": False, "original_name_unchanged": True}
    return {"status": "EDITORIAL_DRAFT_VERIFIED_DICTIONARY",
            "full_name": full_name, "display_alias": pair[0],
            "physical_number": pair[1], "abbreviation_allowed": True,
            "original_name_unchanged": True}


def _placed_boxes(project: SchematicProject, catalog: CatalogResolver):
    parts, symbols = catalog.verify(list(project.catalog_lock))
    byref = {}
    for component in project.circuit.components:
        symbol = symbols[parts[component.part_id].symbol_id]
        byref[component.reference] = {
            "symbol": symbol,
            "body": component.transform.box(symbol.body_keepout).translated(component.origin),
            "stroke": component.transform.box(symbol.stroked_bounds).translated(component.origin),
            "pins": component.pin_positions(symbol),
        }
    return byref, parts, symbols


def preflight_project(project: SchematicProject, catalog: CatalogResolver, *,
                      profile: str = "none") -> dict[str, Any]:
    """Physical model based pre-render evidence; never claim full printable DRC."""
    if profile not in ("none", "tl494"):
        raise ProjectError("INVALID_PREFLIGHT_PROFILE", "Only none or tl494 supported")
    placed, parts, symbols = _placed_boxes(project, catalog)
    record = project.to_record()
    ref_to_id = {c["reference"]: c["id"] for c in record["components"]}
    components = []
    diagnostics = []
    for component in project.circuit.components:
        symbol = placed[component.reference]["symbol"]
        parts_pin = parts[component.part_id].pins
        locked = catalog.lock(component.part_id)
        components.append({
            "reference": component.reference, "component_id": ref_to_id[component.reference],
            "part_id": component.part_id, "symbol_status": symbol.status.value,
            "symbol_sha256": locked["symbol_sha256"],
            "physical_pins": [
                {"number": pin.number, "name": pin.name, "role": pin.electrical_type.value,
                 "world_um": [placed[component.reference]["pins"][pin.number].x,
                              placed[component.reference]["pins"][pin.number].y]}
                for pin in parts_pin
            ],
            "origin_um": [component.origin.x, component.origin.y],
            "rotation": component.transform.rotation,
            "mirror_x": component.transform.mirror_x,
            "body_keepout_um": _bounds(placed[component.reference]["body"]),
            "stroked_bounds_um": _bounds(placed[component.reference]["stroke"]),
        })
        dim = check_verified_dimensions(symbol)
        for d in dim.diagnostics:
            diagnostics.append({"code": d.code, "severity": d.severity.value,
                                "subject": component.reference, "message": d.message,
                                "source": "verified_dimensional_subset"})
    if profile == "tl494":
        actual = {c.reference: c.part_id for c in project.circuit.components}
        for ref, required in TL494_REQUIRED_PARTS.items():
            if ref not in actual:
                diagnostics.append({
                    "code": "TL494_REQUIRED_COMPONENT_MISSING", "severity": "error",
                    "subject": ref, "message": f"{ref} requires physical UGO {required}",
                    "source": "source_selection_matrix",
                })
            elif actual[ref] != required:
                diagnostics.append({
                    "code": "TL494_UGO_VARIANT_MISMATCH", "severity": "error",
                    "subject": ref, "message": (
                        f"{ref}: actual {actual[ref]}, required {required}; "
                        "do not choose by generic category"
                    ),
                    "source": "source_selection_matrix",
                })
    wires = tuple(
        WireObstacle(wire_id, Line(w.start, w.end),
                     stroke_um=project.stroke_widths_um[i], net_name=w.net_name)
        for i, (wire, wire_id) in enumerate(zip(
            project.graph.segments, project.wire_ids, strict=True
        ))
    )
    for d in validate_sheet_wire_rules(wires):
        diagnostics.append({"code": d.code, "severity": d.severity.value,
                            "subject": d.subject, "message": d.message,
                            "source": "actual_ink_eskd_parallel_wire_subset"})
    # Body spacing is an AABB conservative screen-independent check. Does
    # NOT certify 2mm separation of every actual glyph stroke or label.
    names = list(placed)
    for i, left in enumerate(names):
        a = placed[left]["body"]
        for right in names[i+1:]:
            b = placed[right]["body"]
            dx = max(0, a.min_x - b.max_x, b.min_x - a.max_x)
            dy = max(0, a.min_y - b.max_y, b.min_y - a.max_y)
            if dx < 2000 and dy < 2000:
                diagnostics.append({
                    "code": "ESKD_SYMBOL_BODY_CLEARANCE_REVIEW",
                    "severity": "warning", "subject": f"{left}/{right}",
                    "message": (
                        f"{left}/{right}: body keepout AABB gap ({dx},{dy}) µm; "
                        "requires exact 2mm symbol-to-symbol glyph/stroke QA"
                    ),
                    "source": "conservative_body_AABB_only",
                })
    all_boxes = [item["stroke"] for item in placed.values()]
    for wire in project.graph.segments:
        all_boxes.append(primitive_bounds(Line(wire.start, wire.end)))
    bbox = _bounds(enclosing_box(tuple(all_boxes))) if all_boxes else None
    nets = [{
        "net_id": row["id"], "net_name": row["name"],
        "physical_members": [
            {"component_id": pin["component_id"], "physical_pin_number": pin["pin"]}
            for pin in row["members"]
        ],
    } for row in record["nets"]]
    route_stats = {"authored_segment_count": len(project.graph.segments),
                   "explicit_junction_count": len(project.graph.junctions),
                   "route_planner": "NOT_IMPLEMENTED",
                   "route_conflict_checks": [
                       "print_wire_width_0.2_to_1.0mm",
                       "orthogonal_overlapping_parallel_3mm_clearance",
                   ]}
    groups = []
    if profile == "tl494":
        for name, members in TL494_GROUPS.items():
            present = [ref for ref in members if ref in placed]
            groups.append({
                "group": name, "expected_references": list(members),
                "present_references": present,
                "placement_review": "MANUAL_SOURCE_PHOTO_REQUIRED",
                "bbox_um": _bounds(enclosing_box(tuple(
                    placed[ref]["stroke"] for ref in present
                ))) if present else None,
            })
    return {
        "schema_version": 1, "read_only": True,
        "source_of_truth": "restored immutable E3 Circuit + real catalog + ExternalWireGraph",
        "project_id": project.project_id, "project_revision": project.revision,
        "profile": profile, "component_count": len(components),
        "components": components, "nets": nets, "route": route_stats,
        "functional_groups": groups,
        "used_sheet_bbox_um": bbox,
        "sheet_format": "NOT_PERSISTED_IN_P11",
        "print_drc": "PARTIAL_ONLY_NOT_CERTIFIED",
        "not_implemented_checks": [
            "complete wire-to-graphic-stroke and label-ink spacing",
            "full print font ink/label collision", "normative sheet A3/A4 fit",
            "source photo alignment and all true graphical variants",
            "multi-Net safe routing and automatic placement",
        ],
        "diagnostics": sorted(diagnostics, key=lambda d: (
            d["source"], d["code"], d["subject"] or "",
        )),
        "print_ready": False,
        "status": "BLOCKED_INCOMPLETE_PRINT_DRC",
    }
