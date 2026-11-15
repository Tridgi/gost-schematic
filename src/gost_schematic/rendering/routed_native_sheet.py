"""Typed external owner-route -> real complete Circuit native E3 rendering gate.

Unlike legacy static 91-wire image review, this API accepts ANY new,
source-bound ExternalWireGraph (including owner NET #114 previews). It cannot
create or repair connections. An incomplete 15-Net route may be rendered
ONLY as an explicitly blocked diagnostic trial; a clean-looking image is not
evidence of legal electrical or print completeness.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from math import gcd
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Box
from gost_schematic.core.units import format_mm
from gost_schematic.engines.annotation.metrics import TextMeasurer
from gost_schematic.model.annotations import TextStyle
from gost_schematic.model.circuit import Circuit
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.rendering.ic_rectangular import IcRendered
from gost_schematic.rendering.native_sheet_ink_audit import (
    audit_full_native_sheet_ink,
    audit_native_parallel_wire_strokes,
)
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    validate_external_wires,
)

_NS = "{http://www.w3.org/2000/svg}"


@dataclass(frozen=True, slots=True)
class RoutedSheetRender:
    """Authoritative clean+diagnostic artwork plus independent blocking gates."""

    clean_svg: str
    diagnostic_svg: str
    graph_sha256: str
    manifest: dict
    printable_candidate: bool

    def __post_init__(self) -> None:
        if type(self.printable_candidate) is not bool:
            raise TypeError("ROUTED_SHEET_PRINT_FLAG_MUST_BE_BOOLEAN")
        if self.printable_candidate and self.manifest.get("blockers"):
            raise ValueError("ROUTED_SHEET_PASS_WITH_BLOCKERS_FORBIDDEN")


def _graphic_hash(circuit: Circuit, graph: ExternalWireGraph) -> str:
    parts = [
        [c.reference, c.part_id, c.origin.x, c.origin.y,
         c.transform.rotation, c.transform.mirror_x]
        for c in circuit.components
    ]
    nets = [
        [n.name, [[p.reference, p.number] for p in n.members]]
        for n in circuit.nets
    ]
    wires = [
        [s.net_name, s.start.x, s.start.y, s.end.x, s.end.y]
        for s in graph.segments
    ]
    source = json.dumps(
        [parts, nets, wires, [[p.x, p.y] for p in graph.junctions]],
        separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def render_routed_native_sheet(
    circuit: Circuit,
    graph: ExternalWireGraph,
    parts: Mapping[str, PartDefinition],
    symbols_by_part: Mapping[str, SymbolDefinition],
    style: TextStyle,
    measurer: TextMeasurer,
    *,
    physical_ic_renderings_clean: Mapping[str, IcRendered],
    physical_ic_renderings_diagnostic: Mapping[str, IcRendered],
    verified_ic_source: object | None = None,
    verified_ic_paint_binding: object | None = None,
    verified_ic_snapshot: object | None = None,
    source_continuation_project: object | None = None,
    route_preview: object | None = None,
    expected_component_count: int | None = None,
    expected_net_count: int | None = None,
    expected_net_pinrefs: int | None = None,
    stroke_um: int = 300,
    physical_page_box: Box | None = None,
) -> RoutedSheetRender:
    """Render genuine NEW route, independently gate print and source identity.

    Fail immediately on forged Net, illegal foreign T junction or mismatching
    owner-provided route preview. Current 114 RouteDRC runs when actually
    installed; if missing, print is BLOCKED, not silently "pass".
    Nonprintable partial router attempts remain inspectable both clean and
    diagnostic (the clean is conspicuously tagged *BLOCKED*, not released).
    """
    if not isinstance(circuit, Circuit) or not isinstance(graph, ExternalWireGraph):
        raise TypeError("ROUTED_SHEET_TYPED_CIRCUIT_WIRE_GRAPH_REQUIRED")
    if not isinstance(parts, Mapping) or not isinstance(symbols_by_part, Mapping):
        raise TypeError("ROUTED_SHEET_PART_AND_SYMBOL_MAPPINGS_REQUIRED")
    if (
        not isinstance(physical_ic_renderings_clean, Mapping)
        or not physical_ic_renderings_clean
        or not isinstance(physical_ic_renderings_diagnostic, Mapping)
        or set(physical_ic_renderings_clean) != set(physical_ic_renderings_diagnostic)
    ):
        raise TypeError("ROUTED_SHEET_TYPED_PHYSICAL_IC_REQUIRED")
    for key, clean_ic in physical_ic_renderings_clean.items():
        debug_ic = physical_ic_renderings_diagnostic[key]
        if not isinstance(clean_ic, IcRendered) or not isinstance(debug_ic, IcRendered):
            raise TypeError("ROUTED_SHEET_IC_RENDER_PAIR_TYPED_REQUIRED")
        if clean_ic.pin_anchors != debug_ic.pin_anchors or (
            clean_ic.connection_targets != debug_ic.connection_targets
        ):
            raise ValueError("ROUTED_SHEET_CLEAN_DEBUG_PINREF_NET_DRIFT")
    # Source-specific signed manufacturer trust is independent of a pair of
    # plausible raw IcRendered objects. Recompute every graphic from the
    # verified IC97 snapshot, not from 16 freely supplied green squares.
    trust_items = (
        verified_ic_source, verified_ic_paint_binding, verified_ic_snapshot,
    )
    if any(item is not None for item in trust_items) and (
        not all(item is not None for item in trust_items)
    ):
        raise TypeError("ROUTED_SHEET_SIGNED_IC_TRIPLE_REQUIRED")
    signed_source_verified = False
    if all(item is not None for item in trust_items):
        from gost_schematic.electrical.ic_circuit_adapter import (
            IcCircuitBinding,
            IcVerifiedPaintSnapshot,
        )
        from gost_schematic.electrical.ic_paint_bridge import IcPaintBinding

        if (
            not isinstance(verified_ic_source, IcCircuitBinding)
            or not isinstance(verified_ic_snapshot, IcVerifiedPaintSnapshot)
            or not isinstance(verified_ic_paint_binding, IcPaintBinding)
        ):
            raise TypeError("ROUTED_SHEET_SIGNED_MANUFACTURER_TYPES_REQUIRED")
        verified_ic_source.validate()
        if verified_ic_source.circuit is not circuit:
            raise ValueError("ROUTED_SHEET_SIGNED_IC_CIRCUIT_IDENTITY_DRIFT")
        verified_ic_snapshot.verify_against(
            verified_ic_source, verified_ic_paint_binding,
        )
        reference = verified_ic_snapshot.component_ref
        if (
            set(physical_ic_renderings_clean) != {reference}
            or len(verified_ic_snapshot.per_unit_targets) != 1
            or len(verified_ic_snapshot.per_unit_targets[0]) != 16
        ):
            raise ValueError("ROUTED_SHEET_SIGNED_IC_16_PIN_INVENTORY_MISMATCH")
        # Serialized lead inventory must match the authenticated manufacturer
        # contact map, not a caller-manufactured synthetic physical cursor.
        expected = {
            f"{c.component_ref}.P{c.physical_number}": c.anchor
            for c in verified_ic_snapshot.manifest.contacts
        }
        if len(expected) != 16:
            raise ValueError("ROUTED_SHEET_SIGNED_IC_MANIFEST_LOST_PINS")
        for provided in (
            physical_ic_renderings_clean[reference],
            physical_ic_renderings_diagnostic[reference],
        ):
            if dict(provided.pin_anchors) != expected or (
                provided.connection_targets
                != verified_ic_snapshot.per_unit_targets[0]
            ):
                raise ValueError("ROUTED_SHEET_SIGNED_IC_INK_OR_TARGET_DRIFT")
        # Re-render from the signed source in BOTH modes. PinRef targets
        # alone cannot authenticate text glyphs or SVG physical-lead ink.
        expected_clean = verified_ic_snapshot.render(
            verified_ic_source, verified_ic_paint_binding,
            style, measurer, diagnostics=False,
        )
        expected_diagnostic = verified_ic_snapshot.render(
            verified_ic_source, verified_ic_paint_binding,
            style, measurer, diagnostics=True,
        )
        if (
            expected_clean != (physical_ic_renderings_clean[reference],)
            or expected_diagnostic
            != (physical_ic_renderings_diagnostic[reference],)
        ):
            raise ValueError("ROUTED_SHEET_SIGNED_IC_SERIALIZED_INK_CHANGED")
        signed_source_verified = True
    if type(stroke_um) is not int or stroke_um <= 0:
        raise ValueError("ROUTED_SHEET_INVALID_STROKE")
    if physical_page_box is not None and not isinstance(physical_page_box, Box):
        raise TypeError("ROUTED_SHEET_TYPED_PAGE_BOX_REQUIRED")
    for label, expected, observed in (
        ("COMPONENTS", expected_component_count, len(circuit.components)),
        ("NETS", expected_net_count, len(circuit.nets)),
        ("NET_PINREFS", expected_net_pinrefs,
         sum(len(n.members) for n in circuit.nets)),
    ):
        if expected is not None and (
            type(expected) is not int or observed != expected
        ):
            raise ValueError("ROUTED_SHEET_SOURCE_" + label + "_DRIFT")
    net_names = {net.name for net in circuit.nets}
    if len(net_names) != len(circuit.nets):
        raise ValueError("ROUTED_SHEET_DUPLICATE_SOURCE_NET")
    missing_parts = {
        c.part_id for c in circuit.components if c.part_id not in parts
        or c.part_id not in symbols_by_part
    }
    if missing_parts:
        raise ValueError("ROUTED_SHEET_UNKNOWN_SOURCE_PART:" + repr(missing_parts))
    for index, segment in enumerate(graph.segments):
        if segment.net_name not in net_names:
            raise ValueError(f"ROUTED_SHEET_FORGED_FOREIGN_NET:{index}:{segment.net_name}")
    for point in graph.junctions:
        # A printed junction dot must be sourced to a SINGLE named Net;
        # even a close X with different net colors is NEVER an electric node.
        incident = tuple(
            wire for wire in graph.segments
            if _point_on_segment(wire, point)
        )
        touched = {wire.net_name for wire in incident}
        if len(touched) != 1 or not _is_real_branch(incident, point):
            # A straight splice or two-segment elbow does not require a
            # conductive junction dot. Only a real 3+ arm T/X/branch may
            # render a node; foreign-Net overlap is never implicitly joined.
            raise ValueError("ROUTED_SHEET_FOREIGN_OR_DANGLING_JUNCTION")
    if route_preview is not None:
        try:
            from gost_schematic.engines.multiterminal_router import GlobalRoutePreview
        except ImportError as exc:
            raise RuntimeError(
                "ROUTED_SHEET_OWNER_114_ROUTER_NOT_INSTALLED"
            ) from exc

        if not isinstance(route_preview, GlobalRoutePreview):
            raise TypeError("ROUTED_SHEET_OWNER_PREVIEW_TYPED_REQUIRED")
        if route_preview.source_circuit != circuit or route_preview.graph != graph:
            raise ValueError("ROUTED_SHEET_OWNER_PREVIEW_CIRCUIT_GRAPH_DRIFT")
        expected_trees = {n.name for n in circuit.nets}
        observed_trees = [t.net_name for t in route_preview.net_trees]
        if len(set(observed_trees)) != len(observed_trees) or (
            not set(observed_trees) <= expected_trees
        ):
            raise ValueError("ROUTED_SHEET_OWNER_PREVIEW_NET_TREE_FORGERY")
    fingerprint = _graphic_hash(circuit, graph)
    all_sym = {symbol.identifier: symbol for symbol in symbols_by_part.values()}
    electrical = validate_external_wires(circuit, graph, parts, all_sym)
    electric_error_codes = sorted(
        {i.code for i in electrical if i.severity.value == "error"}
    )
    blockers = list(_tl494_source_print_proof_blockers(
        len(circuit.components), len(circuit.nets),
        sum(len(net.members) for net in circuit.nets),
        route_preview=route_preview,
        source_continuation_project=source_continuation_project,
        physical_page_box=physical_page_box,
    ))
    if (len(circuit.components), len(circuit.nets),
            sum(len(net.members) for net in circuit.nets)) == (23, 15, 62):
        if not signed_source_verified:
            blockers.append("TL494_SIGNED_MANUFACTURER_PHYSICAL_BINDING_MISSING")
    if electric_error_codes:
        blockers.extend(f"ELECTRICAL:{code}" for code in electric_error_codes)
    if route_preview is not None and not route_preview.complete:
        blockers.append("ROUTER_INCOMPLETE_OR_UNVERIFIED_15_NETS")
    clean = render_external_wire_sheet(
        circuit, graph, dict(symbols_by_part), style, measurer,
        diagnostic=False, stroke_um=stroke_um, strict_layout=False,
        physical_ic_renderings=physical_ic_renderings_clean,
        source_continuation_project=source_continuation_project,
    )
    debug = render_external_wire_sheet(
        circuit, graph, dict(symbols_by_part), style, measurer,
        diagnostic=True, stroke_um=stroke_um, strict_layout=False,
        physical_ic_renderings=physical_ic_renderings_diagnostic,
        source_continuation_project=source_continuation_project,
    )
    if clean.layout != debug.layout:
        raise AssertionError("ROUTED_SHEET_CLEAN_DEBUG_LAYOUT_DRIFT")
    if not clean.layout.valid:
        blockers.append("ANNOTATION_LAYOUT_HAS_ERRORS")
    ic = next(iter(physical_ic_renderings_clean.values()))
    text_collisions = audit_full_native_sheet_ink(
        circuit, graph, dict(symbols_by_part), clean.layout, ic,
        wire_stroke_um=stroke_um,
    )
    parallel = audit_native_parallel_wire_strokes(
        graph, stroke_um=stroke_um,
    )
    if text_collisions:
        blockers.append("TYPE_A_GLYPH_TO_WIRE_OR_UGO_COLLISIONS")
    if parallel:
        blockers.append("PARALLEL_DISTINCT_NET_UNDER_3MM")
    # This namespace belongs to NET #114. A missing owner implementation
    # MUST NOT let another party certify a print. It is a deliberate optional
    # *read-only* integration, not a vendored or copied router implementation.
    drc = None
    try:
        owner_drc = import_module("gost_schematic.validation.route_drc")
    except ImportError:
        blockers.append("NET114_INDEPENDENT_ROUTE_DRC_NOT_INSTALLED")
    else:
        drc = owner_drc.audit_route_drc(
            circuit, graph, stroke_um=stroke_um,
            symbols_by_part=dict(symbols_by_part),
            annotation_placements=clean.layout.placements,
        )
        if not drc.checked_symbol_geometry or not drc.checked_measured_text:
            blockers.append("NET114_DRC_DID_NOT_CHECK_PRINT_SYMBOLS_AND_TEXT")
        if not drc.valid:
            blockers.append("NET114_POST_RENDER_PRINT_DRC_ERRORS")
    if route_preview is not None and not route_preview.print_pass:
        blockers.append("NET114_ORIGINAL_ROUTE_PREVIEW_NOT_PRINT_PASS")
    # Require source-authoritative continuation data when the caller requested
    # one, but never invent a second nonphysical label for absent source.
    physical_count = len(circuit.components)
    page_fits = None
    if physical_page_box is not None:
        protected_boxes = []
        for component in circuit.components:
            symbol = symbols_by_part[component.part_id]
            protected_boxes.append(component.transform.box(
                symbol.stroked_bounds,
            ).translated(component.origin))
        for region in clean.layout.placements:
            protected_boxes.append(region.ink_bounds)
        for region in ic.ink:
            protected_boxes.append(region.box)
        # The generated ink footprint also includes every segment endpoint
        # with real half-stroke. NO raster crop or symbol scale is tolerated.
        margin = (stroke_um + 1) // 2
        for wire in graph.segments:
            protected_boxes.append(Box(
                min(wire.start.x, wire.end.x)-margin,
                min(wire.start.y, wire.end.y)-margin,
                max(wire.start.x, wire.end.x)+margin+1,
                max(wire.start.y, wire.end.y)+margin+1,
            ))
        for point in graph.junctions:
            protected_boxes.append(Box(
                point.x-550, point.y-550,
                point.x+550, point.y+550,
            ))
        if source_continuation_project is not None:
            # Both nonphysical b glyphs are genuine PRINTED ink. Counting
            # only components/copper silently lets labels or marker rings
            # spill beyond an otherwise falsely 'A3 fits' physical page.
            for endpoint in source_continuation_project.endpoints:
                at = endpoint.anchor
                protected_boxes.append(Box(
                    at.x-2500, at.y-4500-style.em_height_um,
                    at.x+2500, at.y+1000,
                ))
        page_fits = all(
            physical_page_box.min_x <= box.min_x
            and physical_page_box.min_y <= box.min_y
            and box.max_x <= physical_page_box.max_x
            and box.max_y <= physical_page_box.max_y
            for box in protected_boxes
        )
        if not page_fits:
            blockers.append("A3_TRUE_1_TO_1_ARTWORK_OUTSIDE_PAPER")
    full = (
        not blockers
        and drc is not None
        and not electric_error_codes
        and not text_collisions
        and not parallel
        and clean.layout.valid
    )
    result_views = []
    for mode, sheet in (("clean", clean), ("diagnostic", debug)):
        root = ET.fromstring(sheet.svg)
        if physical_page_box is not None and page_fits:
            width_um = physical_page_box.max_x - physical_page_box.min_x
            height_um = physical_page_box.max_y - physical_page_box.min_y
            root.set("width", format_mm(width_um)+"mm")
            root.set("height", format_mm(height_um)+"mm")
            root.set("viewBox", " ".join(format_mm(v) for v in (
                physical_page_box.min_x, physical_page_box.min_y,
                width_um, height_um,
            )))
            root.set("data-physical-page-size", "EXACT_1_TO_1_NO_SCALING")
        root.set("data-route-graph-sha256", fingerprint)
        root.set("data-source-components", str(physical_count))
        root.set("data-source-nets", str(len(circuit.nets)))
        root.set("data-actual-route-segments", str(len(graph.segments)))
        root.set("data-release", (
            "TECHNICAL_GATE_PASS_QA_REQUIRED" if full else
            "BLOCKED_INCOMPLETE_OR_PRINT_DRC"
        ))
        root.set("data-e3-normative-approval", "DRAFT_NOT_APPROVED")
        root.set("data-render-route-kind", "EXTERNAL_VERIFIED_MODEL_GRAPH")
        # Native type-owned assembly, never manual edit of saved SVG.
        if mode == "diagnostic":
            foreground = [
                item for item in list(root)
                if item.get("data-layer") == "editor-connection-targets"
            ]
            if len(foreground) != len(physical_ic_renderings_diagnostic):
                raise ValueError("ROUTED_SHEET_REAL_PIN_TARGET_LAYER_MISSING")
            for item in foreground:
                root.remove(item)
                root.append(item)
        result_views.append(ET.tostring(root, encoding="unicode") + "\n")
    if _graphic_hash(circuit, graph) != fingerprint:
        raise AssertionError("ROUTED_SHEET_INPUT_MUTATED_WHILE_RENDERING")
    manifest = {
        "schema": "paint.routed-native.v1",
        "signed_manufacturer_ic_16_verified": signed_source_verified,
        "status": "TECHNICAL_GATE_PASS_QA_REQUIRED" if full else "BLOCKED",
        "source_components": physical_count,
        "source_nets": len(circuit.nets),
        "source_net_pinrefs": sum(len(n.members) for n in circuit.nets),
        "route_segments": len(graph.segments),
        "authored_junctions": len(graph.junctions),
        "graph_sha256": fingerprint,
        "owner_preview_complete": (
            route_preview.complete if route_preview is not None else None
        ),
        "owner_preview_print_pass": (
            route_preview.print_pass if route_preview is not None else None
        ),
        "electrical_errors": electric_error_codes,
        "routed_3mm_parallel_errors": [
            vars(x) if hasattr(x, "__dict__") else {
                "wire_first": x.first_segment,
                "wire_second": x.second_segment,
                "edge_gap_um": x.edge_gap_um,
            } for x in parallel
        ],
        "glyph_ugo_wire_collision_count": len(text_collisions),
        "glyph_ugo_wire_collision_examples": [
            {
                "code": x.code, "text_owner": x.text_owner,
                "ink_kind": x.ink_kind, "source": x.source,
            } for x in text_collisions[:24]
        ],
        "native_post_render_route_drc": drc.as_dict() if drc is not None else None,
        "blockers": sorted(set(blockers)),
        "printable_candidate": full,
        "physical_page_fits_1_to_1": page_fits,
        "physical_page_um": (
            [physical_page_box.min_x, physical_page_box.min_y,
             physical_page_box.max_x, physical_page_box.max_y]
            if physical_page_box is not None else None
        ),
        "gost_approved": False,
        "source_graph_mutated": False,
        "new_route_not_original_91_required": False,
        "drawable_when_partial": True,
    }
    return RoutedSheetRender(result_views[0], result_views[1],
                             fingerprint, manifest, full)




def _tl494_source_print_proof_blockers(
    component_count: int,
    net_count: int,
    net_memberships: int,
    *,
    route_preview: object | None,
    source_continuation_project: object | None,
    physical_page_box: Box | None,
) -> tuple[str, ...]:
    """Fail closed on three mandatory independent full-source print proofs.

    A 23/15/62 model is not print-approved merely because all SVG segments
    happen to draw. It still needs verified new automatic routing, the source
    b-continuation rebinding, and a bounded physical print page. Tiny generic
    fixtures remain useful without falsely certifying the TL494 source.
    """
    if (component_count, net_count, net_memberships) != (23, 15, 62):
        return ()
    blockers = []
    if route_preview is None:
        blockers.append("TL494_NEW_ROUTER_OWNER_PROVENANCE_MISSING")
    if source_continuation_project is None:
        blockers.append("A3_SOURCE_CONTINUATION_BINDING_UNRESOLVED")
    if physical_page_box is None:
        blockers.append("TL494_PHYSICAL_ONE_TO_ONE_PAGE_NOT_VERIFIED")
    return tuple(blockers)


def _is_real_branch(segments, point) -> bool:
    """At least three distinct exact-µm rays meet at the declared same-Net dot.

    One segment passing through the point contributes two rays. Two endpoint
    wires forming a straight splice or an L contribute only two, so neither
    may be portrayed as a real three-terminal electrical junction.
    """
    rays = set()
    for segment in segments:
        for endpoint in (segment.start, segment.end):
            dx, dy = endpoint.x - point.x, endpoint.y - point.y
            if dx or dy:
                divisor = gcd(abs(dx), abs(dy))
                rays.add((dx // divisor, dy // divisor))
    return len(rays) >= 3


def _point_on_segment(segment, point) -> bool:
    a, b = segment.start, segment.end
    return (
        (b.x - a.x) * (point.y - a.y)
        == (b.y - a.y) * (point.x - a.x)
        and min(a.x, b.x) <= point.x <= max(a.x, b.x)
        and min(a.y, b.y) <= point.y <= max(a.y, b.y)
    )
