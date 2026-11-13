"""PR #78 ↔ real PR #80 typed E1 image-contract gates; never fake model types.

In the ordinary YGO-only branch this optional test skips because PR80 remains
unmerged. The dedicated E1 CI MUST fetch and load genuine PR80 source.
"""

import hashlib
import json
import os
from dataclasses import replace
from fractions import Fraction
from importlib import import_module
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.core.geometry import Point, Side

_structural = pytest.importorskip("gost_schematic.structural")
_graphics = import_module("examples.review_structural_e1_model")
BlockView = _graphics.BlockView
E1GraphicError = _graphics.E1GraphicError
example_views = _graphics.example_views
render_structural_model = _graphics.render_structural_model
BlockPort = _structural.BlockPort
FunctionalBlock = _structural.FunctionalBlock
PortDirection = _structural.PortDirection
PortRef = _structural.PortRef
StructuralDiagram = _structural.StructuralDiagram
resolve_port_positions = _structural.resolve_port_positions
structural_from_json = _structural.structural_from_json
structural_to_json = _structural.structural_to_json
validate_structural_diagram = _structural.validate_structural_diagram

FIXTURE = Path("examples/fixtures/structural_e1/pr80-shared-7b-18p-9l.json")
SVG_NS = "{http://www.w3.org/2000/svg}"


def font():
    path = os.getenv("E1_TEST_FONT")
    if not path or not Path(path).is_file():
        pytest.skip("Measured OpenGOST Type A font must be provided by E1 integration CI")
    return path


def fixture():
    raw = FIXTURE.read_text(encoding="utf-8")
    diagram = structural_from_json(raw)
    assert structural_to_json(diagram) == raw
    assert not validate_structural_diagram(diagram)
    return diagram


def _xml(diagram, **kwargs):
    svg, manifest = render_structural_model(diagram, font(), **kwargs)
    return ET.fromstring(svg), svg, manifest


def test_pr80_canonical_source_is_seven_eighteen_nine_and_unchanged():
    diagram = fixture()
    assert diagram.diagram_type == "E1"
    assert (len(diagram.blocks), len(diagram.ports), len(diagram.links)) == (7, 18, 9)
    assert all(isinstance(l.source, PortRef) and isinstance(l.target, PortRef)
               for l in diagram.links)
    assert not hasattr(diagram, "nets")
    anchors = resolve_port_positions(diagram)
    assert anchors[PortRef("ENTRY", "cmd1")] == Point(60000, 4000)
    assert anchors[PortRef("ENTRY", "cmd2")] == Point(60000, 8000)
    assert anchors[PortRef("CTRL", "cmd1")] == Point(80000, 4000)
    assert anchors[PortRef("CTRL", "cmd2")] == Point(80000, 8000)


def test_all_real_functional_links_match_exact_svg_portrefs_and_process_arrows():
    diagram = fixture()
    root, svg, manifest = _xml(
        diagram, via_by_link={"L09": ((110000, 36000), (110000, 22000),
                                           (130000, 22000))},
    )
    assert (manifest["block_count"], manifest["port_count"],
            manifest["link_count"]) == (7, 18, 9)
    assert manifest["status"] == root.attrib["data-status"] == "DRAFT"
    anchors = resolve_port_positions(diagram)
    paths = root.findall(f".//{SVG_NS}path[@data-role='functional-link']")
    arrows = root.findall(f".//{SVG_NS}path[@data-role='functional-process-arrow']")
    assert len(paths) == len(arrows) == 9
    assert {p.get("data-link-id") for p in paths} == {l.id for l in diagram.links}
    assert not root.findall(f".//{SVG_NS}image")
    assert not root.findall(f".//{SVG_NS}circle[@data-role='junction']")
    assert all("net" not in p.attrib for p in paths)
    by_link = {line["id"]: line for line in manifest["links"]}
    for link in diagram.links:
        row = by_link[link.id]
        path = next(p for p in paths if p.get("data-link-id") == link.id)
        source = [anchors[link.source].x, anchors[link.source].y]
        target = [anchors[link.target].x, anchors[link.target].y]
        assert row["points_um"][0] == source
        assert row["points_um"][-1] == target
        assert json.loads(path.attrib["data-points-um"]) == row["points_um"]
        assert path.attrib["data-source-ref"] == (
            link.source.block_id + ":" + link.source.port_id
        )
        assert path.attrib["data-target-ref"] == (
            link.target.block_id + ":" + link.target.port_id
        )
        assert row["process_direction"] == "source_to_target"
        assert len([p for p in arrows if p.get("data-link-id") == link.id]) == 1
    assert hashlib.sha256(svg.encode("utf-8")).hexdigest() == manifest["svg_sha256"]


def test_every_diagnostic_marker_is_the_model_resolver_coordinate():
    diagram = fixture()
    root, _svg, manifest = _xml(diagram, diagnostic=True)
    anchors = resolve_port_positions(diagram)
    marked = root.findall(f".//{SVG_NS}circle[@data-role='declared-functional-port']")
    assert len(marked) == 18
    assert root.findall(f".//{SVG_NS}rect[@data-role='measured-text-hitbox']")
    for item in marked:
        ref = item.attrib["data-portref"]
        target = next((p for p in anchors if f"{p.block_id}:{p.port_id}" == ref), None)
        assert target is not None
        p = anchors[target]
        assert Fraction(item.attrib["cx"]) * 1000 == p.x
        assert Fraction(item.attrib["cy"]) * 1000 == p.y
    assert all(x["model_um"] == x["svg_um"] for x in manifest["ports"])


def test_text_real_glyph_ink_bounds_stay_inside_real_block_frames():
    diagram = fixture()
    _root, _svg, manifest = _xml(diagram)
    boxes = {v["block_id"]: v["bounds"] for v in manifest["block_boxes_um"]}
    assert manifest["font"]["requested_cap_height_um"] == 2500
    assert abs(manifest["font"]["measured_cap_height_um"] - 2500) <= 5
    assert len(manifest["text_hitboxes_um"]) > 7
    for label in manifest["text_hitboxes_um"]:
        box, region = label["bounds"], boxes[label["block_id"]]
        assert region[0] < box[0] < box[2] < region[2]
        assert region[1] < box[1] < box[3] < region[3]
    assert "".join(example_views(diagram)["ENTRY"].title_lines) == "Ввод команд"
    assert "".join(example_views(diagram)["ADAPT"].title_lines) == "Согласование"


def test_pr80_20000_um_two_auto_ports_rejects_no_rounding_in_both_layers():
    block = FunctionalBlock("ONE", "ONE", Point(0, 0), 28000, 20000)
    diagram = StructuralDiagram(
        (block,),
        (BlockPort("ONE", "A", Side.RIGHT, PortDirection.OUTPUT),
         BlockPort("ONE", "B", Side.RIGHT, PortDirection.OUTPUT)),
        (),
    )
    diagnostic_codes = {d.code for d in validate_structural_diagram(diagram)}
    assert "E1_PORT_OFF_GRID" in diagnostic_codes
    with pytest.raises(ValueError, match="E1_PORT_OFF_GRID"):
        resolve_port_positions(diagram)
    with pytest.raises(E1GraphicError, match="E1_PORT_OFF_GRID"):
        render_structural_model(
            diagram, font(), views={"ONE": BlockView(("ONE",))},
        )


def test_pr80_exact_positions_with_12000_um_two_ports_equal_visual_points():
    diagram = StructuralDiagram(
        (FunctionalBlock("ONE", "ONE", Point(0, 0), 28000, 12000),),
        (BlockPort("ONE", "A", Side.RIGHT, PortDirection.OUTPUT),
         BlockPort("ONE", "B", Side.RIGHT, PortDirection.OUTPUT)),
        (),
    )
    anchors = resolve_port_positions(diagram)
    assert anchors[PortRef("ONE", "A")] == Point(28000, 4000)
    assert anchors[PortRef("ONE", "B")] == Point(28000, 8000)
    root, _svg, m = _xml(diagram, views={"ONE": BlockView(("ONE",))})
    assert m["ports"][0]["model_um"] == m["ports"][0]["svg_um"]
    assert len(root.findall(f".//{SVG_NS}circle")) == 0


@pytest.mark.parametrize("height,n", ((12000, 2), (20000, 4), (24000, 3)))
def test_automatic_fraction_slots_exact_and_reported_on_true_portref(height, n):
    diagram = StructuralDiagram(
        (FunctionalBlock("A", "A", Point(0, 0), 40000, height),),
        tuple(BlockPort("A", f"P{i}", Side.RIGHT, PortDirection.OUTPUT)
              for i in range(n)),
        (),
    )
    anchor = resolve_port_positions(diagram)
    assert [anchor[PortRef("A", f"P{i}")].y for i in range(n)] == [
        (i+1)*height//(n+1) for i in range(n)
    ]
    _root, _svg, result = _xml(diagram, views={"A": BlockView(("A",))})
    assert all(row["model_um"] == row["svg_um"] for row in result["ports"])


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_eight_poses_reposition_view_but_preserve_portref_identity(rotation, mirror):
    diagram = StructuralDiagram(
        (FunctionalBlock("A", "БЛОК", Point(20000, 20000), 30000, 30000),),
        (BlockPort("A", "IN", Side.LEFT, PortDirection.INPUT),
         BlockPort("A", "OUT", Side.RIGHT, PortDirection.OUTPUT)),
        (),
    )
    block_view = BlockView(("БЛОК",), rotation=rotation, mirror_x=mirror)
    xml, _svg, m = _xml(diagram, views={"A": block_view}, diagnostic=True)
    refs = {(r["ref"]["block_id"], r["ref"]["port_id"]) for r in m["ports"]}
    assert refs == {("A", "IN"), ("A", "OUT")}
    assert len({tuple(r["svg_um"]) for r in m["ports"]}) == 2
    assert len(xml.findall(f".//{SVG_NS}circle[@data-role='declared-functional-port']")) == 2
    assert all(x.get("transform") is None
               for x in xml.findall(f".//{SVG_NS}text"))


def test_mutation_of_semantic_source_port_rejected_before_visual_routing():
    diagram = fixture()
    link = diagram.links[0]
    broken = replace(
        diagram, links=(replace(
            link, source=PortRef(link.source.block_id, "NOT_A_PORT"),
        ), *diagram.links[1:]),
    )
    assert any(x.code == "E1_LINK_PORT_UNKNOWN"
               for x in validate_structural_diagram(broken))
    with pytest.raises(E1GraphicError, match="E1_LINK_PORT_UNKNOWN"):
        render_structural_model(broken, font())


def test_nonexistent_waypoint_link_and_inward_path_rejected():
    diagram = fixture()
    with pytest.raises(E1GraphicError, match="Unknown link route"):
        render_structural_model(diagram, font(), via_by_link={"NONEXISTENT": ((1, 2),)})
    with pytest.raises(E1GraphicError, match="does not exit source"):
        render_structural_model(diagram, font(), via_by_link={"L01": ((18000, 6000),)})


def test_font_and_svg_geometry_stable_on_repeat():
    diagram = fixture()
    a, manifest = render_structural_model(diagram, font())
    b, manifest2 = render_structural_model(diagram, font())
    assert a == b and manifest == manifest2
    assert manifest["svg_sha256"] == hashlib.sha256(a.encode()).hexdigest()
