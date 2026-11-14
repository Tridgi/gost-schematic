"""Issue #110 TI pinout vs real manufacturer source, aliases, PNG and D4.

Must not use ERC result as pinout truth, nor treat SVG text as real Net.
"""
import json
import os
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.core.geometry import Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.ic import (
    IcPinType,
    IcTextAngle,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_graphic_revision import (
    revise_ic_text_orientation,
    validate_ic_graphic_revision,
)
from gost_schematic.electrical.ic_pin_alias import (
    IcPinAliasProfile,
    IcPinDisplayOrientation,
    verify_alias_display,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord, ic_from_json, ic_to_json
from gost_schematic.electrical.tl494cn import (
    TI_DATA_SHEET,
    TI_E3_LEFT,
    TI_E3_RIGHT,
    TI_PHYSICAL_PINS,
    TI_REVISION,
    TI_SHORT_LABELS,
    IcFunctionReading,
    tl494cn_alias_profile,
    tl494cn_device,
    tl494cn_record,
    tl494cn_unwired_circuit,
    verify_tl494cn_ti_pinout,
)
from gost_schematic.model.circuit import PinRef
from gost_schematic.model.pins import ElectricalType


def test_ti_authoritative_pin_numbers_names_io_and_package():
    device = tl494cn_device()
    verify_tl494cn_ti_pinout(device)
    assert device.package.datasheet_url == TI_DATA_SHEET
    assert device.package.revision == TI_REVISION
    assert len(device.pin_map) == 16
    assert {int(n) for n in device.pin_map} == set(range(1, 17))
    # Table 4-1: I pin 3, I pin 13, O terminal pins 8/9/10/11/14.
    for number in ("1", "2", "3", "4", "13", "15", "16"):
        assert device.pin_map[number].electrical_type is IcPinType.INPUT
    assert device.pin_map["3"].name == "FEEDBACK"
    assert device.pin_map["13"].name == "OUTPUT CTRL"
    assert device.pin_map["14"].electrical_type is IcPinType.POWER_OUTPUT
    for number in ("8", "9", "10", "11"):
        assert device.pin_map[number].electrical_type is IcPinType.OUTPUT
    for number in ("5", "6"):
        assert device.pin_map[number].electrical_type is IcPinType.PASSIVE
    for number in ("7", "12"):
        assert device.pin_map[number].electrical_type is IcPinType.POWER_INPUT
    assert len(TI_PHYSICAL_PINS) == 16


@pytest.mark.parametrize("number", tuple(str(n) for n in range(1, 17)))
def test_all_16_ti_source_records_are_exact(number):
    pin = tl494cn_device().pin_map[number]
    expected = TI_PHYSICAL_PINS[int(number)-1]
    assert (pin.number, pin.name, pin.function, pin.electrical_type) == expected
    profile = tl494cn_alias_profile()
    a = next(a for a in profile.labels if a.physical_number == number)
    assert a.real_pin_ref == PinRef("DA1", number)
    assert a.manufacturer_pin_name == expected[1]
    assert a.electrical_type is expected[3]
    assert a.schematic_short_label == TI_SHORT_LABELS[number]
    assert len(a.schematic_short_label) <= 6
    assert a.source_document_reference == TI_DATA_SHEET + "#page=3"


def test_historical_example_pins_feedback_input_even_when_erc_green():
    from examples.tl494_ic_paint_reference import PINS

    assert PINS["3"] == ("FEEDBACK", ElectricalType.INPUT)
    assert PINS["13"] == ("OUTPUT CTRL", ElectricalType.INPUT)
    assert PINS["14"] == ("REF", ElectricalType.POWER_OUTPUT)
    assert PINS["8"] == ("C1", ElectricalType.OUTPUT)
    assert len(PINS) == 16


@pytest.mark.parametrize("number,wrong_type", (
    ("3", IcPinType.OUTPUT), ("13", IcPinType.OUTPUT),
    ("12", IcPinType.OUTPUT), ("14", IcPinType.INPUT),
    ("5", IcPinType.INPUT), ("8", IcPinType.INPUT),
    ("7", IcPinType.OUTPUT), ("1", IcPinType.BIDIRECTIONAL),
))
def test_corrupt_ti_physical_electrical_roles_fail_without_erc(number, wrong_type):
    device = tl494cn_device()
    changed = replace(device, pins=tuple(
        replace(pin, electrical_type=wrong_type)
        if pin.number == number else pin for pin in device.pins
    ))
    with pytest.raises(ValueError, match="TL494_TI_PIN_FUNCTION_OR_ELECTRICAL_TYPE"):
        verify_tl494cn_ti_pinout(changed)


@pytest.mark.parametrize("number,new_name", (
    ("3", "FB"), ("13", "OC"), ("8", "E1"), ("14", "VCC"),
))
def test_manufacturer_name_cannot_be_overwritten_by_short_label(number, new_name):
    device = tl494cn_device()
    bad = replace(device, pins=tuple(
        replace(pin, name=new_name) if pin.number == number else pin
        for pin in device.pins
    ))
    with pytest.raises(ValueError, match="TL494_TI_PIN_FUNCTION_OR_ELECTRICAL_TYPE"):
        verify_tl494cn_ti_pinout(bad)


def test_profile_short_labels_are_exact_and_no_silent_truncation():
    profile = tl494cn_alias_profile()
    assert profile.max_display_chars == 6
    assert len(profile.labels) == 16
    assert profile.labels[2].schematic_short_label == "FB"
    assert profile.labels[2].manufacturer_pin_name == "FEEDBACK"
    assert profile.labels[12].schematic_short_label == "OC"
    assert profile.labels[12].manufacturer_pin_name == "OUTPUT CTRL"
    labels = tuple(a.schematic_short_label for a in profile.labels)
    assert len(set(labels)) == 16
    assert max(len(n) for n in labels) <= 6
    assert all(a.display_orientation is IcPinDisplayOrientation.HORIZONTAL
               for a in profile.labels)


@pytest.mark.parametrize("new_label", ("TOOLONG", "КОМАНДА", "OUTPUTCTRL"))
def test_alias_seven_or_more_characters_rejected(new_label):
    profile = tl494cn_alias_profile()
    edited = (replace(
        profile.labels[2], schematic_short_label=new_label,
    ), *profile.labels[3:])
    with pytest.raises(ValueError, match="IC_ALIAS_TOO_LONG_NO_TRUNCATION"):
        IcPinAliasProfile(
            profile.component_ref, profile.device_id,
            (*profile.labels[:2], *edited), 6,
        )


def test_alias_six_char_boundary_is_allowed_but_not_an_inferred_pin():
    profile = tl494cn_alias_profile()
    changed = replace(profile.labels[2], schematic_short_label="ABCDEF")
    custom = replace(profile, labels=(
        *profile.labels[:2], changed, *profile.labels[3:],
    ))
    custom.validate_device(tl494cn_device())
    assert custom.labels[2].schematic_short_label == "ABCDEF"
    assert custom.labels[2].manufacturer_pin_name == "FEEDBACK"


def test_alias_duplicate_casefold_wrong_ref_source_role_rejected():
    profile = tl494cn_alias_profile()
    with pytest.raises(ValueError, match="IC_ALIAS_DUPLICATE_LABEL"):
        replace(profile, labels=(
            *profile.labels[:2],
            replace(profile.labels[2], schematic_short_label="dtc"),
            *profile.labels[3:],
        ))
    with pytest.raises(ValueError, match="IC_ALIAS_FOREIGN_PINREF"):
        replace(profile, labels=(
            replace(profile.labels[0], real_pin_ref=PinRef("DA99", "1")),
            *profile.labels[1:],
        )).validate_device(tl494cn_device())
    with pytest.raises(ValueError, match="IC_ALIAS_MANUFACTURER_SEMANTIC_MISMATCH"):
        replace(profile, labels=(
            *profile.labels[:2],
            replace(profile.labels[2], electrical_type=IcPinType.OUTPUT),
            *profile.labels[3:],
        )).validate_device(tl494cn_device())
    with pytest.raises(ValueError, match="IC_ALIAS_SOURCE_DOCUMENT_MISMATCH"):
        replace(profile, labels=(
            *profile.labels[:2],
            replace(profile.labels[2],
                    source_document_reference="https://fake.example/pinout"),
            *profile.labels[3:],
        )).validate_device(tl494cn_device())


def test_alias_is_explicit_new_graphic_revision_never_physical_change():
    record, profile = tl494cn_record()
    before = resolve_ic_pin_positions(
        record.device, record.specs, record.placements,
    )
    newer = replace(profile, labels=(
        *profile.labels[:2],
        replace(profile.labels[2], schematic_short_label="FDBK"),
        *profile.labels[3:],
    )).apply_to_record(record)
    assert newer.specs[0].revision == record.specs[0].revision + 1
    assert newer.device is record.device
    assert resolve_ic_pin_positions(
        newer.device, newer.specs, newer.placements,
    ) == before
    assert newer.specs[0].rows[2].label == "FDBK"
    assert newer.device.pin_map["3"].name == "FEEDBACK"
    verify_alias_display(profile, record)
    with pytest.raises(ValueError, match="IC_ALIAS_GRAPHIC_TEXT_MISMATCH"):
        verify_alias_display(profile, newer)


def test_tl494_source_authored_pin_sides_locked_and_16_pinref_json_roundtrip():
    record, profile = tl494cn_record()
    verify_alias_display(profile, record)
    refs = resolve_ic_pin_positions(record.device, record.specs, record.placements)
    assert len(refs) == 16
    assert all(ref.reference == "DA1" for ref in refs)
    side_to_numbers = {
        side: tuple(row.number for row in record.specs[0].rows
                    if row.side is side)
        for side in (Side.LEFT, Side.RIGHT)
    }
    assert side_to_numbers[Side.LEFT] == TI_E3_LEFT
    assert side_to_numbers[Side.RIGHT] == TI_E3_RIGHT
    assert len(set(refs.values())) == 16
    assert record == ic_from_json(ic_to_json(record))
    circuit = tl494cn_unwired_circuit(record)
    assert circuit.nets == ()
    assert circuit.components[0].part_id == record.device.identifier


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirrored", (False, True))
def test_all_d4_word_only_never_mutates_pinrefs_numbering_net(rotation, mirrored):
    base, profile = tl494cn_record()
    pose = tuple(replace(place, transform=Transform(rotation, mirrored))
                 for place in base.placements)
    record = IcLibraryRecord(base.device, base.specs, pose)
    before = resolve_ic_pin_positions(record.device, record.specs, record.placements)
    horizontal = revise_ic_text_orientation(record, IcTextAngle.HORIZONTAL)
    vertical = revise_ic_text_orientation(
        horizontal, IcTextAngle.BOTTOM_TO_TOP,
    )
    for candidate in (horizontal, vertical):
        assert resolve_ic_pin_positions(
            candidate.device, candidate.specs, candidate.placements,
        ) == before
        assert candidate.device is record.device
    assert not validate_ic_graphic_revision(record, horizontal).moved
    assert not validate_ic_graphic_revision(horizontal, vertical).moved
    assert len(profile.labels) == 16


def test_bottom_to_top_sign_is_svg_y_up_and_opposite_is_blocked():
    assert IcFunctionReading.BOTTOM_TO_TOP.physical_graphic_angle == (
        IcTextAngle.VERTICAL
    )
    assert Transform(270).apply(Point(1, 0)) == Point(0, -1)
    with pytest.raises(ValueError, match="IC_FUNCTION_WRONG_READING_DIRECTION"):
        _ = IcFunctionReading.TOP_TO_BOTTOM_UNSUPPORTED.physical_graphic_angle


def test_tl494_source_symbol_body_always_portrait():
    record, _ = tl494cn_record()
    spec = record.specs[0]
    assert spec.body.max_y - spec.body.min_y > (
        spec.body.max_x - spec.body.min_x
    )
    assert spec.main_field == "PWM"
    assert len(spec.rows) == 16
    assert spec.profile.function_angle is IcTextAngle.BOTTOM_TO_TOP


def _actual_font():
    pytest.importorskip("gost_schematic.rendering.ic_rectangular")
    source = os.environ.get("IC_TYPE_A_FONT_PATH")
    if source is None:
        pytest.skip("real pinned Type A font only in cross-PR workflow")
    font = Path(source)
    assert font.is_file()
    return font


def test_tl494_real_paint_two_word_poses_16_targets_no_ink_overflow():
    font = _actual_font()
    paint = pytest.importorskip("gost_schematic.rendering.ic_rectangular")
    from examples.tl494_ic_paint_reference import build
    from gost_schematic.electrical.ic_editor_targets import (
        make_ic_editor_manifest,
        make_paint_editor_targets,
    )

    render_resolved_ic = paint.render_resolved_ic
    upright, horizontal, circuit, aliases, style, metrics, face = build(font)
    assert face.style.font_sha256 == style.font_sha256
    verify_alias_display(aliases, upright.record)
    before = resolve_ic_pin_positions(
        upright.record.device, upright.record.specs, upright.record.placements,
    )
    assert before == resolve_ic_pin_positions(
        horizontal.record.device, horizontal.record.specs,
        horizontal.record.placements,
    )
    assert not upright.side_reflows
    actual = make_ic_editor_manifest(upright, circuit)
    target_sets = make_paint_editor_targets(upright, actual, circuit)
    assert len(actual.contacts) == len(target_sets[0]) == 16
    for a, b in zip(upright.views, horizontal.views, strict=True):
        high = render_resolved_ic(
            a, style, metrics, editor_targets=target_sets[0],
            editor_overlay=True,
        )
        flat = render_resolved_ic(b, style, metrics)
        assert high.pin_anchors == flat.pin_anchors
        assert high.body_world == flat.body_world
        for preview in (high, flat):
            root = ET.fromstring(preview.svg)
            leads = [
                node for g in root.iter()
                if g.get("data-layer") == "ic-physical-pin-leads"
                for node in g
            ]
            assert len(leads) == 16
            assert {node.get("data-pin-number") for node in leads} == {
                str(i) for i in range(1, 17)
            }
        assert "editor-connection-targets" not in flat.svg
    assert circuit.nets == ()


def test_real_gallery_has_four_signed_print_schemas(tmp_path):
    font = _actual_font()
    from examples.tl494_ic_paint_reference import generate

    manifest = generate(tmp_path, font)
    assert manifest["physical_count"] == 16
    assert manifest["types"]["3"] == "input"
    assert manifest["short_labels"]["3"] == "FB"
    assert manifest["short_labels"]["13"] == "OC"
    assert manifest["net_assignment_verified"] is False
    assert len(manifest["variants"]) == 4
    assert len(list(tmp_path.glob("*.svg"))) == 4
    assert json.loads(
        (tmp_path / "TL494CN_ic_manifest.json").read_text()
    ) == manifest
