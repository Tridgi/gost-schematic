"""QA #92 independent real YGO2 5ee10bc discrete gate; not owner tests.

Loads byte-identical owner PR working files, runs *production* parsers,
conductor topology, pin transforms, Circuit.Net validation and SVG renderer.
The 3 symbols are DRAFT, physical numbers abstract (NOT datasheet approved).
"""
import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from qa_cycle7_support import (
    BLOBS,
    EXPECTED_NAMES,
    EXPECTED_NUMBERS,
    IDS,
    SNAPSHOTS,
    ensure_verified,
    owner_symbol_part,
)

from gost_schematic.catalog.loader import CatalogError, parse_symbol
from gost_schematic.catalog.part_loader import parse_part
from gost_schematic.core.geometry import Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol
from scripts.audit_symbol_catalog import audit_catalog

SVG = "{http://www.w3.org/2000/svg}"


def _raw(key, category):
    root = SNAPSHOTS / "qa_cycle7_ygo89" / category
    return json.loads((root / (key + ".json")).read_text(encoding="utf-8"))


def test_exact_owner_binaries_not_a_forged_catalog():
    ensure_verified()
    assert len(BLOBS) == 7
    assert set(IDS.values()) == {
        "resistor.variable", "resistor.trimmer", "fuse.general"
    }


@pytest.mark.parametrize("key", tuple(IDS))
def test_real_source_symbol_and_physical_contract_are_separate_and_draft(key):
    symbol, part = owner_symbol_part(key)
    assert symbol.identifier == part.identifier == part.symbol_id == IDS[key]
    assert symbol.status == SymbolStatus.DRAFT
    assert tuple(pin.number for pin in symbol.pins) == EXPECTED_NUMBERS[key]
    assert tuple(pin.number for pin in part.pins) == EXPECTED_NUMBERS[key]
    assert tuple(pin.name for pin in part.pins) == EXPECTED_NAMES[key]
    assert tuple(pin.label for pin in symbol.pins) == EXPECTED_NAMES[key]
    assert len(set(pin.at for pin in symbol.pins)) == len(symbol.pins)
    assert len(set(pin.number for pin in part.pins)) == len(part.pins)
    assert not [d for d in validate_symbol(symbol) if d.severity.value == "error"]
    assert all(pin.electrical_type.value == "passive" for pin in part.pins)
    assert any("EDITORIAL_ASSUMPTION" in s for s in symbol.standard_refs)
    # No mapping of numbers 1/2/3 to a REAL vendor IC/package has been supplied.
    assert part.identifier.startswith(("resistor.", "fuse."))


@pytest.mark.parametrize("key", tuple(IDS))
def test_no_shorts_in_genuine_authored_internal_conductor_graph(key):
    symbol, part = owner_symbol_part(key)
    r = inspect_conductor_topology(symbol)
    assert r.valid, [(x.code, x.message) for x in r.diagnostics]
    assert r.pin_islands == tuple((x,) for x in EXPECTED_NUMBERS[key])
    assert r.explicit_junctions == 0
    assert set(pin.number for pin in part.pins) == set(
        a[0] for a in r.pin_islands
    )
    # Nonconductive glyph lines do not create direct short-circuits.
    assert len(symbol.conductor_topology.conductor_indices) < len(symbol.graphics)


@pytest.mark.parametrize("key", tuple(IDS))
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirrored", (False, True))
def test_actual_e3_pinref_identity_survives_all_eight_discrete_d4_poses(
    key, rotation, mirrored,
):
    symbol, part = owner_symbol_part(key)
    trans = Transform(rotation=rotation, mirror_x=mirrored)
    comp = ComponentInstance(
        reference=("FU12" if key == "fuse" else "R12"),
        part_id=part.identifier,
        origin=Point(100000, 90000),
        transform=trans,
    )
    points = comp.pin_positions(symbol)
    assert set(points) == set(EXPECTED_NUMBERS[key])
    assert len(set(points.values())) == len(points)
    for pin in symbol.pins:
        assert points[pin.number] == trans.apply(pin.at) + comp.origin
    if key != "fuse":
        assert points["3"] not in (points["1"], points["2"])
    # Real circuit validator—not graphic contact—owns connectivity.
    isolated = Circuit((comp,), tuple(
        Net(f"{key}_{number}", (PinRef(comp.reference, number),))
        for number in EXPECTED_NUMBERS[key]
    ))
    assert not [
        d for d in validate_circuit(
            isolated, {part.identifier: part}, {symbol.identifier: symbol}
        ) if d.severity.value == "error"
    ]


@pytest.mark.parametrize("key", ("variable", "trimmer"))
def test_potentiometer_has_true_wiper_and_no_implicit_rheostat_bridge(key):
    symbol, part = owner_symbol_part(key)
    assert part.pins[2].name == "W" and symbol.pins[2].label == "W"
    assert symbol.pins[2].at != symbol.pins[0].at
    assert symbol.pins[2].at != symbol.pins[1].at
    assert symbol.pins[2].side == (
        Side.TOP if key == "variable" else Side.RIGHT
    )
    assert inspect_conductor_topology(symbol).pin_islands == (
        ("1",), ("2",), ("3",)
    )
    component = ComponentInstance("R11", part.identifier)
    tied = Circuit((component,), (
        Net("RHEOSTAT", (PinRef("R11", "1"), PinRef("R11", "3"))),
        Net("OPEN_END", (PinRef("R11", "2"),)),
    ))
    untied = Circuit((component,), tuple(
        Net(f"N{n}", (PinRef("R11", n),)) for n in ("1", "2", "3")
    ))
    for c in (tied, untied):
        assert not [
            d for d in validate_circuit(
                c, {part.identifier: part}, {symbol.identifier: symbol}
            ) if d.severity.value == "error"
        ]
    assert len(tied.nets) == 2 and len(untied.nets) == 3


def test_wiper_geometry_real_ugo_not_fake_terminal_from_arrowhead():
    variable, _ = owner_symbol_part("variable")
    trimmer, _ = owner_symbol_part("trimmer")
    assert variable.pins[2].at == Point(0, -9000)
    assert trimmer.pins[2].at == Point(9000, -5000)
    assert Line(Point(0, -9000), Point(0, -2000)) in variable.graphics
    assert Line(Point(0, -5000), Point(9000, -5000)) in trimmer.graphics
    assert inspect_conductor_topology(variable).pin_islands[-1] == ("3",)
    assert inspect_conductor_topology(trimmer).pin_islands[-1] == ("3",)


def test_fuse_interior_stroke_does_not_turn_fu_into_zero_ohm_wire():
    symbol, part = owner_symbol_part("fuse")
    assert part.reference_prefix == "FU"
    assert len(symbol.pins) == len(part.pins) == 2
    assert Line(Point(-4000, 0), Point(4000, 0)) in symbol.graphics
    assert inspect_conductor_topology(symbol).pin_islands == (("1",), ("2",))


@pytest.mark.parametrize("key", tuple(IDS))
def test_real_svg_ports_and_physical_strokes_match_actual_parsed_owner_source(key):
    symbol, part = owner_symbol_part(key)
    raw_clean = render_symbol_svg(symbol)
    raw_review = render_symbol_svg(symbol, review_overlay=True)
    clean = ET.fromstring(raw_clean)
    review = ET.fromstring(raw_review)
    assert clean.tag == review.tag == SVG + "svg"
    assert clean.attrib["viewBox"] == review.attrib["viewBox"]
    assert raw_clean == render_symbol_svg(symbol)
    assert len(review.findall(f".//{SVG}circle")) == len(part.pins)
    assert not clean.findall(f".//{SVG}image")
    markers = review.findall(f".//{SVG}circle")
    coords = {
        (int(round(float(m.attrib["cx"]) * 1000)),
         int(round(float(m.attrib["cy"]) * 1000)))
        for m in markers
    }
    assert coords == {(p.at.x, p.at.y) for p in symbol.pins}
    # Actual rendered paths preserved, not merely precomputed hitboxes:
    assert len(clean.findall(f".//{SVG}line")) >= 3
    assert clean.find(f".//{SVG}rect") is not None


@pytest.mark.parametrize("key", tuple(IDS))
def test_actual_wrong_physical_pin_id_and_unsafe_graph_crossing_rejected(key):
    symbol, part = owner_symbol_part(key)
    ref = "FU1" if key == "fuse" else "R1"
    fake_part = replace(part, pins=(
        replace(part.pins[0], number="99"), *part.pins[1:]
    ))
    graph = Circuit((ComponentInstance(ref, part.identifier),), (
        Net("PWR", (PinRef(ref, EXPECTED_NUMBERS[key][0]),)),
    ))
    problems = validate_circuit(
        graph, {part.identifier: fake_part}, {symbol.identifier: symbol}
    )
    assert "PIN_MAPPING_MISMATCH" in {d.code for d in problems}
    assert "UNKNOWN_PIN" in {d.code for d in problems}
    # The wiper/fuse internal graphic cannot be declared conductive shunt.
    cross_body = Line(
        Point(symbol.body_keepout.min_x, 0),
        Point(symbol.body_keepout.max_x, 0),
    )
    mutated = replace(symbol, graphics=(*symbol.graphics, cross_body),
        conductor_topology=replace(
            symbol.conductor_topology,
            conductor_indices=(
                *symbol.conductor_topology.conductor_indices,
                len(symbol.graphics),
            ),
        ),
    )
    assert not inspect_conductor_topology(mutated).valid


@pytest.mark.parametrize("key", tuple(IDS))
def test_bad_duplicate_or_trapped_physical_pins_fail_closed(key):
    raw = _raw(key, "symbols")
    raw["pins"][0]["at_mm"] = [0, 0]
    with pytest.raises((ValueError, CatalogError), match="trapped inside"):
        parse_symbol(raw)
    part = _raw(key, "parts")
    part["pins"][0]["number"] = part["pins"][1]["number"]
    with pytest.raises((ValueError, CatalogError), match="uniquely numbered"):
        parse_part(part)
    physical = _raw(key, "parts")
    physical["pins"][0]["polarity"] = "schematically_guessed"
    with pytest.raises(CatalogError, match="Invalid physical"):
        parse_part(physical)


def test_baseline_integrated_dynamic_catalog_count_never_assumes_new_ugo_merged():
    report = audit_catalog()
    assert report["total_symbols"] == len(report["entries"])
    assert report["draft_count"] == report["total_symbols"]
    assert report["hard_errors"] == 0
    assert not report["without_physical_part"]
    integrated = {e["id"] for e in report["entries"]}
    # The isolated owner-branch additions cannot be declared merged/approved.
    assert not (integrated & set(IDS.values()))
    assert report["total_symbols"] >= 21


def test_one_net_two_distant_physical_fragments_is_semantic_only_not_marker_api():
    symbol, part = owner_symbol_part("variable")
    first = ComponentInstance(
        "R1", part.identifier, origin=Point(20000, 20000)
    )
    second = ComponentInstance(
        "R2", part.identifier, origin=Point(160000, 190000)
    )
    graph = Circuit((first, second), (
        Net("REMOTE_SIGNAL", (PinRef("R1", "3"), PinRef("R2", "3"))),
        Net("LOCAL_A", (PinRef("R1", "1"),)),
        Net("LOCAL_B", (PinRef("R2", "1"),)),
    ))
    assert graph.nets[0].members == (
        PinRef("R1", "3"), PinRef("R2", "3")
    )
    assert not [d for d in validate_circuit(
        graph, {part.identifier: part}, {symbol.identifier: symbol}
    ) if d.severity.value == "error"]
    # No NetContinuation model or graphical off-page SVG is asserted as PASS.


def test_different_physical_nets_with_identical_visible_name_rejected():
    symbol, part = owner_symbol_part("variable")
    component = ComponentInstance("R1", part.identifier)
    graph = Circuit((component,), (
        Net("SIG", (PinRef("R1", "1"),)),
        Net("SIG", (PinRef("R1", "2"),)),
    ))
    codes = {d.code for d in validate_circuit(
        graph, {part.identifier: part}, {symbol.identifier: symbol}
    )}
    assert "DUPLICATE_NET_NAME" in codes
    assert "MULTIPLE_NET_OWNERSHIP" not in codes
