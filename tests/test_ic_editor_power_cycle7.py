"""Live source-typed IC hotspots, power modalities and long PWM D4 negatives.

Cross-owner PAINT tests run in pinned real Type A workflow. No mocked PAINT.
"""
import os
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_ic_cycle7 import synthetic_ic
from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.ic import (
    IcDeviceDefinition,
    IcGraphicProfile,
    IcKind,
    IcPinType,
    IcTextAngle,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_editor_targets import (
    IcEditorContactManifest,
    make_ic_editor_manifest,
    make_paint_editor_targets,
    render_ic_editor_review,
    verify_ic_editor_manifest,
)
from gost_schematic.electrical.ic_graphic_revision import (
    IcGeometryConsent,
    ic_record_fingerprint,
    revise_ic_text_orientation,
    validate_ic_graphic_revision,
)
from gost_schematic.electrical.ic_power_presentation import (
    IcPowerMeaning,
    IcPowerMode,
    IcPowerPinLabel,
    IcPowerPresentation,
    validate_ic_power_presentation,
    validate_ic_power_sheet_modes,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef

SIZES = (8, 14, 40, 64)


def _mixed_record(count, kind=IcKind.DIGITAL):
    source = synthetic_ic(count, kind)
    changes = {
        "2": (IcPinType.INPUT, "VCC"),  # Label VCC != power and creates NO Net
        "3": (IcPinType.BIDIRECTIONAL, "IO"),
        "4": (IcPinType.POWER_OUTPUT, "OUT_SUPPLY"),
        str(count - 3): (IcPinType.PASSIVE, "RETURN"),
    }
    device = replace(source.device, pins=tuple(
        replace(pin, electrical_type=changes[pin.number][0],
                name=changes[pin.number][1])
        if pin.number in changes else pin for pin in source.device.pins
    ))
    return IcLibraryRecord(device, source.specs, source.placements)


def _network(record):
    ref = record.placements[0].component_ref
    return Circuit(
        (ComponentInstance(ref, record.device.identifier),),
        (
            Net("REAL_SIGNAL", (PinRef(ref, "3"),)),
            Net("REAL_POWER", (PinRef(ref, str(
                record.device.package.pin_count - 1,
            )),)),
            Net("REAL_OC", (PinRef(ref, str(
                record.device.package.pin_count - 2,
            )),)),
        ),
    )


def _power_plan(record, mode, host_unit=None):
    units = {
        p.number: unit.id for unit in record.device.units
        for p in record.device.pins if p.number in unit.pin_numbers
    }
    n = record.device.package.pin_count
    supply = "U" if record.device.kind is IcKind.ANALOG else "VCC"
    common = "OV" if record.device.kind is IcKind.ANALOG else "GND"
    return IcPowerPresentation(
        record.device.identifier,
        record.placements[0].component_ref,
        mode,
        (
            IcPowerPinLabel(str(n - 1), units[str(n - 1)],
                            IcPowerMeaning.SUPPLY, supply),
            IcPowerPinLabel(str(n - 3), units[str(n - 3)],
                            IcPowerMeaning.COMMON, common),
            IcPowerPinLabel("4", units["4"],
                            IcPowerMeaning.SUPPLY_OUTPUT, "OUT_SUPPLY"),
        ),
        host_unit_id=host_unit,
    )


@pytest.mark.parametrize("count", SIZES)
@pytest.mark.parametrize("kind", (IcKind.ANALOG, IcKind.DIGITAL))
@pytest.mark.parametrize("mode", (
    IcPowerMode.NONLOGICAL_SIDE, IcPowerMode.FREE_SHEET_TEXT,
    IcPowerMode.COMMON_CONTROL, IcPowerMode.IN_ONE_SECTION,
    IcPowerMode.SEPARATE_OUTLINE,
))
def test_power_modes_keep_real_physical_pin_numbers(count, kind, mode):
    record = _mixed_record(count, kind)
    if mode is IcPowerMode.IN_ONE_SECTION and len(record.device.units) == 1:
        return
    host = (
        record.device.units[0].id
        if mode is IcPowerMode.IN_ONE_SECTION else None
    )
    plan = _power_plan(record, mode, host)
    network = _network(record)
    old = network.nets
    validate_ic_power_presentation(plan, record, circuit=network)
    assert network.nets is old
    assert record.device.pin_map[str(count)].electrical_type is IcPinType.NC
    assert record.device.pin_map[str(count - 2)].electrical_type is (
        IcPinType.OPEN_COLLECTOR
    )
    assert record.device.pin_map["4"].electrical_type is IcPinType.POWER_OUTPUT
    assert not any(
        entry.physical_number == str(count)
        for entry in plan.labels
    )
    assert all(entry.unit_id in {u.id for u in record.device.units}
               for entry in plan.labels)


@pytest.mark.parametrize("kind", (IcKind.DIGITAL, IcKind.ANALOG))
def test_power_experimental_tb_is_editorial_only_not_normative(kind):
    record = _mixed_record(14, kind)
    sample = _power_plan(record, IcPowerMode.EXPERIMENTAL_TOP_BOTTOM_RAILS)
    with pytest.raises(ValueError, match="IC_EXPERIMENTAL_TOP_BOTTOM_NOT_NORMATIVE"):
        validate_ic_power_presentation(sample, record)
    validate_ic_power_presentation(
        sample, record, experimental_preview=True,
    )
    with pytest.raises(ValueError, match="IC_EXPERIMENTAL_POWER_NOT_NORMATIVE_SHEET"):
        validate_ic_power_sheet_modes((sample,))
    # This does not edit the actual LEFT/RIGHT rows.
    assert all(row.side in (Side.LEFT, Side.RIGHT)
               for spec in record.specs for row in spec.rows)


def test_power_fig6_a_b_and_a_c_but_never_mix_b_c():
    record = _mixed_record(14)
    a = _power_plan(record, IcPowerMode.COMMON_CONTROL)
    b = _power_plan(record, IcPowerMode.IN_ONE_SECTION, "U1")
    c = _power_plan(record, IcPowerMode.SEPARATE_OUTLINE)
    validate_ic_power_sheet_modes((a, b))
    validate_ic_power_sheet_modes((a, c))
    with pytest.raises(ValueError, match="IC_POWER_FIG6_B_AND_C"):
        validate_ic_power_sheet_modes((a, b, c))


@pytest.mark.parametrize("kind", (IcKind.ANALOG, IcKind.DIGITAL))
def test_power_labels_cannot_synthesize_pinout_or_net(kind):
    record = _mixed_record(14, kind)
    original = _power_plan(record, IcPowerMode.COMMON_CONTROL)
    with pytest.raises(ValueError, match="IC_POWER_UNKNOWN_PHYSICAL_NUMBER"):
        validate_ic_power_presentation(
            replace(original, labels=(
                *original.labels[:-1],
                replace(original.labels[-1], physical_number="99"),
            )), record,
        )
    with pytest.raises(ValueError, match="IC_POWER_WRONG_PHYSICAL_UNIT"):
        validate_ic_power_presentation(
            replace(original, labels=(
                replace(
                    original.labels[0],
                    unit_id=record.device.units[0].id,
                ),
                *original.labels[1:],
            )) if original.labels[0].unit_id != record.device.units[0].id
            else replace(original, labels=(
                replace(original.labels[0], unit_id="UNKNOWN"),
                *original.labels[1:],
            )), record,
        )
    if kind is IcKind.ANALOG:
        with pytest.raises(ValueError, match="IC_ANALOG_COMMON_LABEL_MUST_BE_OV"):
            validate_ic_power_presentation(replace(original, labels=(
                original.labels[0],
                replace(original.labels[1], label="GND"),
                original.labels[2],
            )), record)
    with pytest.raises(ValueError, match="IC_POWER_REQUIRED_SUPPLY_PIN_MISSING"):
        validate_ic_power_presentation(
            replace(original, labels=original.labels[1:]), record,
        )
    assert all(net.name != "VCC" for net in _network(record).nets)


def _actual_renderer():
    pytest.importorskip("gost_schematic.rendering.ic_rectangular")
    from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
    from gost_schematic.standards.type_a_font import inspect_type_a_font

    font = os.environ.get("IC_TYPE_A_FONT_PATH")
    assert font and Path(font).is_file()
    return inspect_type_a_font(Path(font), h_um=3500).style, PillowTextMeasurer()


@pytest.mark.parametrize("count", SIZES)
@pytest.mark.parametrize("kind", (IcKind.DIGITAL, IcKind.ANALOG))
def test_real_editor_complete_targets_and_clean_svg(count, kind):
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding

    style, measurer = _actual_renderer()
    record = _mixed_record(count, kind)
    binding = propose_ic_paint_binding(record, style, measurer)
    circuit = _network(binding.record)
    untouched = circuit.nets
    manifest = make_ic_editor_manifest(binding, circuit)
    assert len(manifest.contacts) == count
    assert len({c.pin_ref for c in manifest.contacts}) == count
    assert {c.unit_id for c in manifest.contacts} == {
        u.id for u in binding.record.device.units
    }
    verify_ic_editor_manifest(binding, manifest, circuit)
    targets = make_paint_editor_targets(binding, manifest, circuit)
    assert sum(len(items) for items in targets) == count
    nc = next(c for c in manifest.contacts
              if c.electrical_type is IcPinType.NC)
    assert not nc.connectable and nc.net_id is None
    assert nc.reason == "NC_PHYSICAL_PIN"
    power = next(c for c in manifest.contacts
                 if c.electrical_type is IcPinType.POWER_INPUT)
    assert power.connectable and power.net_id == "REAL_POWER"
    output_supply = next(c for c in manifest.contacts
                         if c.electrical_type is IcPinType.POWER_OUTPUT)
    assert output_supply.connectable and output_supply.net_id is None
    oc = next(c for c in manifest.contacts
              if c.electrical_type is IcPinType.OPEN_COLLECTOR)
    assert oc.role == "out" and oc.net_id == "REAL_OC"
    bidir = next(c for c in manifest.contacts
                 if c.electrical_type is IcPinType.BIDIRECTIONAL)
    assert bidir.role == "bidir" and bidir.net_id == "REAL_SIGNAL"
    labelled_vcc = next(c for c in manifest.contacts
                        if c.physical_number == "2")
    assert labelled_vcc.pin_name == "VCC"
    assert labelled_vcc.electrical_type is IcPinType.INPUT
    assert labelled_vcc.net_id is None

    diagnostic = render_ic_editor_review(
        binding, style, measurer, circuit=circuit, diagnostics=True,
    )
    clean = render_ic_editor_review(
        binding, style, measurer, circuit=circuit, diagnostics=False,
    )
    assert circuit.nets is untouched
    refs = {}
    for preview, no_markup, view in zip(
        diagnostic, clean, binding.views, strict=True,
    ):
        source = ET.fromstring(preview.svg)
        bare = ET.fromstring(no_markup.svg)
        markers = [
            node for node in source.iter()
            if node.attrib.get("data-layer") == "editor-connection-targets"
        ]
        assert len(markers) == 1
        clean_markers = [
            node for node in bare.iter()
            if node.attrib.get("data-layer") == "editor-connection-targets"
        ]
        assert not clean_markers
        visible = [node for node in markers[0] if node.tag.endswith("rect")]
        assert len(visible) == len(view.pins)
        for node in visible:
            name = node.attrib["data-pin-ref"]
            assert name not in refs
            refs[name] = node.attrib
        assert "editor-connection-targets" not in no_markup.svg
    assert len(refs) == count
    for contact in manifest.contacts:
        row = refs[f"{contact.pin_ref.reference}.{contact.pin_ref.number}"]
        assert row["data-connectable"] == str(contact.connectable).lower()
        assert row["data-net-id"] == (contact.net_id or "")
        assert row["data-reason"] == (contact.reason or "")
        assert row["fill"] == (
            "#148645" if contact.connectable else "#8b1e27"
        )


@pytest.mark.parametrize("count", SIZES)
def test_real_editor_rejects_1um_wrong_ref_wrong_unit_duplicates_and_fake_net(count):
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding

    style, measurer = _actual_renderer()
    record = _mixed_record(count)
    binding = propose_ic_paint_binding(record, style, measurer)
    circuit = _network(binding.record)
    original_nets = circuit.nets
    manifest = make_ic_editor_manifest(binding, circuit)
    head, tail = manifest.contacts[0], manifest.contacts[1:]
    bad = replace(head, anchor=Point(head.anchor.x + 1, head.anchor.y))
    with pytest.raises(ValueError, match="IC_EDITOR_PINREF_ENDPOINT_MISMATCH"):
        verify_ic_editor_manifest(
            binding, IcEditorContactManifest((bad, *tail)), circuit,
        )
    with pytest.raises(ValueError, match="IC_EDITOR_FOREIGN_PHYSICAL_PINREF"):
        verify_ic_editor_manifest(
            binding, IcEditorContactManifest((
                replace(head, component_ref="DD999",
                        pin_ref=PinRef("DD999", head.physical_number)),
                *tail,
            )), circuit,
        )
    with pytest.raises(ValueError, match="IC_EDITOR_WRONG_LOGICAL_UNIT"):
        verify_ic_editor_manifest(
            binding, IcEditorContactManifest((
                replace(head, unit_id="UNRELATED"), *tail,
            )), circuit,
        )
    with pytest.raises(ValueError, match="IC_EDITOR_DUPLICATE_PHYSICAL_CONTACT"):
        IcEditorContactManifest((head, head, *tail))
    with pytest.raises(ValueError, match="IC_EDITOR_INCOMPLETE_TARGETS"):
        verify_ic_editor_manifest(
            binding, IcEditorContactManifest(tail), circuit,
        )
    with pytest.raises(ValueError, match="IC_EDITOR_CONTACT_SEMANTIC_OR_NET_MISMATCH"):
        verify_ic_editor_manifest(
            binding, IcEditorContactManifest((
                replace(head, net_id="INFERRED_VCC_NET"), *tail,
            )), circuit,
        )
    nc = next(c for c in manifest.contacts
              if c.electrical_type is IcPinType.NC)
    with pytest.raises(ValueError, match="IC_EDITOR_NC_MUST_BE_DISABLED"):
        replace(nc, connectable=True)
    assert circuit.nets is original_nets


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirrored", (False, True))
def test_long_pwm_controller_shared_body_two_angles_all_d4(rotation, mirrored):
    from gost_schematic.electrical.ic_paint_bridge import (
        bind_ic_paint_text_only,
        propose_ic_paint_binding,
    )
    from gost_schematic.rendering.ic_rectangular import render_resolved_ic

    style, measurer = _actual_renderer()
    source = _mixed_record(8)
    placements = tuple(replace(
        p, transform=Transform(rotation, mirrored),
    ) for p in source.placements)
    specs = tuple(replace(
        spec, body=Box(0, 0, 60000, 300000),
        main_field="PWM_CONTROLLER",
        profile=IcGraphicProfile.experimental_portrait_pwm(),
    ) for spec in source.specs)
    record = IcLibraryRecord(source.device, specs, placements)
    proposed = propose_ic_paint_binding(record, style, measurer)
    network = _network(proposed.record)
    initial_nets = network.nets
    turned = revise_ic_text_orientation(
        proposed.record, IcTextAngle.HORIZONTAL,
    )
    diff = validate_ic_graphic_revision(
        proposed.record, turned, circuit=network,
    )
    assert not diff.moved and not diff.connected_moved
    second = bind_ic_paint_text_only(proposed, turned)
    assert resolve_ic_pin_positions(
        proposed.record.device, proposed.record.specs,
        proposed.record.placements,
    ) == resolve_ic_pin_positions(
        second.record.device, second.record.specs,
        second.record.placements,
    )
    for view1, view0 in zip(proposed.views, second.views, strict=True):
        assert view1.body == view0.body
        assert view1.pins == view0.pins
        v = render_resolved_ic(view1, style, measurer)
        h = render_resolved_ic(view0, style, measurer)
        assert v.pin_anchors == h.pin_anchors
        assert v.body_world == h.body_world
    assert network.nets is initial_nets


def test_new_graphic_revision_long_word_requires_explicit_contact_consent():
    from gost_schematic.electrical.ic_paint_bridge import propose_ic_paint_binding

    style, measurer = _actual_renderer()
    record = _mixed_record(8)
    long_source = IcLibraryRecord(
        record.device,
        tuple(replace(s, main_field="PWM_CONTROLLER",
                      body=Box(0, 0, 60000, 300000),
                      profile=IcGraphicProfile.experimental_portrait_pwm())
              for s in record.specs),
        record.placements,
    )
    proposed = propose_ic_paint_binding(long_source, style, measurer)
    circuit = _network(long_source)
    with pytest.raises(ValueError, match="IC_GEOMETRY_REAUTHORIZATION_REQUIRED"):
        validate_ic_graphic_revision(
            long_source, proposed.record, circuit=circuit,
        )
    before = resolve_ic_pin_positions(
        long_source.device, long_source.specs, long_source.placements,
    )
    after = resolve_ic_pin_positions(
        proposed.record.device, proposed.record.specs,
        proposed.record.placements,
    )
    moved = tuple(ref for ref in before if before[ref] != after[ref])
    connected = tuple(ref for ref in moved if any(
        ref in net.members for net in circuit.nets
    ))
    permit = IcGeometryConsent(ic_record_fingerprint(long_source),
                               moved, connected)
    accepted = validate_ic_graphic_revision(
        long_source, proposed.record, circuit=circuit, consent=permit,
    )
    assert accepted.moved == moved
    assert accepted.connected_moved == connected
    assert circuit.nets == _network(long_source).nets
