"""Independent acceptance gates for all 15 Cycle 7 physical DRAFT UGO.

A source table reference is NOT a signed 1:1 GOST printed figure overlay;
the numbers 1/2/3 are abstract terminal IDs, not vendor package pinouts.
"""

import json
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_electronic_cycle7_extended import IDS
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Circle, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import ComponentInstance
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from scripts.audit_symbol_catalog import audit_catalog

ROOT = Path(str(files("gost_schematic").joinpath("catalog")))
MATRIX = Path("docs/catalog/issue89-acceptance-matrix.json")
SVG = "{http://www.w3.org/2000/svg}"
PLURAL = {
    "resistor": "resistors",
    "fuse": "fuses",
    "transistor": "transistors",
    "diode": "diodes",
}


@pytest.fixture(scope="module")
def acceptance():
    content = json.loads(MATRIX.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in content["cards"]}


def _pair(identifier):
    family, suffix = identifier.split(".", 1)
    file_name = suffix.replace(".with_case", "_with_case") + ".json"
    rel = Path(PLURAL[family], file_name)
    return (
        load_symbol(ROOT / "symbols" / rel),
        load_part(ROOT / "parts" / rel),
    )


def _confirm_roles(symbol, part, card):
    expected = card["physical_pin_roles"]
    if part.identifier != symbol.identifier or part.symbol_id != symbol.identifier:
        raise ValueError("Part/symbol mismatch")
    if {p.number: p.name for p in part.pins} != expected:
        raise ValueError("Physical pin map changed")
    if {p.number: p.label for p in symbol.pins} != expected:
        raise ValueError("Graphical port role changed")
    if symbol.status != SymbolStatus.DRAFT or card["release"] != "DRAFT_NOT_APPROVED":
        raise ValueError("Forged certification status")


def test_exact_15_DRAFT_not_approvals_or_unsupported_XP_XS(acceptance):
    raw = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert len(raw["cards"]) == len(IDS) == 15
    assert set(acceptance) == set(IDS)
    assert raw["release"].startswith("BLOCKED")
    assert raw["connector_gate"]["status"].startswith("BLOCKED")
    assert len(raw["connector_gate"]["requirements"]) == 5
    for card in acceptance.values():
        assert card["status"] == "DRAFT"
        assert card["release"] == "DRAFT_NOT_APPROVED"
        assert card["figure_overlay"].startswith("BLOCKED")
        assert card["real_device_pinmap"].startswith("BLOCKED")
        assert card["source_pdf"].startswith("https://")
        assert card["source_ref"].startswith("ГОСТ")
        assert len(card["physical_pin_roles"]) in (2, 3)


@pytest.mark.parametrize("identifier", IDS)
def test_each_schematic_port_is_one_real_physical_pin_with_no_fake_bridge(
    acceptance, identifier
):
    symbol, part = _pair(identifier)
    card = acceptance[identifier]
    _confirm_roles(symbol, part, card)
    assert len(symbol.pins) == len(part.pins) == len(card["physical_pin_roles"])
    assert len(set(pin.at for pin in symbol.pins)) == len(part.pins)
    topo = inspect_conductor_topology(symbol)
    assert topo.valid, topo.diagnostics
    assert topo.explicit_junctions == 0
    assert [list(group) for group in topo.pin_islands] == card[
        "canonical_pin_islands"
    ]
    assert all(len(group) == 1 for group in topo.pin_islands)
    # Each physical connection must be an endpoint of a REAL conductive line.
    real_lines = [
        symbol.graphics[index]
        for index in symbol.conductor_topology.conductor_indices
    ]
    assert all(isinstance(item, Line) for item in real_lines)
    ends = {point for item in real_lines for point in (item.start, item.end)}
    assert all(pin.at in ends for pin in symbol.pins)
    assert not any("APPROVED" in source for source in symbol.standard_refs)


@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_real_pin_identity_survives_all_eight_D4_poses(
    acceptance, identifier, rotation, mirror
):
    symbol, part = _pair(identifier)
    expected = acceptance[identifier]["physical_pin_roles"]
    transform = Transform(rotation=rotation, mirror_x=mirror)
    instance = ComponentInstance("X17", part.identifier, Point(95000, 80000), transform)
    positions = instance.pin_positions(symbol)
    assert set(positions) == set(expected)
    assert len(set(positions.values())) == len(expected)
    for pin in symbol.pins:
        assert positions[pin.number] == transform.apply(pin.at) + instance.origin
        assert expected[pin.number] == next(
            physical.name for physical in part.pins
            if physical.number == pin.number
        )


@pytest.mark.parametrize("identifier", IDS)
def test_negative_vendor_substitution_or_fake_APPROVED_is_detected(
    acceptance, identifier
):
    symbol, part = _pair(identifier)
    card = acceptance[identifier]
    bad_pin = replace(part.pins[0], name="UNVERIFIED_VENDOR_PIN")
    wrong_part = replace(part, pins=(bad_pin, *part.pins[1:]))
    with pytest.raises(ValueError, match="Physical pin map"):
        _confirm_roles(symbol, wrong_part, card)
    with pytest.raises(ValueError, match="Forged certification"):
        _confirm_roles(symbol, part, dict(card, release="APPROVED"))


@pytest.mark.parametrize("identifier", IDS)
def test_clean_svg_is_actual_vector_ink_not_an_editor_target(identifier):
    symbol, part = _pair(identifier)
    clean = ET.fromstring(render_symbol_svg(symbol))
    debug = ET.fromstring(render_symbol_svg(symbol, review_overlay=True))
    assert len(clean.findall(f".//{SVG}line")) == sum(
        isinstance(primitive, Line) for primitive in symbol.graphics
    )
    assert not clean.findall(f".//{SVG}image")
    assert len(debug.findall(f".//{SVG}circle")) >= len(part.pins)
    assert clean.attrib["width"].endswith("mm")
    assert clean.attrib["height"].endswith("mm")


def test_physical_mechanisms_and_blocked_npn_prototype(acceptance):
    npn, _ = _pair("transistor.bjt_npn")
    assert any("EXPERIMENTAL_DERIVED_NOT_SOURCE_FIGURE" in source
               for source in npn.standard_refs)
    assert acceptance["transistor.bjt_npn"]["special_guard"].startswith(
        "NPN_3PIN_EXPERIMENTAL"
    )
    for identifier in ("resistor.variable", "resistor.trimmer"):
        symbol, part = _pair(identifier)
        assert len(part.pins) == 3 and part.pins[2].name == "W"
        assert inspect_conductor_topology(symbol).pin_islands == (
            ("1",), ("2",), ("3",)
        )
    for identifier in ("diode.led", "diode.photodiode"):
        symbol, part = _pair(identifier)
        assert len(part.pins) == 2
        assert symbol.conductor_topology.conductor_indices == (0, 1)
        assert len(symbol.graphics) > 2
    fuse, part = _pair("fuse.general")
    assert len(part.pins) == 2
    assert inspect_conductor_topology(fuse).pin_islands == (("1",), ("2",))
    for suffix in ("bjt_npn", "bjt_pnp", "mosfet_n_enh", "mosfet_p_enh"):
        plain, _ = _pair("transistor." + suffix)
        encased, _ = _pair("transistor." + suffix + ".with_case")
        assert encased.pins == plain.pins
        assert encased.conductor_topology == plain.conductor_topology
        assert sum(isinstance(g, Circle) for g in encased.graphics) == 1
        assert sum(isinstance(g, Circle) for g in plain.graphics) == 0
    full = audit_catalog()
    assert full["total_symbols"] >= 36
    assert full["draft_count"] == full["total_symbols"]
    assert full["hard_errors"] == 0
