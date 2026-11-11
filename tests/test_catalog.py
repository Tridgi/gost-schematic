import json

import pytest

from gost_schematic.catalog.loader import CatalogError, parse_symbol
from gost_schematic.catalog.registry import SymbolCatalog
from gost_schematic.core.diagnostics import Severity
from gost_schematic.validation.symbol_checks import validate_symbol


def test_draft_resistor_loads_and_has_stable_geometry(resistor):
    assert resistor.identifier == "resistor.fixed"
    assert resistor.revision == 1
    assert [pin.number for pin in resistor.pins] == ["1", "2"]
    assert resistor.bounds.min_x == -8000
    assert resistor.bounds.max_x >= 8000
    diagnostics = validate_symbol(resistor)
    assert not [issue for issue in diagnostics if issue.severity == Severity.ERROR]
    assert any(issue.code == "UNAPPROVED_SYMBOL" for issue in diagnostics)


def test_registry_refuses_implicit_overwrites(resistor):
    catalog = SymbolCatalog()
    catalog.register(resistor)
    assert catalog.get("resistor.fixed") is resistor
    with pytest.raises(ValueError, match="already registered"):
        catalog.register(resistor)


def test_catalog_schema_rejects_unsupported_versions(resistor_path):
    payload = json.loads(resistor_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 100
    with pytest.raises(CatalogError, match="schema_version"):
        parse_symbol(payload)


def test_pin_direction_must_be_exposed(resistor_path):
    payload = json.loads(resistor_path.read_text(encoding="utf-8"))
    payload["pins"][0]["side"] = "right"
    result = parse_symbol(payload)
    assert "PIN_NOT_EXPOSED" in {issue.code for issue in validate_symbol(result)}


def test_duplicate_pin_number_is_never_accepted(resistor_path):
    payload = json.loads(resistor_path.read_text(encoding="utf-8"))
    payload["pins"][1]["number"] = "1"
    with pytest.raises(CatalogError, match="Duplicate"):
        parse_symbol(payload)
