"""Every installed UGO appears in all three aligned native catalog views."""
import json
from xml.etree import ElementTree as ET

from examples.review_categorized_catalog import SVG, VIEWS, generate
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.rendering.svg import render_symbol_svg


def test_categorized_catalog_exact_native_views(tmp_path):
    catalog = CatalogResolver()
    manifest = generate(tmp_path)
    assert manifest == json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["symbol_count"] == len(catalog.symbols)
    seen = {view: [] for view in VIEWS}
    for family in manifest["categories"]:
        assert family["count"] == sum(len(p["symbols"]) for p in family["pages"])
        for page in family["pages"]:
            positions = {}
            for view in VIEWS:
                root = ET.parse(tmp_path / page["files"][view]).getroot()
                assert root.get("data-category") == family["id"]
                groups = root.findall(f"{SVG}g[@data-symbol-id]")
                assert [g.get("data-symbol-id") for g in groups] == page["symbols"]
                for group in groups:
                    identifier = group.get("data-symbol-id")
                    assert identifier.split(".", 1)[0] == family["id"]
                    seen[view].append(identifier)
                    if view == "clean":
                        positions[identifier] = group.get("transform")
                    else:
                        assert positions[identifier] == group.get("transform")
                    symbol = catalog.symbols[identifier]
                    native = ET.fromstring(render_symbol_svg(
                        symbol, review_overlay=view != "clean",
                    ))
                    for tag in ("rect", "circle", "g"):
                        actual = group.findall(SVG + tag)
                        expected = native.findall(SVG + tag)
                        if view == "protection" and tag == "g":
                            assert not actual
                        else:
                            assert [ET.tostring(x) for x in actual] == [
                                ET.tostring(x) for x in expected
                            ]
                    assert len(group.findall(f"{SVG}text[@data-pin]")) == (
                        0 if view == "clean" else len(symbol.pins)
                    )
                    assert len(group.findall(f"{SVG}text[@data-note]")) == (
                        0 if view == "protection" else len(symbol.constant_annotations)
                    )
    for ids in seen.values():
        assert sorted(ids) == sorted(catalog.symbols)
