"""Cycle 7 P0 DRAFT UGO/physical-pin tests: R variable/trimmer and FU general.

Schema pin numbers 1/2/3 are abstract catalogue numbers, NOT datasheet package
pins. The circuit graph, not ink overlap or a variable-resistor arrow,
establishes the actual rheostat wiring.
"""

import json
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_electronic_cycle7 import generate
from gost_schematic.catalog.loader import parse_symbol, load_symbol
from gost_schematic.catalog.part_loader import load_part, parse_part
from gost_schematic.core.geometry import Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_symbol_catalog import audit_catalog

ROOT = Path(str(files("gost_schematic").joinpath("catalog")))
IDS = ("resistor.variable", "resistor.trimmer", "fuse.general")
SVG = "{http://www.w3.org/2000/svg}"
PREFIX = {"resistor.variable": "R", "resistor.trimmer": "R", "fuse.general": "FU"}
PIN_ROLES = {
    "resistor.variable": ("A", "B", "W"),
    "resistor.trimmer": ("A", "B", "W"),
    "fuse.general": ("A", "B"),
}
TABLE = {"resistor.variable": ("ГОСТ 2.728-74", "таблица 1, поз. 4"),
         "resistor.trimmer": ("ГОСТ 2.728-74", "таблица 1, поз. 9"),
         "fuse.general": ("ГОСТ 2.727-68", "таблица 3, поз. 2")}


def _path(identifier: str, layer: str) -> Path:
    family, name = identifier.split(".", 1)
    plural = {"resistor": "resistors", "fuse": "fuses"}[family]
    return ROOT / layer / plural / (name + ".json")


def _pair(identifier: str):
    return load_symbol(_path(identifier, "symbols")), load_part(
        _path(identifier, "parts")
    )


@pytest.mark.parametrize("identifier", IDS)
def test_source_backed_distinct_draft_ugo_and_independent_physical_part(identifier):
    symbol, part = _pair(identifier)
    assert symbol.identifier == part.identifier == part.symbol_id == identifier
    assert symbol.status == SymbolStatus.DRAFT and symbol.revision == 1
    assert part.reference_prefix == PREFIX[identifier]
    assert part.voltage_orientation_rule.value == "none"
    assert part.nominal_kind is not None if identifier.startswith("resistor") else part.nominal_kind is None
    assert tuple(pin.number for pin in symbol.pins) == tuple(pin.number for pin in part.pins)
    assert tuple(pin.name for pin in part.pins) == PIN_ROLES[identifier]
    assert tuple(pin.label for pin in symbol.pins) == PIN_ROLES[identifier]
    assert all(pin.electrical_type.value == "passive" for pin in part.pins)
    assert all(pin.polarity.value == "none" for pin in part.pins)
    assert any(TABLE[identifier][0] in r and TABLE[identifier][1] in r
               for r in symbol.standard_refs)
    assert any("EDITORIAL_ASSUMPTION" in r for r in symbol.standard_refs)
    assert symbol.line_width_um == 300
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]


@pytest.mark.parametrize("identifier", IDS)
def test_physical_graphics_use_separate_conductor_islands(identifier):
    symbol, _part = _pair(identifier)
    trace = inspect_conductor_topology(symbol)
    expected = (("1",), ("2",), ("3",)) if identifier.startswith("resistor") else (("1",), ("2",))
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == expected
    assert trace.explicit_junctions == 0
    assert len(symbol.pins) == len(expected)
    assert symbol.stroked_bounds.min_x < symbol.bounds.min_x
    assert symbol.stroked_bounds.max_x > symbol.bounds.max_x


@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_all_eight_D4_views_preserve_real_pin_ids_and_isolated_ink(
    identifier, rotation, mirror
):
    symbol, part = _pair(identifier)
    t = Transform(rotation=rotation, mirror_x=mirror)
    instance = ComponentInstance(
        PREFIX[identifier] + "17", part.identifier, Point(90000, 80000), t
    )
    points = instance.pin_positions(symbol)
    assert tuple(points) == tuple(pin.number for pin in part.pins)
    assert len(set(points.values())) == len(part.pins)
    assert all(points[p.number] == t.apply(p.at) + instance.origin for p in symbol.pins)
    corridors = pin_corridors_for_component(symbol, instance)
    assert tuple(x.pin.number for x in corridors) == tuple(points)
    assert tuple(x.side for x in corridors) == tuple(t.side(p.side) for p in symbol.pins)
    assert inspect_conductor_topology(symbol).valid
    if identifier.startswith("resistor"):
        assert points["3"] not in (points["1"], points["2"])
        assert part.pins[2].name == "W"


@pytest.mark.parametrize("identifier", ("resistor.variable", "resistor.trimmer"))
def test_reostat_connection_is_real_Circuit_Net_and_retains_three_physical_contacts(identifier):
    symbol, part = _pair(identifier)
    instance = ComponentInstance("R4", part.identifier)
    rheostat = Circuit((instance,), (
        Net("RHEOSTAT_TIED_END", (PinRef("R4", "1"), PinRef("R4", "3"))),
        Net("RHEOSTAT_OTHER_END", (PinRef("R4", "2"),)),
    ))
    standalone = Circuit((instance,), (
        Net("END_A", (PinRef("R4", "1"),)),
        Net("END_B", (PinRef("R4", "2"),)),
        Net("SLIDER", (PinRef("R4", "3"),)),
    ))
    for graph in (rheostat, standalone):
        diagnostics = validate_circuit(
            graph, {part.identifier: part}, {symbol.identifier: symbol}
        )
        assert not [d for d in diagnostics if d.severity.value == "error"]
    assert tuple(x.number for x in part.pins) == ("1", "2", "3")
    assert tuple(x.number for x in symbol.pins) == ("1", "2", "3")
    assert len(rheostat.nets) == 2 and len(standalone.nets) == 3


def test_variable_wiper_is_real_top_pin_and_arrowhead_not_an_electrical_bridge():
    symbol, part = _pair("resistor.variable")
    assert symbol.pins[2].at == Point(0, -9000)
    assert symbol.pins[2].side == Side.TOP and part.pins[2].name == "W"
    assert symbol.graphics[3] == Line(Point(0, -9000), Point(0, -2000))
    assert symbol.conductor_topology.conductor_indices == (1, 2, 3)
    assert not set((4, 5)) & set(symbol.conductor_topology.conductor_indices)


def test_trimmer_wiper_forms_separate_right_upper_port_not_an_arrow():
    symbol, part = _pair("resistor.trimmer")
    assert part.pins[2].name == "W"
    assert symbol.pins[2].at == Point(9000, -5000)
    assert symbol.pins[2].side == Side.RIGHT
    assert symbol.graphics[3] == Line(Point(0, -2000), Point(0, -5000))
    assert symbol.graphics[4] == Line(Point(0, -5000), Point(9000, -5000))
    assert symbol.conductor_topology.conductor_indices == (1, 2, 3, 4)


def test_fuse_inside_line_must_not_convert_protection_to_a_zero_ohm_net():
    symbol, _part = _pair("fuse.general")
    assert len(symbol.pins) == 2
    assert symbol.graphics[3] == Line(Point(-4000, 0), Point(4000, 0))
    assert symbol.conductor_topology.conductor_indices == (1, 2)
    assert inspect_conductor_topology(symbol).pin_islands == (("1",), ("2",))


@pytest.mark.parametrize("identifier", IDS)
def test_actual_svg_is_vector_with_matching_pin_count(identifier):
    symbol, _part = _pair(identifier)
    clean = ET.fromstring(render_symbol_svg(symbol))
    review = ET.fromstring(render_symbol_svg(symbol, review_overlay=True))
    assert clean.tag == SVG + "svg"
    assert len(clean.findall(f".//{SVG}line")) == len(symbol.graphics) - 1
    assert len(clean.findall(f".//{SVG}rect")) == 1
    assert len(review.findall(f".//{SVG}circle")) == len(symbol.pins)
    assert not clean.findall(f".//{SVG}image")
    assert clean.attrib["width"].endswith("mm")
    assert clean.attrib["height"].endswith("mm")


@pytest.mark.parametrize("identifier", IDS)
def test_mutated_cross_body_shunt_is_rejected_if_marked_conductive(identifier):
    symbol, _ = _pair(identifier)
    body = symbol.body_keepout
    fake = Line(Point(body.min_x, 0), Point(body.max_x, 0))
    mutation = replace(
        symbol,
        graphics=(*symbol.graphics, fake),
        conductor_topology=replace(
            symbol.conductor_topology,
            conductor_indices=(*symbol.conductor_topology.conductor_indices,
                               len(symbol.graphics)),
        ),
    )
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(mutation).diagnostics
    }


@pytest.mark.parametrize("identifier", ("resistor.variable", "resistor.trimmer"))
def test_wiper_connected_to_end_by_ink_is_rejected(identifier):
    symbol, _ = _pair(identifier)
    at_wiper = Point(0, -2000)
    wrong = Line(at_wiper, Point(-5000, 0))
    mutation = replace(
        symbol,
        graphics=(*symbol.graphics, wrong),
        conductor_topology=replace(
            symbol.conductor_topology,
            conductor_indices=(*symbol.conductor_topology.conductor_indices,
                               len(symbol.graphics)),
        ),
    )
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        d.code for d in inspect_conductor_topology(mutation).diagnostics
    }


@pytest.mark.parametrize("identifier", IDS)
def test_mismatched_physical_pin_map_or_duplicate_pin_is_not_acceptable(identifier):
    symbol, part = _pair(identifier)
    bad_part = replace(part, pins=(
        replace(part.pins[0], number="NOT_REAL"), *part.pins[1:],
    ))
    assert {pin.number for pin in symbol.pins} != {
        pin.number for pin in bad_part.pins
    }
    with pytest.raises(ValueError, match="uniquely numbered"):
        replace(part, pins=(part.pins[0], part.pins[0], *part.pins[2:]))
    with pytest.raises(ValueError, match="Duplicate graphic pin"):
        replace(symbol, pins=(symbol.pins[0], symbol.pins[0], *symbol.pins[2:]))


@pytest.mark.parametrize("identifier", IDS)
def test_invalid_json_polarity_or_pin_escape_is_not_silently_accepted(identifier):
    raw = json.loads(_path(identifier, "symbols").read_text(encoding="utf-8"))
    raw["pins"][0]["at_mm"] = [0, 0]
    with pytest.raises(ValueError, match="trapped inside"):
        parse_symbol(raw)
    physical = json.loads(_path(identifier, "parts").read_text(encoding="utf-8"))
    physical["pins"][0]["polarity"] = "inferred_from_schematic"
    with pytest.raises(ValueError, match="Invalid physical part"):
        parse_part(physical)


def test_growth_is_dynamic_24_draft_ugo_with_complete_physical_mapping_and_normative_cards():
    report = audit_catalog()
    assert report["total_symbols"] >= 24
    assert report["draft_count"] == report["total_symbols"]
    assert report["topologies_verified"] == report["total_symbols"]
    assert not report["without_physical_part"]
    assert report["hard_errors"] == 0, report["error_details"]
    by_id = {item["id"]: item for item in report["entries"]}
    for identifier in IDS:
        row = by_id[identifier]
        assert row["physical_part_mapped"]
        assert row["conductor_topology"]["valid"]
        assert row["approval"] == "draft"
        assert row["pin_count"] == len(PIN_ROLES[identifier])
    cards = json.loads(Path(
        "docs/catalog/electronic-cycle7-first-batch-cards.json"
    ).read_text(encoding="utf-8"))
    assert {x["id"] for x in cards["cards"]} == set(IDS)
    assert all(x["status"] == "DRAFT" for x in cards["cards"])
    assert all(x["vendor_pinout"] == "UNVERIFIED_ABSTRACT_NUMBERING"
               for x in cards["cards"])


def test_electronic_gallery_svg_is_deterministic_and_provenance_audited(tmp_path):
    first = generate(tmp_path)
    images = {p: (tmp_path / p).read_bytes() for p in first["files"]}
    second = generate(tmp_path)
    assert first == second
    assert images == {p: (tmp_path / p).read_bytes() for p in second["files"]}
    assert len(first["files"]) == 6
    assert set(first["symbols"]) == set(IDS)
    assert all(entry["status"] == "DRAFT" for entry in first["symbols"].values())
    for name in first["files"]:
        root = ET.fromstring((tmp_path / name).read_text(encoding="utf-8"))
        assert root.attrib["data-symbol-id"] in IDS
        assert root.attrib["data-approval"] == "DRAFT"
