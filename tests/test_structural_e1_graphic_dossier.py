"""Issue #71: standalone non-electrical Э1 graphic-contract fixtures and negatives."""

from copy import deepcopy
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_structural_e1_design import (
    E1DesignError,
    main,
    render_svg,
    validate_design,
)
from scripts.audit_symbol_catalog import audit_catalog

FIXTURE = Path("examples/fixtures/structural_e1/blocks.json")
SVG = "{http://www.w3.org/2000/svg}"


def specimen():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def block(data, name):
    return next(item for item in data["blocks"] if item["id"] == name)


def test_six_blocks_seven_functional_arrows_not_an_electrical_catalog():
    data = specimen()
    scene = validate_design(data)
    assert len(scene["blocks"]) == 6
    assert len(scene["links"]) == 7
    assert scene["diagram_type"] == "E1"
    assert scene["electrical_nets"] is None
    assert all(item["title_lines"] for item in scene["blocks"])
    assert all(len(item["ports"]) >= 1 for item in scene["blocks"])
    current_catalog = audit_catalog()
    assert current_catalog["total_symbols"] == current_catalog["draft_count"] == 21
    assert current_catalog["hard_errors"] == 0
    assert "structural" not in {item["id"].split(".")[0]
                                for item in current_catalog["entries"]}


def test_three_equal_ports_and_stable_9mm_pitch():
    scene = validate_design(specimen())
    b2 = next(item for item in scene["blocks"] if item["id"] == "B2")
    ports = b2["ports"]
    assert [ports[p]["point_um"] for p in ("a", "b", "c")] == [
        (198000, 31000), (198000, 40000), (198000, 49000),
    ]
    b3 = next(item for item in scene["blocks"] if item["id"] == "B3")
    assert [b3["ports"][p]["point_um"] for p in ("a", "b", "c")] == [
        (252000, 31000), (252000, 40000), (252000, 49000),
    ]
    assert tuple(ports[x]["direction"] for x in ("a", "b", "c")) == (
        "output", "output", "output",
    )


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_eight_poses_preserve_port_id_side_normal_and_upright_title(rotation, mirror):
    data = {
        "schema_version": 1, "diagram_type": "E1", "status": "DRAFT",
        "blocks": [{
            "id": "B", "title_lines": ["БЛОК"], "code": None,
            "center_um": [75000, 40000], "size_um": [50000, 50000],
            "rotation": rotation, "mirror_x": mirror,
            "ports": [
                {"id": "A", "side": "LEFT", "relative_position": "0.5",
                 "direction": "input"},
                {"id": "K", "side": "RIGHT", "relative_position": "0.5",
                 "direction": "output"},
            ],
        }],
        "links": [],
    }
    scene = validate_design(data)
    ports = scene["blocks"][0]["ports"]
    assert ports["A"]["direction"] == "input"
    assert ports["K"]["direction"] == "output"
    assert ports["A"]["id"] == "A" and ports["K"]["id"] == "K"
    assert ports["A"]["point_um"] != ports["K"]["point_um"]
    for port in ports.values():
        x, y = port["point_um"]
        dx, dy = port["normal"]
        assert (x - 75000) * dx + (y - 40000) * dy > 0
    svg = ET.fromstring(render_svg(data, diagnostic=True))
    assert len(svg.findall(f".//{SVG}rect[@data-role='functional-block']")) == 1
    assert len(svg.findall(f".//{SVG}circle[@data-role='functional-port']")) == 2
    title = svg.find(f".//{SVG}text[@data-role='block-title']")
    assert title is not None and title.text == "БЛОК"
    assert "transform" not in title.attrib


def test_exact_scale_preserves_fractional_port_attachment_and_raises_no_net():
    data = specimen()
    keep = block(data, "B1")
    data["blocks"] = [keep]
    data["links"] = []
    keep["scale"] = "2"
    keep["code"] = None
    result = validate_design(data)
    assert result["blocks"][0]["box_um"] == (22000, 10000, 118000, 70000)
    assert result["blocks"][0]["ports"]["data_out"]["point_um"] == (118000, 40000)
    assert result["electrical_nets"] is None


def test_svg_is_genuine_vector_repeatable_and_clean_diagnostic_differ():
    data = specimen()
    clean = render_svg(data)
    assert clean == render_svg(data)
    diagnostic = render_svg(data, diagnostic=True)
    assert diagnostic == render_svg(data, diagnostic=True)
    assert clean != diagnostic
    root = ET.fromstring(clean)
    overlay = ET.fromstring(diagnostic)
    assert root.get("data-diagram-type") == "E1"
    assert root.get("data-approval-status") == "DRAFT"
    assert not root.findall(f".//{SVG}image")
    assert len(root.findall(f".//{SVG}rect[@data-role='functional-block']")) == 6
    assert len(root.findall(f".//{SVG}path[@data-role='functional-link']")) == 7
    assert len(root.findall(f".//{SVG}path[@data-role='functional-arrow']")) == 7
    assert not root.findall(f".//{SVG}circle[@data-role='functional-port']")
    assert len(overlay.findall(f".//{SVG}circle[@data-role='functional-port']")) == 14
    assert len(overlay.findall(f".//{SVG}rect[@data-role='editorial-text-keepout']")) == 6


def test_cli_generates_two_svg_specimens_and_provenance(tmp_path):
    assert main(["--fixture", str(FIXTURE), "--output-dir", str(tmp_path)]) == 0
    clean = (tmp_path / "e1-clean.svg").read_text(encoding="utf-8")
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert clean == render_svg(specimen())
    assert (tmp_path / "e1-diagnostic.svg").is_file()
    assert manifest["block_count"] == 6 and manifest["link_count"] == 7
    assert manifest["electrical_semantics"] is False


@pytest.mark.parametrize(("mutator", "pattern"), [
    (lambda d: d["blocks"].append(deepcopy(d["blocks"][0])), "duplicate structural block"),
    (lambda d: block(d, "B2")["ports"].append(
        deepcopy(block(d, "B2")["ports"][0])), "duplicate or blank port"),
    (lambda d: block(d, "B2")["ports"].__setitem__(1, {
        **block(d, "B2")["ports"][1], "relative_position": "0.20",
    }), "evenly distributed"),
    (lambda d: block(d, "B2")["ports"].__setitem__(1, {
        **block(d, "B2")["ports"][1], "relative_position": "0.01",
    }), "corner"),
    (lambda d: d["links"][0]["target"].update(block_id="MISSING"), "dangling"),
    (lambda d: d["links"][0]["target"].update(port_id="border_contact"), "dangling"),
    (lambda d: d["links"][0]["target"].update(
        block_id="B1", port_id="data_out"), "self-loop"),
    (lambda d: block(d, "B1")["ports"][0].update(direction="input"), "flow"),
    (lambda d: d["links"][0].update(via_um=[[105000, 36000]]), "diagonal"),
    (lambda d: d["links"][0].update(via_um=[[94000, 40000]]), "zero-length"),
    (lambda d: block(d, "B2").update(rotation=45), "transformation"),
    (lambda d: block(d, "B2").update(scale="0"), "scale"),
    (lambda d: block(d, "B2")["ports"][0].update(
        relative_position=0.5), "decimal string"),
    (lambda d: block(d, "B1").update(title_lines=["X" * 100]), "title"),
    (lambda d: block(d, "B1").update(PartDefinition={}), "electrical"),
    (lambda d: d.update(nets=[]), "electrical"),
    (lambda d: d["links"].append(deepcopy(d["links"][0])), "duplicate or blank"),
])
def test_negative_dossier_cases_reject_invalid_graphics(mutator, pattern):
    data = specimen()
    mutator(data)
    with pytest.raises(E1DesignError, match=pattern):
        validate_design(data)


def test_short_same_side_fails_minimum_editorial_port_pitch():
    data = specimen()
    b2 = block(data, "B2")
    b2["size_um"] = [56000, 18000]
    b2["code"] = None
    with pytest.raises(E1DesignError, match="port"):
        validate_design(data)


def test_diagram_link_crossing_remains_declared_only_not_a_junction():
    # Two visually crossing line segments, four independent block/port pairs.
    def b(identifier, xy, side, direction):
        return {
            "id": identifier, "title_lines": ["A"], "code": None,
            "center_um": list(xy), "size_um": [20000, 20000],
            "ports": [{"id": "P", "side": side, "relative_position": "0.5",
                       "direction": direction}],
        }

    data = {
        "schema_version": 1, "diagram_type": "E1", "status": "DRAFT",
        "blocks": [b("L", (0, 0), "RIGHT", "output"),
                   b("R", (100000, 0), "LEFT", "input"),
                   b("T", (50000, -40000), "BOTTOM", "output"),
                   b("D", (50000, 40000), "TOP", "input")],
        "links": [
            {"id": "H", "source": {"block_id": "L", "port_id": "P"},
             "target": {"block_id": "R", "port_id": "P"}},
            {"id": "V", "source": {"block_id": "T", "port_id": "P"},
             "target": {"block_id": "D", "port_id": "P"}},
        ],
    }
    scene = validate_design(data)
    assert len(scene["links"]) == 2
    assert scene["electrical_nets"] is None
    svg = render_svg(data)
    assert "junction" not in svg.lower() and "pinref" not in svg.lower()


def test_two_links_cannot_occupy_same_parallel_sheet_segment():
    data = specimen()
    new_link = deepcopy(data["links"][0])
    new_link["id"] = "L8"
    data["links"].append(new_link)
    with pytest.raises(E1DesignError, match="parallel functional links too close"):
        validate_design(data)
