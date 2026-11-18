"""Issue 72: independent positive checks of NEW PR59 Issue67 fixed form1 source.

Pin form_one.py from PR59 SHA 71ee7f0c; do not check out PR59 or change
production imports during pytest. Use a deliberately narrow deterministically
measured QA glyph model to isolate positional/field semantics from OpenGost A
font availability. External 1:1 300dpi font approval remains BLOCKED.
"""

from hashlib import sha1
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.core.geometry import Box
from gost_schematic.model.annotations import MeasuredText, TextStyle

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests/fixtures/qa_form1_pr59_71ee7f_snapshot.txt"
PR59_SHA = "71ee7f0c26d2f2f41a67d9e4450aa33d265286fa"
BLOB = "ffa94169439353ab5c35738c5dfae9c7fb6dfe6f"
SVG = "{http://www.w3.org/2000/svg}"
ROLES = (
    "role_developed", "role_checked", "role_tech_control",
    "role_norm_control", "role_approved",
)


class DeterministicNarrowQA:
    """Repeatable contract stub, NOT actual OpenGost measurements or approval."""

    def measure(self, value, style):
        assert value and isinstance(style, TextStyle)
        # Height truly 2.5mm; narrow variation is enough to make margins vary
        # under center alignment but not touch 17mm cells.
        width = 820 * len(value)
        return MeasuredText(Box(0, -2500, width, 0), width)


@pytest.fixture(scope="module")
def fixed_form():
    raw = FIXTURE.read_bytes()
    got = sha1(
        b"blob " + str(len(raw)).encode() + bytes((0,)) + raw
    ).hexdigest()
    assert got == BLOB
    name = "gost_schematic.rendering._qa_pr59_71ee7f_form_one"
    spec = spec_from_loader(name, SourceFileLoader(name, str(FIXTURE)))
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(fixed_form, values=None, headings=True):
    node = ET.Element("svg")
    box = Box(20000, 237000, 205000, 292000)
    fixed_form.draw_form_one_geometry(node, box)
    style = TextStyle("qa-font-not-vendored.ttf", "QA Contract Only", 3500)
    placements = fixed_form.write_form_one_fields(
        node, box, values or {}, style, DeterministicNarrowQA(),
        cap_height_um=2500, padding_um=400, captions=headings,
    )
    return node, box, placements


def test_fixed_form_shape_and_explicit_graph30_dashed_qa(fixed_form):
    parent, _bounds, _places = _run(fixed_form)
    outline = parent.find(f".//{SVG}rect")
    assert outline is not None
    assert (outline.attrib["width"], outline.attrib["height"]) == (
        "185", "55"
    )
    dashed = [
        line for line in parent.findall(f".//{SVG}line")
        if line.get("data-service-graph") == "30"
    ]
    assert len(dashed) == 1
    line = dashed[0]
    assert line.get("stroke-dasharray") == "3 2"
    assert (line.get("x1"), line.get("x2")) == ("85", "195")
    assert line.get("y1") == line.get("y2") == "245"
    assert (fixed_form.CELLS["designation"].min_y,
            fixed_form.CELLS["designation"].max_y) == (8000, 15000)


def test_fixed_role_caps_share_exact_measured_800um_left_inset(fixed_form):
    _parent, _box, placements = _run(fixed_form)
    roles = {entry.key: entry for entry in placements if entry.key in ROLES}
    assert set(roles) == set(ROLES)
    assert fixed_form.ROLE_CAPTION_INSET_UM == 800
    for entry in roles.values():
        assert entry.ink.min_x - entry.cell.min_x == 800
        assert entry.ink.max_x < entry.cell.max_x - 400
        assert entry.ink.min_y - entry.cell.min_y == 1250
        assert entry.cell.max_y - entry.ink.max_y == 1250
        assert entry.cell.max_x - entry.cell.min_x == 17000
    assert [roles[key].text for key in ROLES] == [
        "Разраб.", "Пров.", "Т. контр.", "Н. контр.", "Утв.",
    ]


def test_new_role_surname_sign_date_have_independent_graph_11_12_13_cells(
    fixed_form,
):
    surname = {"developed_surname": "Иванов"}
    page, _, placed = _run(fixed_form, surname, headings=False)
    bykey = {entry.key: entry for entry in placed}
    assert set(ROLES).issubset(bykey)
    assert bykey["developed_surname"].text == "Иванов"
    assert bykey["role_developed"].text == "Разраб."
    assert (bykey["developed_surname"].cell.min_x,
            bykey["developed_surname"].cell.max_x) == (37000, 60000)
    drawn = {
        tag.get("data-graph"): tag
        for tag in page.findall(f".//{SVG}text")
    }
    assert drawn["developed_surname"].get("data-graph-number") == "11"
    assert drawn["role_developed"].get("data-graph-number") == "10"
    for role in (
        "developed", "checked", "tech_control",
        "norm_control", "approved",
    ):
        for part, graph, start, stop in (
            ("surname", "11", 17000, 40000),
            ("signature", "12", 40000, 55000),
            ("date", "13", 55000, 65000),
        ):
            key = f"{role}_{part}"
            cell = fixed_form.CELLS[key]
            assert (cell.min_x, cell.max_x) == (start, stop)
            assert cell.max_y - cell.min_y == 5000
    for role in ROLES:
        assert drawn[role].get("data-ink-align") == "left"


def test_fixed_role_cannot_be_overwritten_by_surname(fixed_form):
    with pytest.raises(ValueError, match="TITLE_ROLE_RESERVED"):
        _run(fixed_form, {"developed": "Иванов"})
    with pytest.raises(ValueError, match="TITLE_FIELD_OVERFLOW"):
        _run(
            fixed_form,
            {"developed_surname": "Иванов" * 12},
            headings=False,
        )


def test_explicit_zone_version_copied_format_graphs_present(fixed_form):
    page, bounds, placed = _run(fixed_form)
    fields = {entry.key: entry for entry in placed}
    assert len(fields) >= 19
    for key, label, number in (
        ("zone_caption", "Зона", "33"),
        ("version_caption", "Вер.", "35"),
        ("copied_caption", "Копировал", "31"),
        ("format_caption", "Формат", "32"),
    ):
        assert fields[key].text == label
        tag = next(
            x for x in page.findall(f".//{SVG}text")
            if x.attrib["data-graph"] == key
        )
        assert tag.attrib["data-graph-number"] == number
    # 31/32 in bottom 5mm page margin, explicitly outside the 185x55 stamp.
    assert fields["copied_caption"].cell.min_y == bounds.max_y
    assert fields["copied_caption"].cell.max_y == bounds.max_y + 5000


def test_blank_new_form_does_not_invent_signers_and_renderer_is_draft(
    fixed_form,
):
    page, _box, values = _run(fixed_form, headings=False)
    assert values == ()
    group = page.find(f".//{SVG}g[@data-layer='title-block-grid']")
    assert group is not None
    assert group.get("data-approval") == "DRAFT_MANUAL_1_TO_1_REVIEW"
    assert all("surname" not in field.key for field in values)
