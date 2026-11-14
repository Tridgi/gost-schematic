"""Texas Instruments TL494CN 16 physical pins (SLVS074J §4 table 4-1).

SOURCE-FAITHFUL pinout but DRAFT E3 drawing; no generic GOST certification.
Schematic view is source-authored, not a product footprint or auto-router.
"""
from enum import Enum

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.electrical.ic import (
    IcBodyAxis,
    IcDeviceDefinition,
    IcGraphicProfile,
    IcKind,
    IcPackage,
    IcPhysicalPin,
    IcPinRow,
    IcPinType,
    IcPortLayout,
    IcSymbolSpec,
    IcTextAngle,
    IcUnit,
    IcUnitPlacement,
    PinoutOrigin,
)
from gost_schematic.electrical.ic_pin_alias import (
    IcPinAliasProfile,
    IcPinDisplayAlias,
    IcPinDisplayOrientation,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord
from gost_schematic.model.circuit import Circuit, ComponentInstance, PinRef

TI_DATA_SHEET = "https://www.ti.com/lit/ds/symlink/tl494.pdf"
TI_PIN_TABLE = TI_DATA_SHEET + "#page=3"
TI_REVISION = "SLVS074J, September 2026"
TI_DEVICE_ID = "ti.tl494cn.pdip16"

# Exact manufacturer numbers/names, TI I/O and descriptions; generic CT/RT
# and GND/VCC have type dash in TI table, so model subtypes are editorial.
# TL494 Rev.J calls C/E terminals O; pin 3 and pin 13 unequivocally I.
TI_PHYSICAL_PINS: tuple[tuple[str, str, str, IcPinType], ...] = (
    ("1", "1IN+", "Noninverting input to error amplifier 1", IcPinType.INPUT),
    ("2", "1IN-", "Inverting input to error amplifier 1", IcPinType.INPUT),
    ("3", "FEEDBACK", "Input pin for feedback", IcPinType.INPUT),
    ("4", "DTC", "Dead-time control comparator input", IcPinType.INPUT),
    ("5", "CT", "Capacitor terminal used to set oscillator frequency",
     IcPinType.PASSIVE),
    ("6", "RT", "Resistor terminal used to set oscillator frequency",
     IcPinType.PASSIVE),
    ("7", "GND", "Ground / common return", IcPinType.POWER_INPUT),
    ("8", "C1", "Output 1 transistor collector/drain terminal",
     IcPinType.OUTPUT),
    ("9", "E1", "Output 1 transistor emitter/source terminal",
     IcPinType.OUTPUT),
    ("10", "E2", "Output 2 transistor emitter/source terminal",
     IcPinType.OUTPUT),
    ("11", "C2", "Output 2 transistor collector/drain terminal",
     IcPinType.OUTPUT),
    ("12", "VCC", "Positive supply", IcPinType.POWER_INPUT),
    ("13", "OUTPUT CTRL", "Output-mode selector input", IcPinType.INPUT),
    ("14", "REF", "5-V reference regulator output", IcPinType.POWER_OUTPUT),
    ("15", "2IN-", "Inverting input to error amplifier 2", IcPinType.INPUT),
    ("16", "2IN+", "Noninverting input to error amplifier 2",
     IcPinType.INPUT),
)

TI_SHORT_LABELS = {
    "1": "1IN+", "2": "1IN-", "3": "FB", "4": "DTC",
    "5": "CT", "6": "RT", "7": "GND", "8": "C1",
    "9": "E1", "10": "E2", "11": "C2", "12": "VCC",
    "13": "OC", "14": "REF", "15": "2IN-", "16": "2IN+",
}

# Source-backed AUTHORIAL E3 LEFT/RIGHT pin presentation. Inputs LEFT; the
# five functional outputs plus REF RIGHT; power/return RIGHT. This is NOT
# a claim to copy a manufacturer package top view or a source PHOTO's exact
# graphical order. Auto-router must NEVER reorder these sides.
TI_E3_LEFT = ("1", "2", "3", "4", "5", "6", "13", "15", "16")
TI_E3_RIGHT = ("8", "9", "10", "11", "14", "12", "7")


class IcFunctionReading(str, Enum):
    """Meaningful word orientation, not an ambiguous signless rotation."""

    HORIZONTAL = "horizontal"
    BOTTOM_TO_TOP = "bottom_to_top"
    TOP_TO_BOTTOM_UNSUPPORTED = "top_to_bottom_unsupported"

    @property
    def physical_graphic_angle(self) -> IcTextAngle:
        if self is IcFunctionReading.HORIZONTAL:
            return IcTextAngle.HORIZONTAL
        if self is IcFunctionReading.BOTTOM_TO_TOP:
            # PAINT Transform(270) sends the word x-basis toward SVG -Y.
            return IcTextAngle.BOTTOM_TO_TOP
        raise ValueError("IC_FUNCTION_WRONG_READING_DIRECTION_BLOCKED")


def tl494cn_device() -> IcDeviceDefinition:
    device = IcDeviceDefinition(
        identifier=TI_DEVICE_ID,
        kind=IcKind.ANALOG,
        package=IcPackage(
            "TL494CN.N16", "PDIP-16", 16,
            PinoutOrigin.MANUFACTURER_DATASHEET,
            "Texas Instruments", TI_DATA_SHEET, TI_REVISION,
        ),
        pins=tuple(IcPhysicalPin(*p) for p in TI_PHYSICAL_PINS),
        units=(IcUnit(
            "control", "PWM and dual error amplifiers",
            tuple(str(i) for i in range(1, 17)),
        ),),
    )
    verify_tl494cn_ti_pinout(device)
    return device


def verify_tl494cn_ti_pinout(device: IcDeviceDefinition) -> None:
    """Independent COMPLETE 16/16 TI whitelist, not a green ERC heuristic."""
    if not isinstance(device, IcDeviceDefinition):
        raise TypeError("TL494_TI_DEVICE_TYPED_REQUIRED")
    if (
        device.identifier != TI_DEVICE_ID
        or device.kind is not IcKind.ANALOG
        or device.package.pin_count != 16
        or device.package.origin is not PinoutOrigin.MANUFACTURER_DATASHEET
        or device.package.manufacturer != "Texas Instruments"
        or device.package.datasheet_url != TI_DATA_SHEET
        or device.package.revision != TI_REVISION
    ):
        raise ValueError("TL494_TI_PROVENANCE_MISMATCH")
    actual = tuple((p.number, p.name, p.function, p.electrical_type)
                   for p in device.pins)
    if actual != TI_PHYSICAL_PINS:
        raise ValueError("TL494_TI_PIN_FUNCTION_OR_ELECTRICAL_TYPE_MISMATCH")
    if len(device.units) != 1 or set(device.units[0].pin_numbers) != {
        str(i) for i in range(1, 17)
    }:
        raise ValueError("TL494_TI_UNIT_COVERAGE_MISMATCH")


def tl494cn_alias_profile(
    component_ref: str = "DA1",
) -> IcPinAliasProfile:
    device = tl494cn_device()
    profile = IcPinAliasProfile(
        component_ref, device.identifier,
        tuple(IcPinDisplayAlias(
            pin.number,
            pin.name,
            TI_SHORT_LABELS[pin.number],
            pin.electrical_type,
            PinRef(component_ref, pin.number),
            IcPinDisplayOrientation.HORIZONTAL,
            TI_PIN_TABLE,
        ) for pin in device.pins),
        max_display_chars=6,
    )
    profile.validate_device(device)
    return profile


def tl494cn_record(
    component_ref: str = "DA1",
    *,
    reading: IcFunctionReading = IcFunctionReading.BOTTOM_TO_TOP,
) -> tuple[IcLibraryRecord, IcPinAliasProfile]:
    """Portrait center source, NO routing, unchanged physical package."""
    if not isinstance(reading, IcFunctionReading):
        raise TypeError("TL494_READING_TYPED_REQUIRED")
    angle = reading.physical_graphic_angle
    device = tl494cn_device()
    aliases = tl494cn_alias_profile(component_ref)
    sides = ((Side.LEFT, TI_E3_LEFT), (Side.RIGHT, TI_E3_RIGHT))
    rows = []
    for side, numbers in sides:
        for index, number in enumerate(numbers, start=1):
            rows.append(IcPinRow(
                number=number, side=side,
                anchor=Point(
                    -8000 if side is Side.LEFT else 68000,
                    5000 * index + 2500,
                ),
                row_key="tl494.ti." + number,
                label=TI_SHORT_LABELS[number],
                visual_row=index,
            ))
    specs = (IcSymbolSpec(
        device.identifier, "control",
        Box(0, 0, 60000, 110000), "PWM",
        tuple(rows), revision=1,
        profile=IcGraphicProfile(
            port_layout=IcPortLayout.LEFT_RIGHT,
            body_axis=IcBodyAxis.PORTRAIT,
            function_angle=angle,
            other_text_angle=IcTextAngle.HORIZONTAL,
        ),
    ),)
    placement = (IcUnitPlacement(
        component_ref, device.identifier, "control",
        Point(100000, 70000),
    ),)
    record = IcLibraryRecord(device, specs, placement)
    aliases.validate_device(record.device)
    return record, aliases


def tl494cn_unwired_circuit(
    record: IcLibraryRecord,
) -> Circuit:
    """No invented VCC/GND/FB net: only physical identity is verified."""
    verify_tl494cn_ti_pinout(record.device)
    ref = record.placements[0].component_ref
    return Circuit((ComponentInstance(ref, record.device.identifier),), ())
