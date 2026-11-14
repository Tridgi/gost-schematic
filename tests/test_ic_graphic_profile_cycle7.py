"""Independent typed IC graphical profile; model-only cases run without PAINT.

Genuine PAINT #93 integration cases use its pinned OpenGost Type A source in
the dedicated two-repository workflow. All pin identities are SYNTHETIC.
"""
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from examples.review_ic_cycle7 import synthetic_ic
from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.electrical.ic import (
    IcBodyAxis,
    IcGraphicProfile,
    IcKind,
    IcPortLayout,
    IcTextAngle,
    resolve_ic_pin_positions,
    validate_ic_circuit,
)
from gost_schematic.electrical.ic_agent_snapshot import (
    snapshot_ic_for_agent,
    verify_agent_ic_snapshot,
)
from gost_schematic.electrical.ic_graphic_revision import (
    IcGeometryConsent,
    ic_record_fingerprint,
    revise_ic_text_orientation,
    validate_ic_graphic_revision,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord, ic_from_json, ic_to_json
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef

COUNTS = (8, 14, 40, 64)


def _network(record):
    ref = record.placements[0].component_ref
    total = record.device.package.pin_count
    return Circuit(
        (ComponentInstance(ref, record.device.identifier),),
        (
            Net("SIGNAL", (PinRef(ref, "1"),)),
            Net("SUPPLY", (PinRef(ref, str(total - 1)),)),
            Net("OC", (PinRef(ref, str(total - 2)),)),
        ),
    )


def _vertical_record(record):
    """Actual local TOP/BOTTOM physical sides; NOT a rotated LEFT/RIGHT SVG."""
    specs = []
    for spec in record.specs:
        width = (len(spec.rows) + 5) * 5000
        # Wider than nominal unrendered source so each local column is
        # interior; real Type A PAINT remains sole authority for final size.
        box = Box(0, 0, width, 65000)
        rows = []
        for index, row in enumerate(spec.rows, 1):
            role = record.device.pin_map[row.number].electrical_type.value
            side = (
                Side.TOP if role in ("input", "power_input", "bidirectional")
                else Side.BOTTOM
            )
            rows.append(replace(
                row, side=side, anchor=Point(
                    index * 5000,
                    -10000 if side is Side.TOP else box.max_y + 10000,
                ),
            ))
        specs.append(replace(
            spec, body=box, rows=tuple(rows), revision=spec.revision + 1,
            profile=replace(spec.profile, port_layout=IcPortLayout.TOP_BOTTOM),
        ))
    return IcLibraryRecord(record.device, tuple(specs), record.placements)


def test_opt_in_new_e3_portrait_pwm_preset_is_independent_and_not_legacy_default():
    selected = IcGraphicProfile.experimental_portrait_pwm()
    assert selected.port_layout is IcPortLayout.LEFT_RIGHT
    assert selected.body_axis is IcBodyAxis.PORTRAIT
    assert selected.function_angle is IcTextAngle.VERTICAL
    assert selected.other_text_angle is IcTextAngle.HORIZONTAL
    historic = IcGraphicProfile()
    assert historic.body_axis is IcBodyAxis.AUTO
    assert historic.function_angle is IcTextAngle.HORIZONTAL
    assert historic != selected


@pytest.mark.parametrize("kind", (IcKind.ANALOG, IcKind.DIGITAL))
@pytest.mark.parametrize("count", COUNTS)
def test_function_pwm_only_rotates_text_never_ports_or_graph(count, kind):
    record = synthetic_ic(count, kind)
    original_specs = tuple(replace(s, main_field="PWM") for s in record.specs)
    source = IcLibraryRecord(record.device, original_specs, record.placements)
    circuit = _network(source)
    validate_ic_circuit(source.device, circuit, kind.reference_prefix + "1")
    before = ic_to_json(source)
    horizontal_points = resolve_ic_pin_positions(
        source.device, source.specs, source.placements,
    )
    changed = revise_ic_text_orientation(source, IcTextAngle.VERTICAL)
    assert ic_to_json(source) == before
    assert changed.device is source.device
    assert changed.placements is source.placements
    assert circuit.nets == _network(source).nets
    assert all(
        s.main_field == "PWM"
        and s.profile.port_layout is IcPortLayout.LEFT_RIGHT
        and s.profile.function_angle is IcTextAngle.VERTICAL
        and s.profile.other_text_angle is IcTextAngle.HORIZONTAL
        and s.body == old.body and s.rows == old.rows
        for s, old in zip(changed.specs, source.specs, strict=True)
    )
    assert horizontal_points == resolve_ic_pin_positions(
        changed.device, changed.specs, changed.placements,
    )
    delta = validate_ic_graphic_revision(source, changed, circuit=circuit)
    assert delta.moved == () and delta.connected_moved == ()
    assert ic_from_json(ic_to_json(changed)) == changed
    assert json.loads(ic_to_json(changed))["schema_version"] == 2
    original_again = revise_ic_text_orientation(
        changed, IcTextAngle.HORIZONTAL,
    )
    assert all(s.main_field == "PWM" for s in original_again.specs)
    assert all(s.profile.function_angle is IcTextAngle.HORIZONTAL
               for s in original_again.specs)
    assert validate_ic_graphic_revision(
        changed, original_again, circuit=circuit,
    ).moved == ()


@pytest.mark.parametrize("kind", (IcKind.ANALOG, IcKind.DIGITAL))
@pytest.mark.parametrize("count", COUNTS)
def test_independent_top_bottom_profile_preserves_physical_graph(count, kind):
    source = synthetic_ic(count, kind)
    vertical = _vertical_record(source)
    circuit = _network(vertical)
    validate_ic_circuit(vertical.device, circuit, kind.reference_prefix + "1")
    points = resolve_ic_pin_positions(
        vertical.device, vertical.specs, vertical.placements,
    )
    rotated = revise_ic_text_orientation(vertical, IcTextAngle.VERTICAL)
    assert all(s.profile.port_layout is IcPortLayout.TOP_BOTTOM
               for s in rotated.specs)
    assert resolve_ic_pin_positions(
        rotated.device, rotated.specs, rotated.placements,
    ) == points
    assert validate_ic_graphic_revision(
        vertical, rotated, circuit=circuit,
    ).moved == ()
    assert ic_from_json(ic_to_json(rotated)) == rotated
    assert len(points) == count
    assert {p.number for p in vertical.device.pins} == {
        str(i) for i in range(1, count + 1)
    }


def test_profile_body_axis_and_strict_schema_reject_unsafe_input():
    source = synthetic_ic(8)
    spec = source.specs[0]
    with pytest.raises(TypeError, match="IC_TEXT_ANGLE_TYPED_REQUIRED"):
        replace(spec, profile=replace(spec.profile, function_angle=45))
    with pytest.raises(TypeError, match="IC_PORT_LAYOUT_TYPED_REQUIRED"):
        replace(spec, profile=replace(spec.profile, port_layout="top_bottom"))
    with pytest.raises(ValueError, match="IC_BODY_AXIS_GEOMETRY_MISMATCH"):
        replace(spec, profile=replace(
            spec.profile, body_axis=IcBodyAxis.PORTRAIT,
        ))
    tall = replace(spec, body=Box(0, 0, 60000, 180000), rows=tuple(
        replace(row, anchor=Point(
            row.anchor.x,
            5500 + index * 12000,
        )) for index, row in enumerate(spec.rows)
    ), profile=IcGraphicProfile(body_axis=IcBodyAxis.PORTRAIT))
    assert tall.body.max_y > tall.body.max_x
    assert tall.profile.function_angle is IcTextAngle.HORIZONTAL
    record = IcLibraryRecord(source.device, (tall,), source.placements)
    raw = json.loads(ic_to_json(record))
    assert raw["schema_version"] == 2
    for value in (90.0, True, "90", -90, 180):
        broken = json.loads(ic_to_json(record))
        broken["specs"][0]["graphic_profile"]["function_angle"] = value
        with pytest.raises((TypeError, ValueError)):
            ic_from_json(json.dumps(broken))
    broken = json.loads(ic_to_json(record))
    broken["specs"][0]["graphic_profile"].pop("other_text_angle")
    with pytest.raises(ValueError):
        ic_from_json(json.dumps(broken))
    assert ic_from_json(ic_to_json(record)) == record
    assert json.loads(ic_to_json(source))["schema_version"] == 1


@pytest.mark.parametrize("count", COUNTS)
def test_graphic_revision_gate_requires_exact_pin_specific_consent(count):
    source = synthetic_ic(count)
    candidate = IcLibraryRecord(
        source.device, tuple(replace(
            s, rows=tuple(replace(
                row, anchor=Point(
                    row.anchor.x + (-1000 if row.side is Side.LEFT else 1000),
                    row.anchor.y,
                ),
            ) for row in s.rows), revision=s.revision + 1,
        ) for s in source.specs), source.placements,
    )
    circuit = _network(source)
    with pytest.raises(ValueError, match="IC_GEOMETRY_REAUTHORIZATION_REQUIRED"):
        validate_ic_graphic_revision(source, candidate, circuit=circuit)
    original = resolve_ic_pin_positions(
        source.device, source.specs, source.placements,
    )
    updated = resolve_ic_pin_positions(
        candidate.device, candidate.specs, candidate.placements,
    )
    refs = tuple(sorted(original, key=lambda p: (p.reference, p.number)))
    assert all(updated[ref] != original[ref] for ref in refs)
    with pytest.raises(ValueError, match="IC_GEOMETRY_CONSENT_SOURCE_STALE"):
        validate_ic_graphic_revision(
            source, candidate, circuit=circuit,
            consent=IcGeometryConsent("0" * 64, refs),
        )
    with pytest.raises(ValueError, match="IC_CONNECTED_REROUTE_CONSENT_MISMATCH"):
        validate_ic_graphic_revision(
            source, candidate, circuit=circuit,
            consent=IcGeometryConsent(ic_record_fingerprint(source), refs),
        )
    connected = tuple(sorted(
        (ref for net in circuit.nets for ref in net.members),
        key=lambda p: (p.reference, p.number),
    ))
    consent = IcGeometryConsent(
        ic_record_fingerprint(source), refs, connected,
    )
    accepted = validate_ic_graphic_revision(
        source, candidate, circuit=circuit, consent=consent,
    )
    assert set(accepted.moved) == set(refs)
    assert set(accepted.connected_moved) == set(connected)
    assert source.device == candidate.device
    assert source.placements == candidate.placements
    assert circuit.nets == _network(source).nets


def test_text_only_and_geometry_revisions_fail_on_circuit_identity_mutation():
    record = synthetic_ic(14)
    new = revise_ic_text_orientation(record, IcTextAngle.VERTICAL)
    # IcLibraryRecord rejects a foreign device even before the revision
    # gate can be invoked: no phantom component or dropped physical pin.
    with pytest.raises(ValueError):
        IcLibraryRecord(
            replace(new.device, identifier="TEST_IC_DIGITAL_MALICIOUS"),
            new.specs, new.placements,
        )
    with pytest.raises(ValueError, match="IC_REVISION_PHYSICAL_IDENTITY_CHANGED"):
        validate_ic_graphic_revision(record, replace(
            new, placements=tuple(replace(
                p, origin=Point(p.origin.x + 10, p.origin.y),
            ) for p in new.placements),
        ))


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize("angle", (IcTextAngle.HORIZONTAL, IcTextAngle.VERTICAL))
def test_real_paint_two_text_poses_same_physical_lr_view(count, angle):
    paint = pytest.importorskip("gost_schematic.rendering.ic_rectangular")
    from gost_schematic.electrical.ic_paint_bridge import (
        bind_ic_paint_text_only,
        propose_ic_paint_binding,
    )
    from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
    from gost_schematic.standards.type_a_font import inspect_type_a_font

    font = os.environ.get("IC_TYPE_A_FONT_PATH")
    assert font and Path(font).is_file()
    style = inspect_type_a_font(Path(font), h_um=3500).style
    measure = PillowTextMeasurer()
    source = synthetic_ic(count)
    baseline = IcLibraryRecord(
        source.device,
        tuple(replace(s, main_field="PWM") for s in source.specs),
        source.placements,
    )
    fixed = propose_ic_paint_binding(baseline, style, measure)
    circuit = _network(fixed.record)
    orientation = revise_ic_text_orientation(fixed.record, angle)
    assert validate_ic_graphic_revision(
        fixed.record, orientation, circuit=circuit,
    ).moved == ()
    rebound = bind_ic_paint_text_only(fixed, orientation)
    assert rebound.record == orientation
    assert rebound.record.device is fixed.record.device
    assert all(a.body == b.body for a, b in zip(
        fixed.views, rebound.views, strict=True,
    ))
    assert all(a.pins == b.pins for a, b in zip(
        fixed.views, rebound.views, strict=True,
    ))
    for unit in rebound.views:
        rendered = paint.render_resolved_ic(unit, style, measure)
        assert len(rendered.pin_anchors) == len(unit.pins)
        assert any(ink.kind == "function" for ink in rendered.ink)


@pytest.mark.parametrize("count", COUNTS)
@pytest.mark.parametrize("angle", (IcTextAngle.HORIZONTAL, IcTextAngle.VERTICAL))
def test_real_paint_top_bottom_text_poses_preserve_true_physical_side(count, angle):
    paint = pytest.importorskip("gost_schematic.rendering.ic_rectangular")
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
    from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
    from gost_schematic.standards.type_a_font import inspect_type_a_font

    font = os.environ.get("IC_TYPE_A_FONT_PATH")
    assert font and Path(font).is_file()
    style = inspect_type_a_font(Path(font), h_um=3500).style
    measure = PillowTextMeasurer()
    raw = _vertical_record(synthetic_ic(count))
    revised = revise_ic_text_orientation(raw, angle)
    binding = propose_ic_paint_binding(revised, style, measure)
    assert all(v.orientation is paint.IcOrientation.TOP_BOTTOM
               for v in binding.views)
    binding.verify_endpoints()
    before = resolve_ic_pin_positions(
        binding.record.device, binding.record.specs, binding.record.placements,
    )
    view_changes = revise_ic_text_orientation(
        binding.record, (
            IcTextAngle.VERTICAL if angle is IcTextAngle.HORIZONTAL
            else IcTextAngle.HORIZONTAL
        ),
    )
    after = resolve_ic_pin_positions(
        view_changes.device, view_changes.specs, view_changes.placements,
    )
    assert before == after
    assert validate_ic_graphic_revision(
        binding.record, view_changes, circuit=_network(binding.record),
    ).moved == ()
    for view in binding.views:
        try:
            outcome = paint.render_resolved_ic(view, style, measure)
        except ValueError as error:
            # Text collision is a strict measured-ink BLOCKED case, never
            # a permission to silently move the physical pin to make it fit.
            assert any(x in str(error) for x in (
                "IC_TEXT_OVERFLOW", "IC_INK_COLLISION",
                "IC_GLYPH_INK_COLLISION", "IC_REFDES_UNPLACEABLE",
            )), str(error)
        else:
            assert len(outcome.pin_anchors) == len(view.pins)


@pytest.mark.parametrize("count", COUNTS)
def test_agent_lossless_ic_archive_keeps_nc_oc_power_units_and_nets(count):
    source = synthetic_ic(count)
    physical = _network(source)
    cached = physical.nets
    first = snapshot_ic_for_agent(source, physical)
    encoded = first.to_json()
    recovered = verify_agent_ic_snapshot(encoded, physical)
    assert recovered == first
    assert recovered.record == source
    assert recovered.record.device.units == source.device.units
    assert recovered.record.device.pins == source.device.pins
    assert len(recovered.record.device.units) == (2 if count >= 14 else 1)
    assert source.device.pin_map[str(count)].electrical_type.value == "nc"
    assert source.device.pin_map[str(count - 1)].electrical_type.value == "power_input"
    assert source.device.pin_map[str(count - 2)].electrical_type.value == "open_collector"
    assert physical.nets is cached
    assert all(not p.reference.endswith(".1") for net in physical.nets
               for p in net.members)
    # #96 ProjectService v1 cannot store multi-unit/NC via legacy PartDefinition.
    with pytest.raises(ValueError, match="IC_UNSAFE_LEGACY_ADAPTER"):
        source.device.to_legacy_part("unsafe-legacy-ic")


def test_agent_archive_corruption_wrong_nets_or_stale_revision_fails():
    record = synthetic_ic(14)
    circuit = _network(record)
    stored = snapshot_ic_for_agent(record, circuit).to_json()
    json_doc = json.loads(stored)
    json_doc["ic_record_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="IC_AGENT_RECORD_HASH_MISMATCH"):
        verify_agent_ic_snapshot(json.dumps(json_doc), circuit)
    json_doc = json.loads(stored)
    json_doc["connected_nets"][0]["numbers"][0] = "14"
    with pytest.raises(ValueError, match="IC_AGENT_NET_PINREF_INVALID"):
        verify_agent_ic_snapshot(json.dumps(json_doc), circuit)
    other = Circuit(
        circuit.components,
        (Net("CHANGED", (PinRef("DD1", "1"),)),),
    )
    with pytest.raises(ValueError, match="IC_AGENT_REAL_NET_MEMBERSHIP_CHANGED"):
        verify_agent_ic_snapshot(stored, other)
    with pytest.raises(ValueError, match="IC_AGENT_DUPLICATE_JSON_KEY"):
        verify_agent_ic_snapshot('{"format":"a","format":"b"}', circuit)
    with pytest.raises(ValueError, match="IC_AGENT_NONINTEGER_JSON"):
        verify_agent_ic_snapshot('{"format":1.0}', circuit)


def test_agent_archive_preserves_function_angle_v2_without_legacy_downcast():
    source = synthetic_ic(14)
    switched = revise_ic_text_orientation(source, IcTextAngle.VERTICAL)
    circuit = _network(switched)
    saved = snapshot_ic_for_agent(switched, circuit).to_json()
    loaded = verify_agent_ic_snapshot(saved, circuit)
    assert all(
        s.profile.function_angle is IcTextAngle.VERTICAL
        for s in loaded.record.specs
    )
    assert json.loads(ic_to_json(loaded.record))["schema_version"] == 2
    assert loaded.record.device.pin_map["14"].electrical_type.value == "nc"


@pytest.mark.parametrize("count", COUNTS)
def test_portrait_left_right_pwm_is_valid_in_model_with_two_text_angles(count):
    source = synthetic_ic(count)
    tall = IcLibraryRecord(
        source.device,
        tuple(replace(
            spec,
            body=Box(0, 0, 60000, 300000),
            main_field="PWM",
            profile=replace(spec.profile, body_axis=IcBodyAxis.PORTRAIT),
            revision=spec.revision + 1,
        ) for spec in source.specs),
        source.placements,
    )
    circuit = _network(tall)
    validate_ic_circuit(tall.device, circuit, "DD1")
    same_pin_refs = resolve_ic_pin_positions(
        tall.device, tall.specs, tall.placements,
    )
    angled = revise_ic_text_orientation(tall, IcTextAngle.VERTICAL)
    assert validate_ic_graphic_revision(
        tall, angled, circuit=circuit,
    ).moved == ()
    assert resolve_ic_pin_positions(
        angled.device, angled.specs, angled.placements,
    ) == same_pin_refs
    assert all(
        spec.profile.body_axis is IcBodyAxis.PORTRAIT
        and spec.profile.port_layout is IcPortLayout.LEFT_RIGHT
        and spec.profile.function_angle is IcTextAngle.VERTICAL
        and spec.profile.other_text_angle is IcTextAngle.HORIZONTAL
        and spec.body.max_y > spec.body.max_x
        and spec.main_field == "PWM"
        for spec in angled.specs
    )
    assert ic_from_json(ic_to_json(angled)) == angled
    assert angled.device.pin_map[str(count)].electrical_type.value == "nc"


@pytest.mark.parametrize("count", COUNTS)
def test_portrait_left_right_paint_0_and_90_contract_proof(count):
    paint = pytest.importorskip("gost_schematic.rendering.ic_rectangular")
    from gost_schematic.electrical.ic_paint_bridge import (
        bind_ic_paint_text_only,
        propose_ic_paint_binding,
    )
    from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
    from gost_schematic.standards.type_a_font import inspect_type_a_font

    font = os.environ.get("IC_TYPE_A_FONT_PATH")
    assert font and Path(font).is_file()
    style = inspect_type_a_font(Path(font), h_um=3500).style
    measure = PillowTextMeasurer()
    source = synthetic_ic(count)
    portrait = IcLibraryRecord(
        source.device,
        tuple(replace(
            spec, main_field="PWM",
            body=Box(0, 0, 60000, 300000),
            profile=replace(spec.profile, body_axis=IcBodyAxis.PORTRAIT),
            revision=spec.revision + 1,
        ) for spec in source.specs),
        source.placements,
    )
    horizontal = propose_ic_paint_binding(portrait, style, measure)
    assert all(
        spec.profile.body_axis is IcBodyAxis.PORTRAIT
        for spec in horizontal.record.specs
    )
    network = _network(horizontal.record)
    for view in horizontal.views:
        painted = paint.render_resolved_ic(view, style, measure)
        assert len(painted.pin_anchors) == len(view.pins)
    vertical_text = revise_ic_text_orientation(
        horizontal.record, IcTextAngle.VERTICAL,
    )
    assert validate_ic_graphic_revision(
        horizontal.record, vertical_text, circuit=network,
    ).moved == ()
    turned_view = bind_ic_paint_text_only(horizontal, vertical_text)
    assert all(a.pins == b.pins and a.body == b.body
               for a, b in zip(
                   horizontal.views, turned_view.views, strict=True,
               ))
    for angle, gallery in ((0, horizontal), (90, turned_view)):
        for view in gallery.views:
            painted = paint.render_resolved_ic(view, style, measure)
            assert len(painted.pin_anchors) == len(view.pins)
            assert view.function_rotation == angle


@pytest.mark.parametrize("count", (8, 14, 40, 64))
def test_real_paint_exports_measured_field_requirements_and_ink_guards(count):
    paint = pytest.importorskip("gost_schematic.rendering.ic_rectangular")
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding
    from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
    from gost_schematic.standards.type_a_font import inspect_type_a_font

    font = os.environ.get("IC_TYPE_A_FONT_PATH")
    assert font and Path(font).is_file()
    style = inspect_type_a_font(Path(font), h_um=3500).style
    measurer = PillowTextMeasurer()
    measured = propose_ic_paint_binding(synthetic_ic(count), style, measurer)
    measured.verify_endpoints()
    assert len(measured.requirements) == len(measured.views)
    for spec, required in zip(
        measured.record.specs, measured.requirements, strict=True,
    ):
        assert spec.unit_id == required.unit_id
        assert required.port_layout is IcPortLayout.LEFT_RIGHT
        assert spec.body.max_x - spec.body.min_x == required.body_width_um
        assert spec.body.max_y - spec.body.min_y == required.body_height_um
        assert required.main_field_min_dimension_um >= 15000
        assert required.external_lead_um >= 8000
        assert required.guard_um == 1000
    protected = measured.protected_text_areas(style, measurer)
    assert any(p.kind == "function" for p in protected)
    assert any(p.kind == "pin-number" for p in protected)
    for item in protected:
        assert item.unit_id in measured.unit_ids
        assert item.box.max_x > item.box.min_x
        assert item.box.max_y > item.box.min_y
    assert paint.IcOrientation.LEFT_RIGHT.value == (
        measured.views[0].orientation.value
    )
