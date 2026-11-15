"""Verified overlay of source-owned E3 IC ink onto a newly rendered Circuit sheet.

The inputs are live Circuit/GraphicPin and IcRendered objects. This NEVER
patches a saved SVG file, invents a Net or changes component placement.
"""
from collections.abc import Mapping
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import Point
from gost_schematic.core.units import format_mm
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.rendering.ic_rectangular import IcRendered

_NS = "{http://www.w3.org/2000/svg}"


def compose_authoritative_ic_layers(
    root: ET.Element,
    circuit: Circuit,
    symbols_by_part: Mapping[str, SymbolDefinition],
    renderings: Mapping[str, IcRendered],
    *,
    diagnostic: bool,
) -> None:
    """Fail closed unless every displayed IC terminal equals the true Net/PinRef.

    Asserts all external physical endpoints, target membership, NC policy
    and the generated SVG lead ink before composing any rendered group.
    """
    if not isinstance(renderings, Mapping) or not renderings:
        raise TypeError("SHEET_IC_TYPED_LAYER_MAPPING_REQUIRED")
    components = {c.reference: c for c in circuit.components}
    if len(components) != len(circuit.components):
        raise ValueError("SHEET_IC_DUPLICATE_COMPONENT_REFERENCE")
    net_ids = {}
    for net in circuit.nets:
        for pin in net.members:
            if pin in net_ids:
                raise ValueError("SHEET_IC_DUPLICATE_NET_MEMBERSHIP")
            net_ids[pin] = net.name
    for reference, paint in renderings.items():
        if reference not in components or not isinstance(paint, IcRendered):
            raise TypeError("SHEET_IC_MISSING_COMPONENT_OR_TYPED_PAINT")
        component = components[reference]
        symbol = symbols_by_part.get(component.part_id)
        if symbol is None:
            raise ValueError("SHEET_IC_CATALOG_SYMBOL_MISSING")
        authoritative = {
            pin.number: component.transform.apply(pin.at) + component.origin
            for pin in symbol.pins
        }
        model_points = {}
        for pin_id, anchor in paint.pin_anchors:
            prefix = f"{reference}.P"
            if not pin_id.startswith(prefix) or not isinstance(anchor, Point):
                raise ValueError("SHEET_IC_FOREIGN_PHYSICAL_PINREF")
            number = pin_id.removeprefix(prefix)
            if number in model_points:
                raise ValueError("SHEET_IC_DUPLICATE_PHYSICAL_PIN")
            model_points[number] = anchor
        if model_points != authoritative or len(model_points) != len(symbol.pins):
            raise ValueError("SHEET_IC_PINREF_POINT_INVENTORY_MISMATCH")
        paint_xml = ET.fromstring(paint.svg)
        if paint_xml.get("data-pin-anchor-authority") != "external-resolved-only":
            raise ValueError("SHEET_IC_UNVERIFIED_PAINT_ORIGIN")
        leads = paint_xml.findall(
            f".//{_NS}g[@data-layer='ic-physical-pin-leads']/{_NS}line"
        )
        if len(leads) != len(authoritative):
            raise ValueError("SHEET_IC_MISSING_RENDERED_LEAD")
        role = {}
        for lead in leads:
            number = lead.get("data-pin-number")
            at = authoritative.get(number)
            if at is None or (
                lead.get("x2"), lead.get("y2")
            ) != (format_mm(at.x), format_mm(at.y)):
                raise ValueError("SHEET_IC_SVG_PINREF_INK_MISMATCH")
            role[number] = lead.get("data-role")
        if len(paint.connection_targets) != len(authoritative):
            raise ValueError("SHEET_IC_INCOMPLETE_TARGET_MANIFEST")
        seen = set()
        for target in paint.connection_targets:
            if not isinstance(target, IcConnectionTarget):
                raise TypeError("SHEET_IC_TYPED_TARGET_REQUIRED")
            number = target.pin_ref.number
            pin = PinRef(reference, number)
            if (
                target.pin_ref != pin
                or target.pin_id != f"{reference}.P{number}"
                or pin in seen
                or target.anchor != authoritative.get(number)
                or target.net_id != net_ids.get(pin)
            ):
                raise ValueError("SHEET_IC_FORGED_TARGET_PINREF_OR_NET")
            nc = role.get(number) == "nc"
            if (
                target.connectable == nc
                or (nc and (target.reason != "NC" or target.net_id is not None))
            ):
                raise ValueError("SHEET_IC_FORGED_NC_OR_DISABLED_TARGET")
            seen.add(pin)
        if seen != {PinRef(reference, num) for num in authoritative}:
            raise ValueError("SHEET_IC_PARTIAL_TARGET_INVENTORY")
        markers = paint_xml.findall(
            f".//{_NS}g[@data-layer='editor-connection-targets']/{_NS}rect"
        )
        if (diagnostic and len(markers) != len(authoritative)) or (
            not diagnostic and markers
        ):
            raise ValueError("SHEET_IC_DEBUG_LAYER_POLICY_MISMATCH")
        for marker in markers:
            number = marker.get("data-pin-number")
            at = authoritative.get(number)
            if at is None or (
                marker.get("data-external-anchor-x-um"),
                marker.get("data-external-anchor-y-um"),
            ) != (str(at.x), str(at.y)):
                raise ValueError("SHEET_IC_DEBUG_MARKER_CENTER_MISMATCH")
        surrogate = [
            g for g in root
            if g.tag == _NS+"g" and g.get("data-layer") == "symbols"
            and g.get("data-reference") == reference
        ]
        if len(surrogate) != 1:
            raise ValueError("SHEET_IC_MISSING_NATIVE_SURROGATE")
        index = list(root).index(surrogate[0])
        root.remove(surrogate[0])
        native = ET.Element(_NS+"g", {
            "data-reference": reference,
            "data-layer": "symbols",
            "data-composed-engine": "physical-ic-renderer",
            "data-physical-pin-count": str(len(authoritative)),
            "data-typed-net-count": str(len(circuit.nets)),
        })
        target_layer = None
        for child in paint_xml:
            if child.tag == _NS+"title":
                continue
            if child.get("data-layer") == "editor-connection-targets":
                if not diagnostic or target_layer is not None:
                    raise ValueError("SHEET_IC_EDITOR_LAYER_MULTIPLE_OR_IN_CLEAN")
                target_layer = child
                continue
            native.append(child)
        if diagnostic and target_layer is None:
            raise ValueError("SHEET_IC_VERIFIED_EDITOR_LAYER_MISSING")
        root.insert(index, native)
        # Original native renderer prints wires *after* symbol groups. If
        # the verified pin squares stayed in this symbol group, the real
        # copper line would paint BLACK across each 0.7mm green square's
        # center. In the genuinely interactive diagnostic overlay, physical
        # contact targets MUST be the final foreground layer, and MUST NOT
        # be duplicated or leak into clean print SVG/PDF.
        if target_layer is not None:
            target_layer.set("data-reference", reference)
            target_layer.set("data-layer-order", "after-all-copper")
            target_layer.set("data-circuit-provenance", "verified-pinrefs-and-nets")
            root.append(target_layer)
        for text in list(root):
            if (text.tag == _NS+"text"
                    and text.get("data-layer") == "annotations"
                    and text.get("data-owner") == reference):
                root.remove(text)
    root.set("data-native-ic-composition", "exact-circuit-pinrefs")


def append_verified_sheet_continuations(
    root: ET.Element,
    circuit: Circuit,
    project: object,
    style,
    *,
    diagnostic: bool,
    symbols_by_part: Mapping[str, SymbolDefinition] | None = None,
) -> None:
    """Paint typed b continuation addresses as nonphysical labels, not pads.

    The caller's NetContinuationProject is source-validated by the electrical
    owner. Refuse foreign circuit Net membership or invented a indicators.
    """
    from gost_schematic.electrical.netrefs import (
        NetContinuationProject,
        validate_net_continuations,
    )

    if not isinstance(project, NetContinuationProject):
        raise TypeError("SHEET_CONTINUATION_SOURCE_TYPED_PROJECT_REQUIRED")
    if project.circuit.nets != circuit.nets:
        raise ValueError("SHEET_CONTINUATION_FOREIGN_CIRCUIT_NETS")
    if len(project.endpoints) != 2 or {
        endpoint.id for endpoint in project.endpoints
    } != {"b-X2", "b-R5"}:
        raise ValueError("SHEET_CONTINUATION_SOURCE_B_PAIR_MISMATCH")
    if {endpoint.label for endpoint in project.endpoints} != {"b"}:
        raise ValueError("SHEET_CONTINUATION_FORGED_A_SOURCE_LABEL")
    expected_pins = {
        "b-X2": PinRef("X2", "1"),
        "b-R5": PinRef("R5", "2"),
    }
    if (
        project.schema_version != 2
        or len(project.nets) != 1
        or len(project.stubs) != 2
        or {stub.endpoint_id for stub in project.stubs} != set(expected_pins)
        or any(stub.pin != expected_pins[stub.endpoint_id]
               for stub in project.stubs)
    ):
        raise ValueError("SHEET_CONTINUATION_SOURCE_B_STUB_INVENTORY_DRIFT")
    endpoints = {item.id: item for item in project.endpoints}
    for stub in project.stubs:
        endpoint = endpoints[stub.endpoint_id]
        if (
            stub.end != endpoint.anchor
            or stub.start == stub.end
            or (stub.start.x != stub.end.x
                and stub.start.y != stub.end.y)
        ):
            raise ValueError("SHEET_CONTINUATION_SOURCE_B_STUB_GEOMETRY_DRIFT")
    if not isinstance(symbols_by_part, Mapping):
        raise TypeError("SHEET_CONTINUATION_PHYSICAL_SYMBOLS_REQUIRED")
    by_ref = {component.reference: component for component in circuit.components}
    if len(by_ref) != len(circuit.components):
        raise ValueError("SHEET_CONTINUATION_DUPLICATE_PHYSICAL_PART")
    true_pins = {}
    for stub in project.stubs:
        comp = by_ref.get(stub.pin.reference)
        if comp is None:
            raise ValueError("SHEET_CONTINUATION_MISSING_PHYSICAL_PART")
        symbol = symbols_by_part.get(comp.part_id)
        if symbol is None:
            raise ValueError("SHEET_CONTINUATION_MISSING_PHYSICAL_UGO")
        if not isinstance(symbol, SymbolDefinition):
            raise TypeError("SHEET_CONTINUATION_INVALID_PHYSICAL_UGO_TYPE")
        tip = comp.pin_positions(symbol).get(stub.pin.number)
        if tip is None or tip != stub.start:
            raise ValueError("SHEET_CONTINUATION_SOURCE_B_PHYSICAL_TIP_DRIFT")
        true_pins[stub.pin] = tip
    problems = validate_net_continuations(
        project, physical_pin_anchors=true_pins,
    )
    if problems:
        raise ValueError(
            "SHEET_CONTINUATION_SOURCE_B_TYPED_INVALID:"
            + ",".join(item.code for item in problems)
        )
    region = ET.SubElement(root, _NS+"g", {
        "data-layer": "typed-nonphysical-continuations",
        "data-nonphysical": "true",
        "data-do-not-infer-net-from-shapes": "true",
    })
    # Source-authored NON-ELECTRICAL visible local b stubs: they do not
    # enter Circuit.Nets, ExternalWireGraph, junctions or green hotspots.
    # Draw these BEFORE the terminal marker circles so the white centers
    # remain legible. Exact integer-µm coordinates come from project.stubs.
    for stub in project.stubs:
        ET.SubElement(region, _NS+"line", {
            "x1": format_mm(stub.start.x),
            "y1": format_mm(stub.start.y),
            "x2": format_mm(stub.end.x),
            "y2": format_mm(stub.end.y),
            "stroke": "#000000",
            "stroke-width": "0.3",
            "fill": "none",
            "data-layer": "nonphysical-continuation-stub",
            "data-nonphysical": "true",
            "data-electrical-junction": "false",
            "data-connectable": "false",
            "data-source-pin-ref": (
                f"{stub.pin.reference}.{stub.pin.number}"
            ),
            "data-nonphysical-net-continuation": stub.endpoint_id,
            "data-source-stub-id": stub.id,
        })
    for end in project.endpoints:
        at = end.anchor
        ET.SubElement(region, _NS+"circle", {
            "cx": format_mm(at.x), "cy": format_mm(at.y),
            "r": "0.65", "stroke": "#000000",
            "stroke-width": "0.3", "fill": "#ffffff",
            "data-nonphysical-net-continuation": end.id,
            "data-electrical-junction": "false",
        })
        label = ET.SubElement(region, _NS+"text", {
            "x": format_mm(at.x),
            "y": format_mm(at.y-4000),
            "font-family": style.font_family,
            "font-size": format_mm(style.em_height_um),
            "text-anchor": "middle", "stroke": "none", "fill": "#000000",
            "data-source": "typed-net-continuation-v2",
            "data-nonphysical": "true",
        })
        if style.font_sha256 is not None:
            label.set("data-font-sha256", style.font_sha256)
        label.text = end.label
        if diagnostic:
            ET.SubElement(region, _NS+"rect", {
                "x": format_mm(at.x-2500), "y": format_mm(at.y-2500),
                "width": "5", "height": "5", "fill": "none",
                "stroke": "#be6300", "stroke-width": "0.35",
                "stroke-dasharray": "1 0.5",
                "data-layer": "nonphysical-continuation-editor-reading-zone",
                "data-connectable": "false",
                "data-not-a-physical-terminal": "true",
            })
