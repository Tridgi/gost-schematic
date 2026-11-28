"""Batch 01: native catalogue and real SVG regression."""
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_resistor_batch01 import IDS, generate
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Rectangle
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol


@pytest.mark.parametrize("identifier", IDS)
def test_source_backed_resistor_variant(identifier):
    part, symbol = CatalogResolver().resolve(identifier)
    assert symbol.status == SymbolStatus.DRAFT
    assert len(part.pins) == len(symbol.pins)
    body = next(g.box for g in symbol.graphics if isinstance(g, Rectangle))
    assert (body.max_x - body.min_x, body.max_y - body.min_y) == (10000, 4000)
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    trace = inspect_conductor_topology(symbol)
    assert trace.valid
    assert trace.pin_islands == symbol.conductor_topology.pin_groups
    if "power_" in identifier:
        assert symbol.conductor_topology.conductor_indices == (1, 2)
        assert len(symbol.graphics) > 3
    if "rheostat" in identifier:
        assert len(symbol.pins) == 2
    if identifier == "resistor.shunt_kelvin":
        assert trace.pin_islands == (("1", "3"), ("2", "4"))


def test_native_render_files(tmp_path: Path):
    generate(tmp_path)
    ns = "{http://www.w3.org/2000/svg}"
    catalog = CatalogResolver()
    for identifier in IDS:
        clean = ET.parse(tmp_path / f"{identifier}-clean.svg").getroot()
        diagnostic = ET.parse(tmp_path / f"{identifier}-diagnostic.svg").getroot()
        assert not clean.findall(f"./{ns}circle")
        assert len(diagnostic.findall(f"./{ns}circle")) == len(catalog.symbols[identifier].pins)
        assert diagnostic.find(f"./{ns}rect") is not None
