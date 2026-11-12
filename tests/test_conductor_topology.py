"""Internal graphic continuity is declared, not inferred from intersections."""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.geometry import Box, Line, Point, Semicircle, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.model.conductor_topology import ConductorTopology
from gost_schematic.model.pins import GraphicPin
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol


def _load(category, ident):
    root = files("gost_schematic").joinpath("catalog")
    if category == "inductor":
        return load_inductor(Path(str(root.joinpath(f"inductors/{ident}.json")))).symbol
    return load_symbol(Path(str(root.joinpath(f"symbols/{category}/{ident}.json"))))


@pytest.mark.parametrize(
    ("kind", "name", "expected_groups"),
    [
        ("resistors", "fixed", (("1",), ("2",))),
        ("capacitors", "fixed", (("1",), ("2",))),
        ("capacitors", "polarized", (("1",), ("2",))),
        ("inductor", "inductor.air_core", (("1", "2"),)),
        ("inductor", "inductor.tapped", (("1", "2", "3"),)),
        ("inductor", "inductor.double_tapped", (("1", "2", "3", "4"),)),
        ("inductor", "inductor.sliding_contact", (("1", "2", "3"),)),
        ("inductor", "inductor.double_sliding", (("1", "2", "3", "4"),)),
        ("inductor", "inductor.trim_copper", (("1", "2"),)),
        ("inductor", "choke.ferrite", (("1", "2"),)),
    ],
)
def test_authored_conductor_groups_match_physical_device_graphics(
    kind, name, expected_groups,
):
    symbol = _load(kind, name)
    result = inspect_conductor_topology(symbol)
    assert result.valid, result.diagnostics
    assert result.pin_islands == expected_groups
    assert result.visited_primitives >= 2
    assert symbol.conductor_topology is not None
    assert not [
        issue for issue in validate_symbol(symbol)
        if issue.severity.value == "error"
    ]


def test_capacitor_plate_break_is_detected_without_false_connection():
    symbol = _load("capacitors", "fixed")
    # Left plate moved by 0.1 mm without moving its wire lead end.
    updated = list(symbol.graphics)
    updated[2] = Line(Point(-650, -4000), Point(-650, 4000))
    broken = replace(symbol, graphics=tuple(updated))
    codes = {issue.code for issue in inspect_conductor_topology(broken).diagnostics}
    assert "TOPOLOGY_JUNCTION_DANGLING" in codes
    assert "TOPOLOGY_ORPHAN_CONDUCTOR" in codes


def test_resistor_both_leads_are_not_a_graphical_short():
    symbol = _load("resistors", "fixed")
    result = inspect_conductor_topology(symbol)
    assert result.pin_islands == (("1",), ("2",))
    assert result.valid


def test_accidental_plate_bridge_is_rejected():
    symbol = _load("capacitors", "fixed")
    bridge = Line(Point(-750, 0), Point(750, 0))
    topology = symbol.conductor_topology
    assert topology is not None
    malformed = replace(
        symbol,
        graphics=(*symbol.graphics, bridge),
        conductor_topology=replace(
            topology, conductor_indices=(*topology.conductor_indices, 4)
        ),
    )
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        issue.code for issue in inspect_conductor_topology(malformed).diagnostics
    }


def test_missing_coil_arc_detects_disconnected_winding():
    symbol = _load("inductor", "inductor.air_core")
    malformed = list(symbol.graphics)
    malformed[2] = Semicircle(Point(-1900, 0), 2000, Side.TOP)
    result = inspect_conductor_topology(replace(symbol, graphics=tuple(malformed)))
    assert not result.valid
    assert "TOPOLOGY_GROUP_DISCONNECTED" in {d.code for d in result.diagnostics}


def test_missing_tap_junction_does_not_implicitly_connect_to_arc_interior():
    symbol = _load("inductor", "inductor.tapped")
    assert symbol.conductor_topology is not None
    malformed = replace(
        symbol, conductor_topology=replace(
            symbol.conductor_topology, junctions=(),
        ),
    )
    result = inspect_conductor_topology(malformed)
    assert "TOPOLOGY_GROUP_DISCONNECTED" in {d.code for d in result.diagnostics}


def test_missing_contact_attachment_is_rejected():
    symbol = _load("inductor", "inductor.tapped")
    assert symbol.conductor_topology is not None
    malformed = replace(
        symbol,
        conductor_topology=replace(
            symbol.conductor_topology,
            conductor_indices=symbol.conductor_topology.conductor_indices[:-1],
        ),
    )
    result = inspect_conductor_topology(malformed)
    assert "TOPOLOGY_PIN_UNATTACHED" in {d.code for d in result.diagnostics}


def _fixture_for_unmarked_crossing():
    return SymbolDefinition(
        identifier="topology.crossing",
        revision=1,
        body_keepout=Box(-1000, -1000, 1000, 1000),
        line_width_um=300,
        graphics=(
            Line(Point(-5000, 0), Point(5000, 0)),
            Line(Point(0, -5000), Point(0, 5000)),
        ),
        pins=(
            GraphicPin("1", Point(-5000, 0), Side.LEFT),
            GraphicPin("2", Point(5000, 0), Side.RIGHT),
            GraphicPin("3", Point(0, -5000), Side.TOP),
            GraphicPin("4", Point(0, 5000), Side.BOTTOM),
        ),
        conductor_topology=ConductorTopology(
            conductor_indices=(0, 1), junctions=(),
            pin_groups=(("1", "2"), ("3", "4")),
        ),
    )


def test_unmarked_crossing_does_not_join_two_distinct_conducting_groups():
    item = _fixture_for_unmarked_crossing()
    assert inspect_conductor_topology(item).valid
    assert inspect_conductor_topology(item).pin_islands == (
        ("1", "2"), ("3", "4"),
    )
    connected = replace(item, conductor_topology=replace(
        item.conductor_topology, junctions=(Point(0, 0),),
    ))
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in {
        issue.code for issue in inspect_conductor_topology(connected).diagnostics
    }


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_transform_preserves_authored_graph_groups(rotation, mirror):
    original = _load("inductor", "inductor.double_sliding")
    topology = original.conductor_topology
    assert topology is not None
    tx = Transform(rotation, mirror)
    transformed = replace(
        original,
        graphics=tuple(tx.primitive(item) for item in original.graphics),
        pins=tuple(replace(pin, at=tx.apply(pin.at), side=tx.side(pin.side))
                   for pin in original.pins),
        body_keepout=tx.box(original.body_keepout),
        conductor_topology=replace(
            topology, junctions=tuple(tx.apply(point) for point in topology.junctions)
        ),
    )
    result = inspect_conductor_topology(transformed)
    assert result.valid, result.diagnostics
    assert result.pin_islands == (("1", "2", "3", "4"),)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"conductor_indices": (0, 0)},
        {"conductor_indices": (-1,)},
        {"pin_groups": (("1", "1"),)},
        {"pin_groups": ((),)},
        {"junctions": (Point(0, 0), Point(0, 0))},
    ],
)
def test_invalid_topology_definition_fails_before_validation(kwargs):
    defaults = {
        "conductor_indices": (0, 1),
        "junctions": (),
        "pin_groups": (("1",), ("2",)),
    }
    with pytest.raises(ValueError):
        ConductorTopology(**(defaults | kwargs))


def test_conductor_graph_remains_safe_for_long_reverse_connected_chains():
    from gost_schematic.validation.conductor_checks import _DisjointSets

    graph = _DisjointSets()
    # Deliberately build a worst-case parent chain in descending order.
    for position in range(1800, 0, -1):
        graph.union(Point(position - 1, 0), Point(position, 0))
    assert graph.find(Point(1800, 0)) == Point(0, 0)
    assert all(graph.find(Point(i, 0)) == Point(0, 0) for i in (1, 500, 1799))
