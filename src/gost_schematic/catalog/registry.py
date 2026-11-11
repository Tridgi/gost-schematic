"""Explicitly scoped registry; no mutable process-wide singleton."""
from dataclasses import dataclass, field
from pathlib import Path

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.model.symbol import SymbolDefinition


@dataclass(slots=True)
class SymbolCatalog:
    _symbols: dict[str, SymbolDefinition] = field(default_factory=dict)

    def register(self, symbol: SymbolDefinition) -> None:
        if symbol.identifier in self._symbols:
            raise ValueError(f"Symbol already registered: {symbol.identifier}")
        self._symbols[symbol.identifier] = symbol

    def get(self, identifier: str) -> SymbolDefinition:
        return self._symbols[identifier]

    def identifiers(self) -> tuple[str, ...]:
        return tuple(sorted(self._symbols))

    @classmethod
    def from_directory(cls, path: str | Path) -> "SymbolCatalog":
        result = cls()
        for filename in sorted(Path(path).rglob("*.json")):
            result.register(load_symbol(filename))
        return result
