"""Integration tests for real ProjectFileV2 fixtures in #122 and PNG300 in #124.

Run explicitly: python -m pytest -q ui/bridge/export/tests
"""
import copy
import hashlib
import importlib
import io
import json
import struct
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from ui.bridge.export.canonical import ExportError, ExportRequest, compose_clean_svg
from ui.bridge.export.project_v2 import export_v2, render_v2_source

_model = importlib.import_module("ui.editor.src.model.contract")
ContractError, digest, validate = _model.ContractError, _model.digest, _model.validate

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


def test_v2_sheet_rejects_mismatched_export_paper():
    """An A3 project cannot be silently scaled into A4 or rotated paper."""
    doc = load()
    sha = digest(doc)
    for page, orientation in (("A4", "portrait"), ("A2", "landscape"),
                              ("A3", "portrait")):
        req = ExportRequest(page=page, orientation=orientation,
                            strict_font=False, include_frame=False)
        with pytest.raises(ExportError, match="SHEET_PAGE_SIZE_MISMATCH"):
            export_v2(doc, "sheet-1", req, expected_project_sha256=sha)


def _make_authored_wire(document, wire_id, net_name, endpoints, bend_points):
    """Fixture helper uses true manufacturer PinRef IDs, never guessed labels."""
    project = document["project"]
    component_ids = {c["source_refdes"]: c["id"] for c in project["components"]}
    net = next(n for n in project["nets"] if n["name"] == net_name)
    coordinates = [endpoints[0][2], *bend_points, endpoints[1][2]]
    vertices = []
    for i, coords in enumerate(coordinates):
        anchor = {"kind": "bend"}
        if i == 0 or i == len(coordinates) - 1:
            ref, pin, _ = endpoints[0] if i == 0 else endpoints[1]
            anchor = {"kind": "pin", "component_id": component_ids[ref],
                      "physical_pin_number": pin}
        vertices.append({"id": f"{wire_id}-vertex-{i}", "at_um": list(coords),
                         "anchor": anchor})
    segments = [
        {"id": f"{wire_id}-segment-{i}",
         "from_vertex_id": vertices[i]["id"],
         "to_vertex_id": vertices[i+1]["id"]}
        for i in range(len(vertices) - 1)
    ]
    return {"id": wire_id, "net_id": net["id"], "layer_id": "layer-electric",
            "vertices": vertices, "segments": segments,
            "mode": "orthogonal", "needs_routing_review": True}


def _two_crossing_nets():
    document = load()
    sheet = document["project"]["sheets"][0]
    # True placed pin coordinates from the v2 fixture. At (260,130) mm
    # COMMON passes through a_INPUT_PLUS, but no junction is authored.
    sheet["wires"].append(_make_authored_wire(
        document, "authored-plus", "a_INPUT_PLUS",
        [("X1", "1", (146000, 186000)), ("L1", "1", (350000, 130000))],
        [(200000, 186000), (200000, 130000)]
    ))
    sheet["wires"].append(_make_authored_wire(
        document, "authored-common", "COMMON",
        [("X1", "2", (166000, 186000)), ("DA1", "7", (284000, 256000))],
        [(166000, 110000), (260000, 110000),
         (260000, 256000)]
    ))
    return document


def test_real_authored_project_v2_wire_geometry_preserves_net_pinrefs():
    document = _two_crossing_nets()
    validate(document)
    sha = digest(document)
    xml = ET.fromstring(render_v2_source(
        document, "sheet-1", expected_project_sha256=sha))
    assert xml.get("data-authored-wire-count") == "2"
    groups = xml.findall(".//" + S + "g[@data-layer='wires']")
    assert len(groups) == 2
    assert {g.get("data-net") for g in groups} == {"a_INPUT_PLUS", "COMMON"}
    assert sum(len(g.findall(S + "line")) for g in groups) == 7
    assert all(len(json.loads(g.get("data-pinrefs"))) == 2 for g in groups)
    # Physical X crossing (260,130) is NOT an authored junction.
    assert not xml.findall(".//" + S + "circle")
    assert not xml.findall(".//*[@data-net='b']")
    # Real signed source Net names and physical PinRef remain distinct.
    assert groups[0].get("data-net-id") != groups[1].get("data-net-id")


def test_real_cross_net_junction_is_fatal_not_a_printed_false_dot():
    doc = _two_crossing_nets()
    sheet = doc["project"]["sheets"][0]
    plus = next(n for n in doc["project"]["nets"] if n["name"] == "a_INPUT_PLUS")
    sheet["junctions"].append({
        "id": "invalid-cross-net-dot",
        "net_id": plus["id"],
        "at_um": [260000,130000],
        "layer_id": "layer-electric",
    })
    with pytest.raises(ContractError, match="JUNCTION_CROSSES_FOREIGN_NET"):
        render_v2_source(doc, "sheet-1", expected_project_sha256="0" * 64)
