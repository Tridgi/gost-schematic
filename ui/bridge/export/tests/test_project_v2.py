"""Integration tests for real ProjectFileV2 fixtures in #122 and PNG300 in #124.

Run explicitly: python -m pytest -q ui/bridge/export/tests
"""
import copy
import hashlib
import io
import json
import struct
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from ui.bridge.export.canonical import ExportError, ExportRequest, compose_clean_svg
from ui.bridge.export.project_v2 import export_v2, render_v2_source
from ui.editor.src.model.contract import ContractError, digest, validate

ROOT = Path(__file__).resolve().parents[4]
FIX = ROOT / "ui" / "fixtures"
S = "{http://www.w3.org/2000/svg}"


def load(name="tl494-subset-e695-v2.gscad.json"):
    doc = json.loads((FIX / name).read_text(encoding="utf-8"))
    return validate(doc)


def test_read_real_source_and_keep_16_physical_pins():
    document = load()
    source = render_v2_source(document, "sheet-1",
                              expected_project_sha256=digest(document))
    root = ET.fromstring(source)
    assert root.attrib["data-source-model"] == "gscad-project-v2"
    assert root.attrib["data-source-net-count"] == "3"
    assert root.attrib["data-authored-wire-count"] == "0"
    da1 = root.find(".//" + S + "g[@data-reference='DA1']")
    assert da1 is not None
    assert len(json.loads(da1.attrib["data-pinrefs"])) == 16
    assert not root.findall(".//" + S + "circle")
    assert not root.findall(".//" + S + "g[@data-layer='geometry-review']")


def test_graphic_only_b_and_micrometre_not_conductor():
    document = load()
    graphic = document["project"]["sheets"][0]["graphics"][0]
    graphic["points_um"][1][0] += 1
    # Graphic placement may change without changing physical source Net inventory.
    source = render_v2_source(document, "sheet-1",
                              expected_project_sha256=digest(document))
    root = ET.fromstring(source)
    b = root.find(".//" + S + "g[@data-id='source-b-graphic-1']")
    assert b is not None and b.attrib["data-electrical"] == "false"
    assert b.find(S + "line").get("x2") == "7.001"
    assert not b.findall(".//*[@data-net]")
    assert len(root.findall(".//" + S + "g[@data-kind='source_b_continuation']")) == 2


def test_svg_absolute_sheet_coordinates_no_auto_recentering():
    doc = load()
    source = render_v2_source(doc, "sheet-1", expected_project_sha256=digest(doc))
    clean, warnings = compose_clean_svg(source, ExportRequest(
        page="A3", orientation="landscape", page_coords=True,
        include_frame=False, strict_font=False
    ))
    root = ET.fromstring(clean)
    assert root.attrib["viewBox"] == "0 0 420 297"
    content = root.find(".//" + S + "g[@data-layer='schematic-content']")
    assert content.get("transform") == "translate(0 0)"
    b = root.find(".//" + S + "g[@data-id='source-b-graphic-1']")
    assert b.find(S + "line").attrib["x1"] == "5"
    assert warnings == ("FONT_RENDER_UNVERIFIED",)


def test_real_png_300dpi_same_svg_and_repeatability():
    doc = load()
    sha = digest(doc)
    req = ExportRequest(page="A3", orientation="landscape",
                        include_frame=False, strict_font=False)
    a = export_v2(doc, "sheet-1", req, expected_project_sha256=sha)
    b = export_v2(doc, "sheet-1", req, expected_project_sha256=sha)
    assert a.svg == b.svg and a.png == b.png
    assert a.size_um == (420000,297000)
    assert a.pixels == (4961,3508)
    assert a.svg_sha256 == hashlib.sha256(a.svg).hexdigest()
    assert ET.fromstring(a.svg).attrib["data-source-project-sha256"] == sha
    with Image.open(io.BytesIO(a.png)) as image:
        assert image.size == (4961,3508)
        assert image.info["dpi"] == pytest.approx((300,300), abs=0.02)
    offset = a.png.index(b"pHYs")
    assert struct.unpack(">IIB",a.png[offset+4:offset+13]) == (11811,11811,1)


def test_strict_font_rejects_unverified_b_not_silent_fallback():
    doc = load()
    req = ExportRequest(include_frame=False, strict_font=True)
    with pytest.raises(ExportError,match="FONT_NOT_OUTLINED"):
        export_v2(doc,"sheet-1",req,expected_project_sha256=digest(doc))


def test_stale_hash_and_unsafe_source_fails_closed():
    doc = load()
    with pytest.raises(ExportError,match="SOURCE_SHA_CONFLICT"):
        render_v2_source(doc,"sheet-1",expected_project_sha256="0"*64)
    with pytest.raises(ExportError,match="UNKNOWN_SHEET"):
        render_v2_source(doc,"missing",expected_project_sha256=digest(doc))
    with pytest.raises(ExportError,match="Page coordinates"):
        ExportRequest(page_coords=True,offset_um=(1000,0))
    doc2 = copy.deepcopy(doc)
    doc2["project"]["sheets"][0]["graphics"][0]["kind"] = "wire"
    with pytest.raises(ContractError):
        render_v2_source(doc2,"sheet-1",expected_project_sha256=digest(doc))


def test_full_e695_is_unrouted_23_15_62_16_two_b():
    doc = load("tl494-source-e695-v2.gscad.json")
    project = doc["project"]
    assert len(project["components"]) == 23
    assert len(project["nets"]) == 15
    assert sum(len(n["members"]) for n in project["nets"]) == 62
    assert all(len(s["wires"]) == 0 for s in project["sheets"])
    source = render_v2_source(doc,project["sheets"][0]["id"],
                              expected_project_sha256=digest(doc))
    root = ET.fromstring(source)
    assert root.attrib["data-source-net-count"] == "15"
    assert root.attrib["data-authored-wire-count"] == "0"
    assert len(root.findall(".//" + S + "g[@data-kind='source_b_continuation']")) == 2
