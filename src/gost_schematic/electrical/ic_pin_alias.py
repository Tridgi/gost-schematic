"""Source-bound, reversible E3 IC pin-label aliases; physical identity immutable.

Short labels are a PROJECT editorial constraint, not a GOST pin-name limit.
No truncation, whitespace coercion, guessed pin numbers, or Net changes.
"""
from dataclasses import dataclass, replace
from enum import Enum
from unicodedata import normalize

from gost_schematic.electrical.ic import (
    IcDeviceDefinition,
    IcPinType,
    resolve_ic_pin_positions,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord
from gost_schematic.model.circuit import PinRef


class IcPinDisplayOrientation(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL_BOTTOM_TO_TOP = "vertical_bottom_to_top"


@dataclass(frozen=True, slots=True)
class IcPinDisplayAlias:
    physical_number: str
    manufacturer_pin_name: str
    schematic_short_label: str
    electrical_type: IcPinType
    real_pin_ref: PinRef
    display_orientation: IcPinDisplayOrientation
    source_document_reference: str

    def __post_init__(self) -> None:
        for name in (
            "physical_number", "manufacturer_pin_name",
            "schematic_short_label", "source_document_reference",
        ):
            value = getattr(self, name)
            if (not isinstance(value, str) or not value
                    or value != value.strip()
                    or normalize("NFC", value) != value):
                raise ValueError("IC_ALIAS_NONCANONICAL_" + name.upper())
        if any(ch.isspace() for ch in self.schematic_short_label):
            raise ValueError("IC_ALIAS_SPACES_FORBIDDEN")
        if not isinstance(self.electrical_type, IcPinType):
            raise TypeError("IC_ALIAS_ELECTRICAL_TYPE_REQUIRED")
        if not isinstance(self.display_orientation, IcPinDisplayOrientation):
            raise TypeError("IC_ALIAS_TYPED_LABEL_ORIENTATION_REQUIRED")
        if not isinstance(self.real_pin_ref, PinRef) or (
            self.real_pin_ref.number != self.physical_number
        ):
            raise ValueError("IC_ALIAS_FOREIGN_PINREF")
        if not self.source_document_reference.startswith("https://"):
            raise ValueError("IC_ALIAS_SOURCE_MUST_BE_HTTPS")


@dataclass(frozen=True, slots=True)
class IcPinAliasProfile:
    """Complete physical-package aliases for a single component reference."""

    component_ref: str
    device_id: str
    labels: tuple[IcPinDisplayAlias, ...]
    max_display_chars: int = 6

    def __post_init__(self) -> None:
        if (not isinstance(self.component_ref, str) or not self.component_ref
                or not isinstance(self.device_id, str) or not self.device_id):
            raise ValueError("IC_ALIAS_PHYSICAL_ID_REQUIRED")
        if type(self.max_display_chars) is not int or (
            self.max_display_chars <= 0
        ):
            raise ValueError("IC_ALIAS_MAX_CHARS_INVALID")
        if not isinstance(self.labels, tuple) or not self.labels or any(
            not isinstance(alias, IcPinDisplayAlias) for alias in self.labels
        ):
            raise TypeError("IC_ALIAS_TYPED_LABELS_REQUIRED")
        names = [label.schematic_short_label for label in self.labels]
        if any(len(name) > self.max_display_chars for name in names):
            raise ValueError("IC_ALIAS_TOO_LONG_NO_TRUNCATION")
        if len({normalize("NFC", name).casefold() for name in names}) != len(names):
            raise ValueError("IC_ALIAS_DUPLICATE_LABEL")
        if len({alias.physical_number for alias in self.labels}) != len(names):
            raise ValueError("IC_ALIAS_DUPLICATE_PHYSICAL_NUMBER")
        if len({alias.real_pin_ref for alias in self.labels}) != len(names):
            raise ValueError("IC_ALIAS_DUPLICATE_PINREF")

    def validate_device(self, device: IcDeviceDefinition) -> None:
        if not isinstance(device, IcDeviceDefinition):
            raise TypeError("IC_ALIAS_DEVICE_TYPED_REQUIRED")
        if device.identifier != self.device_id or len(self.labels) != len(device.pins):
            raise ValueError("IC_ALIAS_DEVICE_OR_COVERAGE_MISMATCH")
        if {alias.physical_number for alias in self.labels} != set(device.pin_map):
            raise ValueError("IC_ALIAS_INCOMPLETE_PHYSICAL_PINOUT")
        expected_source = device.package.datasheet_url
        if not expected_source:
            raise ValueError("IC_ALIAS_UNVERIFIED_SOURCE")
        for alias in self.labels:
            real = device.pin_map[alias.physical_number]
            if alias.real_pin_ref != PinRef(
                self.component_ref, alias.physical_number,
            ):
                raise ValueError("IC_ALIAS_FOREIGN_PINREF")
            if (
                alias.manufacturer_pin_name != real.name
                or alias.electrical_type is not real.electrical_type
            ):
                raise ValueError("IC_ALIAS_MANUFACTURER_SEMANTIC_MISMATCH")
            if not alias.source_document_reference.startswith(expected_source):
                raise ValueError("IC_ALIAS_SOURCE_DOCUMENT_MISMATCH")

    def apply_to_record(self, record: IcLibraryRecord) -> IcLibraryRecord:
        """Explicit new graphic revision, same real contact points and device."""
        if not isinstance(record, IcLibraryRecord):
            raise TypeError("IC_ALIAS_RECORD_TYPED_REQUIRED")
        self.validate_device(record.device)
        if {p.component_ref for p in record.placements} != {self.component_ref}:
            raise ValueError("IC_ALIAS_FOREIGN_COMPONENT")
        by_number = {p.physical_number: p for p in self.labels}
        specs = tuple(replace(
            spec, revision=spec.revision + 1,
            rows=tuple(replace(
                row, label=by_number[row.number].schematic_short_label,
            ) for row in spec.rows),
        ) for spec in record.specs)
        result = IcLibraryRecord(record.device, specs, record.placements)
        if resolve_ic_pin_positions(
            record.device, record.specs, record.placements,
        ) != resolve_ic_pin_positions(
            result.device, result.specs, result.placements,
        ):
            raise ValueError("IC_ALIAS_MOVED_PHYSICAL_PIN")
        return result


def verify_alias_display(
    profile: IcPinAliasProfile, record: IcLibraryRecord,
) -> None:
    """Independent source→graphic integrity check, no inferred wiring."""
    profile.validate_device(record.device)
    if {p.component_ref for p in record.placements} != {profile.component_ref}:
        raise ValueError("IC_ALIAS_FOREIGN_COMPONENT")
    indexed = {a.physical_number: a for a in profile.labels}
    for spec in record.specs:
        for row in spec.rows:
            if row.label != indexed[row.number].schematic_short_label:
                raise ValueError("IC_ALIAS_GRAPHIC_TEXT_MISMATCH")
