"""Issue #69 ESKD E1: independent documentary and geometrical test gates.

This is NOT a production renderer test. The 7-block SVG is explicitly DRAFT:
font is not metric-certified and its dimensions are editorial examples.
"""

import json
from itertools import combinations
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "docs" / "standards" / "issue-69-e1-rule-cards.json"
EXAMPLE = ROOT / "docs" / "standards" / "issue-69-e1-example.json"
SVG = ROOT / "docs" / "standards" / "evidence" / "issue69-seven-block-e1.svg"
REPORT = ROOT / "docs" / "standards" / "issue-69-e1-structural-review.md"
NS = "{http://www.w3.org/2000/svg}"


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _card(id_):
    return next(item for item in _json(RULES)["cards"] if item["id"] == id_)


def _inside_side(bbox, xy, side):
    x, y, width, height = bbox
    px, py = xy
    return {
        "left": px == x and y <= py <= y + height,
        "right": px == x + width and y <= py <= y + height,
        "top": py == y and x <= px <= x + width,
        "bottom": py == y + height and x <= px <= x + width,
    }[side]


def _segments(links):
    return [
        (link["id"], a, b)
        for link in links
        for a, b in zip(link["route"], link["route"][1:], strict=False)
    ]


def _crossings(links):
    """All orthogonal H/V intersections; return point and incident link IDs."""
    out = set()
    for (i, a, b), (j, c, d) in combinations(_segments(links), 2):
        if i == j:
            continue
        ah, bh = a[1] == b[1], c[1] == d[1]
        if ah == bh:
            continue
        horizontal, vertical = ((a, b), (c, d)) if ah else ((c, d), (a, b))
        (ha, hb), (va, vb) = horizontal, vertical
        point = (va[0], ha[1])
        if (
            min(ha[0], hb[0]) <= point[0] <= max(ha[0], hb[0])
            and min(va[1], vb[1]) <= point[1] <= max(va[1], vb[1])
        ):
            out.add((i, j, point))
    return out


def _unjoined_crossings(links):
    intersections = set()
    for a, b, point in _crossings(links):
        segment_for_a = [
            (p, q) for name, p, q in _segments(links) if name == a
        ]
        segment_for_b = [
            (p, q) for name, p, q in _segments(links) if name == b
        ]
        if any(tuple(p) == point or tuple(q) == point for p, q in segment_for_a):
            continue
        if any(tuple(p) == point or tuple(q) == point for p, q in segment_for_b):
            continue
        intersections.add((frozenset((a, b)), point))
    return intersections


def _min_ink_clearance_between_parallel(first, second, width):
    """Only positive longitudinal overlap; a point-touch does not create lanes."""
    a, b = first
    c, d = second
    h1, h2 = a[1] == b[1], c[1] == d[1]
    if h1 != h2:
        return None
    if h1:
        overlap = min(max(a[0], b[0]), max(c[0], d[0])) - max(
            min(a[0], b[0]), min(c[0], d[0])
        )
        offset = abs(a[1] - c[1])
    else:
        overlap = min(max(a[1], b[1]), max(c[1], d[1])) - max(
            min(a[1], b[1]), min(c[1], d[1])
        )
        offset = abs(a[0] - c[0])
    if overlap <= 0:
        return None
    return offset - width


def _validate_ink_clearance(links, width):
    if not 0.2 <= width <= 1.0:
        raise ValueError("E1_STROKE_WIDTH_OUTSIDE_GOST")
    for first, second in combinations(_segments(links), 2):
        if first[0] == second[0]:
            continue
        clearance = _min_ink_clearance_between_parallel(
            (first[1], first[2]), (second[1], second[2]), width
        )
        if clearance is not None and clearance < 3.0:
            raise ValueError("E1_PARALLEL_LINK_INK_GAP")


def test_42_cards_have_distinct_force_and_nonhardened_editor_default():
    data = _json(RULES)
    assert data["issue"] == 69
    assert data["document_type"] == "Э1"
    assert data["branch"] == "parallel/standards-structural-e1"
    assert data["approval"] == "DRAFT_NOT_FORMALLY_APPROVED"
    assert data["baseline_sha"] == "e2b280d91957ff678c90b792e2c94fa9e73e27ae"
    cards = data["cards"]
    assert len(cards) == 42
    assert len({c["id"] for c in cards}) == len(cards)
    for c in cards:
        assert c["source_standard"] in data["standards"]
        assert c["source_clause"]
        assert c["normative_force"] in {
            "MUST", "MUST_QUALITATIVE", "MUST_WITH_EXCEPTION", "MUST_FOR_UGO",
            "RECOMMENDED", "PERMITTED_ALTERNATIVES", "OPTIONAL",
            "CONDITIONAL_MUST", "CONDITIONAL_ALLOWED", "NOT_SPECIFIED",
            "EDITORIAL_DEFAULT", "EDITORIAL_SAFETY", "EDITORIAL_SEMANTICS",
        }
        assert c["positive_case"] and c["negative_case"] and c["owner"]
        assert c["status"] == "DRAFT_FOR_IMPLEMENTATION"
    assert data["source_policy"]["secondary_is_normative"] is False
    assert "habr.com" not in " ".join(
        str(data["standards"][c["source_standard"]])
        for c in cards
    )
    assert all(item["status"] == "Действует" for item in data["standards"].values())


def test_ports_centre_are_editorial_not_gost_and_no_fixed_port_count():
    for key in ("E1-13", "E1-14", "E1-15"):
        c = _card(key)
        assert c["normative_force"] == "EDITORIAL_DEFAULT"
        assert c["evidence"] in {"explicit_absence", "not_specified"}
    assert _card("E1-16")["normative_force"] == "NOT_SPECIFIED"
    assert _card("E1-39")["normative_force"] == "NOT_SPECIFIED"
    src = _json(RULES)["editor_defaults"]
    assert src["single_port"].startswith("midpoint")
    assert "not ГОСТ" in src["single_port"]
    assert src["avoid_physical_pin_refs"] is True


def test_mandatory_block_names_arrows_are_recommendations():
    assert _card("E1-05")["normative_force"] == "MUST"
    assert _card("E1-06")["normative_force"] == "RECOMMENDED"
    assert _card("E1-11")["normative_force"] == "RECOMMENDED"
    assert _card("E1-08")["normative_force"] == "CONDITIONAL_MUST"
    assert _card("E1-20")["dimensions_mm"]["min"] == 0.2
    assert _card("E1-20")["dimensions_mm"]["max"] == 1.0
    assert _card("E1-21")["dimensions_mm"]["recommended_min"] == 0.3
    assert _card("E1-25")["dimensions_mm"]["ink_clearance_min"] == 3.0
    assert _card("E1-24")["dimensions_mm"]["min"] == 2
    assert _card("E1-26")["dimensions_mm"]["min"] == 1
    assert _card("E1-27")["dimensions_mm"]["project_default_cap_height"] == 3.5
    assert _card("E1-28")["dimensions_mm"]["project_padding"] == 2


def test_rectangles_svg_names_and_separate_ugo_font_approval():
    doc = _json(EXAMPLE)
    root = ET.parse(SVG).getroot()
    assert doc["status"] == "DRAFT_ILLUSTRATION_NOT_APPROVED"
    assert doc["document_type"] == "Э1"
    assert doc["not_paper_sheet"] is True
    assert doc["diagram_mm"] == [240, 175]
    assert root.attrib["width"] == "240mm"
    assert root.attrib["height"] == "175mm"
    assert root.attrib["viewBox"] == "0 0 240 175"
    assert root.attrib["data-document-type"] == "Э1"
    assert root.attrib["data-approval-status"] == "DRAFT"
    assert root.attrib["data-font-compliance"] == "UNVERIFIED"
    assert root.attrib["data-physical-netlist"] == "none"
    assert len(doc["rectangles"]) == 7
    rects = {
        e.attrib["data-block-id"]: e
        for e in root.iter(f"{NS}rect")
        if e.get("data-kind") == "functional-rectangle"
    }
    labels = {
        e.attrib["data-block-label"]: "".join(e.itertext()).strip()
        for e in root.iter(f"{NS}text")
        if e.get("data-block-label")
    }
    assert set(rects) == set(labels) == {node["id"] for node in doc["rectangles"]}
    for node in doc["rectangles"]:
        assert node["name"].replace(" ", "") in labels[node["id"]].replace(" ", "")
        r = rects[node["id"]]
        x, y, w, h = node["bbox"]
        assert tuple(float(r.get(k)) for k in ("x", "y", "width", "height")) == (
            x, y, w, h,
        )
        assert w > 0 and h > 0
    assert not root.findall(f".//{NS}g[@data-layer='electrical-nets']")


def test_nine_svg_paths_preserve_exact_authored_directed_graph():
    d = _json(EXAMPLE)
    root = ET.parse(SVG).getroot()
    polylines = {
        p.attrib["data-link-id"]: p
        for p in root.iter(f"{NS}polyline")
        if p.get("data-link-id")
    }
    assert len(d["links"]) == len(polylines) == 9
    assert len({l["id"] for l in d["links"]}) == 9
    by_node = {n["id"]: n for n in d["rectangles"]}
    for link in d["links"]:
        line = polylines[link["id"]]
        assert line.get("marker-end") == "url(#process-arrow)"
        assert line.get("data-role") == "logical-process"
        assert line.get("data-source-block") == link["source"]
        assert line.get("data-target-block") == link["target"]
        actual = [
            list(map(float, p.split(","))) for p in line.get("points").split()
        ]
        assert actual == link["route"]
        assert link["source"] in by_node and link["target"] in by_node
        assert _inside_side(by_node[link["target"]]["bbox"], link["route"][-1],
                            link["target_side"])
        if "branch_from" not in link:
            assert _inside_side(by_node[link["source"]]["bbox"], link["route"][0],
                                link["source_side"])
        for a, b in zip(link["route"], link["route"][1:], strict=False):
            assert (a[0] == b[0]) != (a[1] == b[1])


def test_crossings_are_exact_two_unjoined_and_one_explicit_branch():
    d = _json(EXAMPLE)
    expected = {
        (frozenset(c["link_ids"]), tuple(c["at"]))
        for c in d["unconnected_geometrical_crossings"]
    }
    assert expected == {
        (frozenset(("L1", "L8")), (84, 27)),
        (frozenset(("L6", "L9")), (112, 115)),
    }
    assert _unjoined_crossings(d["links"]) == expected
    branch = d["explicit_logical_branches"]
    assert len(branch) == 1
    assert branch[0]["id"] == "P1"
    assert branch[0]["at"] == [72, 80]
    assert branch[0]["not_physical_junction"] is True
    assert branch[0]["marker_project_defined"] is True
    assert branch[0]["targets"] == ["B4", "B7"]
    assert any(
        {x, y} == {"L2", "L9"} and tuple(xy) == (72, 80)
        for x, y, xy in _crossings(d["links"])
    )
    circles = [
        el for el in ET.parse(SVG).getroot().iter(f"{NS}circle")
        if el.get("data-kind") == "editorial-logical-branch"
    ]
    assert len(circles) == 1
    assert [float(circles[0].get(k)) for k in ("cx", "cy", "r")] == [
        72, 80, 0.5,
    ]
    assert not any(
        (float(c.get("cx")), float(c.get("cy"))) in {(84, 27), (112, 115)}
        for c in circles
    )


def test_real_line_ink_clearance_and_separate_block_clearance():
    d = _json(EXAMPLE)
    assert d["stroke_mm"] == 0.35
    _validate_ink_clearance(d["links"], 0.35)
    nodes = d["rectangles"]
    for n, m in combinations(nodes, 2):
        x, y, w, h = n["bbox"]
        a, b, c, e = m["bbox"]
        dx = max(a - (x + w), x - (a + c), 0)
        dy = max(b - (y + h), y - (b + e), 0)
        assert dx >= 2 or dy >= 2
    multi = d["multi_port_examples"]
    assert len(multi) == 2
    assert multi[0]["block"] == "B2"
    assert multi[0]["centerline_spacing_mm"] == 5
    assert multi[0]["actual_ink_clearance_mm"] == 4.65


@pytest.mark.parametrize("width", (0.15, 1.2))
def test_negative_invalid_stroke_is_hard_fail(width):
    with pytest.raises(ValueError, match="STROKE_WIDTH_OUTSIDE_GOST"):
        _validate_ink_clearance(_json(EXAMPLE)["links"], width)


def test_negative_3mm_axis_is_not_3mm_real_ink_clearance():
    assert _min_ink_clearance_between_parallel(
        ((64, 75), (84, 75)), ((64, 78), (91, 78)), 0.35
    ) == pytest.approx(2.65)
    damaged = _json(EXAMPLE)["links"]
    for link in damaged:
        if link["id"] == "L2":
            link["route"] = [[64, 78], [91, 78]]
    with pytest.raises(ValueError, match="PARALLEL_LINK_INK_GAP"):
        _validate_ink_clearance(damaged, 0.35)


def test_negative_conflating_x_and_branch_is_rejected_in_semantic_review():
    d = _json(EXAMPLE)
    unconnected = {
        tuple(x["at"]) for x in d["unconnected_geometrical_crossings"]
    }
    authored_branch_points = {
        tuple(x["at"]) for x in d["explicit_logical_branches"]
    }
    assert authored_branch_points.isdisjoint(unconnected)
    wrong = authored_branch_points | {(84, 27)}
    assert not wrong.isdisjoint(unconnected)
    assert _card("E1-34")["normative_force"] == "EDITORIAL_SEMANTICS"
    assert _card("E1-35")["normative_force"] == "EDITORIAL_SEMANTICS"


def test_negative_missing_name_and_incorrect_multiport_centre_are_not_gost():
    blocks = _json(EXAMPLE)["rectangles"]
    assert all(block["name"] for block in blocks)
    corrupted = [dict(block) for block in blocks]
    corrupted[3]["name"] = ""
    assert not all(block["name"] for block in corrupted)
    assert _card("E1-05")["normative_force"] == "MUST"
    assert _card("E1-13")["normative_force"] == "EDITORIAL_DEFAULT"
    assert _card("E1-14")["normative_force"] == "EDITORIAL_DEFAULT"


def test_negative_unsafe_code_claims_not_source_backed():
    data = _json(RULES)
    assert "Э1" == data["document_type"]
    c = {rule["id"]: rule for rule in data["cards"]}
    assert c["E1-08"]["normative_force"] == "CONDITIONAL_MUST"
    assert "таблиц" in c["E1-08"]["rule"]
    assert c["E1-23"]["normative_force"] == "CONDITIONAL_MUST"
    assert c["E1-36"]["normative_force"] == "EDITORIAL_SAFETY"
    assert "semantic functional blocks" in c["E1-37"]["rule"]


def test_document_gives_named_primary_sources_and_no_fake_approved():
    t = REPORT.read_text(encoding="utf-8")
    for phrase in (
        "ГОСТ 2.702-2011", "ГОСТ 2.701-2008",
        "ГОСТ 2.304-81", "ГОСТ 2.721-74", "Habr",
        "5.1.1", "5.1.2", "5.1.3", "5.1.4", "5.1.5",
        "Э1", "42", "семь прямоугольников", "девять функциональных связей", "0.35",
        "3.35", "5 мм", "84,27", "112,115",
        "ELEKTRIK", "YGO 2", "DRAFT", "рекомендуется",
    ):
        assert phrase.casefold() in t.casefold()
    assert "ГОСТ 2.702" not in _json(EXAMPLE)["font_note"]
