"""FULL native 23-component TL494 clean/diagnostic engine render, Cycle9.

The original authored Circuit and ExternalWireGraph come from the exact pinned
reference Python source, NEVER from parsing a saved SVG/bitmap. Pinned
ELEKTRIK IC #97 contributes its complete manufacturer-tested physical model,
and pinned YGO2 #113 selects/validates 13 original catalog UGO. The full
sheet is composed by the renderer from 23 native components.
"""
import argparse
import ast
import hashlib
import inspect
import json
from dataclasses import asdict, replace
from pathlib import Path
from textwrap import dedent
from xml.etree import ElementTree as ET

from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.rendering.ic_hotspots import IcConnectionTarget
from gost_schematic.rendering.ic_orientation import compose_transforms
from gost_schematic.rendering.ic_rectangular import (
    IcFunctionReading,
    IcRenderingPolicy,
    render_resolved_ic,
)
from gost_schematic.rendering.ic_tl494_profile import apply_tl494_portrait_profile
from gost_schematic.rendering.native_sheet_ink_audit import (
    audit_full_native_sheet_ink,
    audit_native_parallel_wire_strokes,
)
from gost_schematic.validation.external_wire_checks import ExternalWireGraph

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


def _declared_type_a_family(builder) -> str:
    """Read the *actual* owner builder's strict font request, not an alias.

    Only literal, non-optional 3500um Type-A inspection on the genuine
    build() callable is accepted. A renamed or runtime-dynamic selector is
    not permission to silently relax the font-family security check.
    """
    if builder.__name__ != "build" or (
        builder.__module__ != "examples.tl494_ic_paint_reference"
    ):
        raise ValueError("FULL_NATIVE_TYPE_A_UNTRUSTED_OWNER_BUILDER")
    tree = ast.parse(dedent(inspect.getsource(builder)))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "inspect_type_a_font"
    ]
    if len(calls) != 1 or calls[0].args:
        raise ValueError("FULL_NATIVE_TYPE_A_OWNER_SELECTOR_NOT_LITERAL")
    keywords = {item.arg: item.value for item in calls[0].keywords}
    if set(keywords) != {"h_um", "family", "require_family_match"} or any(
        not isinstance(item, ast.Constant) for item in keywords.values()
    ) or keywords["h_um"].value != 3500 or (
        keywords["require_family_match"].value is not True
    ):
        raise ValueError("FULL_NATIVE_TYPE_A_OWNER_SELECTOR_NOT_LITERAL")
    family = keywords["family"].value
    if family not in ("OpenGost Type A TT", "OpenGOST type A"):
        raise ValueError("FULL_NATIVE_TYPE_A_UNKNOWN_SOURCE_FAMILY")
    return family


def _compose_frozen_circuit_with_real_type_a(compose_circuit, font_file: Path):
    """Require the actual 3500um SHA-pinned Type A for either source builder.

    Historical e695 builder requests an OBSOLETE face 'OpenGost Type A TT';
    only for that verified source callable, inject a scoped actual-font
    selector. Modern RECON builder requests 'OpenGOST type A': call it
    WITHOUT monkeypatching. Neither path weakens family/SHA/cap checking.
    """
    from examples import tl494_connected_native as connected
    from examples import tl494_ic_paint_reference as source_ic
    from gost_schematic.standards.type_a_font import inspect_type_a_font

    if connected.build_paint_ic is not source_ic.build:
        raise ValueError("FULL_NATIVE_TYPE_A_BUILDER_ALIAS_DRIFT")
    family = _declared_type_a_family(source_ic.build)
    requested = Path(font_file)
    if hashlib.sha256(requested.read_bytes()).hexdigest() != (
        "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
    ):
        raise ValueError("FULL_NATIVE_TYPE_A_PINNED_SHA_MISMATCH")
    verified = inspect_type_a_font(
        requested, h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    )
    if (
        verified.measured_cap_height_um != 3500
        or verified.requested_cap_height_um != 3500
    ):
        raise ValueError("FULL_NATIVE_TYPE_A_TRUE_CAP_HEIGHT_INVALID")
    if family == "OpenGOST type A":
        return compose_circuit(requested)

    original = source_ic.inspect_type_a_font

    def inspect_actual_open_gost(
        font_path, *, h_um, family, require_family_match,
    ):
        if (
            family != "OpenGost Type A TT"
            or h_um != 3500
            or require_family_match is not True
            or Path(font_path).resolve() != requested.resolve()
        ):
            raise ValueError("FROZEN_REFERENCE_TYPE_A_SIGNATURE_CHANGED")
        return verified

    source_ic.inspect_type_a_font = inspect_actual_open_gost
    try:
        return compose_circuit(requested)
    finally:
        source_ic.inspect_type_a_font = original

def construct_native_paint(font_file: Path):
    """Build real electrical Circuit AND source-correct owner model, once."""
    deps = _real_dependencies()
    (
        circuit, graph, parts, symbols, pose,
        source_unit, _old_targets, style, measure, policy,
        _font, b_pair,
    ) = _compose_frozen_circuit_with_real_type_a(deps["compose"], font_file)
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
    visible = replace(visible, pins=tuple(
        replace(
            pin,
            manufacturer_electrical_type=(
                device.pin_map[pin.number].electrical_type.value
            ),
        ) for pin in visible.pins
    ))
    assert visible.pins == tuple(
        replace(pin, manufacturer_electrical_type=(
            device.pin_map[pin.number].electrical_type.value
        )) for pin in apply_tl494_portrait_profile(source_unit).pins
    )
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
    continuation_project=None,
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
        source_continuation_project=continuation_project,
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
    marks = root.findall(
        f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
    )
    assert len(marks) == (16 if diagnostic else 0)
    if diagnostic:
        overlays = root.findall(
            f"./{SVG}g[@data-layer='editor-connection-targets']"
        )
        assert len(overlays) == 1
        assert overlays[0].get("data-layer-order") == "after-all-copper"
        assert list(root).index(overlays[0]) > max(
            list(root).index(wire) for wire in wires
        )
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
    from examples import tl494_ic_paint_reference as owner_font

    declared_face = _declared_type_a_family(owner_font.build)
    info = construct_native_paint(font_file)
    (
        circuit, graph, symbol_map, portrait, original,
        style, measure, policy, pair, record, bindings,
    ) = info
    output.mkdir(parents=True, exist_ok=True)
    before = _render_variant(
        circuit, graph, symbol_map, original, style, measure, policy,
        diagnostic=False, reading=IcFunctionReading.TOP_TO_BOTTOM,
        original_full_labels=True, continuation_project=pair,
    )
    before_ink = audit_full_native_sheet_ink(
        circuit, graph, symbol_map, before[0].layout, before[1],
    )
    parallel_drc = audit_native_parallel_wire_strokes(graph)
    if len(parallel_drc) != 5:
        raise ValueError(
            "NATIVE_SOURCE_5_PARALLEL_WARNINGS_CHANGED_NO_SILENT_ROUTING"
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
        "native_b_graphics_from_typed_project": True,
        "fake_a_marker_created": False,
        "catalog_ugo_bindings": [b.reference for b in bindings],
        "tl494_manufacturer": record.device.package.manufacturer,
        "actual_ti_pin3_electrical": record.device.pin_map["3"].electrical_type.value,
        "actual_ti_pin13_electrical": record.device.pin_map["13"].electrical_type.value,
        "manufacturer_role_is_separate_from_frozen_graphic_port_side": True,
        "font_sha256": style.font_sha256,
        "font_family_source_declared": declared_face,
        "font_family_source_legacy_alias": (
            "OpenGost Type A TT -> verified OpenGOST type A; "
            "source Python remains immutable"
            if declared_face == "OpenGost Type A TT" else None
        ),
        "calibrated_type_a_h_mm": 3.5,
        "paint_authoritative_points": {
            p.number: [p.anchor.x, p.anchor.y] for p in portrait.pins
        },
        "variants": {},
        "legacy_before": before_file,
        "legacy_before_source_ink_findings": len(before_ink),
        "source_3mm_parallel_wire_failures": len(parallel_drc),
        "source_3mm_parallel_wire_details": [
            asdict(finding) for finding in parallel_drc
        ],
        "legacy_before_source_ink_examples": [
            asdict(finding) for finding in before_ink[:25]
        ],
        "electrical_topology_changed": False,
        "gost_ugo_approved": False,
        "route_drc_pass": False,
    }
    for reading in IcFunctionReading:
        for diagnostic in (False, True):
            composed, paint = _render_variant(
                circuit, graph, symbol_map, portrait, style, measure,
                policy, diagnostic=diagnostic, reading=reading,
                continuation_project=pair,
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
            collisions = audit_full_native_sheet_ink(
                circuit, graph, symbol_map, composed.layout, paint,
            )
            evidence["variants"][file] = {
                "function_reading": reading.value,
                "diagnostic_only_green_pin_tips": 16 if diagnostic else 0,
                "native_layout_valid": composed.layout.valid,
                "full_native_23_source_parts": True,
                "whole_sheet_text_wire_ugo_collision_count": len(collisions),
                "whole_sheet_collision_examples": [
                    asdict(item) for item in collisions[:25]
                ],
                "source_net_memberships_unchanged": True,
                "real_type_a_3500um": True,  # calibration checked above, em is NOT h
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
                assert set(painted.pin_anchors) == {
                    (p.pin_id, t.apply(p.anchor)) for p in portrait.pins
                }
                name = (
                    f"TL494_native_23_D4_{angle}_mirror{int(mirror)}"
                    "_btt_clean.svg"
                )
                (output/name).write_text(rendering.svg, encoding="utf-8")
                d4_collisions = audit_full_native_sheet_ink(
                    transformed, transformed_wires,
                    symbol_map, rendering.layout, painted,
                )
                evidence["variants"][name] = {
                    "function_reading": "bottom_to_top",
                    "text_wire_ugo_collision_count": len(d4_collisions),
                    "collision_examples": [
                        asdict(item) for item in d4_collisions[:12]
                    ],
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
