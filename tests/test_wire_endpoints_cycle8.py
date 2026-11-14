"""Issue #90/#100 independent source-bound wire-endpoint safety regressions."""
import itertools
import json
import subprocess
import sys
from dataclasses import replace
from io import BytesIO
from xml.etree import ElementTree as ET

import pytest

from examples.review_wire_endpoints_cycle8 import fixture, generate
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.netrefs import (
    ContinuationDirection,
    ContinuationPair,
    ContinuationScope,
    ContinuationSheet,
    ContinuationStub,
    NetContinuationEndpoint,
    NetContinuationProject,
)
from gost_schematic.electrical.wire_endpoints import (
    TargetState,
    WireEndSide,
    WireTermination,
    collect_wire_endpoints,
    validate_wire_endpoint_snapshot,
)
from gost_schematic.model.circuit import PinRef
from gost_schematic.rendering.wire_end_overlay import wire_endpoint_svg
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment

_NS = "{http://www.w3.org/2000/svg}"


def data():
    return fixture()


def collected():
    circuit, graph, nets, ids, parts, symbols, blocked_pins, blocked_ends = data()
    return collect_wire_endpoints(
        circuit, graph, nets, ids, parts, symbols,
        blocked_pins=blocked_pins, blocked_wire_ends=blocked_ends,
    )


def verify_raw(svg):
    root = ET.fromstring(svg)
    assert root.tag == _NS + "svg"
    assert svg.count('xmlns="http://www.w3.org/2000/svg"') == 1
    return root


def test_exact_real_net_identity_and_six_semantically_distinct_objects():
    shot = collected()
    assert len(shot.circuit.nets) == 3
    assert len(shot.wire_endpoints) == 10
    assert len(shot.nonjoining_crossings) == 1
    assert shot.nonjoining_crossings[0].point == Point(65000, 70000)
    assert shot.nonjoining_crossings[0].first_net_id != (
        shot.nonjoining_crossings[0].second_net_id
    )
    kinds = {e.termination for e in shot.wire_endpoints}
    assert WireTermination.FREE in kinds
    assert WireTermination.PHYSICAL_PIN in kinds
    assert WireTermination.JUNCTION in kinds
    assert WireTermination.CONNECTOR_CONTACT in kinds
    assert WireTermination.JOINED_WIRE not in kinds  # Separate variant tested below
    assert {e.id for e in shot.wire_endpoints} == {
        f"{w}:{side.value}" for w in shot.wire_ids for side in WireEndSide
    }
    assert any(c.connector and c.pin == PinRef("XP1", "1") for c in shot.physical_contacts)
    assert any(c.connector and c.pin == PinRef("XS1", "1") for c in shot.physical_contacts)
    assert any(c.pin == PinRef("DD1", "NC") and c.state is TargetState.BLOCKED
               for c in shot.physical_contacts)
    assert all(e.net_id.startswith("N-") for e in shot.wire_endpoints)
    validate_wire_endpoint_snapshot(shot)


def test_free_and_forbidden_wire_ends_are_authoritative_not_visual():
    shot = collected()
    by_id = {e.id: e for e in shot.wire_endpoints}
    for key in ("W-CTRL-A:end", "W-SHIELD:end", "W-AUX-TEE:end"):
        assert by_id[key].termination is WireTermination.FREE
        assert by_id[key].state is TargetState.AVAILABLE
        assert by_id[key].can_accept_connection
    forbidden = by_id["W-CTRL-B:end"]
    assert forbidden.termination is WireTermination.FREE
    assert forbidden.state is TargetState.BLOCKED
    assert not forbidden.can_accept_connection
    assert forbidden.reason_code == "POLICY_BLOCKED"
    assert by_id["W-AUX-TEE:start"].termination is WireTermination.JUNCTION
    assert not by_id["W-AUX-TEE:start"].can_accept_connection
    assert by_id["W-AUX:end"].termination is WireTermination.CONNECTOR_CONTACT
    assert by_id["W-AUX:end"].attached_pin == PinRef("XP1", "1")
    assert not by_id["W-AUX:end"].can_accept_connection


def test_exact_clean_svg_has_no_editor_color_or_hidden_click_areas():
    clean, diagnostic, report = generate()
    assert report["approval"].startswith("DRAFT")
    original = verify_raw(clean)
    reviewed = verify_raw(diagnostic)
    assert "editor-connection-targets" not in clean
    assert "#008c52" not in clean and "#b34444" not in clean
    assert "data-connectable" not in clean
    assert len(original.findall(f".//{_NS}line[@data-layer='wires']")) == 5
    assert len(original.findall(f".//{_NS}circle[@data-kind='authored-junction']")) == 1
    assert len(reviewed.findall(f".//{_NS}line[@data-layer='wires']")) == 5
    assert len(reviewed.findall(f".//{_NS}circle[@data-kind='authored-junction']")) == 1
    layers = reviewed.findall(f".//{_NS}g[@data-layer='editor-connection-targets']")
    assert len(layers) == 1 and layers[0].attrib["data-print"] == "false"
    squares = layers[0].findall(f".//{_NS}rect")
    assert len(squares) == 5  # Four free tips + one blocked synthetic NC pin
    assert len([r for r in squares if r.attrib["stroke"] == "#008c52"]) == 3
    assert len([r for r in squares if r.attrib["stroke"] == "#b34444"]) == 2
    assert all(r.find(_NS + "title") is not None for r in squares)
    assert not any(
        r.attrib.get("data-id") in ("X:W-AUX:W-SHIELD", "W-AUX-TEE:start")
        for r in squares
    )
    meta = reviewed.find(f".//{_NS}metadata[@data-layer='diagnostic-electrical-endpoint-inventory']")
    assert meta is not None
    actual = json.loads(meta.text)
    assert len(actual["unconnected_crossings"]) == 1
    assert actual["unconnected_crossings"][0]["point_um"] == [65000, 70000]
    assert actual["explicit_junctions_um"] == [[50000, 70000]]


def test_graph_presentation_is_readonly_and_exact_source_pins_not_svg_metadata():
    before = data()
    first = collected()
    second = collected()
    assert first == second and first.circuit == before[0] and first.graph == before[1]
    clean, _, _ = generate()
    _, _, _, _, parts, symbols, blocked, denied = before
    changed = replace(first, wire_endpoints=(
        replace(first.wire_endpoints[0], point=Point(20001, 40000)),
        *first.wire_endpoints[1:],
    ))
    with pytest.raises(ValueError, match="WIRE_END_POINT_MISMATCH"):
        validate_wire_endpoint_snapshot(changed)
    with pytest.raises(ValueError, match="WIRE_END_POINT_MISMATCH"):
        wire_endpoint_svg(clean, changed, parts, symbols, diagnostic=True,
                          blocked_pins=blocked, blocked_wire_ends=denied)
    tampered = replace(first, wire_endpoints=(
        replace(first.wire_endpoints[0], net_id="N-AUX"),
        *first.wire_endpoints[1:],
    ))
    with pytest.raises(ValueError, match="WIRE_END_NET_ID_MISMATCH"):
        validate_wire_endpoint_snapshot(tampered)
    with pytest.raises(ValueError, match="WIRE_END_SNAPSHOT_NOT_SOURCE_VERIFIED"):
        wire_endpoint_svg(clean, replace(first, physical_contacts=()), parts, symbols,
                          diagnostic=True, blocked_pins=blocked, blocked_wire_ends=denied)


def test_one_micrometre_wire_move_changes_view_but_never_snaps_or_mutates_net():
    circuit, graph, nets, ids, parts, symbols, blocked, denied = data()
    wire = graph.segments[0]
    shifted = replace(graph, segments=(
        replace(wire, end=Point(wire.end.x + 1, wire.end.y)),
        *graph.segments[1:],
    ))
    snap = collect_wire_endpoints(circuit, shifted, nets, ids, parts, symbols,
                                 blocked_pins=blocked, blocked_wire_ends=denied)
    assert snap.wire_endpoints[1].point == Point(60001, 40000)
    assert snap.circuit is circuit
    assert snap.circuit.nets is circuit.nets
    assert snap.wire_endpoints[1].net_id == "N-CTRL"


def test_unmarked_X_not_a_junction_and_cross_net_T_is_blocked():
    circuit, graph, nets, ids, parts, symbols, _, _ = data()
    assert Point(65000, 70000) not in graph.junctions
    with pytest.raises(ValueError, match="WIRE_END_INVALID_OR_CROSS_NET_JUNCTION"):
        collect_wire_endpoints(
            circuit,
            replace(graph, junctions=(*graph.junctions, Point(65000, 70000))),
            nets, ids, parts, symbols,
        )
    # Move a foreign AUX wire endpoint exactly onto the CTRL free tip.
    foreign = replace(graph.segments[2], end=Point(60000, 40000))
    # The original authored T no longer lies on the shortened AUX wire;
    # deliberately remove it in this isolated foreign-endpoint scenario.
    touched = replace(
        graph, segments=(*graph.segments[:2], foreign, *graph.segments[3:]),
        junctions=(),
    )
    shot = collect_wire_endpoints(circuit, touched, nets, ids, parts, symbols)
    a = next(e for e in shot.wire_endpoints if e.id == "W-CTRL-A:end")
    b = next(e for e in shot.wire_endpoints if e.id == "W-AUX:end")
    assert a.termination is WireTermination.UNMARKED_TOUCH
    assert b.termination is WireTermination.UNMARKED_TOUCH
    assert not a.can_accept_connection and not b.can_accept_connection
    assert shot.circuit.nets == circuit.nets


def test_diagonal_X_is_exact_nonjoining_metadata_without_rounded_fake_node():
    circuit, graph, nets, ids, parts, symbols, _, _ = data()
    first = WireSegment(Point(0, 0), Point(10000, 10000), "CTRL")
    second = WireSegment(Point(0, 10000), Point(10000, 0), "SHIELD")
    altered = replace(graph, segments=(
        first, graph.segments[1], graph.segments[2],
        second, graph.segments[4],
    ))
    shot = collect_wire_endpoints(circuit, altered, nets, ids, parts, symbols)
    assert len(shot.nonjoining_crossings) == 1
    crossing = shot.nonjoining_crossings[0]
    assert crossing.point == Point(5000, 5000)
    assert crossing.first_net_id != crossing.second_net_id
    assert all(e.point != crossing.point for e in shot.wire_endpoints)
    assert Point(5000, 5000) not in altered.junctions
    # A half-micrometre X cannot be rounded to an invented exact µm node.
    frac = replace(altered, segments=(
        WireSegment(Point(0, 0), Point(3, 3), "CTRL"),
        altered.segments[1], altered.segments[2],
        WireSegment(Point(0, 3), Point(3, 0), "SHIELD"),
        altered.segments[4],
    ))
    fractional = collect_wire_endpoints(circuit, frac, nets, ids, parts, symbols)
    assert fractional.nonjoining_crossings == ()
    assert fractional.circuit.nets == circuit.nets


def test_partial_foreign_net_collinear_overlap_fails_closed():
    circuit, graph, nets, ids, parts, symbols, _, _ = data()
    foreign = replace(graph.segments[3],
                      start=Point(55000, 40000), end=Point(75000, 40000))
    with pytest.raises(ValueError, match="WIRE_END_CROSS_NET_COLLINEAR_SHORT"):
        collect_wire_endpoints(
            circuit, replace(graph, segments=(
                *graph.segments[:3], foreign, graph.segments[4],
            )), nets, ids, parts, symbols,
        )


@pytest.mark.parametrize("physical_point", (
    Point(50000, 40000),  # Same-net wire interior, not an authored contact.
    Point(65000, 70000),  # Foreign-net X, still no actual physical junction.
))
def test_physical_pin_on_unmarked_wire_interior_is_not_eligible(physical_point):
    circuit, graph, nets, ids, parts, symbols, _, _ = data()
    altered = dict(symbols)
    vt = altered["synthetic.vt.symbol"]
    relative = physical_point - Point(110000, 40000)
    altered["synthetic.vt.symbol"] = replace(
        vt, pins=(replace(vt.pins[0], at=relative),),
    )
    shot = collect_wire_endpoints(circuit, graph, nets, ids, parts, altered)
    pin = next(c for c in shot.physical_contacts if c.pin == PinRef("VT1", "G"))
    assert pin.point == physical_point
    assert pin.state is TargetState.BLOCKED
    assert not pin.can_accept_connection
    assert pin.reason_code == "UNMARKED_PIN_WIRE_INTERIOR"
    assert shot.circuit.nets == circuit.nets


def test_stale_duplicate_id_and_incomplete_physical_map_fail_closed():
    circuit, graph, nets, ids, parts, symbols, _, _ = data()
    with pytest.raises(ValueError, match="WIRE_END_WIRE_IDS_DUPLICATE_OR_INVALID"):
        collect_wire_endpoints(
            circuit, graph, nets, (ids[0], ids[0], *ids[2:]), parts, symbols,
        )
    broken_parts = dict(parts)
    dd = broken_parts["synthetic.dd"]
    broken_parts["synthetic.dd"] = replace(dd, pins=dd.pins[:-1])
    with pytest.raises(ValueError, match="WIRE_END_INCOMPLETE_PHYSICAL_PIN_MAP"):
        collect_wire_endpoints(circuit, graph, nets, ids, broken_parts, symbols)
    unknown = replace(circuit, nets=(replace(circuit.nets[0],
        members=(PinRef("DD1", "999"), PinRef("VT1", "G"))), *circuit.nets[1:]))
    with pytest.raises(ValueError, match="WIRE_END_REAL_NET_MEMBERS_MISMATCH"):
        collect_wire_endpoints(unknown, graph, nets, ids, parts, symbols)


def test_orphan_drawing_is_not_green_merely_because_its_label_matches_net():
    circuit, graph, nets, ids, parts, symbols, blocked, denied = data()
    orphan = WireSegment(Point(145000, 120000), Point(165000, 120000), "CTRL")
    shot = collect_wire_endpoints(
        circuit, replace(graph, segments=(*graph.segments, orphan)),
        nets, (*ids, "W-ORPHAN"), parts, symbols,
        blocked_pins=blocked, blocked_wire_ends=denied,
    )
    ends = [e for e in shot.wire_endpoints if e.wire_id == "W-ORPHAN"]
    assert len(ends) == 2
    assert all(e.termination is WireTermination.FREE for e in ends)
    assert all(e.state is TargetState.BLOCKED for e in ends)
    assert all(not e.can_accept_connection for e in ends)
    assert all(e.reason_code == "UNANCHORED_CONDUCTOR_ISLAND" for e in ends)


def test_two_segments_same_net_join_by_authored_common_endpoint_without_green_node():
    circuit, graph, nets, ids, parts, symbols, _, _ = data()
    attached = WireSegment(Point(60000, 40000), Point(62500, 40000), "CTRL")
    shot = collect_wire_endpoints(
        circuit, replace(graph, segments=(*graph.segments, attached)),
        nets, (*ids, "W-CTRL-C"), parts, symbols,
    )
    a = next(e for e in shot.wire_endpoints if e.id == "W-CTRL-A:end")
    b = next(e for e in shot.wire_endpoints if e.id == "W-CTRL-C:start")
    assert a.termination is b.termination is WireTermination.JOINED_WIRE
    assert not a.can_accept_connection and not b.can_accept_connection
    assert graph.junctions == (Point(50000, 70000),)


def _continuation():
    circuit, graph, nets, _, _, _, _, _ = data()
    endpoints = (
        NetContinuationEndpoint(
            "M1", "N-CTRL", "S1", 1, "1/D4", "2/B7",
            Point(60000, 40000), "CTRL", ContinuationDirection.SOURCE,
        ),
        NetContinuationEndpoint(
            "M2", "N-CTRL", "S2", 2, "2/B7", "1/D4",
            Point(70000, 40000), "CTRL", ContinuationDirection.TARGET,
        ),
    )
    return NetContinuationProject(
        circuit, nets, (ContinuationSheet("S1", 1), ContinuationSheet("S2", 2)),
        endpoints,
        (ContinuationPair("P", "M1", "M2", ContinuationScope.GLOBAL),),
        (
            ContinuationStub("S-A", "M1", PinRef("DD1", "5"),
                             graph.segments[0].start, graph.segments[0].end),
            ContinuationStub("S-B", "M2", PinRef("VT1", "G"),
                             graph.segments[1].start, graph.segments[1].end),
        ),
    )


def test_nonphysical_named_continuation_is_not_free_wire_or_XP_contact():
    circuit, graph, nets, ids, parts, symbols, blocked, denied = data()
    project = _continuation()
    shot = collect_wire_endpoints(
        circuit, graph, nets, ids, parts, symbols,
        continuations=project, blocked_pins=blocked, blocked_wire_ends=denied,
    )
    a, b = (next(e for e in shot.wire_endpoints if e.id == n)
            for n in ("W-CTRL-A:end", "W-CTRL-B:end"))
    assert a.termination is b.termination is WireTermination.CONTINUATION
    assert a.state is b.state is TargetState.NONPHYSICAL
    assert a.continuation_id == "M1" and b.continuation_id == "M2"
    assert not a.can_accept_connection and not b.can_accept_connection
    assert a.attached_pin is b.attached_pin is None
    assert shot.continuation_ids == ("M1", "M2")


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_all_D4_transformations_preserve_exact_physical_net_members(rotation, mirror):
    circuit, graph, nets, ids, parts, symbols, blocked, denied = data()
    tx = Transform(rotation, mirror)
    transformed = replace(
        circuit, components=tuple(
            replace(c, origin=tx.apply(c.origin), transform=tx)
            for c in circuit.components
        ),
    )
    changed_graph = ExternalWireGraph(
        tuple(WireSegment(tx.apply(w.start), tx.apply(w.end), w.net_name)
              for w in graph.segments),
        tuple(tx.apply(p) for p in graph.junctions),
    )
    shot = collect_wire_endpoints(
        transformed, changed_graph, nets, ids, parts, symbols,
        blocked_pins=blocked, blocked_wire_ends=denied,
    )
    assert shot.nets == nets and shot.circuit.nets is circuit.nets
    assert shot.wire_endpoints[1].point == tx.apply(Point(60000, 40000))
    assert len(shot.nonjoining_crossings) == 1
    assert shot.nonjoining_crossings[0].point == tx.apply(Point(65000, 70000))
    assert sum(e.can_accept_connection for e in shot.wire_endpoints) == 3


@pytest.mark.parametrize("order", tuple(itertools.permutations((
    "gost_schematic.rendering.svg",
    "gost_schematic.rendering.sheet_svg",
    "gost_schematic.rendering.external_wire_sheet",
))))
def test_svg_strict_namespace_is_independent_of_module_import_order(order):
    script = (
        "import importlib,xml.etree.ElementTree as ET\n"
        + "".join(f"importlib.import_module({module!r})\n" for module in order)
        + "from examples.review_wire_endpoints_cycle8 import generate\n"
        + "c,d,_=generate()\n"
        + "for svg in (c,d):\n"
        + " assert svg.count('xmlns=') == 1\n"
        + " assert ET.fromstring(svg).tag=='{http://www.w3.org/2000/svg}svg'\n"
        + "print('OK')\n"
    )
    run = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        timeout=20, check=False,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "OK"


def test_rasterized_png_has_green_only_in_explicit_review_not_clean():
    import resvg_py
    from PIL import Image

    clean, reviewed, _ = generate()
    a = resvg_py.svg_to_bytes(svg_string=clean, dpi=300)
    b = resvg_py.svg_to_bytes(svg_string=reviewed, dpi=300)
    with Image.open(BytesIO(a)) as image:
        assert image.format == "PNG" and image.width > 500 and image.height > 250
        pixels = list(image.convert("RGB").get_flattened_data())
        assert not any(g > r + 45 and g > blue + 15 for r, g, blue in pixels)
    with Image.open(BytesIO(b)) as image:
        assert image.format == "PNG" and image.width > 500 and image.height > 250
        pixels = list(image.convert("RGB").get_flattened_data())
        assert any(g > r + 45 and g > blue + 15 for r, g, blue in pixels)
