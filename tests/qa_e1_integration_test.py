"""P0 independent E1 integration gate: execute *real* PR80 and PR78 code.

Strict integration acceptance checks are intentionally NOT xfailed or skipped:
unresolved model↔view disagreements must leave the CI red. Separately, all
non-gating evidence tests exercise actual authored functions/fixtures and
identify their precise scope. All source code is SHA-verified test-only copies.
"""

import json
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from qa_e1_integration_support import (
    DISPLAY_ONLY,
    SOURCE_COMMITS,
    convert_previous_to_model_data,
    graphic_source,
    materialize_previous,
    previous_32,
    real_sources,
    verify_exact_source_files,
)

from gost_schematic.core.geometry import Point, Side
from gost_schematic.model.circuit import Circuit, PinRef

SVG = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def upstream():
    with real_sources() as sources:
        yield sources


def _case_counts(cases):
    assert len(cases) == 32
    assert {case["id"] for case in cases} == {
        f"E1-NEG-{n:02d}" for n in range(1, 33)
    }


def _graphic_block(visual, *, height=20000, width=56000, values=None):
    """Call the REAL PR78 _block geometry checker on a precise view specimen."""
    values = values or ("0.3333333333333333333333333333333",
                        "0.6666666666666666666666666666667")
    data = {
        "id": "G", "name": "БЛОК", "title_lines": ["БЛОК"],
        "code": None, "center_um": [50000, 40000 + height // 2],
        "size_um": [width, height],
        "ports": [
            {"id": "out1", "side": "RIGHT", "direction": "output",
             "relative_position": values[0]},
            {"id": "out2", "side": "RIGHT", "direction": "output",
             "relative_position": values[1]},
        ],
    }
    return visual._block(data)


def _two_port_diagram(model, height):
    block = model.FunctionalBlock(
        "G", "БЛОК", Point(22000, 40000), 56000, height
    )
    ports = (
        model.BlockPort("G", "out1", Side.RIGHT, model.PortDirection.OUTPUT),
        model.BlockPort("G", "out2", Side.RIGHT, model.PortDirection.OUTPUT),
    )
    return model.StructuralDiagram((block,), ports, ())


def _actual_svg_ports(xml_text):
    root = ET.fromstring(xml_text)
    return {
        (tag.attrib["data-block-id"], tag.attrib["data-port-id"]):
        Point(
            int(Decimal(tag.attrib["cx"]) * 1000),
            int(Decimal(tag.attrib["cy"]) * 1000),
        )
        for tag in root.findall(f".//{SVG}circle[@data-role='functional-port']")
    }


def test_source_hash_manifest_and_genuine_modules(upstream):
    model, model_example, visual = upstream
    verify_exact_source_files()
    assert SOURCE_COMMITS["model"].startswith("9c7f6251")
    assert SOURCE_COMMITS["graphics"].startswith("c49b7632")
    assert "qa-e1-upstream-" in model.__file__
    assert model.__file__.endswith("gost_schematic/structural/__init__.py")
    assert visual.__file__.endswith("review_structural_e1_design.py")
    assert model_example.__file__.endswith("review_structural_e1.py")
    assert model.FunctionalBlock.__module__ == "gost_schematic.structural.model"
    assert visual.validate_design.__module__ == "_qa_real_pr78_svg"


def test_native_six_block_real_svg_ports_match_real_model_after_explicit_marker(
    upstream,
):
    """Isolation probe: correct *only* missing marker to reach deeper geometry."""
    model, _example, visual = upstream
    data = graphic_source()
    original = deepcopy(data)
    scene = visual.validate_design(data)
    svg = visual.render_svg(data, diagnostic=True)
    assert svg == visual.render_svg(data, diagnostic=True)
    points_svg = _actual_svg_ports(svg)
    assert len(scene["blocks"]) == 6
    assert len(scene["links"]) == 7
    assert len(points_svg) == 14
    assert scene["electrical_nets"] is None
    projection = visual.semantic_projection(data)
    assert "diagram_type" not in projection  # existing seam FAIL exposed below
    # Explicit marker is a QA diagnostic adapter, NOT an upstream fix.
    normalized = {"diagram_type": "E1", **projection}
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    semantic = model.structural_from_json(encoded)
    assert semantic.diagram_type == "E1"
    assert len(semantic.blocks) == 6 and len(semantic.links) == 7
    anchors = model.resolve_port_positions(semantic)
    assert len(anchors) == len(points_svg)
    for ref, position in anchors.items():
        key = ref.block_id, ref.port_id
        view_block = next(
            block for block in scene["blocks"] if block["id"] == ref.block_id
        )
        view_position = Point(*view_block["ports"][ref.port_id]["point_um"])
        assert position == view_position == points_svg[key]
    for edge in scene["links"]:
        counterpart = next(link for link in semantic.links if link.id == edge["id"])
        assert Point(*edge["path_um"][0]) == anchors[counterpart.source]
        assert Point(*edge["path_um"][-1]) == anchors[counterpart.target]
    assert graphic_source() == original
    assert model.structural_to_json(model.structural_from_json(
        model.structural_to_json(semantic)
    )) == model.structural_to_json(semantic)
    assert sha256(svg.encode()).hexdigest() == sha256(
        visual.render_svg(data, diagnostic=True).encode()
    ).hexdigest()


def test_seven_block_real_model_rehydrates_bit_identical_and_no_e3_types(upstream):
    model, actual_example, _visual = upstream
    graph = actual_example.specimen()
    assert len(graph.blocks) == 7
    assert len(graph.ports) == 18
    assert len(graph.links) == 9
    assert model.validate_structural_diagram(graph) == ()
    canonical = model.structural_to_json(graph)
    assert model.structural_to_json(model.structural_from_json(canonical)) == canonical
    assert json.loads(canonical)["diagram_type"] == "E1"
    assert all(isinstance(link.source, model.PortRef) for link in graph.links)
    assert not isinstance(graph, Circuit)
    assert not isinstance(graph.links[0].source, PinRef)
    assert not hasattr(graph, "nets")
    assert not hasattr(graph, "physical_pins")
    ports = model.resolve_port_positions(graph)
    assert ports[model.PortRef("ENTRY", "cmd1")] == Point(60000, 4000)
    assert ports[model.PortRef("ENTRY", "cmd2")] == Point(60000, 8000)


def test_24mm_two_automatic_side_ports_match_real_view_including_svg(upstream):
    model, _example, visual = upstream
    graphic = _graphic_block(visual, height=24000)
    diagram = _two_port_diagram(model, 24000)
    anchors = model.resolve_port_positions(diagram)
    assert anchors[model.PortRef("G", "out1")] == Point(78000, 48000)
    assert anchors[model.PortRef("G", "out2")] == Point(78000, 56000)
    assert tuple(graphic["ports"][k]["point_um"]
                 for k in ("out1", "out2")) == (
        (78000, 48000), (78000, 56000)
    )
    assert len(model.structural_to_json(diagram)) > 100


def test_20mm_two_ports_cross_branch_exact_coordinate_gate(upstream):
    """Known P0: PR78 rounds 1/3; PR80 fails closed E1_PORT_OFF_GRID.

    DO NOT xfail or soften this production interoperability requirement.
    """
    model, _example, visual = upstream
    graphic = _graphic_block(visual, height=20000)
    assert [
        graphic["ports"][k]["point_um"] for k in ("out1", "out2")
    ] == [(78000, 46667), (78000, 53333)]
    diagram = _two_port_diagram(model, 20000)
    anchors = model.resolve_port_positions(diagram)  # currently raises!
    assert [
        (anchors[model.PortRef("G", key)].x, anchors[model.PortRef("G", key)].y)
        for key in ("out1", "out2")
    ] == [
        graphic["ports"][key]["point_um"] for key in ("out1", "out2")
    ]


def test_pr78_projection_canonical_e1_json_marker_gate(upstream):
    """Known P0: unmodified source projection MUST decode as PR80 v1."""
    model, _example, visual = upstream
    emitted = visual.semantic_projection(graphic_source())
    assert emitted["diagram_type"] == "E1"  # currently KeyError
    roundtrip = model.structural_to_json(
        model.structural_from_json(json.dumps(emitted, ensure_ascii=False))
    )
    assert json.loads(roundtrip)["diagram_type"] == "E1"


@pytest.mark.parametrize(
    ("fraction", "side_length", "decimal_string"),
    [
        (Fraction(1, 3), 24000, "0.333333333333333333333333333333333"),
        (Fraction(1, 2), 24000, "0.5"),
        (Fraction(2, 3), 24000, "0.666666666666666666666666666667"),
        (Fraction(3, 7), 70000, "0.428571428571428571428571428571429"),
        (Fraction(7, 16), 64000, "0.4375"),
    ],
)
def test_actual_fraction_anchors_vs_view_rounding(
    upstream, fraction, side_length, decimal_string,
):
    model, _example, visual = upstream
    b = model.FunctionalBlock("X", "БЛОК", Point(0, 0), 56000, side_length)
    p = model.BlockPort(
        "X", "out", Side.RIGHT, model.PortDirection.OUTPUT, fraction
    )
    obj = model.StructuralDiagram((b,), (p,), ())
    source = model.resolve_port_positions(obj)[p.ref]
    graphic = visual._block({
        "id": "X", "name": "БЛОК", "title_lines": ["БЛОК"],
        "code": None, "center_um": [28000, side_length // 2],
        "size_um": [56000, side_length],
        "ports": [{
            "id": "out", "side": "RIGHT",
            "direction": "output",
            "relative_position": decimal_string,
        }],
    })
    viewpoint = Point(*graphic["ports"]["out"]["point_um"])
    assert source == viewpoint
    assert model.structural_from_json(model.structural_to_json(obj)) == obj


def test_complex_rational_semantic_projection_keeps_exact_fraction_gate(upstream):
    """PR78 Decimal strings cannot preserve exact 3/7 Fraction identity."""
    model, _example, visual = upstream
    data = {
        "schema_version": 1, "diagram_type": "E1", "status": "DRAFT",
        "blocks": [{
            "id": "X", "name": "БЛОК", "title_lines": ["БЛОК"],
            "code": None, "center_um": [28000, 35000],
            "size_um": [56000, 70000],
            "ports": [{
                "id": "out", "side": "RIGHT", "direction": "output",
                "relative_position": "0.428571428571428571428571428571429",
            }],
        }],
        "links": [],
    }
    scene = visual.validate_design(data)
    assert scene["blocks"][0]["ports"]["out"]["point_um"] == (56000, 30000)
    projection = visual.semantic_projection(data)
    actual = projection["ports"][0]["position"]
    assert Fraction(*actual) == Fraction(3, 7)  # currently false
    normalized = {"diagram_type": "E1", **projection}
    graph = model.structural_from_json(json.dumps(normalized))
    assert model.resolve_port_positions(graph)[model.PortRef("X", "out")] == Point(
        56000, 30000
    )


def test_model_duplicate_fractional_anchor_and_bad_link_directions(upstream):
    model, _example, _visual = upstream
    d = _two_port_diagram(model, 24000)
    assert model.validate_structural_diagram(d) == ()
    one, two = d.ports
    duplicate = replace(d, ports=(one, replace(
        two, position=Fraction(1, 3),
    ),))
    assert "E1_PORT_COLLISION" in {
        item.code for item in model.validate_structural_diagram(duplicate)
    }
    with pytest.raises(ValueError, match="E1_PORT_COLLISION"):
        model.resolve_port_positions(duplicate)
    # Real class rejects float even if within (0,1).
    with pytest.raises(TypeError, match="Fraction"):
        model.BlockPort("G", "p", Side.RIGHT, model.PortDirection.INPUT, 0.5)


def test_visual_real_rounding_collision_and_small_port_pitch_fail(upstream):
    _model, _example, visual = upstream
    with pytest.raises(visual.E1DesignError, match="pitch"):
        _graphic_block(visual, height=24000, values=("0.3333333", "0.3333334"))
    with pytest.raises(visual.E1DesignError, match="corner"):
        _graphic_block(visual, height=20000, values=("0.01", "0.6666666666667"))
    # Model permits 6mm height and one integral mid-side semantic contact;
    # visual preview rightly has independent *editorial* text/port guards.
    graphic = {
        "id": "T", "name": "БЛОК", "title_lines": ["БЛОК"],
        "code": None, "center_um": [30000, 30000],
        "size_um": [18000, 6000],
        "ports": [{
            "id": "p", "side": "RIGHT", "direction": "output",
            "relative_position": "0.5",
        }],
    }
    with pytest.raises(visual.E1DesignError, match="content keepout"):
        visual._block(graphic)


def _crossing_view():
    def block(i, center, side, direction):
        return {
            "id": i, "name": "БЛОК", "title_lines": ["БЛОК"],
            "code": None, "center_um": list(center),
            "size_um": [20000, 20000],
            "ports": [{
                "id": "p", "side": side, "direction": direction,
                "relative_position": "0.5",
            }],
        }
    return {
        "schema_version": 1, "diagram_type": "E1", "status": "DRAFT",
        "blocks": [
            block("A", (40000, 40000), "RIGHT", "output"),
            block("B", (140000, 100000), "LEFT", "input"),
            block("C", (40000, 100000), "RIGHT", "output"),
            block("D", (140000, 40000), "LEFT", "input"),
        ],
        "links": [
            {"id": "L1", "source": {"block_id": "A", "port_id": "p"},
             "target": {"block_id": "B", "port_id": "p"},
             "arrow_at": "target",
             "via_um": [[90000, 40000], [90000, 100000]]},
            {"id": "L2", "source": {"block_id": "C", "port_id": "p"},
             "target": {"block_id": "D", "port_id": "p"},
             "arrow_at": "target",
             "via_um": [[80000, 100000], [80000, 70000],
                        [110000, 70000], [110000, 40000]]},
        ],
    }


def test_real_visual_crossing_is_nonconductive_and_model_chords_report_x(upstream):
    model, _example, visual = upstream
    scene = visual.validate_design(_crossing_view())
    assert len(scene["blocks"]) == 4 and len(scene["links"]) == 2
    assert scene["electrical_nets"] is None
    assert not any("junction" in str(x).lower() for x in scene["links"])
    xml = ET.fromstring(visual.render_svg(_crossing_view(), diagnostic=True))
    assert len(xml.findall(f".//{SVG}path[@data-role='functional-link']")) == 2
    assert len(xml.findall(f".//{SVG}path[@data-role='functional-arrow']")) == 2
    assert not xml.findall(f".//{SVG}circle[@data-role='junction']")
    projected = visual.semantic_projection(_crossing_view())
    semantic = model.structural_from_json(json.dumps({
        "diagram_type": "E1",
        **projected,
    }))  # PR80 forbids crossing straight inspection chords, currently raises.
    assert "E1_LINK_CROSSING" not in {
        diag.code for diag in model.validate_structural_diagram(semantic)
    }


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_real_graphic_eight_d4_poses_preserve_local_port_id(upstream, angle, mirror):
    _model, _example, visual = upstream
    data = {
        "schema_version": 1, "diagram_type": "E1", "status": "DRAFT",
        "blocks": [{
            "id": "X", "name": "БЛОК", "title_lines": ["БЛОК"],
            "code": None, "center_um": [70000, 70000],
            "size_um": [50000, 50000],
            "rotation": angle, "mirror_x": mirror,
            "ports": [
                {"id": "a", "side": "LEFT", "direction": "input",
                 "relative_position": "0.5"},
                {"id": "b", "side": "RIGHT", "direction": "output",
                 "relative_position": "0.5"},
            ],
        }],
        "links": [],
    }
    scene = visual.validate_design(data)
    positions = scene["blocks"][0]["ports"]
    assert positions["a"]["point_um"] != positions["b"]["point_um"]
    img = _actual_svg_ports(visual.render_svg(data, diagnostic=True))
    assert img[("X", "a")] == Point(*positions["a"]["point_um"])
    assert img[("X", "b")] == Point(*positions["b"]["point_um"])
    if angle != 0 or mirror:
        with pytest.raises(visual.E1DesignError, match="model projection"):
            visual.semantic_projection(data)
    else:
        assert len(visual.semantic_projection(data)["ports"]) == 2


def test_pr80_actual_seven_blocks_to_pr78_svg_semantic_fidelity_gate(upstream):
    """No resizing or invented route may conceal owner model/view mismatch."""
    model, actual_example, visual = upstream
    graph = actual_example.specimen()
    positions = model.resolve_port_positions(graph)
    grouped = {}
    for port in graph.ports:
        grouped.setdefault(port.block_id, []).append(port)
    blocks = []
    for b in graph.blocks:
        view_ports = []
        for port in grouped[b.id]:
            side_ports = [p for p in grouped[b.id] if p.side == port.side]
            ordinal = side_ports.index(port)
            fraction = port.position or Fraction(ordinal + 1, len(side_ports) + 1)
            # Decimal approximation is explicitly tested; never move the model.
            decimal_fraction = format(
                Decimal(fraction.numerator) / Decimal(fraction.denominator),
                "f",
            )
            view_ports.append({
                "id": port.id, "side": port.side.name,
                "relative_position": decimal_fraction,
                "direction": port.direction.value,
            })
        blocks.append({
            "id": b.id, "name": b.name,
            "title_lines": [b.name], "code": None,
            "center_um": [b.origin.x + b.width_um // 2,
                          b.origin.y + b.height_um // 2],
            "size_um": [b.width_um, b.height_um],
            "ports": view_ports,
        })
    # The model's links have no orthogonal via_um. Do not invent routes:
    # a faithful view adapter has none, and must fail closed where required.
    links = [{
        "id": link.id,
        "source": {"block_id": link.source.block_id,
                   "port_id": link.source.port_id},
        "target": {"block_id": link.target.block_id,
                   "port_id": link.target.port_id},
        "arrow_at": "target",
    } for link in graph.links]
    native = {
        "schema_version": 1, "diagram_type": "E1", "status": "DRAFT",
        "blocks": blocks, "links": links,
    }
    assert len(positions) == 18 and len(blocks) == 7
    view = visual.validate_design(native)  # currently fails on small text/port gap
    assert len(view["blocks"]) == 7 and len(view["links"]) == 9
    assert len(ET.fromstring(visual.render_svg(native)).findall(
        f".//{SVG}rect[@data-role='functional-block']"
    )) == 7


def test_legacy_32_manifest_references_all_real_scenarios(upstream):
    model, _example, _visual = upstream
    cases = previous_32()
    _case_counts(cases)
    assert len([c for c in cases if c["category"] in DISPLAY_ONLY]) == 8
    assert model.structural_from_json is not None


@pytest.mark.parametrize(
    "case",
    previous_32(),
    ids=[case["id"] for case in previous_32()],
)
def test_prior_issue72_case_is_executed_against_real_model(upstream, case):
    """32 categories: actual PR80 strict decoder, no fake success-only fixture.

    Eight visual-only categories are explicitly classified as pending visual
    port/route/text/pose acceptance, not misrepresented as PR80 tests.
    """
    model, _example, _visual = upstream
    legacy = materialize_previous(case)
    raw = json.dumps(convert_previous_to_model_data(legacy), ensure_ascii=False)
    if case["category"] in DISPLAY_ONLY:
        # Explicit scope: exercise canonical baseline using REAL PR80 decoder,
        # but never claim to have tested a view-only mutation via semantic API.
        baseline = json.loads(
            (Path(__file__).parent / "fixtures"
             / "qa_structural_e1_negative_vectors.json").read_text(
                 encoding="utf-8"
             )
        )["base_diagram"]
        diagram = model.structural_from_json(json.dumps(
            convert_previous_to_model_data(baseline), ensure_ascii=False
        ))
        assert len(diagram.blocks) == 2 and len(diagram.links) == 2
        return
    if case["expected"] == "REJECT":
        with pytest.raises((ValueError, TypeError)):
            model.structural_from_json(raw)
    elif case["expected"] == "ACCEPT":
        graph = model.structural_from_json(raw)
        assert model.validate_structural_diagram(graph) == ()
    else:
        raise AssertionError(
            f"Untested previous contract case {case['id']}: {case['expected']}"
        )


def test_strict_json_duplicate_keys_nonfinite_and_electrical_fields(upstream):
    model, ex, _visual = upstream
    data = json.loads(model.structural_to_json(ex.specimen()))
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        model.structural_from_json('{"schema_version":1,"schema_version":1}')
    mutated = deepcopy(data)
    mutated["blocks"][0]["physical_pins"] = []
    with pytest.raises(ValueError, match="expected keys"):
        model.structural_from_json(json.dumps(mutated))
    mutated = deepcopy(data)
    mutated["ports"][0]["position"] = 0.5
    with pytest.raises(ValueError, match="position"):
        model.structural_from_json(json.dumps(mutated))
    with pytest.raises(ValueError, match="nonfinite"):
        model.structural_from_json(
            model.structural_to_json(ex.specimen()).replace(
                '"schema_version": 1', '"schema_version": NaN'
            )
        )
    assert not hasattr(model, "Circuit")
