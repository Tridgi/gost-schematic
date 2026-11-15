"""Independent cycle-4 property checks for the complete installed DRAFT catalog.

These tests deliberately use the same public loaders as the packaged wheel and
never assume a fixed catalog size. Pytest discovers *_test.py by default.
"""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import CatalogError, load_symbol, parse_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.diagnostics import Severity
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import ComponentInstance
from gost_schematic.model.conductor_topology import ConductorTopology
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

_SVG = "{http://www.w3.org/2000/svg}"


def _catalog_entries():
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    parts = {
        part.identifier: part
        for path in sorted((root / "parts").rglob("*.json"))
        for part in (load_part(path),)
    }
    entries = {}
    for path in sorted((root / "symbols").rglob("*.json")):
        symbol = load_symbol(path)
        assert symbol.identifier not in entries, path
        entries[symbol.identifier] = (symbol, parts.get(symbol.identifier))
    for path in sorted((root / "inductors").glob("*.json")):
        variant = load_inductor(path)
        assert variant.symbol.identifier not in entries, path
        entries[variant.symbol.identifier] = (variant.symbol, variant.part)
    assert entries, "Installed symbol catalog is unexpectedly empty"
    return tuple((identifier, *entries[identifier]) for identifier in sorted(entries))


@pytest.fixture(scope="module")
def catalog():
    return _catalog_entries()


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_every_installed_symbol_transforms_without_losing_physical_identity(
    catalog, rotation, mirror,
):
    tx = Transform(rotation, mirror)
    origin = Point(137_009, -57_003)
    for identifier, original, part in catalog:
        assert part is not None, identifier
        assert part.symbol_id == identifier
        physical = {pin.number for pin in part.pins}
        graphic = {pin.number for pin in original.pins}
        assert physical == graphic, identifier
        assert original.status == SymbolStatus.DRAFT, identifier

        original_groups = inspect_conductor_topology(original)
        assert original_groups.valid, (identifier, original_groups.diagnostics)
        topology = original.conductor_topology
        assert topology is not None, identifier

        transformed = replace(
            original,
            graphics=tuple(tx.primitive(shape) for shape in original.graphics),
            pins=tuple(
                replace(pin, at=tx.apply(pin.at), side=tx.side(pin.side))
                for pin in original.pins
            ),
            body_keepout=tx.box(original.body_keepout),
            conductor_topology=ConductorTopology(
                conductor_indices=topology.conductor_indices,
                junctions=tuple(tx.apply(junction) for junction in topology.junctions),
                pin_groups=topology.pin_groups,
            ),
        )
        assert transformed.identifier == identifier
        assert len(transformed.graphics) == len(original.graphics)
        assert transformed.conductor_topology.pin_groups == topology.pin_groups
        for pin in original.pins:
            actual = next(item for item in transformed.pins if item.number == pin.number)
            assert actual.at == tx.apply(pin.at)
            assert actual.side == tx.side(pin.side)
            assert actual.label == pin.label

        failures = [
            item.code for item in validate_symbol(transformed)
            if item.severity == Severity.ERROR
        ]
        assert failures == [], (identifier, rotation, mirror, failures)
        graph = inspect_conductor_topology(transformed)
        assert graph.valid, (identifier, rotation, mirror, graph.diagnostics)
        assert graph.pin_islands == original_groups.pin_islands

        instance = ComponentInstance("QA1", part.identifier, origin, tx)
        expected = {pin.number: tx.apply(pin.at) + origin for pin in original.pins}
        assert instance.pin_positions(original) == expected
        assert {item.number for item in transformed.pins} == set(expected)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_inverse_dihedral_transform_preserves_all_real_ugo_primitives(catalog, rotation, mirror):
    forward = Transform(rotation, mirror)
    reverse = Transform(rotation if mirror else (-rotation) % 360, mirror)
    for identifier, symbol, _ in catalog:
        for pin in symbol.pins:
            assert reverse.apply(forward.apply(pin.at)) == pin.at, identifier
            assert reverse.side(forward.side(pin.side)) == pin.side, identifier
        for shape in symbol.graphics:
            assert reverse.primitive(forward.primitive(shape)) == shape, identifier
        assert reverse.box(forward.box(symbol.body_keepout)) == symbol.body_keepout


def test_every_installed_ugo_svg_is_well_formed_deterministic_and_has_one_shape_per_primitive(
    catalog,
):
    for identifier, symbol, part in catalog:
        assert part is not None
        assert not [
            diagnostic for diagnostic in validate_symbol(symbol)
            if diagnostic.severity == Severity.ERROR
        ], identifier
        clean = render_symbol_svg(symbol, review_overlay=False)
        assert clean == render_symbol_svg(symbol, review_overlay=False), identifier
        root = ET.fromstring(clean)
        assert root.tag == f"{_SVG}svg"
        assert root.find(f"{_SVG}title").text == identifier
        assert root.attrib["width"].endswith("mm")
        assert root.attrib["height"].endswith("mm")
        assert len(root.attrib["viewBox"].split()) == 4
        assert not root.findall(f".//{_SVG}image"), identifier
        group = root.find(f"{_SVG}g")
        assert group is not None
        assert len(group) == len(symbol.graphics), identifier
        assert all(
            shape.tag in {
                f"{_SVG}line", f"{_SVG}rect",
                f"{_SVG}circle", f"{_SVG}path",
            }
            for shape in group
        ), identifier

        overlay = ET.fromstring(render_symbol_svg(symbol, review_overlay=True))
        assert len(overlay.findall(f".//{_SVG}circle")) >= len(symbol.pins), identifier
        assert len(overlay.find(f"{_SVG}g")) == len(symbol.graphics)
        assert symbol.status == SymbolStatus.DRAFT


@pytest.mark.parametrize("bad", [
    {"schema_version": 0, "id": "invalid"},
    {"schema_version": True, "id": "invalid"},
    {"schema_version": 1, "id": "invalid", "geometry": {}},
    {"schema_version": 1, "id": "invalid", "geometry": {"lines": [[[0, 0], [0, 0]]]},
     "pins": [], "body_keepout_mm": [-1, -1, 1, 1], "line_width_mm": 0.3,
     "revision": 1},
])
def test_bad_symbol_documents_fail_with_public_catalog_error(bad):
    with pytest.raises(CatalogError):
        parse_symbol(bad)


@pytest.mark.xfail(
    reason="Known robustness defect: parse_symbol propagates AttributeError for geometry: []",
    strict=False,
)
def test_json_array_in_geometry_returns_catalog_error_instead_of_attribute_error():
    with pytest.raises(CatalogError):
        parse_symbol({"schema_version": 1, "id": "qa.invalid", "geometry": []})
