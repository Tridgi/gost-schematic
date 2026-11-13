"""Issue #72 independent pinned Draft PR59 form-one FAIL evidence.

This file does NOT assert that old defects are acceptable. It makes legacy
FAILs reproducible without breaking integration CI; the expected corrected
behavior is documented in QA manifest. The SHA-verified file is isolated.
Never import this fixture as the active production renderer.
"""

import json
import shutil
import subprocess
from hashlib import sha1
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.core.geometry import Box
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.annotations import TextStyle

REPO = Path(__file__).resolve().parents[1]
PR59_HEAD = "c42f7b617942c8a0b1cae45e432ef12cede7f876"
FORM_ONE_GIT_BLOB = "9025fefd18ec9e50118d7353f5b2565eb064b5c4"
SOURCE = REPO / "tests/fixtures/qa_form1_pr59_c42f7b_snapshot.txt"
ROLE_NAMES = ("developed", "checked", "tech_control", "norm_control", "approved")
REQUIRED_SERVICE = ("Зона", "Вер.", "Копировал", "Формат")


@pytest.fixture(scope="module")
def form_one():
    raw = SOURCE.read_bytes()
    digest = sha1(
        b"blob " + str(len(raw)).encode() + bytes((0,)) + raw
    ).hexdigest()
    assert digest == FORM_ONE_GIT_BLOB
    name = "gost_schematic.rendering._qa_pr59_c42f7b_form_one"
    spec = spec_from_loader(name, SourceFileLoader(name, str(SOURCE)))
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _font_and_style():
    command = shutil.which("fc-match")
    if command is None:
        pytest.skip("Cannot measure role ink: fontconfig absent")
    font = Path(subprocess.run(
        (command, "-f", "%{file}", "sans-serif"),
        check=True, capture_output=True, text=True,
    ).stdout.strip())
    if not font.is_file():
        pytest.skip("No reproducible fontconfig face")
    measurer = PillowTextMeasurer()
    # Independent FreeType calibration for Cyrillic cap Н = 2500 um.
    rough = 3600
    start = TextStyle(str(font), "sans-serif", em_height_um=rough)
    cap = -measurer.measure("Н", start).ink_box.min_y
    ideal = round(2500 * rough / cap)
    choices = (
        TextStyle(str(font), "sans-serif", em_height_um=em)
        for em in range(ideal - 25, ideal + 26)
    )
    style = min(
        choices,
        key=lambda candidate: abs(
            -measurer.measure("Н", candidate).ink_box.min_y - 2500
        ),
    )
    assert abs(-measurer.measure("Н", style).ink_box.min_y - 2500) <= 30
    return measurer, style


def _render(form_one, fields=None, captions=True):
    measurer, style = _font_and_style()
    parent = ET.Element("svg")
    bounds = Box(0, 0, 185000, 55000)
    form_one.draw_form_one_geometry(parent, bounds)
    # DejaVu Sans is a real measured fallback, NOT the verified OpenGost A.
    # Its longest role "Н. контр." exceeds the 17mm cell at h=2.5mm.
    # Render the other four actual labels for ink-alignment diagnostics.
    # The full-font failure is asserted in a separate fail-closed test below.
    short_roles = {
        key: value for key, value in form_one.CAPTIONS.items()
        if key != "norm_control"
    }
    with patch.object(form_one, "CAPTIONS", short_roles):
        placed = form_one.write_form_one_fields(
            parent, bounds, fields or {}, style, measurer,
            cap_height_um=2500, padding_um=400, captions=captions,
        )
    return parent, placed


def test_normative_merged_pr66_matrix_exact_pin_and_status_counts():
    evidence = json.loads(
        (REPO / "docs/standards/issue-63-form-one-matrix.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["target"]["pinned_code_commit"] == PR59_HEAD
    assert evidence["target"]["form_one_blob_sha"] == FORM_ONE_GIT_BLOB
    entries = evidence["matrix"]
    assert len(entries) == 38
    assert {
        status: sum(item["status"] == status for item in entries)
        for status in ("PASS", "FAIL", "BLOCKED")
    } == {"PASS": 24, "FAIL": 6, "BLOCKED": 8}
    assert {
        item["id"] for item in entries if item["status"] == "FAIL"
    } == {
        "F63-22", "F63-23", "F63-24", "F63-25",
        "F63-26", "F63-27",
    }


def test_pr59_form_one_real_vector_size_17mm_role_column_and_25_lines(
    form_one,
):
    parent = ET.Element("svg")
    form_one.draw_form_one_geometry(
        parent, Box(20000, 237000, 205000, 292000)
    )
    namespace = "{http://www.w3.org/2000/svg}"
    outline = parent.find(f".//{namespace}rect")
    assert outline is not None
    assert outline.attrib["width"] == "185"
    assert outline.attrib["height"] == "55"
    assert len(parent.findall(f".//{namespace}line")) == 25
    for field in ROLE_NAMES:
        cell = form_one.CELLS[field]
        assert (cell.min_x, cell.max_x) == (0, 17000)
        assert cell.max_y - cell.min_y == 5000


def test_pr59_real_freetype_role_ink_is_centered_not_shared_left_x(
    form_one,
):
    _, placed = _render(form_one)
    roles = {entry.key: entry for entry in placed if entry.key in ROLE_NAMES}
    assert set(roles) == set(ROLE_NAMES) - {"norm_control"}
    # Independent ink measurement detects the current center policy.
    lefts = {entry.ink.min_x - entry.cell.min_x for entry in roles.values()}
    assert len(lefts) > 1, "Pinned legacy roles unexpectedly left-aligned"
    assert all(
        abs((entry.ink.min_x + entry.ink.max_x)
            - (entry.cell.min_x + entry.cell.max_x)) <= 1
        for entry in roles.values()
    )
    assert {entry.text for entry in roles.values()} == {
        "Разраб.", "Пров.", "Т. контр.", "Утв."
    }
    assert all(
        entry.ink.max_y - entry.ink.min_y > 2200
        for entry in roles.values()
    )
    # The approved future behavior is common left ink-x with measured inset;
    # this pinned PR59 SHA is independently FAIL for that acceptance criterion.


def test_pr59_role_value_overwrites_caption_in_graph10_not_surname11(
    form_one,
):
    _parent, placed = _render(form_one, {"developed": "Иванов"})
    role = next(entry for entry in placed if entry.key == "developed")
    assert role.text == "Иванов"
    assert (role.cell.min_x, role.cell.max_x) == (0, 17000)
    assert "Разраб." not in {entry.text for entry in placed}
    # The missing cells are an API/geometry defect, not permission to invent
    # actual surname/signature/date for a blank DRAFT.
    keys = set(form_one.CELLS) | set(form_one.CAPTION_CELLS)
    for suffix in ("surname", "signature", "date"):
        assert not any(
            key.startswith("developed_") and suffix in key for key in keys
        )


def test_pr59_service_cells_and_dashed_graph30_are_absent_as_documented(
    form_one,
):
    parent, placed = _render(form_one)
    captions = {entry.text for entry in placed}
    assert not captions.intersection(REQUIRED_SERVICE)
    namespace = "{http://www.w3.org/2000/svg}"
    lines = parent.findall(f".//{namespace}line")
    assert len(lines) == 25
    assert all("stroke-dasharray" not in line.attrib for line in lines)
    # This is FAIL evidence against proposed corrected Annex B.1.
    # Current file is a frozen historic SHA, not production acceptance.


def test_empty_pr59_form_one_does_not_invent_people_or_approval(form_one):
    _parent, placed = _render(form_one, captions=False)
    assert placed == ()


def test_nonapproved_sans_serif_fallback_overflows_long_role_not_autoshrunk(
    form_one,
):
    """Independent UI warning: cap-matched DejaVu ≠ approved OpenGost A."""
    measurer, style = _font_and_style()
    with pytest.raises(ValueError, match="TITLE_FIELD_OVERFLOW: norm_control"):
        form_one.write_form_one_fields(
            ET.Element("svg"), Box(0, 0, 185000, 55000),
            {}, style, measurer, captions=True, cap_height_um=2500,
        )
