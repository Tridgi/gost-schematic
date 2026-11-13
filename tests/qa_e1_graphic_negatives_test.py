"""Execute the eight PR77 visual-only negative vectors against ACTUAL PR78.

No fake production E1 renderer is supplied. Where the semantic PR80 has no
view concept, the test records/inspects the actual cross-layer policy mismatch,
never treating absence of a feature as an invented passing implementation.
"""

from copy import deepcopy

import pytest
from qa_e1_integration_support import (
    DISPLAY_ONLY,
    graphic_source,
    previous_32,
    real_current_sources,
)
from qa_e1_integration_test import _crossing_view

from gost_schematic.core.geometry import Point, Side


@pytest.fixture(scope="module")
def upstream():
    with real_current_sources() as (model, example, visual, _typed):
        yield model, example, visual


def _graphic_id(dataset, value):
    return next(block for block in dataset["blocks"] if block["id"] == value)


def _fanout_view():
    def block(identifier, center, side, direction):
        return {
            "id": identifier,
            "name": identifier, "title_lines": [identifier], "code": None,
            "center_um": list(center), "size_um": [20000, 14000],
            "ports": [{
                "id": "p", "side": side, "direction": direction,
                "relative_position": "0.5",
            }],
        }
    return {
        "schema_version": 1, "diagram_type": "E1", "status": "DRAFT",
        "blocks": [
            block("A", (20000, 40000), "RIGHT", "output"),
            block("B", (70000, 40000), "LEFT", "input"),
            block("C", (70000, 80000), "LEFT", "input"),
        ],
        "links": [
            {
                "id": "L1",
                "source": {"block_id": "A", "port_id": "p"},
                "target": {"block_id": "B", "port_id": "p"},
                "arrow_at": "target",
            },
            {
                "id": "L2",
                "source": {"block_id": "A", "port_id": "p"},
                "target": {"block_id": "C", "port_id": "p"},
                "arrow_at": "target",
                "via_um": [[40000, 40000], [40000, 80000]],
            },
        ],
    }


@pytest.mark.parametrize(
    "case_id", [
        "E1-NEG-20", "E1-NEG-21", "E1-NEG-22", "E1-NEG-25",
        "E1-NEG-26", "E1-NEG-27", "E1-NEG-30", "E1-NEG-31",
    ],
)
def test_previous_visual_only_negative_is_executed_against_real_pr78(
    upstream, case_id,
):
    model, _example, visual = upstream
    lookup = {entry["id"]: entry for entry in previous_32()}
    assert case_id in lookup
    case = lookup[case_id]
    assert case["category"] in DISPLAY_ONLY
    sample = graphic_source()
    if case_id == "E1-NEG-20":
        first = _graphic_id(sample, "B1")
        first["code"] = None
        first["name"] = "ДЛИННОЕ НАЗВАНИЕ " * 10
        first["title_lines"] = [first["name"].strip()]
        first["name"] = first["name"].strip()
        with pytest.raises(visual.E1DesignError, match="content keepout"):
            visual.validate_design(sample)
    elif case_id == "E1-NEG-21":
        first = _graphic_id(sample, "B1")
        first["code"] = None
        first["size_um"] = [48000, 18000]
        first["name"] = "ПЕРВАЯ ВТОРАЯ ТРЕТЬЯ"
        first["title_lines"] = ["ПЕРВАЯ", "ВТОРАЯ", "ТРЕТЬЯ"]
        with pytest.raises(visual.E1DesignError, match="content keepout"):
            visual.validate_design(sample)
    elif case_id == "E1-NEG-22":
        _graphic_id(sample, "B1")["rotation"] = 45
        with pytest.raises(visual.E1DesignError, match="transformation"):
            visual.validate_design(sample)
    elif case_id == "E1-NEG-25":
        b2 = _graphic_id(sample, "B2")
        b2["size_um"] = [56000, 21000]
        b2["code"] = None
        with pytest.raises(visual.E1DesignError, match="pitch"):
            visual.validate_design(sample)
        # Actual PR80 model accepts same 21mm/three-port semantic geometry;
        # independent *editorial* 6mm pitch makes it fail in PR78 view.
        b = model.FunctionalBlock("X", "БЛОК", Point(0, 0), 56000, 21000)
        ports = tuple(
            model.BlockPort("X", f"p{i}", Side.RIGHT, model.PortDirection.OUTPUT)
            for i in range(3)
        )
        assert model.validate_structural_diagram(
            model.StructuralDiagram((b,), ports, ())
        ) == ()
    elif case_id == "E1-NEG-26":
        data = _crossing_view()
        scene = visual.validate_design(data)
        assert len(scene["links"]) == 2
        assert scene["electrical_nets"] is None
        assert "junction" not in visual.render_svg(data).lower()
    elif case_id == "E1-NEG-27":
        sample["nets"] = [{"invalid_electrical": True}]
        with pytest.raises(visual.E1DesignError, match="electrical"):
            visual.validate_design(sample)
    elif case_id == "E1-NEG-30":
        sample["links"][0]["arrow_at"] = "source"
        with pytest.raises(visual.E1DesignError, match="arrow"):
            visual.validate_design(sample)
    elif case_id == "E1-NEG-31":
        sample = _fanout_view()
        with pytest.raises(visual.E1DesignError, match="parallel"):
            visual.validate_design(sample)
        blocks = (
            model.FunctionalBlock("A", "A", Point(10000, 33000), 20000, 14000),
            model.FunctionalBlock("B", "B", Point(60000, 33000), 20000, 14000),
            model.FunctionalBlock("C", "C", Point(60000, 73000), 20000, 14000),
        )
        ports = (
            model.BlockPort("A", "p", Side.RIGHT, model.PortDirection.OUTPUT),
            model.BlockPort("B", "p", Side.LEFT, model.PortDirection.INPUT),
            model.BlockPort("C", "p", Side.LEFT, model.PortDirection.INPUT),
        )
        links = (
            model.FunctionalLink(
                "L1", model.PortRef("A", "p"), model.PortRef("B", "p")
            ),
            model.FunctionalLink(
                "L2", model.PortRef("A", "p"), model.PortRef("C", "p")
            ),
        )
        assert model.validate_structural_diagram(
            model.StructuralDiagram(blocks, ports, links)
        ) == ()
    else:
        pytest.fail(f"Unmapped PR77 visual scenario: {case_id}")


def test_legacy_visual_coverage_exactly_eight_and_no_untested_contract():
    visual_ids = {
        c["id"] for c in previous_32() if c["category"] in DISPLAY_ONLY
    }
    assert visual_ids == {
        "E1-NEG-20", "E1-NEG-21", "E1-NEG-22", "E1-NEG-25",
        "E1-NEG-26", "E1-NEG-27", "E1-NEG-30", "E1-NEG-31",
    }
    assert deepcopy(graphic_source()) == graphic_source()
