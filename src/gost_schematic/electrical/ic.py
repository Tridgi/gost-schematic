"""Draft E3 IC physical-package / graphical-unit contract (Issue #87).

No changes to the E3 Circuit/Net/PinRef/PartDefinition/SymbolDefinition API.
A physical IC is ONE Circuit component even when displayed as many units.
PAINT owns text measurement and all ink geometry; exact resolved physical
pin endpoints are authoritative for its SVG strokes.
"""

from dataclasses import dataclass, field
from enum import Enum

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, PhysicalPin


def _name(value: str, context: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{context} must be a nonblank canonical string")
    return value


def _unique(values: tuple[str, ...], context: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {context}")


class IcPinType(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    POWER_INPUT = "power_input"
    POWER_OUTPUT = "power_output"
    OPEN_COLLECTOR = "open_collector"
    PASSIVE = "passive"
    NC = "nc"


class IcKind(str, Enum):
    ANALOG = "analog"
    DIGITAL = "digital"

    @property
    def reference_prefix(self) -> str:
        return "DA" if self is IcKind.ANALOG else "DD"

    @property
    def draft_standard(self) -> str:
        return "ГОСТ 2.759-82 (DRAFT)" if self is IcKind.ANALOG else (
            "ГОСТ 2.743-91 (DRAFT)"
        )


class PinoutOrigin(str, Enum):
    SYNTHETIC = "synthetic"
    MANUFACTURER_DATASHEET = "manufacturer_datasheet"


@dataclass(frozen=True, slots=True)
class IcPackage:
    package_id: str
    family: str
    pin_count: int
    origin: PinoutOrigin
    manufacturer: str | None = None
    datasheet_url: str | None = None
    revision: str | None = None

    def __post_init__(self) -> None:
        _name(self.package_id, "package_id")
        _name(self.family, "package family")
        if type(self.pin_count) is not int or self.pin_count < 2:
            raise ValueError("Package pin_count must be an integer >=2")
        if not isinstance(self.origin, PinoutOrigin):
            raise TypeError("Pinout origin must be typed")
        if self.origin is PinoutOrigin.SYNTHETIC:
            if any(x is not None for x in (
                self.manufacturer, self.datasheet_url, self.revision,
            )):
                raise ValueError("Synthetic pinout cannot claim a manufacturer")
        else:
            _name(self.manufacturer, "manufacturer")
            _name(self.revision, "datasheet revision")
            if not isinstance(self.datasheet_url, str) or not (
                self.datasheet_url.startswith("https://")
            ):
                raise ValueError("Real pinout requires https manufacturer datasheet URL")


@dataclass(frozen=True, slots=True)
class IcPhysicalPin:
    number: str
    name: str
    function: str
    electrical_type: IcPinType

    def __post_init__(self) -> None:
        _name(self.number, "physical pin number")
        _name(self.name, "physical pin name")
        _name(self.function, "physical pin function")
        if not isinstance(self.electrical_type, IcPinType):
            raise TypeError("IC electrical type must be IcPinType")


@dataclass(frozen=True, slots=True)
class IcUnit:
    id: str
    function: str
    pin_numbers: tuple[str, ...]

    def __post_init__(self) -> None:
        _name(self.id, "unit id")
        _name(self.function, "unit function")
        if not isinstance(self.pin_numbers, tuple) or not self.pin_numbers:
            raise ValueError("IC unit requires physical numbers")
        for value in self.pin_numbers:
            _name(value, "unit physical number")
        _unique(self.pin_numbers, "unit physical numbers")


@dataclass(frozen=True, slots=True)
class IcDeviceDefinition:
    identifier: str
    kind: IcKind
    package: IcPackage
    pins: tuple[IcPhysicalPin, ...]
    units: tuple[IcUnit, ...]

    def __post_init__(self) -> None:
        _name(self.identifier, "IC part identifier")
        if not isinstance(self.kind, IcKind) or not isinstance(self.package, IcPackage):
            raise TypeError("IC kind/package must be typed")
        if self.package.origin is PinoutOrigin.SYNTHETIC and not (
            self.identifier.startswith("TEST_IC_")
        ):
            raise ValueError("Synthetic IC identifiers must start TEST_IC_")
        if not isinstance(self.pins, tuple) or len(self.pins) != self.package.pin_count:
            raise ValueError("Physical pin inventory must equal package pin count")
        if not all(isinstance(p, IcPhysicalPin) for p in self.pins):
            raise TypeError("Physical pins must be IcPhysicalPin")
        numbers = tuple(p.number for p in self.pins)
        _unique(numbers, "physical IC pin numbers")
        if not isinstance(self.units, tuple) or not self.units:
            raise ValueError("IC requires at least one logical functional unit")
        if not all(isinstance(unit, IcUnit) for unit in self.units):
            raise TypeError("IC units must be IcUnit")
        _unique(tuple(unit.id for unit in self.units), "IC unit IDs")
        actual = tuple(number for unit in self.units for number in unit.pin_numbers)
        _unique(actual, "unit ownership of physical pin")
        if not set(actual) <= set(numbers):
            raise ValueError("Unit references nonexistent physical package pin")
        required = {pin.number for pin in self.pins if pin.electrical_type is not IcPinType.NC}
        if not required <= set(actual):
            raise ValueError("Non-NC physical pin missing from logical units")

    @property
    def pin_map(self) -> dict[str, IcPhysicalPin]:
        return {pin.number: pin for pin in self.pins}

    def to_legacy_part(self, symbol_id: str) -> PartDefinition:
        """Typed legacy inventory bridge; does not construct a multi-unit symbol.

        Existing E3 cannot represent NC or multi-unit symbol views.
        Reject these cases rather than silently mapping NC to UNSPECIFIED.
        """
        _name(symbol_id, "symbol_id")
        if len(self.units) != 1 or any(
            pin.electrical_type is IcPinType.NC for pin in self.pins
        ):
            raise ValueError(
                "IC_UNSAFE_LEGACY_ADAPTER: NC or split units require reviewed mapping"
            )
        legacy = {
            item.value: item for item in ElectricalType
        }
        pins = tuple(
            PhysicalPin(
                pin.number, pin.name,
                legacy[pin.electrical_type.value],
            ) for pin in self.pins
        )
        return PartDefinition(
            self.identifier, self.kind.reference_prefix, symbol_id, pins,
        )


class IcPortLayout(str, Enum):
    """Logical pin-side arrangement, independent from body or text rotation."""

    LEFT_RIGHT = "left_right"
    TOP_BOTTOM = "top_bottom"


class IcBodyAxis(str, Enum):
    """Graphical rectangle aspect intent; NOT a physical package footprint."""

    AUTO = "auto"
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class IcTextAngle(int, Enum):
    """DRAFT display angle in untransformed local coordinates (degrees)."""

    HORIZONTAL = 0
    VERTICAL = 90


@dataclass(frozen=True, slots=True)
class IcGraphicProfile:
    """Independent source-view choices. This is NOT an ESKD signoff.

    Port layout, rectangle aspect, central function and remaining field text
    are four independent attributes. In particular LEFT_RIGHT + VERTICAL
    function text is representable and serializable even while PAINT #93
    refuses to print that experimental combination.
    """

    port_layout: IcPortLayout = IcPortLayout.LEFT_RIGHT
    body_axis: IcBodyAxis = IcBodyAxis.AUTO
    function_angle: IcTextAngle = IcTextAngle.HORIZONTAL
    other_text_angle: IcTextAngle = IcTextAngle.HORIZONTAL

    def __post_init__(self) -> None:
        if not isinstance(self.port_layout, IcPortLayout):
            raise TypeError("IC_PORT_LAYOUT_TYPED_REQUIRED")
        if not isinstance(self.body_axis, IcBodyAxis):
            raise TypeError("IC_BODY_AXIS_TYPED_REQUIRED")
        if not isinstance(self.function_angle, IcTextAngle) or not isinstance(
            self.other_text_angle, IcTextAngle,
        ):
            raise TypeError("IC_TEXT_ANGLE_TYPED_REQUIRED")


class IcField(str, Enum):
    MAIN = "main"
    AUX_LEFT = "aux_left"
    AUX_RIGHT = "aux_right"


@dataclass(frozen=True, slots=True)
class IcPinRow:
    """Physical number and outer lead endpoint, NEVER the displayed ink label."""
    number: str
    side: Side
    anchor: Point
    row_key: str
    label: str = ""
    field: IcField = IcField.MAIN
    visual_row: int = 1

    def __post_init__(self) -> None:
        _name(self.number, "row physical number")
        _name(self.row_key, "row grouping key")
        if not isinstance(self.side, Side) or not isinstance(self.anchor, Point):
            raise TypeError("Row side/anchor must be typed")
        if not isinstance(self.field, IcField):
            raise TypeError("Row field must be IcField")
        if not isinstance(self.label, str):
            raise TypeError("Display label must be text")
        if type(self.visual_row) is not int or self.visual_row < 1:
            raise ValueError("IC_PIN_ROW_INVALID: visual row starts at 1")


def _outside_on_side(point: Point, side: Side, body: Box) -> bool:
    return {
        Side.LEFT: point.x < body.min_x and body.min_y < point.y < body.max_y,
        Side.RIGHT: point.x > body.max_x and body.min_y < point.y < body.max_y,
        Side.TOP: point.y < body.min_y and body.min_x < point.x < body.max_x,
        Side.BOTTOM: point.y > body.max_y and body.min_x < point.x < body.max_x,
    }[side]


@dataclass(frozen=True, slots=True)
class IcSymbolSpec:
    device_id: str
    unit_id: str
    body: Box
    main_field: str
    rows: tuple[IcPinRow, ...]
    aux_left: str | None = None
    aux_right: str | None = None
    revision: int = 1
    profile: IcGraphicProfile = field(default_factory=IcGraphicProfile)

    def __post_init__(self) -> None:
        _name(self.device_id, "symbol device_id")
        _name(self.unit_id, "symbol unit_id")
        if not isinstance(self.body, Box):
            raise TypeError("IC body must be explicit Box; PAINT measures its dimensions")
        _name(self.main_field, "main field text")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("Symbol revision must be positive integer")
        if not isinstance(self.profile, IcGraphicProfile):
            raise TypeError("IC_GRAPHIC_PROFILE_TYPED_REQUIRED")
        w = self.body.max_x - self.body.min_x
        h = self.body.max_y - self.body.min_y
        if (
            self.profile.body_axis is IcBodyAxis.PORTRAIT and h <= w
        ) or (
            self.profile.body_axis is IcBodyAxis.LANDSCAPE and w <= h
        ):
            raise ValueError("IC_BODY_AXIS_GEOMETRY_MISMATCH")
        allowed = (
            (Side.LEFT, Side.RIGHT)
            if self.profile.port_layout is IcPortLayout.LEFT_RIGHT
            else (Side.TOP, Side.BOTTOM)
        )
        if any(row.side not in allowed for row in self.rows):
            raise ValueError("IC_PORT_LAYOUT_MISMATCH: explicit side profile")
        for aux in (self.aux_left, self.aux_right):
            if aux is not None:
                _name(aux, "auxiliary field text")
        if not isinstance(self.rows, tuple) or not self.rows:
            raise ValueError("IC graphical view requires rows")
        if not all(isinstance(row, IcPinRow) for row in self.rows):
            raise TypeError("IC rows must be typed")
        _unique(tuple(row.number for row in self.rows), "IC symbol physical pin")
        if len({row.anchor for row in self.rows}) != len(self.rows):
            raise ValueError("IC_ANCHOR_COLLISION")
        if len({(row.side, row.visual_row) for row in self.rows}) != len(self.rows):
            raise ValueError("IC_DUPLICATE_VISUAL_ROW: two pins on same side/row")
        for row in self.rows:
            if not _outside_on_side(row.anchor, row.side, self.body):
                raise ValueError("IC_ANCHOR_INSIDE: endpoint is not strictly outside its side")
            if row.field is IcField.AUX_LEFT and self.aux_left is None:
                raise ValueError("Pin requires absent left auxiliary field")
            if row.field is IcField.AUX_RIGHT and self.aux_right is None:
                raise ValueError("Pin requires absent right auxiliary field")


@dataclass(frozen=True, slots=True)
class IcUnitPlacement:
    component_ref: str
    device_id: str
    unit_id: str
    origin: Point = field(default_factory=lambda: Point(0, 0))
    transform: Transform = field(default_factory=Transform)

    def __post_init__(self) -> None:
        _name(self.component_ref, "physical component reference")
        _name(self.device_id, "device id")
        _name(self.unit_id, "unit id")
        if not isinstance(self.origin, Point) or not isinstance(self.transform, Transform):
            raise TypeError("Unit placement requires Point and Transform")


def resolve_ic_pin_positions(
    device: IcDeviceDefinition,
    specs: tuple[IcSymbolSpec, ...],
    placements: tuple[IcUnitPlacement, ...],
) -> dict[PinRef, Point]:
    """Only authoritative PAINT port coordinates, no text layout inferred."""
    if not isinstance(device, IcDeviceDefinition):
        raise TypeError("Expected IcDeviceDefinition")
    if not isinstance(specs, tuple) or not isinstance(placements, tuple):
        raise TypeError("IC specs and placements must be tuples")
    unit_map = {unit.id: unit for unit in device.units}
    spec_map: dict[str, IcSymbolSpec] = {}
    for spec in specs:
        if not isinstance(spec, IcSymbolSpec) or spec.device_id != device.identifier:
            raise ValueError("Unknown or invalid IC symbol specification")
        if spec.unit_id not in unit_map or spec.unit_id in spec_map:
            raise ValueError("Unknown or duplicated IC view unit")
        if {row.number for row in spec.rows} != set(unit_map[spec.unit_id].pin_numbers):
            raise ValueError("IC_PIN_NOT_PRESENTED: a view must expose its exact unit pins")
        spec_map[spec.unit_id] = spec

    if set(spec_map) != set(unit_map):
        raise ValueError("IC_PIN_NOT_PRESENTED: every logical unit needs a view")
    if len(placements) != len(unit_map):
        raise ValueError("Each IC unit needs exactly one physical view placement")
    if len({p.component_ref for p in placements}) != 1:
        raise ValueError("Multiple physical components for one IC package")
    reference = placements[0].component_ref
    if not reference.startswith(device.kind.reference_prefix) or not (
        reference[len(device.kind.reference_prefix):].isdigit()
    ):
        raise ValueError("IC must use a stable DA/DD physical component reference")
    resolved: dict[PinRef, Point] = {}
    seen_units: set[str] = set()
    seen_points: set[Point] = set()
    for placement in placements:
        if not isinstance(placement, IcUnitPlacement) or (
            placement.device_id != device.identifier
        ):
            raise ValueError("Invalid or foreign IC unit placement")
        if placement.unit_id in seen_units or placement.unit_id not in spec_map:
            raise ValueError("Repeated or unknown unit placement")
        seen_units.add(placement.unit_id)
        for row in spec_map[placement.unit_id].rows:
            ref = PinRef(placement.component_ref, row.number)
            point = placement.transform.apply(row.anchor) + placement.origin
            if ref in resolved or point in seen_points:
                raise ValueError("IC_ANCHOR_COLLISION: reused physical pin or position")
            resolved[ref] = point
            seen_points.add(point)
    return resolved


def resolve_ic_port_sides(
    device: IcDeviceDefinition,
    specs: tuple[IcSymbolSpec, ...],
    placements: tuple[IcUnitPlacement, ...],
) -> dict[PinRef, Side]:
    """PAINT must use transformed normals, without changing any number."""
    resolve_ic_pin_positions(device, specs, placements)
    by_unit = {spec.unit_id: spec for spec in specs}
    return {
        PinRef(p.component_ref, row.number): p.transform.side(row.side)
        for p in placements for row in by_unit[p.unit_id].rows
    }


def validate_ic_circuit(
    device: IcDeviceDefinition, circuit: Circuit, component_ref: str,
) -> None:
    """Independent E3 electrical gate for NC and conflicting package membership."""
    if not isinstance(circuit, Circuit):
        raise TypeError("Expected Circuit")
    _name(component_ref, "component_ref")
    if not component_ref.startswith(device.kind.reference_prefix) or not (
        component_ref[len(device.kind.reference_prefix):].isdigit()
    ):
        raise ValueError("Physical IC reference does not match DA/DD kind")
    components = [c for c in circuit.components if c.reference == component_ref]
    if len(components) != 1 or components[0].part_id != device.identifier:
        raise ValueError("Exactly one real Circuit component must match this IC")
    pins = device.pin_map
    seen: set[PinRef] = set()
    for net in circuit.nets:
        for ref in net.members:
            if ref.reference != component_ref:
                continue
            if ref.number not in pins:
                raise ValueError("Net references nonexistent physical IC pin")
            if pins[ref.number].electrical_type is IcPinType.NC:
                raise ValueError("IC_NC_CONNECTED: no-connect package pin cannot be wired")
            if ref in seen:
                raise ValueError("One physical IC contact belongs to multiple nets")
            seen.add(ref)
