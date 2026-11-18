"""Installed physical catalog resolver. Never infer pinouts from artwork."""
import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from importlib.resources import files
from pathlib import Path
from typing import Any

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part


class ProjectError(ValueError):
    """Stable fail-closed application error code."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def normalized(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return format(value, "f")
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: normalized(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (tuple, list)):
        return [normalized(item) for item in value]
    if isinstance(value, Mapping):
        return {str(k): normalized(v) for k, v in value.items()}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise ProjectError("CATALOG_UNSUPPORTED", f"Unsupported catalog data: {type(value)}")


def canonical_bytes(record: dict[str, Any]) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def value_digest(value: Any) -> str:
    return digest(canonical_bytes(normalized(value)))


class CatalogResolver:
    """Load actual installed part/symbol JSON and parametric winding definitions."""

    def __init__(self) -> None:
        self.parts: dict[str, Any] = {}
        self.symbols: dict[str, Any] = {}
        root = Path(str(files("gost_schematic").joinpath("catalog")))
        for source in sorted(root.joinpath("parts").rglob("*.json")):
            part = load_part(source)
            if part.identifier in self.parts:
                raise ProjectError("CATALOG_DUPLICATE", part.identifier)
            self.parts[part.identifier] = part
        for source in sorted(root.joinpath("symbols").rglob("*.json")):
            symbol = load_symbol(source)
            if symbol.identifier in self.symbols:
                raise ProjectError("CATALOG_DUPLICATE", symbol.identifier)
            self.symbols[symbol.identifier] = symbol
        for source in sorted(root.joinpath("inductors").glob("*.json")):
            winding = load_inductor(source)
            if winding.part.identifier in self.parts or winding.symbol.identifier in self.symbols:
                raise ProjectError("CATALOG_DUPLICATE", winding.part.identifier)
            self.parts[winding.part.identifier] = winding.part
            self.symbols[winding.symbol.identifier] = winding.symbol

    def resolve(self, part_id: str) -> tuple[Any, Any]:
        part = self.parts.get(part_id)
        if part is None:
            raise ProjectError("CATALOG_PART_MISSING", f"No installed physical part {part_id}")
        symbol = self.symbols.get(part.symbol_id)
        if symbol is None:
            raise ProjectError("CATALOG_SYMBOL_MISSING", part.symbol_id)
        if {pin.number for pin in part.pins} != {pin.number for pin in symbol.pins}:
            raise ProjectError("CATALOG_PIN_MISMATCH", part_id)
        return part, symbol

    def lock(self, part_id: str) -> dict[str, Any]:
        part, symbol = self.resolve(part_id)
        return {
            "part_id": part.identifier,
            "part_sha256": value_digest(part),
            "symbol_id": symbol.identifier,
            "symbol_sha256": value_digest(symbol),
            "symbol_revision": symbol.revision,
            "symbol_status": symbol.status.value,
            "physical_pins": [
                {"number": pin.number, "name": pin.name,
                 "electrical_type": pin.electrical_type.value,
                 "polarity": pin.polarity.value, "function": pin.function.value}
                for pin in part.pins
            ],
        }

    def verify(self, locks: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
        parts: dict[str, Any] = {}
        symbols: dict[str, Any] = {}
        for item in locks:
            if not isinstance(item, Mapping) or not isinstance(item.get("part_id"), str):
                raise ProjectError("CATALOG_REVISION_MISMATCH", "Invalid pinned part")
            if normalized(item) != self.lock(item["part_id"]):
                raise ProjectError("CATALOG_REVISION_MISMATCH", item["part_id"])
            part, symbol = self.resolve(item["part_id"])
            parts[part.identifier] = part
            symbols[symbol.identifier] = symbol
        if len(parts) != len(locks):
            raise ProjectError("CATALOG_DUPLICATE", "Repeated physical part in project lock")
        return parts, symbols
