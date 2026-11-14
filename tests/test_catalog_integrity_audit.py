"""Global catalog quality gate is deterministic and honest about approval."""

import json
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.model.pins import TerminalPolarity
from scripts.audit_symbol_catalog import audit_catalog, main


def test_all_current_catalog_symbols_pass_structural_integrity_audit():
    result = audit_catalog()
    assert result["schema_version"] == 1
    # Accepted original inventory is a lower bound, not a ceiling for YGO.
    assert result["total_symbols"] >= 19
    assert result["total_symbols"] == len(result["entries"])
    assert result["draft_count"] == result["total_symbols"]
    assert result["hard_errors"] == 0
    assert result["error_details"] == []
    assert result["without_physical_part"] == []
    assert [item["id"] for item in result["entries"]] == sorted(
        item["id"] for item in result["entries"]
    )
    assert len({item["id"] for item in result["entries"]}) == result["total_symbols"]
    for item in result["entries"]:
        assert len(item["source_sha256"]) == 64
        assert item["physical_part_mapped"]
        assert item["approval"] == "draft"
        assert item["pin_count"] >= (1 if item["id"] in {
            "connector.plug_contact", "connector.socket_contact"
        } else 2)
        assert item["stroked_bounds_mm"]
        assert not [
            issue for issue in item["diagnostics"]
            if issue["severity"] == "error"
        ]


def test_resistor_now_has_a_real_physical_part_and_pins():
    root = files("gost_schematic").joinpath("catalog")
    part = load_part(Path(str(root.joinpath("parts/resistors/fixed.json"))))
    symbol = load_symbol(Path(str(root.joinpath("symbols/resistors/fixed.json"))))
    assert part.symbol_id == symbol.identifier == "resistor.fixed"
    assert part.reference_prefix == "R"
    assert [pin.number for pin in part.pins] == [pin.number for pin in symbol.pins]
    assert [pin.polarity for pin in part.pins] == [
        TerminalPolarity.NONE, TerminalPolarity.NONE,
    ]


def test_audit_report_exactly_reproducible_across_runs(tmp_path):
    path = tmp_path / "symbol-catalog.json"
    assert main(["--output", str(path)]) == 0
    first = path.read_bytes()
    assert main(["--output", str(path)]) == 0
    assert path.read_bytes() == first
    assert json.loads(first) == audit_catalog()
