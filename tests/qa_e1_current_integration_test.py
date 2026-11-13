"""Independent integration of CURRENT PR80 82d400 & PR78 b7fa owners' REAL code.

These tests execute both real immutable owner modules, not a simulated model.
The separate OpenGost-equipped Actions job executes actual typed SVG/PNG and
measured ink. The older 5-case gate remains pinned to historical owner SHAs.
"""

import json
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from xml.etree import ElementTree as ET

import pytest
from qa_e1_integration_support import (
    CURRENT_BLOBS,
    CURRENT_SHAS,
    blob_hash,
    current_shared_visual_seed,
    real_current_sources,
)

from gost_schematic.core.geometry import Point, Side

SVG = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def latest():
    with real_current_sources() as sources:
        yield sources


def _model_two_ports(model, length):
    b = model.FunctionalBlock("X", "БЛОК", Point(0, 0), 28000, length)
    ps = tuple(
        model.BlockPort("X", key, Side.RIGHT, model.PortDirection.OUTPUT)
        for key in ("a", "b")
    )
    return model.StructuralDiagram((b,), ps, ())


def test_latest_snapshots_are_exact_upstream_commits():
    assert CURRENT_SHAS["model"] == "82d400d2472a0a546dafcbf18f70d581642ca284"
    assert CURRENT_SHAS["graphics"] == "b7fa2138e84d5279ef0b894cb4ca56b32732b11b"
    from qa_e1_integration_support import FIXTURES
    assert all(
        blob_hash((FIXTURES / path).read_bytes()) == target
        for path, target in CURRENT_BLOBS.items()
    )


def test_updated_real_7block_graph_and_standalone_ygo2_view_18_actual_ports(latest):
    model, authored, viewer, new_renderer = latest
    graph = authored.specimen()
    visual = authored.ygo2_visual_seed()
    assert visual == current_shared_visual_seed()
    assert (len(graph.blocks), len(graph.ports), len(graph.links)) == (7, 18, 9)
    assert model.validate_structural_diagram(graph) == ()
    assert model.validate_port_clearances(graph) == ()
    assert len(viewer.validate_design(visual)["blocks"]) == 7
    scene = viewer.validate_design(visual)
    assert len(scene["links"]) == 9
    anchors = model.resolve_port_positions(graph)
    graphics = {
        model.PortRef(b["id"], port["id"]): Point(*port["point_um"])
        for b in scene["blocks"] for port in b["ports"].values()
    }
    assert anchors == graphics
    assert len(anchors) == 18
    clean = viewer.render_svg(visual)
    diagnostic = viewer.render_svg(visual, diagnostic=True)
    assert ET.fromstring(clean).get("data-diagram-type") == "E1"
    assert len(ET.fromstring(clean).findall(
        f".//{SVG}rect[@data-role='functional-block']"
    )) == 7
    assert len(ET.fromstring(clean).findall(
        f".//{SVG}path[@data-role='functional-link']"
    )) == 9
    assert len(ET.fromstring(diagnostic).findall(
        f".//{SVG}circle[@data-role='functional-port']"
    )) == 18
    assert new_renderer.render_structural_model is not None
    assert model.structural_to_json(model.structural_from_json(
        model.structural_to_json(graph)
    )) == model.structural_to_json(graph)


def test_current_model_and_view_ports_at_20k_and_24k(latest):
    model, _authored, viewer, _typed = latest
    for length, expected in (
        (20000, (6667, 13333)),
        (24000, (8000, 16000)),
    ):
        graph = _model_two_ports(model, length)
        a = model.resolve_port_positions(graph)
        assert [
            a[model.PortRef("X", key)].y for key in ("a", "b")
        ] == list(expected)
        view = {
            "id": "X", "name": "БЛОК", "title_lines": ["БЛОК"], "code": None,
            "size_um": [28000, length],
            "center_um": [14000, length // 2],
            "ports": [
                {
                    "id": key, "side": "RIGHT", "direction": "output",
                    "relative_position": fraction,
                }
                for key, fraction in (
                    ("a", "0.333333333333333333333333333333333"),
                    ("b", "0.666666666666666666666666666666667"),
                )
            ],
        }
        graphics = viewer._block(view)
        assert [
            graphics["ports"][key]["point_um"][1] for key in ("a", "b")
        ] == list(expected)
        assert model.validate_structural_diagram(graph) == ()


@pytest.mark.parametrize(
    ("fraction", "length", "expected"),
    [
        (Fraction(1, 3), 20000, 6667),
        (Fraction(1, 2), 20000, 10000),
        (Fraction(2, 3), 20000, 13333),
        (Fraction(3, 7), 70000, 30000),
        (Fraction(7, 16), 64000, 28000),
        (Fraction(1, 24000), 12000, 1),
    ],
)
def test_updated_fraction_rounding_once_to_actual_integer_model_point(
    latest, fraction, length, expected,
):
    model, _authored, _viewer, _typed = latest
    b = model.FunctionalBlock("X", "X", Point(0, 0), 28000, length)
    port = model.BlockPort(
        "X", "p", Side.RIGHT, model.PortDirection.OUTPUT, fraction
    )
    diagram = model.StructuralDiagram((b,), (port,), ())
    assert model.resolve_port_positions(diagram)[port.ref] == Point(28000, expected)
    assert model.structural_from_json(model.structural_to_json(diagram)) == diagram


def test_updated_rounding_collisions_not_silently_merged(latest):
    model, _author, _viewer, _typed = latest
    b = model.FunctionalBlock("X", "X", Point(0, 0), 28000, 12000)
    ps = (
        model.BlockPort("X", "a", Side.RIGHT, model.PortDirection.OUTPUT,
                        Fraction(1, 48000)),
        model.BlockPort("X", "b", Side.RIGHT, model.PortDirection.OUTPUT,
                        Fraction(1, 60000)),
    )
    diagram = model.StructuralDiagram((b,), ps, ())
    assert "E1_PORT_COLLISION" in {
        d.code for d in model.validate_structural_diagram(diagram)
    }
    with pytest.raises(ValueError, match="E1_PORT_COLLISION"):
        model.resolve_port_positions(diagram)


def test_current_editorial_port_gap_validator_real_model(latest):
    model, _author, viewer, _typed = latest
    graph = _model_two_ports(model, 20000)
    assert model.validate_structural_diagram(graph) == ()
    assert model.validate_port_clearances(graph) == ()
    b = replace(graph.blocks[0], height_um=9000)
    short = replace(graph, blocks=(b,))
    assert model.validate_structural_diagram(short) == ()
    assert model.validate_port_clearances(short)  # precisely editorial, not GOST
    too_small = {
        "id": "X", "name": "БЛОК", "title_lines": ["БЛОК"], "code": None,
        "size_um": [28000, 9000], "center_um": [14000, 4500],
        "ports": [{
            "id": "p", "side": "RIGHT", "direction": "output",
            "relative_position": "0.5",
        }],
    }
    with pytest.raises(viewer.E1DesignError, match="content keepout"):
        viewer._block(too_small)


def test_latest_declared_ports_reject_bad_direction_nonexistence_and_circuit_leak(
    latest,
):
    model, _authored, viewer, _typed = latest
    diagram = _model_two_ports(model, 24000)
    bad = replace(diagram, ports=diagram.ports + (diagram.ports[0],))
    assert "E1_DUPLICATE_PORT" in {
        x.code for x in model.validate_structural_diagram(bad)
    }
    with pytest.raises((ValueError, TypeError)):
        model.structural_from_json(json.dumps({
            "schema_version": 1, "diagram_type": "E1",
            "blocks": [{"id": "X", "name": "X", "origin_um": [0, 0],
                        "width_um": 28000, "height_um": 24000,
                        "physical_pin_ref": "R1.1"}],
            "ports": [], "links": [],
        }))
    candidate = current_shared_visual_seed()
    candidate["links"][0]["target"]["port_id"] = "NOT_DECLARED"
    with pytest.raises(viewer.E1DesignError, match="dangling"):
        viewer.validate_design(candidate)
    assert not hasattr(diagram, "nets")
    assert all(type(x).__name__ == "PortRef" for x in (
        model.PortRef("X", "a"), model.PortRef("X", "b")
    ))


def test_new_model_view_rotations_are_view_only_and_fail_closed_for_legacy_export(
    latest,
):
    model, _authored, viewer, typed = latest
    base = current_shared_visual_seed()
    # Stand-alone SVG transforms all four orthogonal rotations + two mirrors;
    # semantic export deliberately cannot carry view transformation.
    for rot in (0, 90, 180, 270):
        for mirrored in (False, True):
            one = {
                "schema_version": 1, "diagram_type": "E1", "status": "DRAFT",
                "blocks": [{
                    "id": "X", "name": "БЛОК", "title_lines": ["БЛОК"],
                    "code": None, "center_um": [45000, 45000],
                    "size_um": [30000, 30000], "rotation": rot,
                    "mirror_x": mirrored,
                    "ports": [{
                        "id": "p", "side": "RIGHT", "direction": "output",
                        "relative_position": "0.5",
                    }],
                }],
                "links": [],
            }
            scene = viewer.validate_design(one)
            assert len(scene["blocks"]) == 1
            img = ET.fromstring(viewer.render_svg(one, diagnostic=True))
            circle = img.find(f".//{SVG}circle[@data-role='functional-port']")
            assert circle is not None
            assert Point(
                int(Decimal(circle.attrib["cx"]) * 1000),
                int(Decimal(circle.attrib["cy"]) * 1000),
            ) == Point(*scene["blocks"][0]["ports"]["p"]["point_um"])
            if rot != 0 or mirrored:
                with pytest.raises(viewer.E1DesignError, match="model projection"):
                    viewer.semantic_projection(one)
    assert typed.BlockView(("БЛОК",), rotation=270, mirror_x=True)
    assert len(model.structural_to_json(model.structural_from_json(
        model.structural_to_json(_model_two_ports(model, 24000))
    ))) > 1
    assert len(base["blocks"]) == 7


def test_new_ygo_standalone_projection_still_not_canonical(latest):
    model, authored, viewer, _typed = latest
    projected = viewer.semantic_projection(authored.ygo2_visual_seed())
    assert "diagram_type" not in projected
    # Test adapter is an EXPLICIT delta for source reconciliation ONLY.
    corrected = {"diagram_type": "E1", **projected}
    assert model.structural_from_json(json.dumps(corrected)) == authored.specimen()
    with pytest.raises(ValueError, match="expected keys"):
        model.structural_from_json(json.dumps(projected))
