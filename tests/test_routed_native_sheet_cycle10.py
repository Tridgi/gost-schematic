"""Adversarial owner-agnostic NEW native route graph -> whole sheet gate."""
import json
from xml.etree import ElementTree as ET

import pytest
from test_full_native_cycle9 import STYLE, FixedInk, fixture

from gost_schematic.core.geometry import Box, Point
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, PhysicalPin
from gost_schematic.rendering.routed_native_sheet import (
    _is_real_branch,
    _tl494_source_print_proof_blockers,
    render_routed_native_sheet,
)
from gost_schematic.validation.external_wire_checks import (
    ExternalWireGraph,
    WireSegment,
)

NS = "{http://www.w3.org/2000/svg}"


def _case():
    _, circuit, symbols, clean = fixture(diagnostic=False)
    _, _, _, diagnostic = fixture(diagnostic=True)
    at = {k: p for k, p in clean.pin_anchors}
    graph = ExternalWireGraph((
        WireSegment(at["DD1.P1"], at["DD1.P3"], "A"),
        WireSegment(at["DD1.P2"], at["DD1.P4"], "B"),
    ))
    part = PartDefinition(
        "test.ic", "DD", "test.ic",
        tuple(PhysicalPin(n, n, ElectricalType.PASSIVE)
              for n in ("1", "2", "3", "4")),
    )
    return circuit, graph, {"test.ic": part}, symbols, clean, diagnostic


def _render(
    circuit, graph, parts, symbols, clean, diagnostic,
    *,
    expected_net_count=2, route_preview=None,
):
    return render_routed_native_sheet(
        circuit, graph, parts, symbols, STYLE, FixedInk(),
        physical_ic_renderings_clean={"DD1": clean},
        physical_ic_renderings_diagnostic={"DD1": diagnostic},
        expected_component_count=1,
        expected_net_count=expected_net_count,
        expected_net_pinrefs=4,
        route_preview=route_preview,
    )


def test_new_graph_not_old91_exact_lines_and_source_unmodified():
    circuit, graph, parts, symbols, clean, diag = _case()
    before = tuple(circuit.nets)
    snapshot = tuple(graph.segments)
    result = _render(circuit, graph, parts, symbols, clean, diag)
    assert not result.printable_candidate
    assert result.manifest["route_segments"] == 2
    assert result.manifest["source_nets"] == 2
    assert "NET114_INDEPENDENT_ROUTE_DRC_NOT_INSTALLED" in (
        result.manifest["blockers"]
    ) or "NET114_POST_RENDER_PRINT_DRC_ERRORS" in result.manifest["blockers"]
    assert result.manifest["graph_sha256"] == result.graph_sha256
    assert circuit.nets == before and graph.segments == snapshot
    assert json.dumps(result.manifest)
    for svg in (result.clean_svg, result.diagnostic_svg):
        root = ET.fromstring(svg)
        assert root.get("data-route-graph-sha256") == result.graph_sha256
        assert root.get("data-release") == "BLOCKED_INCOMPLETE_OR_PRINT_DRC"
        lines = root.findall(f".//{NS}line[@data-layer='wires']")
        assert len(lines) == 2
        assert {w.get("data-net") for w in lines} == {"A", "B"}
        assert len(root.findall(f".//{NS}g[@data-layer='symbols']")) == 1
    assert "editor-connection-targets" not in result.clean_svg
    assert "editor-connection-targets" in result.diagnostic_svg


@pytest.mark.parametrize("tamper,code", (
    ("foreign", "ROUTED_SHEET_FORGED_FOREIGN_NET"),
    ("count", "ROUTED_SHEET_SOURCE_NETS_DRIFT"),
    ("junction", "ROUTED_SHEET_FOREIGN_OR_DANGLING_JUNCTION"),
    ("fake_dot", "ROUTED_SHEET_FOREIGN_OR_DANGLING_JUNCTION"),
    ("no_ic", "ROUTED_SHEET_TYPED_PHYSICAL_IC_REQUIRED"),
    ("owner", "ROUTED_SHEET_OWNER_(PREVIEW|114_ROUTER)"),
))
def test_reject_forged_external_graph_or_evidence(tamper, code):
    circuit, graph, parts, symbols, clean, diag = _case()
    kwargs = {
        "circuit": circuit, "graph": graph, "parts": parts,
        "symbols_by_part": symbols, "style": STYLE, "measurer": FixedInk(),
        "physical_ic_renderings_clean": {"DD1": clean},
        "physical_ic_renderings_diagnostic": {"DD1": diag},
        "expected_component_count": 1, "expected_net_count": 2,
        "expected_net_pinrefs": 4,
    }
    if tamper == "foreign":
        kwargs["graph"] = ExternalWireGraph((
            WireSegment(graph.segments[0].start,
                        graph.segments[0].end, "UNKNOWN_GROUND_PE"),
        ))
    elif tamper == "count":
        kwargs["expected_net_count"] = 15
    elif tamper == "junction":
        kwargs["graph"] = ExternalWireGraph((
            WireSegment(Point(-1000, 0), Point(1000, 0), "A"),
            WireSegment(Point(0, -1000), Point(0, 1000), "B"),
        ), (Point(0, 0),))
    elif tamper == "fake_dot":
        first = graph.segments[0]
        halfway = Point(
            (first.start.x+first.end.x)//2,
            (first.start.y+first.end.y)//2,
        )
        kwargs["graph"] = ExternalWireGraph(
            graph.segments, (halfway,),
        )
    elif tamper == "no_ic":
        kwargs["physical_ic_renderings_clean"] = {}
    elif tamper == "owner":
        kwargs["route_preview"] = object()
    with pytest.raises((ValueError, TypeError, RuntimeError), match=code):
        render_routed_native_sheet(**kwargs)


def test_reject_forged_physical_pinref_from_renderer_output():
    circuit, graph, parts, symbols, clean, diag = _case()
    # Replacing the serialized physical stamp without the underlying
    # authoritative catalog contact cannot evade the layer composer.
    from dataclasses import replace

    bad = replace(clean, pin_anchors=(
        ("DD1.P999", clean.pin_anchors[0][1]),
        *clean.pin_anchors[1:],
    ))
    with pytest.raises(ValueError, match="ROUTED_SHEET_CLEAN_DEBUG_PINREF_NET_DRIFT"):
        _render(circuit, graph, parts, symbols, bad, diag)
    # Even a colluding clean/debug pair with identical forged PinRef data
    # must fail against the source-owned physical catalogue.
    forged_pair = replace(diag, pin_anchors=bad.pin_anchors)
    with pytest.raises(ValueError, match="SHEET_IC_PINREF_POINT_INVENTORY_MISMATCH"):
        _render(circuit, graph, parts, symbols, bad, forged_pair)


def test_debug_layer_is_truly_foreground_after_all_new_wire_and_junction_ink():
    circuit, graph, parts, symbols, clean, diagnostic = _case()
    result = render_routed_native_sheet(
        circuit, graph, parts, symbols, STYLE, FixedInk(),
        physical_ic_renderings_clean={"DD1": clean},
        physical_ic_renderings_diagnostic={"DD1": diagnostic},
    )
    root = ET.fromstring(result.diagnostic_svg)
    layer = root.findall(
        f"./{NS}g[@data-layer='editor-connection-targets']"
    )
    assert len(layer) == 1
    assert layer[0] is list(root)[-1]
    assert len(layer[0].findall(f"./{NS}rect")) == 4
    assert not root.findall(
        f".//{NS}g[@data-layer='geometry-review']/{NS}circle"
    )
    assert all(marker.get("data-pin-ref").startswith("DD1.")
               for marker in layer[0].findall(f"./{NS}rect"))


@pytest.mark.parametrize("segments", (
    (
        WireSegment(Point(-2000, 0), Point(0, 0), "A"),
        WireSegment(Point(0, 0), Point(2000, 0), "A"),
    ),
    (
        WireSegment(Point(-2000, 0), Point(0, 0), "A"),
        WireSegment(Point(0, 0), Point(0, 2000), "A"),
    ),
))
def test_reject_nonbranch_splice_or_elbow_artwork_dot(segments):
    circuit, _, parts, symbols, clean, diag = _case()
    graph = ExternalWireGraph(segments, (Point(0, 0),))
    assert not _is_real_branch(segments, Point(0, 0))
    with pytest.raises(ValueError, match="ROUTED_SHEET_FOREIGN_OR_DANGLING_JUNCTION"):
        _render(circuit, graph, parts, symbols, clean, diag)


def test_real_three_arm_t_and_four_arm_x_are_genuine_junction_geometry():
    at = Point(0, 0)
    straight = WireSegment(Point(-2000, 0), Point(2000, 0), "A")
    branch = WireSegment(at, Point(0, 1000), "A")
    crossing = WireSegment(Point(0, -1000), Point(0, 1000), "A")
    # Geometry proof only; Circuit.Net identity, same-Net membership and
    # physical PinRef constraints remain independently checked by the renderer.
    assert _is_real_branch((straight, branch), at)
    assert _is_real_branch((straight, crossing), at)
    assert not _is_real_branch((straight, straight), at)


def test_real_23_15_62_never_claims_print_without_three_source_proofs():
    blocked = _tl494_source_print_proof_blockers(
        23, 15, 62,
        route_preview=None, source_continuation_project=None,
        physical_page_box=None,
    )
    assert set(blocked) == {
        "TL494_NEW_ROUTER_OWNER_PROVENANCE_MISSING",
        "A3_SOURCE_CONTINUATION_BINDING_UNRESOLVED",
        "TL494_PHYSICAL_ONE_TO_ONE_PAGE_NOT_VERIFIED",
    }
    # A print page and owner proof do not establish the two nonphysical
    # source-b addresses. They remain a separate typed integration contract.
    assert _tl494_source_print_proof_blockers(
        23, 15, 62,
        route_preview=object(), source_continuation_project=None,
        physical_page_box=Box(0, 0, 420000, 297000),
    ) == ("A3_SOURCE_CONTINUATION_BINDING_UNRESOLVED",)


@pytest.mark.parametrize("inventory", (
    (1, 2, 4), (23, 15, 61), (23, 14, 62), (22, 15, 62),
))
def test_generic_or_incomplete_source_inventory_not_mislabeled_as_tl494(inventory):
    assert not _tl494_source_print_proof_blockers(
        *inventory,
        route_preview=None, source_continuation_project=None,
        physical_page_box=None,
    )
