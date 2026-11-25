"""Ensure reference symbols really load and do not create fake conductive shorts."""
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_resistor_batch02 import IDS, generate
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol


@pytest.mark.parametrize("identifier", IDS)
def test_new_symbol_ports_and_topology(identifier):
    part, symbol = CatalogResolver().resolve(identifier)
    assert [p.number for p in part.pins] == [p.number for p in symbol.pins]
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    result = inspect_conductor_topology(symbol)
    assert result.valid
    assert result.pin_islands == symbol.conductor_topology.pin_groups
    assert symbol.status.value == "draft"


def test_native_review_notes_and_contacts(tmp_path: Path):
    generate(tmp_path)
    ns = "{http://www.w3.org/2000/svg}"
    catalog = CatalogResolver()
    for identifier in IDS:
        symbol = catalog.symbols[identifier]
        clean = ET.parse(tmp_path / f"{identifier}-clean.svg").getroot()
        review = ET.parse(tmp_path / f"{identifier}-diagnostic.svg").getroot()
        assert not clean.findall(f"./{ns}circle")
        assert len(review.findall(f"./{ns}circle")) == len(symbol.pins)
        assert len(review.findall(f"./{ns}text[@data-pin]")) == len(symbol.pins)
        assert len(clean.findall(f"./{ns}text[@data-note]")) == len(symbol.constant_annotations)
        assert review.find(f"./{ns}rect") is not None
