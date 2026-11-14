"""Source-traced IC supply drawing choices, separate from physical pinout.

ГОСТ 2.743-91 §§2.1.4, 2.3.6 table 5, 2.3.11 fig.6:
inputs LEFT, outputs RIGHT; nonlogical/power may be LEFT or RIGHT.
Power can be described as free sheet text or using common control,
a logical section, or separate outline; no assumption that supply pins
belong at graphical TOP/BOTTOM. Analog 2.759-82 table 2: U / OV.
This is a DRAFT placement PLAN, not yet a drawn certified power UGO.
"""
from dataclasses import dataclass
from enum import Enum

from gost_schematic.core.geometry import Side
from gost_schematic.electrical.ic import IcKind, IcPinType, PinoutOrigin
from gost_schematic.electrical.ic_serde import IcLibraryRecord
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.electrical.ic import validate_ic_circuit


class IcPowerMode(str, Enum):
    NONLOGICAL_SIDE = "nonlogical_left_right"
    FREE_SHEET_TEXT = "free_sheet_text"
    COMMON_CONTROL = "common_control_fig6a"
    IN_ONE_SECTION = "one_unit_fig6b"
    SEPARATE_OUTLINE = "separate_outline_fig6c"
    EXPERIMENTAL_TOP_BOTTOM_RAILS = "experimental_top_bottom_rails"


class IcPowerMeaning(str, Enum):
    SUPPLY = "supply"
    COMMON = "common"
    SUPPLY_OUTPUT = "supply_output"


@dataclass(frozen=True, slots=True)
class IcPowerPinLabel:
    """Explicit physical number, unit ownership, semantic role and marker."""

    physical_number: str
    unit_id: str
    meaning: IcPowerMeaning
    label: str

    def __post_init__(self) -> None:
        if any(not isinstance(v, str) or not v.strip() or v != v.strip()
               for v in (self.physical_number, self.unit_id, self.label)):
            raise ValueError("IC_POWER_CANONICAL_LABEL_REQUIRED")
        if not isinstance(self.meaning, IcPowerMeaning):
            raise TypeError("IC_POWER_MEANING_TYPED_REQUIRED")


@dataclass(frozen=True, slots=True)
class IcPowerPresentation:
    """One explicit physical-device presentation decision, not a netlist edit."""

    device_id: str
    component_ref: str
    mode: IcPowerMode
    labels: tuple[IcPowerPinLabel, ...]
    host_unit_id: str | None = None
    draft_only: bool = True

    def __post_init__(self) -> None:
        if not self.device_id or not self.component_ref:
            raise ValueError("IC_POWER_PHYSICAL_IDENTITY_REQUIRED")
        if not isinstance(self.mode, IcPowerMode):
            raise TypeError("IC_POWER_MODE_TYPED_REQUIRED")
        if type(self.draft_only) is not bool or not self.draft_only:
            raise ValueError("IC_POWER_NOT_NORMATIVE_APPROVED")
        if not isinstance(self.labels, tuple) or not self.labels:
            raise ValueError("IC_POWER_EMPTY_TERMINAL_SET")
        if not all(isinstance(x, IcPowerPinLabel) for x in self.labels):
            raise TypeError("IC_POWER_TYPED_LABEL_REQUIRED")
        if len({p.physical_number for p in self.labels}) != len(self.labels):
            raise ValueError("IC_POWER_DUPLICATE_PHYSICAL_NUMBER")
        if self.mode is IcPowerMode.IN_ONE_SECTION:
            if not self.host_unit_id:
                raise ValueError("IC_POWER_HOST_UNIT_REQUIRED")
        elif self.host_unit_id is not None:
            raise ValueError("IC_POWER_HOST_UNIT_NOT_APPLICABLE")


def validate_ic_power_presentation(
    presentation: IcPowerPresentation,
    record: IcLibraryRecord,
    *,
    circuit: Circuit | None = None,
    experimental_preview: bool = False,
) -> None:
    """Never infer a net/physical number from a printed VCC/GND/U label."""
    if not isinstance(presentation, IcPowerPresentation) or not isinstance(
        record, IcLibraryRecord,
    ):
        raise TypeError("IC_POWER_TYPED_RECORD_REQUIRED")
    device = record.device
    if (presentation.device_id != device.identifier
            or {p.component_ref for p in record.placements} != {
                presentation.component_ref
            }):
        raise ValueError("IC_POWER_FOREIGN_DEVICE_OR_COMPONENT")
    if circuit is not None:
        validate_ic_circuit(device, circuit, presentation.component_ref)
    units = {unit.id: set(unit.pin_numbers) for unit in device.units}
    if presentation.host_unit_id is not None and (
        presentation.host_unit_id not in units
    ):
        raise ValueError("IC_POWER_UNKNOWN_HOST_UNIT")
    map_pin = device.pin_map
    expected_power = {
        pin.number for pin in device.pins
        if pin.electrical_type in (IcPinType.POWER_INPUT, IcPinType.POWER_OUTPUT)
    }
    all_marked = {entry.physical_number for entry in presentation.labels}
    if not expected_power <= all_marked:
        raise ValueError("IC_POWER_REQUIRED_SUPPLY_PIN_MISSING")
    if not all_marked <= set(map_pin):
        raise ValueError("IC_POWER_UNKNOWN_PHYSICAL_NUMBER")
    for entry in presentation.labels:
        if entry.unit_id not in units or entry.physical_number not in (
            units[entry.unit_id]
        ):
            raise ValueError("IC_POWER_WRONG_PHYSICAL_UNIT")
        physical = map_pin[entry.physical_number]
        if entry.meaning is IcPowerMeaning.SUPPLY:
            if physical.electrical_type is not IcPinType.POWER_INPUT:
                raise ValueError("IC_POWER_NOT_POWER_INPUT")
        elif entry.meaning is IcPowerMeaning.SUPPLY_OUTPUT:
            if physical.electrical_type is not IcPinType.POWER_OUTPUT:
                raise ValueError("IC_POWER_NOT_POWER_OUTPUT")
        elif physical.electrical_type not in (
            IcPinType.POWER_INPUT, IcPinType.PASSIVE,
        ):
            raise ValueError("IC_COMMON_ROLE_TYPE_MISMATCH")
        if device.kind is IcKind.ANALOG:
            if entry.meaning is IcPowerMeaning.COMMON:
                if entry.label != "OV":
                    raise ValueError("IC_ANALOG_COMMON_LABEL_MUST_BE_OV")
            elif entry.meaning is IcPowerMeaning.SUPPLY and entry.label != "U":
                # A manufacturer-specific identifier is possible but cannot
                # automatically be certified via a generic UGO label.
                raise ValueError("IC_ANALOG_SUPPLY_LABEL_MUST_BE_U")
        else:
            if entry.meaning is IcPowerMeaning.COMMON and entry.label not in (
                "GND", "OV",
            ):
                raise ValueError("IC_DIGITAL_COMMON_LABEL_INVALID")
            if entry.meaning is IcPowerMeaning.SUPPLY and (
                entry.label not in ("VCC", "Vcc", "U")
            ):
                raise ValueError("IC_DIGITAL_SUPPLY_LABEL_INVALID")
    if presentation.mode is IcPowerMode.EXPERIMENTAL_TOP_BOTTOM_RAILS:
        if not experimental_preview:
            raise ValueError("IC_EXPERIMENTAL_TOP_BOTTOM_NOT_NORMATIVE")
        if not any(p.meaning is IcPowerMeaning.SUPPLY
                   for p in presentation.labels) or not any(
                       p.meaning is IcPowerMeaning.COMMON
                       for p in presentation.labels
                   ):
            raise ValueError("IC_POWER_EXPERIMENTAL_RAIL_PAIR_REQUIRED")
        # This is only a drawing intent. It cannot move PinRef ends or turn
        # an L/R body into a true TOP/BOTTOM source without new revision.
    elif presentation.mode is IcPowerMode.NONLOGICAL_SIDE:
        spec_by_unit = {spec.unit_id: spec for spec in record.specs}
        for entry in presentation.labels:
            row = next(
                x for x in spec_by_unit[entry.unit_id].rows
                if x.number == entry.physical_number
            )
            if row.side not in (Side.LEFT, Side.RIGHT):
                raise ValueError("IC_POWER_NONLOGICAL_SIDE_MUST_BE_LR")
    if presentation.mode is IcPowerMode.IN_ONE_SECTION:
        if len(units) < 2:
            raise ValueError("IC_POWER_ONE_SECTION_NEEDS_SPLIT_IC")
        # Power physically belongs to its own unit, independently of the
        # common field drawn inside one chosen graphical section.
    if device.package.origin is PinoutOrigin.SYNTHETIC and not (
        device.identifier.startswith("TEST_IC_")
    ):
        raise ValueError("IC_POWER_SYNTHETIC_PINOUT_PROVENANCE_INVALID")


def validate_ic_power_sheet_modes(
    presentations: tuple[IcPowerPresentation, ...],
) -> None:
    """ГОСТ fig.6 note: choose a+b OR a+c; never mix b and c in one set."""
    if not isinstance(presentations, tuple) or any(
        not isinstance(p, IcPowerPresentation) for p in presentations
    ):
        raise TypeError("IC_POWER_SHEET_TYPED_REQUIRED")
    modes = {p.mode for p in presentations}
    if (
        IcPowerMode.IN_ONE_SECTION in modes
        and IcPowerMode.SEPARATE_OUTLINE in modes
    ):
        raise ValueError("IC_POWER_FIG6_B_AND_C_SAME_DOCUMENT_FORBIDDEN")
    if any(p.mode is IcPowerMode.EXPERIMENTAL_TOP_BOTTOM_RAILS
           for p in presentations):
        raise ValueError("IC_EXPERIMENTAL_POWER_NOT_NORMATIVE_SHEET")
