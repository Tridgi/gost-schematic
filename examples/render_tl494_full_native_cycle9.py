"""FULL native 23-component TL494 clean/diagnostic engine render, Cycle9.

The original authored Circuit and ExternalWireGraph come from the exact pinned
reference Python source, NEVER from parsing a saved SVG/bitmap. Pinned
ELEKTRIK IC #97 contributes its complete manufacturer-tested physical model,
and pinned YGO2 #113 selects/validates 13 original catalog UGO. The full
sheet is composed by the renderer from 23 native components.
"""
import argparse
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.rendering.ic_orientation import compose_transforms
from gost_schematic.validation.external_wire_checks import ExternalWireGraph
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.rendering.ic_rectangular import (
    IcFunctionReading,
    IcRenderingPolicy,
    render_resolved_ic,
)
from gost_schematic.rendering.ic_tl494_profile import apply_tl494_portrait_profile

FROZEN_SOURCE = "e695c415fdced164b0e0c39c5249d030795a0aa6"
FROZEN_IC = "6161e9102cbc0c9e0491fb27ed7a496dc0b274bc"
FROZEN_CATALOG = "edc71a48035723d48a203ae2ea12588701f68ba8"
SVG = "{http://www.w3.org/2000/svg}"


def _real_dependencies():
    """Require actual Git-source owners, never fake test stand-ins."""
    try:
        from examples.tl494_named_photo_sheet import compose_circuit
        from gost_schematic.catalog.source_profiles import (
            PINNED_REFERENCE_SHA,
            bind_tl494_source,
        )
        from gost_schematic.electrical.ic import (
            IcBodyAxis,
            IcGraphicProfile,
            IcPinRow,
            IcPortLayout,
            IcSymbolSpec,
            IcTextAngle,
            IcUnitPlacement,
            resolve_ic_pin_positions,
            validate_ic_circuit,
        )
        from gost_schematic.electrical.ic_pin_alias import verify_alias_display
        from gost_schematic.electrical.ic_serde import IcLibraryRecord
        from gost_schematic.electrical.tl494cn import (
            tl494cn_alias_profile,
            tl494cn_device,
            verify_tl494cn_ti_pinout,
        )
    except ImportError as exc:
        raise RuntimeError(
            "FULL_NATIVE_PINNED_SOURCE_REQUIRED: stage actual source SHA "
            "and two PR owner SHAs; never fallback to synthetic SVG"
        ) from exc
    if PINNED_REFERENCE_SHA != FROZEN_SOURCE:
        raise ValueError("FULL_NATIVE_SOURCE_SHA_DISAGREES_WITH_CATALOG")
    return {
        "compose": compose_circuit,
        "catalog": bind_tl494_source,
        "types": (
            IcBodyAxis, IcGraphicProfile, IcPinRow, IcPortLayout,
            IcSymbolSpec, IcTextAngle, IcUnitPlacement,
        ),
        "model": (resolve_ic_pin_positions, validate_ic_circuit, IcLibraryRecord),
        "aliases": (tl494cn_alias_profile, verify_alias_display),
        "device": (tl494cn_device, verify_tl494cn_ti_pinout),
    }


def _net_pin_id_map(circuit: Circuit):
    owner = {}
    for net in circuit.nets:
        for physical in net.members:
            if physical in owner:
                raise ValueError("FULL_NATIVE_DUPLICATE_NET_PINREF")
            owner[physical] = net.name
    return owner


def construct_native_paint(font_file: Path):
    """Build real electrical Circuit AND source-correct owner model, once."""
    deps = _real_dependencies()
    (
        circuit, graph, parts, symbols, pose,
        source_unit, _old_targets, style, measure, policy,
        _font, b_pair,
    ) = deps["compose"](font_file)
    assert isinstance(circuit, Circuit)
    if (len(circuit.components), len(circuit.nets), len(graph.segments),
            len(graph.junctions), len(source_unit.pins)) != (23, 15, 91, 37, 16):
        raise ValueError("FULL_NATIVE_FROZEN_23_15_91_37_16_SOURCE_CHANGED")
    source_memberships = tuple((n.name, n.members) for n in circuit.nets)
    catalog_bindings = deps["catalog"](circuit.components, parts, symbols)
    if len(catalog_bindings) != 13:
        raise ValueError("FULL_NATIVE_13_CATALOG_SELECTION_MISSING")
    device = deps["device"][0]()
    deps["device"][1](device)
    alias = deps["aliases"][0]("DA1")
    alias.validate_device(device)
    (
        IcBodyAxis, IcGraphicProfile, IcPinRow, IcPortLayout,
        IcSymbolSpec, IcTextAngle, IcUnitPlacement,
    ) = deps["types"]
    resolve, validate, IcLibraryRecord = deps["model"]
    rows = []
    for pin in source_unit.pins:
        if (
            pin.label.replace("−", "-") != device.pin_map[pin.number].name
        ):
            raise ValueError(
                f"FULL_NATIVE_MANUFACTURER_SOURCE_NAME_MISMATCH: {pin.number}"
            )
        rows.append(IcPinRow(
            pin.number, pin.side,
            pin.anchor - source_unit.origin,
            f"photo.source.{pin.number}",
            pin.label.replace("−", "-"),
            visual_row=pin.row,
        ))
    # The frozen photo places 8 pins on each side, unlike ELEKTRIK's
    # approved-for-DRAFT default 9/7 editorial alternate. Model THAT
    # SOURCE position explicitly: no unreviewed reflow of 91 fixed wires.
    spec = IcSymbolSpec(
        device.identifier, "control", source_unit.body, "PWM",
        tuple(rows), profile=IcGraphicProfile(
            port_layout=IcPortLayout.LEFT_RIGHT,
            body_axis=IcBodyAxis.PORTRAIT,
            function_angle=IcTextAngle.BOTTOM_TO_TOP,
        ),
    )
    record = IcLibraryRecord(
        device, (spec,), (
            IcUnitPlacement(
                "DA1", device.identifier, "control", source_unit.origin,
            ),
        ),
    )
    revised = alias.apply_to_record(record)
    deps["aliases"][1](alias, revised)
    if resolve(
        revised.device, revised.specs, revised.placements,
    ) != {PinRef("DA1", p.number): p.anchor for p in source_unit.pins}:
        raise ValueError("FULL_NATIVE_OWNER_RECORD_CHANGED_PINREF_POINT")
    if device.pin_map["3"].electrical_type.value != "input" or (
        device.pin_map["13"].electrical_type.value != "input"
    ):
        raise ValueError("FULL_NATIVE_TI_FEEDBACK_OR_OC_NOT_INPUT")
    # Rebuild NEW actual Circuit DA1 PartDefinition from ELEKTRIK's correct
    # physical source model; all 23 references, origins, pins and Nets stay.
    new_components = tuple(
        replace(c, part_id=device.identifier)
        if c.reference == "DA1" else c for c in circuit.components
    )
    current = Circuit(new_components, circuit.nets)
    if tuple((n.name, n.members) for n in current.nets) != source_memberships:
        raise AssertionError("FULL_NATIVE_V1_ELECTRICAL_TOPOLOGY_CHANGED")
    validate(device, current, "DA1")
    parts[device.identifier] = device.to_legacy_part(device.identifier)
    symbols[device.identifier] = replace(
        symbols["reference.tl494cn"], identifier=device.identifier,
    )
    symbol_map = {
        identifier: symbols[part.symbol_id]
        for identifier, part in parts.items()
    }
    da = next(c for c in current.components if c.reference == "DA1")
    physical_pose = da.pin_positions(symbols[device.identifier])
    if physical_pose != pose["DA1"]:
        raise AssertionError("FULL_NATIVE_CHANGED_SURROGATE_CATALOG_POINT")
    if any(
        physical_pose[p.number] != p.anchor for p in source_unit.pins
    ):
        raise AssertionError("FULL_NATIVE_SOURCE_PINREF_DELTA")
    visible = apply_tl494_portrait_profile(source_unit)
    for p in visible.pins:
        expected_alias = alias.labels[int(p.number)-1].schematic_short_label
        if p.visible_label.replace("−", "-") != expected_alias:
            raise ValueError("FULL_NATIVE_OWNER_ALIAS_DISAGREES_WITH_PAINT")
    return (
        current, graph, symbol_map, visible, source_unit,
        style, measure, policy, b_pair, revised, catalog_bindings,
    )


def _render_variant(
    circuit, graph, symbols, visible, style, measure,
    policy: IcRenderingPolicy, *,
    diagnostic: bool,
    reading: IcFunctionReading,
    original_full_labels: bool = False,
):
    model = visible.select_function_text_reading(reading)
    net_map = _net_pin_id_map(circuit)
    targets = tuple(
        IcConnectionTarget(
            pin.pin_id, PinRef("DA1", pin.number), pin.anchor, True,
            net_id=net_map.get(PinRef("DA1", pin.number)),
        ) for pin in model.pins
    )
    rendered = render_resolved_ic(
        model, style, measure, policy=policy,
        editor_targets=targets, editor_overlay=diagnostic,
        review_overlay=diagnostic, glyph_detail=diagnostic,
    )
    composed = render_external_wire_sheet(
        circuit, graph, symbols, style, measure,
        diagnostic=diagnostic, strict_layout=False,
        physical_ic_renderings={"DA1": rendered},
    )
    root = ET.fromstring(composed.svg)
    native = root.find(
        f".//{SVG}g[@data-composed-engine='physical-ic-renderer']"
    )
    if native is None:
        raise AssertionError("FULL_NATIVE_DA1_NOT_RENDERED_BY_ENGINE")
    assert len(root.findall(f"./{SVG}g[@data-layer='symbols']")) == 23
    wires = root.findall(f".//{SVG}line[@data-layer='wires']")
    assert len(wires) == 91
    assert all(
        (wire.get("data-net"), wire.get("data-wire-index"))
        == (segment.net_name, str(i))
        for i, (wire, segment) in enumerate(
            zip(wires, graph.segments, strict=True)
        )
    )
    assert len(root.findall(
        f".//{SVG}circle[@data-kind='authored-junction']"
    )) == 37
    marks = native.findall(
        f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
    )
    assert len(marks) == (16 if diagnostic else 0)
    names = {
        el.get("data-physical-pin-number"): el.text
        for el in native.findall(f".//{SVG}text[@data-kind='pin-label']")
    }
    if original_full_labels:
        assert names["3"] == "FEEDBACK"
        assert names["13"] == "OUTPUT CTRL"
    else:
        assert names["3"] == "FB" and names["13"] == "OC"
    assert len(names) == 16
    assert len([el for el in native.findall(
        f".//{SVG}text[@data-kind='function']"
    ) if el.text == "PWM"]) == 1
    assert root.get("data-native-ic-composition") == "exact-circuit-pinrefs"
    return composed, rendered


def transformed_complete_scene(
    circuit: Circuit,
    graph: ExternalWireGraph,
    unit,
    pose: Transform,
):
    """Exact global D4 for ALL 23 components, 91 wires and the resolved IC.

    A closed orthogonal transform is a REVIEW view: no fixed Net membership
    change and no rerouting. The source photo's D4 orientation need not be
    confused with a different manufacturer pinout or a new GOST card.
    """
    if not isinstance(pose, Transform):
        raise TypeError("NATIVE_D4_TRANSFORM_TYPED_REQUIRED")
    moved_components = tuple(replace(
        component,
        origin=pose.apply(component.origin),
        transform=compose_transforms(pose, component.transform),
    ) for component in circuit.components)
    transformed = Circuit(moved_components, circuit.nets)
    moved_wires = ExternalWireGraph(
        tuple(replace(
            wire, start=pose.apply(wire.start), end=pose.apply(wire.end),
        ) for wire in graph.segments),
        tuple(pose.apply(point) for point in graph.junctions),
    )
    moved_unit = replace(
        unit,
        origin=pose.apply(unit.origin),
        transform=compose_transforms(pose, unit.transform),
        pins=tuple(replace(
            pin, anchor=pose.apply(pin.anchor),
        ) for pin in unit.pins),
    )
    if transformed.nets != circuit.nets:
        raise AssertionError("NATIVE_D4_CHANGED_CIRCUIT_NET")
    original = {c.reference: c for c in circuit.components}
    for component in transformed.components:
        before = original[component.reference]
        if component.part_id != before.part_id or (
            component.origin != pose.apply(before.origin)
        ):
            raise AssertionError("NATIVE_D4_CHANGED_COMPONENT_IDENTITY")
    for old, new in zip(graph.segments, moved_wires.segments, strict=True):
        if (
            new.net_name != old.net_name
            or new.start != pose.apply(old.start)
            or new.end != pose.apply(old.end)
        ):
            raise AssertionError("NATIVE_D4_CHANGED_WIRE_IDENTITY")
    return transformed, moved_wires, moved_unit


def generate(output: Path, font_file: Path, *, d4: bool = False):
    info = construct_native_paint(font_file)
    (
        circuit, graph, symbol_map, portrait, original,
        style, measure, policy, pair, record, bindings,
    ) = info
    output.mkdir(parents=True, exist_ok=True)
    before = _render_variant(
        circuit, graph, symbol_map, original, style, measure, policy,
        diagnostic=False, reading=IcFunctionReading.TOP_TO_BOTTOM,
        original_full_labels=True,
    )
    before_file = "TL494_native_23_BEFORE_old_pwm_top_to_bottom.svg"
    (output/before_file).write_text(before[0].svg, encoding="utf-8")
    evidence = {
        "source_sha": FROZEN_SOURCE,
        "owner_ic_sha": FROZEN_IC,
        "owner_catalog_sha": FROZEN_CATALOG,
        "status": "FULL_NATIVE_23_ENGINE_RENDER_SOURCE_LOCKED_DRAFT",
        "components": len(circuit.components),
        "Nets": len(circuit.nets),
        "wires": len(graph.segments),
        "explicit_junctions": len(graph.junctions),
        "original_b_continuations": [
            e.id for e in pair.endpoints
        ],
        "catalog_ugo_bindings": [b.reference for b in bindings],
        "tl494_manufacturer": record.device.package.manufacturer,
        "actual_ti_pin3_electrical": record.device.pin_map["3"].electrical_type.value,
        "actual_ti_pin13_electrical": record.device.pin_map["13"].electrical_type.value,
        "font_sha256": style.font_sha256,
        "paint_authoritative_points": {
            p.number: [p.anchor.x, p.anchor.y] for p in portrait.pins
        },
        "variants": {},
        "legacy_before": before_file,
        "electrical_topology_changed": False,
        "gost_ugo_approved": False,
        "route_drc_pass": False,
    }
    for reading in IcFunctionReading:
        for diagnostic in (False, True):
            composed, paint = _render_variant(
                circuit, graph, symbol_map, portrait, style, measure,
                policy, diagnostic=diagnostic, reading=reading,
            )
            mode = "diagnostic" if diagnostic else "clean"
            file = f"TL494_native_23_{reading.value}_{mode}.svg"
            (output/file).write_text(composed.svg, encoding="utf-8")
            assert len(paint.pin_anchors) == 16
            assert {n: (point.x, point.y) for n, point in (
                (p.number, p.anchor) for p in portrait.pins
            )} == {
                number: (point.x, point.y)
                for owner, point in paint.pin_anchors
                for number in [owner.removeprefix("DA1.P")]
            }
            evidence["variants"][file] = {
                "function_reading": reading.value,
                "diagnostic_only_green_pin_tips": 16 if diagnostic else 0,
                "native_layout_valid": composed.layout.valid,
                "full_native_23_source_parts": True,
                "source_net_memberships_unchanged": True,
                "real_type_a_3500um": style.em_height_um == 3500,
            }
    if d4:
        for angle in (0, 90, 180, 270):
            for mirror in (False, True):
                t = Transform(angle, mirror)
                transformed, transformed_wires, transformed_ic = (
                    transformed_complete_scene(
                        circuit, graph, portrait, t,
                    )
                )
                rendering, painted = _render_variant(
                    transformed, transformed_wires, symbol_map,
                    transformed_ic, style, measure, policy,
                    diagnostic=False,
                    reading=IcFunctionReading.BOTTOM_TO_TOP,
                )
                assert set(
                    (number, point) for number, point in painted.pin_anchors
                ) == {
                    (p.pin_id, t.apply(p.anchor)) for p in portrait.pins
                }
                name = (
                    f"TL494_native_23_D4_{angle}_mirror{int(mirror)}"
                    "_btt_clean.svg"
                )
                (output/name).write_text(rendering.svg, encoding="utf-8")
                evidence["variants"][name] = {
                    "function_reading": "bottom_to_top",
                    "D4": [angle, mirror],
                    "native_full_sheet": True,
                    "immutable_Net_memberships": transformed.nets == circuit.nets,
                    "exact_geometry_isometry": True,
                    "physical_component_count": 23,
                    "line_segment_count": 91,
                }
    (output/"TL494_full_native_23_engine_manifest.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "source": FROZEN_SOURCE[:10], "parts": 23, "nets": 15,
        "wires": 91, "engine_native_render": True, "vendor_pin3": "input",
        "formats": list(evidence["variants"]),
        "original_print_DRC": "BLOCKED",
    }))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--d4", action="store_true", help="all eight entire-circuit D4 poses")
    args = parser.parse_args()
    generate(args.output, args.font_file, d4=args.d4)


if __name__ == "__main__":
    main()
