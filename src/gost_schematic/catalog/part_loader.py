"""Versioned, reviewable physical part catalog, separate from graphic UGO JSON."""

import json
from pathlib import Path
from typing import Any

from gost_schematic.catalog.loader import CatalogError
from gost_schematic.model.part import PartDefinition, VoltageOrientationRule
from gost_schematic.model.pins import ElectricalType, PhysicalPin, TerminalPolarity
from gost_schematic.model.quantities import QuantityKind


def parse_part(data: dict[str, Any]) -> PartDefinition:
    """Parse a physical component, never infer its terminal roles from pin labels."""
    if not isinstance(data, dict):
        raise CatalogError("Part document must be an object")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise CatalogError("Unsupported physical part schema_version")
    try:
        part = PartDefinition(
            identifier=data["id"],
            reference_prefix=data["reference_prefix"],
            symbol_id=data["symbol_id"],
            pins=tuple(
                PhysicalPin(
                    number=str(pin["number"]),
                    name=pin["name"],
                    electrical_type=ElectricalType(pin["electrical_type"]),
                    polarity=TerminalPolarity(pin.get("polarity", "none")),
                )
                for pin in data["pins"]
            ),
            nominal_kind=(
                QuantityKind(data["nominal_kind"])
                if data.get("nominal_kind") is not None
                else None
            ),
            voltage_orientation_rule=VoltageOrientationRule(
                data.get("voltage_orientation_rule", "none")
            ),
        )
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        raise CatalogError(f"Invalid physical part {data.get('id', '<unknown>')}: {error}") from error
    return part


def load_part(path: str | Path) -> PartDefinition:
    try:
        content = Path(path).read_text(encoding="utf-8")
        document = json.loads(content)
    except (OSError, ValueError) as error:
        raise CatalogError(f"Cannot load part from {path}: {error}") from error
    return parse_part(document)
