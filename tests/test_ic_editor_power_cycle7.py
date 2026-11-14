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
