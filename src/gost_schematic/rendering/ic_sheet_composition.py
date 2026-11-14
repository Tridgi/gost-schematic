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
        for child in paint_xml:
            if child.tag != _NS+"title":
                native.append(child)
        root.insert(index, native)
        for text in list(root):
            if (text.tag == _NS+"text"
                    and text.get("data-layer") == "annotations"
                    and text.get("data-owner") == reference):
                root.remove(text)
    root.set("data-native-ic-composition", "exact-circuit-pinrefs")
