"""All installed entries must appear once in each native review view."""
from xml.etree import ElementTree as ET

from examples.review_full_catalog_native import SVG, generate
from gost_schematic.agent_project.catalog import CatalogResolver


def test_full_native_gallery_covers_installed_catalog(tmp_path):
    catalog = CatalogResolver()
    assert generate(tmp_path) == len(catalog.symbols)
    seen = {"clean": [], "diagnostic": []}
    for path in sorted(tmp_path.glob("catalog-*.svg")):
        root = ET.parse(path).getroot()
        for group in root.findall(f"{SVG}g[@data-symbol-id]"):
            identifier = group.get("data-symbol-id")
            view = group.get("data-view")
            seen[view].append(identifier)
            symbol = catalog.symbols[identifier]
            assert len(group.findall(f"{SVG}circle")) == (
                len(symbol.pins) if view == "diagnostic" else 0
            )
            assert len(group.findall(f"{SVG}text[@data-note]")) == len(
                symbol.constant_annotations
            )
    for values in seen.values():
        assert values == sorted(catalog.symbols)
