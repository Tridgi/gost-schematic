"""Issue #87/#110: typed physical IC -> existing Circuit/Part/PinRef/PAINT.

Circuit connectivity is authoritative, never inferred from SVG labels or ink.
Optional single-unit SymbolDefinition is a DRAFT layout surrogate ONLY: PAINT
draws the actual IC. Multi-unit ICs are electrically complete but cannot be
misrepresented as one printed compact surrogate.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from gost_schematic.core.geometry import Box, Line, Point, Rectangle, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.ic import (
    IcPinType,
    resolve_ic_pin_positions,
    resolve_ic_port_sides,
    validate_ic_circuit,
)
from gost_schematic.electrical.ic_graphic_revision import (
    IcGeometryConsent,
    IcGraphicRevisionDelta,
    validate_ic_graphic_revision,
)
from gost_schematic.electrical.ic_pin_alias import (
    IcPinAliasProfile,
    IcPinDisplayAlias,
    IcPinDisplayOrientation,
    verify_alias_display,
)
from gost_schematic.electrical.ic_serde import (
    IcLibraryRecord,
    ic_from_json,
    ic_to_json,
)
from gost_schematic.model.circuit import (
    Circuit,
    ComponentInstance,
    Net,
    PinRef,
)
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, GraphicPin, PhysicalPin
from gost_schematic.model.quantities import Quantity
from gost_schematic.model.symbol import SymbolDefinition, SymbolStatus

_SIDES = (Side.LEFT, Side.RIGHT, Side.TOP, Side.BOTTOM)


def _inverse_pose(p: Point, instance: ComponentInstance) -> Point:
    """D4 inverse by orthonormal integer basis, no floats or rounding."""
    delta = p - instance.origin
    x_axis = instance.transform.apply(Point(1, 0))
    y_axis = instance.transform.apply(Point(0, 1))
    return Point(
        delta.x * x_axis.x + delta.y * x_axis.y,
        delta.x * y_axis.x + delta.y * y_axis.y,
    )


def _local_side(world_side: Side, instance: ComponentInstance) -> Side:
    matching = tuple(s for s in _SIDES if instance.transform.side(s) is world_side)
    if len(matching) != 1:
        raise ValueError("IC_ADAPTER_D4_SIDE_NONINVERTIBLE")
    return matching[0]


def _single_symbol(
    record: IcLibraryRecord,
    component: ComponentInstance,
    display_labels: dict[str, str],
) -> SymbolDefinition:
    """One-part geometry surrogate: print ink always comes from PAINT."""
    if len(record.specs) != 1 or len(record.placements) != 1:
        raise ValueError("IC_ADAPTER_MULTI_UNIT_PRINT_SURROGATE_BLOCKED")
    spec, placement = record.specs[0], record.placements[0]
    corners = (
        Point(spec.body.min_x, spec.body.min_y),
        Point(spec.body.min_x, spec.body.max_y),
        Point(spec.body.max_x, spec.body.min_y),
        Point(spec.body.max_x, spec.body.max_y),
    )
    transformed = tuple(
        _inverse_pose(
            placement.transform.apply(corner) + placement.origin, component,
        ) for corner in corners
    )
    body = Box(
        min(p.x for p in transformed), min(p.y for p in transformed),
        max(p.x for p in transformed), max(p.y for p in transformed),
    )
    geometry = [Rectangle(body)]
    pins = []
    for row in spec.rows:
        world = placement.transform.apply(row.anchor) + placement.origin
        endpoint = _inverse_pose(world, component)
        side = _local_side(placement.transform.side(row.side), component)
        if side is Side.LEFT:
            boundary = Point(body.min_x, endpoint.y)
        elif side is Side.RIGHT:
            boundary = Point(body.max_x, endpoint.y)
        elif side is Side.TOP:
            boundary = Point(endpoint.x, body.min_y)
        else:
            boundary = Point(endpoint.x, body.max_y)
        if boundary == endpoint:
            raise ValueError("IC_ADAPTER_ZERO_LEAD")
        if (
            (side is Side.LEFT and endpoint.x >= boundary.x)
            or (side is Side.RIGHT and endpoint.x <= boundary.x)
            or (side is Side.TOP and endpoint.y >= boundary.y)
            or (side is Side.BOTTOM and endpoint.y <= boundary.y)
        ):
            raise ValueError("IC_ADAPTER_LEAD_NORMAL_MISMATCH")
        geometry.append(Line(boundary, endpoint))
        pins.append(GraphicPin(row.number, endpoint, side, display_labels[row.number]))
    # No physical view ink or render transformations are copied into Circuit.
    signature = hashlib.sha256(
        json.dumps({
            "device_id": record.device.identifier,
            "body": [body.min_x, body.min_y, body.max_x, body.max_y],
            "pins": [(p.number, p.at.x, p.at.y, p.side.value) for p in pins],
        }, sort_keys=True).encode("utf-8"),
    ).hexdigest()[:16]
    return SymbolDefinition(
        identifier=f"draft.ic.circuit-surrogate.{signature}",
        revision=spec.revision,
        graphics=tuple(geometry),
        pins=tuple(pins),
        body_keepout=body,
        line_width_um=300,
        status=SymbolStatus.DRAFT,
        standard_refs=(
            "NOT_PRINTABLE_SURROGATE: PAINT owns actual UGO ink",
            "Texas Instruments manufacturer numbers, GOST status DRAFT",
        ),
    )


def _json_pairs(pairs: list[tuple[str, object]]) -> dict:
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("IC_ADAPTER_DUPLICATE_JSON_KEY")
        out[k] = v
    return out


def _strict_keys(obj: object, keys: set[str], context: str) -> dict:
    if type(obj) is not dict or set(obj) != keys:
        raise ValueError(f"IC_ADAPTER_BAD_{context.upper()}_FIELDS")
    return obj


def _point_json(point: Point) -> list[int]:
    return [point.x, point.y]


def _read_point(value: object) -> Point:
    if type(value) is not list or len(value) != 2 or any(
        type(v) is not int for v in value
    ):
        raise ValueError("IC_ADAPTER_INTEGER_UM_POINT_REQUIRED")
    return Point(*value)


@dataclass(frozen=True, slots=True)
class IcCircuitContact:
    pin_ref: PinRef
    unit_id: str
    manufacturer_pin_name: str
    schematic_short_label: str
    electrical_type: IcPinType
    world_anchor: Point
    world_side: Side
    net_id: str | None


@dataclass(frozen=True, slots=True)
class IcCircuitBinding:
    """One device / ONE Circuit component / N functional graphical units."""

    record: IcLibraryRecord
    circuit: Circuit
    aliases: IcPinAliasProfile | None
    external_pin_numbers: tuple[tuple[str, tuple[str, ...]], ...]
    part: PartDefinition
    symbol_surrogate: SymbolDefinition | None
    contacts: tuple[IcCircuitContact, ...]

    @property
    def component_ref(self) -> str:
        return self.record.placements[0].component_ref

    def contact(self, ref: PinRef) -> IcCircuitContact:
        found = tuple(c for c in self.contacts if c.pin_ref == ref)
        if len(found) != 1:
            raise ValueError("IC_ADAPTER_UNKNOWN_PHYSICAL_PINREF")
        return found[0]

    def validate(self) -> None:
        """Re-derive every interface and reject semantic or geometric tampering."""
        expected = bind_ic_circuit(
            self.record, self.circuit, aliases=self.aliases,
            external_pin_numbers=dict(self.external_pin_numbers),
        )
        if self != expected:
            raise ValueError("IC_ADAPTER_INTEGRITY_MISMATCH")

    def revise(
        self, candidate: IcLibraryRecord, *,
        consent: IcGeometryConsent | None = None,
    ) -> tuple[IcCircuitBinding, IcGraphicRevisionDelta]:
        """Explicit proposal: no Net rewrite, linked wire reroute separately."""
        delta = validate_ic_graphic_revision(
            self.record, candidate, circuit=self.circuit, consent=consent,
        )
        updated = bind_ic_circuit(
            candidate, self.circuit, aliases=self.aliases,
            external_pin_numbers=dict(self.external_pin_numbers),
        )
        if updated.circuit != self.circuit:
            raise ValueError("IC_ADAPTER_REVISION_MUTATED_NET")
        return updated, delta

    def bind_paint(self, paint_binding) -> object:
        """The caller supplies PAINT's genuine resolved view; no mock view."""
        from gost_schematic.electrical.ic_editor_targets import (
            make_ic_editor_manifest,
        )
        from gost_schematic.electrical.ic_paint_bridge import IcPaintBinding

        if not isinstance(paint_binding, IcPaintBinding):
            raise TypeError("IC_ADAPTER_REQUIRES_REAL_PAINT_BINDING")
        if paint_binding.record != self.record:
            raise ValueError("IC_ADAPTER_STALE_PAINT_GEOMETRY")
        paint_binding.verify_endpoints()
        manifest = make_ic_editor_manifest(paint_binding, self.circuit)
        mapped = {item.pin_ref: item for item in self.contacts}
        if len(manifest.contacts) != len(mapped):
            raise ValueError("IC_ADAPTER_PAINT_PIN_COVERAGE_MISMATCH")
        for item in manifest.contacts:
            physical = mapped.get(item.pin_ref)
            if physical is None or (
                physical.world_anchor != item.anchor
                or physical.net_id != item.net_id
                or physical.electrical_type is not item.electrical_type
                or physical.manufacturer_pin_name != item.pin_name
                or physical.unit_id != item.unit_id
            ):
                raise ValueError("IC_ADAPTER_PAINT_CONTACT_MISMATCH")
        return manifest

    def to_json(self) -> str:
        """Strict schema v1 including full physical IC and real 23-part Circuit."""
        aliases = None
        if self.aliases is not None:
            aliases = {
                "component_ref": self.aliases.component_ref,
                "device_id": self.aliases.device_id,
                "max_display_chars": self.aliases.max_display_chars,
                "labels": [{
                    "physical_number": a.physical_number,
                    "manufacturer_pin_name": a.manufacturer_pin_name,
                    "schematic_short_label": a.schematic_short_label,
                    "electrical_type": a.electrical_type.value,
                    "real_pin_ref": [
                        a.real_pin_ref.reference, a.real_pin_ref.number,
                    ],
                    "display_orientation": a.display_orientation.value,
                    "source_document_reference": a.source_document_reference,
                } for a in self.aliases.labels],
            }
        value = {
            "schema_version": 1,
            "record_type": "DRAFT_IC_CIRCUIT_PINREF_BINDING",
            "ic_record": json.loads(ic_to_json(self.record)),
            "aliases": aliases,
            "external_pin_numbers": {
                ref: list(nums) for ref, nums in self.external_pin_numbers
            },
            "components": [{
                "reference": c.reference,
                "part_id": c.part_id,
                "origin_um": _point_json(c.origin),
                "rotation": c.transform.rotation,
                "mirror_x": c.transform.mirror_x,
                "nominal": c.nominal.to_record() if c.nominal else None,
            } for c in self.circuit.components],
            "nets": [{
                "name": n.name,
                "members": [[m.reference, m.number] for m in n.members],
            } for n in self.circuit.nets],
        }
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, payload: str) -> IcCircuitBinding:
        if not isinstance(payload, str):
            raise TypeError("IC_ADAPTER_JSON_TEXT_REQUIRED")
        value = json.loads(
            payload, object_pairs_hook=_json_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("IC_ADAPTER_NONFINITE_JSON_FORBIDDEN"),
            ),
        )
        value = _strict_keys(value, {
            "schema_version", "record_type", "ic_record", "aliases",
            "external_pin_numbers", "components", "nets",
        }, "ROOT")
        if (type(value["schema_version"]) is not int
                or value["schema_version"] != 1
                or value["record_type"] != "DRAFT_IC_CIRCUIT_PINREF_BINDING"):
            raise ValueError("IC_ADAPTER_SCHEMA_UNSUPPORTED")
        record = ic_from_json(json.dumps(value["ic_record"]))
        alias_data = value["aliases"]
        aliases = None
        if alias_data is not None:
            alias_data = _strict_keys(alias_data, {
                "component_ref", "device_id", "max_display_chars", "labels",
            }, "ALIASES")
            if type(alias_data["labels"]) is not list:
                raise ValueError("IC_ADAPTER_LABEL_LIST_REQUIRED")
            items = []
            for source in alias_data["labels"]:
                source = _strict_keys(source, {
                    "physical_number", "manufacturer_pin_name",
                    "schematic_short_label", "electrical_type", "real_pin_ref",
                    "display_orientation", "source_document_reference",
                }, "ALIAS")
                ref = source["real_pin_ref"]
                if type(ref) is not list or len(ref) != 2 or any(
                    type(v) is not str for v in ref
                ):
                    raise ValueError("IC_ADAPTER_PINREF_PAIR_REQUIRED")
                items.append(IcPinDisplayAlias(
                    physical_number=source["physical_number"],
                    manufacturer_pin_name=source["manufacturer_pin_name"],
                    schematic_short_label=source["schematic_short_label"],
                    electrical_type=IcPinType(source["electrical_type"]),
                    real_pin_ref=PinRef(*ref),
                    display_orientation=IcPinDisplayOrientation(
                        source["display_orientation"],
                    ),
                    source_document_reference=source["source_document_reference"],
                ))
            aliases = IcPinAliasProfile(
                alias_data["component_ref"], alias_data["device_id"],
                tuple(items), alias_data["max_display_chars"],
            )
        inventory = value["external_pin_numbers"]
        if type(inventory) is not dict:
            raise ValueError("IC_ADAPTER_EXTERNAL_INVENTORY_REQUIRED")
        external = {}
        for ref, numbers in inventory.items():
            if type(ref) is not str or type(numbers) is not list or any(
                type(n) is not str for n in numbers
            ):
                raise ValueError("IC_ADAPTER_EXTERNAL_PINS_TYPED_REQUIRED")
            external[ref] = tuple(numbers)
        if type(value["components"]) is not list or type(value["nets"]) is not list:
            raise ValueError("IC_ADAPTER_CIRCUIT_LISTS_REQUIRED")
        components = []
        for item in value["components"]:
            item = _strict_keys(item, {
                "reference", "part_id", "origin_um", "rotation",
                "mirror_x", "nominal",
            }, "COMPONENT")
            origin = _read_point(item["origin_um"])
            if (type(item["rotation"]) is not int
                    or type(item["mirror_x"]) is not bool):
                raise ValueError("IC_ADAPTER_TRANSFORM_TYPED_REQUIRED")
            nominal = item["nominal"]
            if nominal is not None:
                nominal = Quantity.from_record(_strict_keys(nominal, {
                    "schema_version", "kind", "si_value",
                }, "NOMINAL"))
            components.append(ComponentInstance(
                item["reference"], item["part_id"], origin,
                Transform(item["rotation"], item["mirror_x"]), nominal,
            ))
        nets = []
        for item in value["nets"]:
            item = _strict_keys(item, {"name", "members"}, "NET")
            members = item["members"]
            if type(members) is not list:
                raise ValueError("IC_ADAPTER_NET_MEMBERS_LIST_REQUIRED")
            collected = []
            for m in members:
                if type(m) is not list or len(m) != 2 or any(
                    type(n) is not str for n in m
                ):
                    raise ValueError("IC_ADAPTER_NET_PINREF_PAIR_REQUIRED")
                collected.append(PinRef(*m))
            nets.append(Net(item["name"], tuple(collected)))
        return bind_ic_circuit(
            record, Circuit(tuple(components), tuple(nets)),
            aliases=aliases, external_pin_numbers=external,
        )


def bind_ic_circuit(
    record: IcLibraryRecord, circuit: Circuit, *,
    aliases: IcPinAliasProfile | None = None,
    external_pin_numbers: dict[str, tuple[str, ...]] | None = None,
) -> IcCircuitBinding:
    """Fail closed on all typed source + complete external Net references."""
    if not isinstance(record, IcLibraryRecord) or not isinstance(circuit, Circuit):
        raise TypeError("IC_ADAPTER_REQUIRES_TYPED_RECORD_AND_CIRCUIT")
    # A hostile caller may forge BOTH the pin table and its UI alias object.
    # Neither ERC nor two mutually matching edited objects establish TI truth.
    from gost_schematic.electrical.tl494cn import (
        TI_DEVICE_ID,
        verify_tl494cn_ti_pinout,
    )

    if record.device.identifier == TI_DEVICE_ID:
        verify_tl494cn_ti_pinout(record.device)
    ref = record.placements[0].component_ref
    # The common IC validator does not distinguish duplicate entries in a
    # single Net from ownership across two Nets. Preserve typed error cases
    # BEFORE running the older IC-only validator; neither may be ignored.
    preliminary_members: set[PinRef] = set()
    for net in circuit.nets:
        if len(set(net.members)) != len(net.members):
            raise ValueError("IC_ADAPTER_DUPLICATE_NET_MEMBER")
        for item in net.members:
            if item in preliminary_members:
                raise ValueError("IC_ADAPTER_MULTIPLE_NET_OWNERSHIP")
            preliminary_members.add(item)
    validate_ic_circuit(record.device, circuit, ref)
    if len({c.reference for c in circuit.components}) != len(circuit.components):
        raise ValueError("IC_ADAPTER_DUPLICATE_COMPONENT")
    if len({n.name for n in circuit.nets}) != len(circuit.nets):
        raise ValueError("IC_ADAPTER_DUPLICATE_NET")
    if aliases is not None:
        if not isinstance(aliases, IcPinAliasProfile):
            raise TypeError("IC_ADAPTER_ALIASES_TYPED_REQUIRED")
        verify_alias_display(aliases, record)
    positions = resolve_ic_pin_positions(
        record.device, record.specs, record.placements,
    )
    sides = resolve_ic_port_sides(
        record.device, record.specs, record.placements,
    )
    if len(positions) != record.device.package.pin_count:
        raise ValueError("IC_ADAPTER_MISSING_PHYSICAL_PINS")
    if len(set(positions.values())) != len(positions):
        raise ValueError("IC_ADAPTER_DUPLICATE_WORLD_ENDPOINT")
    external = {} if external_pin_numbers is None else external_pin_numbers
    if type(external) is not dict:
        raise TypeError("IC_ADAPTER_EXTERNAL_INVENTORY_TYPED_REQUIRED")
    expected_external = {
        c.reference for c in circuit.components if c.reference != ref
    }
    if set(external) != expected_external:
        raise ValueError("IC_ADAPTER_EXTERNAL_PIN_INVENTORY_INCOMPLETE")
    for comp, numbers in external.items():
        if not isinstance(comp, str) or (
            type(numbers) is not tuple or not numbers
            or any(type(n) is not str or not n for n in numbers)
            or len(set(numbers)) != len(numbers)
        ):
            raise ValueError("IC_ADAPTER_EXTERNAL_PIN_INVENTORY_INVALID")
    members: dict[PinRef, str] = {}
    for net in circuit.nets:
        if len(set(net.members)) != len(net.members):
            raise ValueError("IC_ADAPTER_DUPLICATE_NET_MEMBER")
        for physical in net.members:
            if physical in members:
                raise ValueError("IC_ADAPTER_MULTIPLE_NET_OWNERSHIP")
            members[physical] = net.name
            if physical.reference == ref:
                if physical not in positions:
                    raise ValueError("IC_ADAPTER_UNKNOWN_IC_PHYSICAL_PIN")
                if record.device.pin_map[physical.number].electrical_type is IcPinType.NC:
                    raise ValueError("IC_ADAPTER_NC_CONNECTED")
            elif (
                physical.reference not in external
                or physical.number not in external[physical.reference]
            ):
                raise ValueError("IC_ADAPTER_FOREIGN_OR_UNKNOWN_EXTERNAL_PIN")
    ownership = {}
    for spec in record.specs:
        for row in spec.rows:
            if row.number in ownership:
                raise ValueError("IC_ADAPTER_DUPLICATE_FUNCTIONAL_UNIT_OWNER")
            ownership[row.number] = spec.unit_id
    if set(ownership) != set(record.device.pin_map):
        raise ValueError("IC_ADAPTER_UNOWNED_PHYSICAL_CONTACT")
    physical_names = {p.number: p.name for p in record.device.pins}
    display_labels = {
        row.number: row.label for spec in record.specs for row in spec.rows
    }
    if aliases is not None:
        display_labels = {
            a.physical_number: a.schematic_short_label for a in aliases.labels
        }
    for number, item in record.device.pin_map.items():
        if (physical_names[number] != item.name
                or number not in display_labels):
            raise ValueError("IC_ADAPTER_MANUFACTURER_PIN_CHANGED")
    contacts = tuple(IcCircuitContact(
        pin_ref=PinRef(ref, p.number),
        unit_id=ownership[p.number],
        manufacturer_pin_name=p.name,
        schematic_short_label=display_labels[p.number],
        electrical_type=p.electrical_type,
        world_anchor=positions[PinRef(ref, p.number)],
        world_side=sides[PinRef(ref, p.number)],
        net_id=members.get(PinRef(ref, p.number)),
    ) for p in record.device.pins)
    if any(p.electrical_type is IcPinType.NC for p in record.device.pins):
        # Common ElectricalType does not represent NC, never lie PASSIVE.
        raise ValueError("IC_ADAPTER_UNSUPPORTED_LEGACY_NC_PIN")
    part = PartDefinition(
        identifier=record.device.identifier,
        reference_prefix=record.device.kind.reference_prefix,
        symbol_id=f"draft.ic.circuit-surrogate.{record.device.identifier}",
        pins=tuple(PhysicalPin(
            p.number, p.name, ElectricalType(p.electrical_type.value),
        ) for p in record.device.pins),
    )
    physical_instance = next(
        c for c in circuit.components if c.reference == ref
    )
    symbol = None
    if len(record.specs) == 1:
        symbol = _single_symbol(record, physical_instance, display_labels)
        part = PartDefinition(
            part.identifier, part.reference_prefix, symbol.identifier, part.pins,
        )
        native_points = physical_instance.pin_positions(symbol)
        if native_points != {
            pin.number: positions[pin.pin_ref] for pin in contacts
        }:
            raise ValueError("IC_ADAPTER_NATIVE_GRAPHIC_WORLD_DRIFT")
        if {pin.number: pin.name for pin in part.pins} != physical_names:
            raise ValueError("IC_ADAPTER_LEGACY_PART_PIN_NAME_LOSS")
    return IcCircuitBinding(
        record, circuit, aliases,
        tuple(sorted(external.items())),
        part, symbol, contacts,
    )
