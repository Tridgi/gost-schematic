"""Strict deterministic PRIVATE DRAFT JSON v1 for a physical IC and its E3 views."""

import json
from dataclasses import dataclass

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.ic import (
    IcBodyAxis,
    IcDeviceDefinition,
    IcField,
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
    resolve_ic_pin_positions,
)


@dataclass(frozen=True, slots=True)
class IcLibraryRecord:
    device: IcDeviceDefinition
    specs: tuple[IcSymbolSpec, ...]
    placements: tuple[IcUnitPlacement, ...]

    def __post_init__(self) -> None:
        resolve_ic_pin_positions(self.device, self.specs, self.placements)


def _point(point: Point) -> list[int]:
    return [point.x, point.y]


def _p(raw: object) -> Point:
    if type(raw) is not list or len(raw) != 2 or any(type(x) is not int for x in raw):
        raise ValueError("Point requires exactly two integer µm values")
    return Point(raw[0], raw[1])


def _b(raw: object) -> Box:
    if type(raw) is not list or len(raw) != 4 or any(type(x) is not int for x in raw):
        raise ValueError("Box requires exactly four integer µm values")
    return Box(*raw)


def _object(raw: object, fields: set[str]) -> dict:
    if type(raw) is not dict or set(raw) != fields:
        raise ValueError(f"Expected exactly fields {sorted(fields)}")
    return raw


def _array(raw: object) -> list:
    if type(raw) is not list:
        raise ValueError("Expected JSON array")
    return raw


def _pairs(values: list[tuple[str, object]]) -> dict:
    result = {}
    for k, v in values:
        if k in result:
            raise ValueError(f"Duplicate JSON key: {k}")
        result[k] = v
    return result


def _forbid_constant(value: str) -> None:
    raise ValueError(f"Invalid nonfinite numeric value: {value}")


def ic_to_json(record: IcLibraryRecord) -> str:
    if not isinstance(record, IcLibraryRecord):
        raise TypeError("Expected IcLibraryRecord")
    extended = any(s.profile != IcGraphicProfile() for s in record.specs)
    d = record.device
    p = d.package
    value = {
        "schema_version": 2 if extended else 1,
        "record_type": "DRAFT_E3_IC",
        "device": {
            "identifier": d.identifier, "kind": d.kind.value,
            "package": {
                "package_id": p.package_id, "family": p.family,
                "pin_count": p.pin_count, "origin": p.origin.value,
                "manufacturer": p.manufacturer,
                "datasheet_url": p.datasheet_url, "revision": p.revision,
            },
            "pins": [{
                "number": x.number, "name": x.name, "function": x.function,
                "electrical_type": x.electrical_type.value,
            } for x in d.pins],
            "units": [{
                "id": u.id, "function": u.function,
                "pin_numbers": list(u.pin_numbers),
            } for u in d.units],
        },
        "specs": [{
            "device_id": s.device_id, "unit_id": s.unit_id,
            "body_um": [s.body.min_x, s.body.min_y, s.body.max_x, s.body.max_y],
            "main_field": s.main_field, "aux_left": s.aux_left,
            "aux_right": s.aux_right, "revision": s.revision,
            **({"graphic_profile": {
                "port_layout": s.profile.port_layout.value,
                "body_axis": s.profile.body_axis.value,
                "function_angle": s.profile.function_angle.value,
                "other_text_angle": s.profile.other_text_angle.value,
            }} if extended else {}),
            "rows": [{
                "number": row.number, "side": row.side.value,
                "anchor_um": _point(row.anchor), "row_key": row.row_key,
                "label": row.label, "field": row.field.value,
                "visual_row": row.visual_row,
            } for row in s.rows],
        } for s in record.specs],
        "placements": [{
            "component_ref": t.component_ref, "device_id": t.device_id,
            "unit_id": t.unit_id, "origin_um": _point(t.origin),
            "rotation": t.transform.rotation,
            "mirror_x": t.transform.mirror_x,
        } for t in record.placements],
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def ic_from_json(data: str) -> IcLibraryRecord:
    if not isinstance(data, str):
        raise TypeError("Expected IC JSON string")
    raw = _object(
        json.loads(data, object_pairs_hook=_pairs, parse_constant=_forbid_constant),
        {"schema_version", "record_type", "device", "specs", "placements"},
    )
    version = raw["schema_version"]
    if type(version) is not int or version not in (1, 2):
        raise ValueError("Unsupported IC schema version")
    if raw["record_type"] != "DRAFT_E3_IC":
        raise ValueError("Not a DRAFT physical E3 IC record")
    item = _object(raw["device"], {"identifier", "kind", "package", "pins", "units"})
    pkg = _object(item["package"], {
        "package_id", "family", "pin_count", "origin",
        "manufacturer", "datasheet_url", "revision",
    })
    device = IcDeviceDefinition(
        identifier=item["identifier"],
        kind=IcKind(item["kind"]),
        package=IcPackage(
            package_id=pkg["package_id"], family=pkg["family"],
            pin_count=pkg["pin_count"], origin=PinoutOrigin(pkg["origin"]),
            manufacturer=pkg["manufacturer"], datasheet_url=pkg["datasheet_url"],
            revision=pkg["revision"],
        ),
        pins=tuple(IcPhysicalPin(
            **_object(p, {"number", "name", "function", "electrical_type"})
            | {"electrical_type": IcPinType(p["electrical_type"])}
        ) for p in _array(item["pins"])),
        units=tuple(IcUnit(
            **{**_object(u, {"id", "function", "pin_numbers"}),
               "pin_numbers": tuple(_array(u["pin_numbers"]))}
        ) for u in _array(item["units"])),
    )
    specs = []
    for s in _array(raw["specs"]):
        expected = {
            "device_id", "unit_id", "body_um", "main_field",
            "aux_left", "aux_right", "revision", "rows",
        }
        if version == 2:
            expected.add("graphic_profile")
        s = _object(s, expected)
        profile = IcGraphicProfile()
        if version == 2:
            g = _object(s["graphic_profile"], {
                "port_layout", "body_axis", "function_angle", "other_text_angle",
            })
            for field_name in ("function_angle", "other_text_angle"):
                if type(g[field_name]) is not int:
                    raise ValueError("IC_TEXT_ANGLE_TYPED_REQUIRED")
            profile = IcGraphicProfile(
                port_layout=IcPortLayout(g["port_layout"]),
                body_axis=IcBodyAxis(g["body_axis"]),
                function_angle=IcTextAngle(g["function_angle"]),
                other_text_angle=IcTextAngle(g["other_text_angle"]),
            )
        rows = []
        for row in _array(s["rows"]):
            row = _object(row, {
                "number", "side", "anchor_um", "row_key", "label", "field",
                "visual_row",
            })
            rows.append(IcPinRow(
                number=row["number"], side=Side(row["side"]),
                anchor=_p(row["anchor_um"]), row_key=row["row_key"],
                label=row["label"], field=IcField(row["field"]),
                visual_row=row["visual_row"],
            ))
        specs.append(IcSymbolSpec(
            device_id=s["device_id"], unit_id=s["unit_id"],
            body=_b(s["body_um"]), main_field=s["main_field"], rows=tuple(rows),
            aux_left=s["aux_left"], aux_right=s["aux_right"],
            revision=s["revision"], profile=profile,
        ))
    placements = []
    for p in _array(raw["placements"]):
        p = _object(p, {
            "component_ref", "device_id", "unit_id", "origin_um",
            "rotation", "mirror_x",
        })
        placements.append(IcUnitPlacement(
            component_ref=p["component_ref"], device_id=p["device_id"],
            unit_id=p["unit_id"], origin=_p(p["origin_um"]),
            transform=Transform(p["rotation"], p["mirror_x"]),
        ))
    return IcLibraryRecord(device, tuple(specs), tuple(placements))
