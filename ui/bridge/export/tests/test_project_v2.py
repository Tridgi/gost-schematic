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
from ui.bridge.export.project_v2 import export_v2, export_v2_svg, render_v2_source

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


def test_duplicate_component_id_cannot_enter_canonical_export():
    document = load()
    document["project"]["components"].append(copy.deepcopy(
        document["project"]["components"][0]
    ))
    with pytest.raises(ContractError, match="DUPLICATE_ID"):
        render_v2_source(document, "sheet-1", expected_project_sha256=digest(document))


def test_second_blank_sheet_does_not_leak_first_sheet_symbols_or_wires():
    """Sheet-local ink must not be replicated when source Nets span sheets."""
    document = load()
    original = document["project"]["sheets"][0]
    second = copy.deepcopy(original)
    second["id"] = "qa-blank-sheet"
    second["index"] = original["index"] + 1
    for name in ("instances", "wires", "junctions", "splices", "texts", "labels", "graphics"):
        second[name] = []
    for layer in second["layers"]:
        layer["id"] = "qa-blank-" + layer["id"]
    document["project"]["sheets"].append(second)
    validate(document)
    svg, warnings = export_v2_svg(
        document, second["id"], ExportRequest(
            page="A3", orientation="landscape", include_frame=False,
            strict_font=False,
        ), expected_project_sha256=digest(document),
    )
    root = ET.fromstring(svg)
    assert root.attrib["width"] == "420mm"
    assert root.attrib["height"] == "297mm"
    assert root.attrib["data-source-net-count"] == "3"
    assert not root.findall(".//" + S + "g[@data-layer='symbols']")
    assert not root.findall(".//" + S + "g[@data-layer='wires']")
    assert warnings == ()


def test_raster_pixel_budget_rejects_600dpi_a3_before_allocating_png():
    document = load()
    with pytest.raises(ExportError, match="PNG exceeds approved pixel budget"):
        export_v2(document, "sheet-1", ExportRequest(
            page="A3", orientation="landscape", dpi=600,
            include_frame=False, strict_font=False,
        ), expected_project_sha256=digest(document))


def test_r32l_visible_refs_values_and_unplaced_export_warning():
    doc = load("tl494-source-e695-v2.gscad.json")
    original = copy.deepcopy(doc)
    req = ExportRequest(include_frame=False, strict_font=False)
    svg, warnings = export_v2_svg(doc, "sheet-1", req,
                                  expected_project_sha256=digest(doc))
    root = ET.fromstring(svg)
    placed = int(root.get("data-component-label-count"))
    missing = int(root.get("data-unplaced-label-count"))
    assert placed + missing == 23
    assert len(root.findall(".//" + S + "text[@data-label-role='reference']")) == placed
    assert not root.findall(".//" + S + "text[@data-label-role='value']")
    assert "FONT_RENDER_UNVERIFIED" in warnings
    assert doc == original
    assert export_v2_svg(doc, "sheet-1", req, expected_project_sha256=digest(doc))[0] == svg

    doc["project"]["components"][0]["value"] = '10 < 20 & "V"'
    svg, _ = export_v2_svg(doc, "sheet-1", req, expected_project_sha256=digest(doc))
    texts = ET.fromstring(svg).findall(".//" + S + "text[@data-label-role='value']")
    assert [t.text for t in texts] == ['10 < 20 & "V"']

    doc["project"]["components"][0]["value"] = "x"*65
    svg, warnings = export_v2_svg(doc, "sheet-1", req,
                                  expected_project_sha256=digest(doc))
    assert "COMPONENT_LABELS_UNPLACED" in warnings
    metadata = ET.fromstring(svg).find(".//" + S + "metadata[@data-kind='unplaced-component-labels']")
    assert any(item["refdes"] == "C1" and item["reason"] == "LABEL_TEXT_UNSUPPORTED"
               for item in json.loads(metadata.text))


def _annotation_only_document(rotation):
    doc = load()
    sheet = copy.deepcopy(doc["project"]["sheets"][0])
    sheet["id"] = "qa-rotated-annotation"
    sheet["index"] += 1
    for name in ("instances", "wires", "junctions", "splices", "texts", "labels", "graphics"):
        sheet[name] = []
    for layer in sheet["layers"]:
        layer["id"] = "qa-annotation-" + layer["id"]
    layer = {"id": "qa-annotation-text-layer", "name": "Text", "kind": "annotation",
             "visible": True, "printable": True, "locked": False}
    sheet["layers"].append(layer)
    sheet["texts"].append({"id": "qa-text", "layer_id": layer["id"], "text": "MMMMMM",
                           "at_um": [120125, 120500], "height_um": 5000,
                           "rotation_deg": rotation})
    doc["project"]["sheets"].append(sheet)
    return validate(doc), sheet["id"]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_r49_annotation_rotation_svg_and_physical_bounds(rotation):
    doc, sheet_id = _annotation_only_document(rotation)
    original = copy.deepcopy(doc)
    source = render_v2_source(doc, sheet_id, expected_project_sha256=digest(doc))
    root = ET.fromstring(source)
    t = root.find(".//" + S + "text[@data-id='qa-text']")
    assert t.text == "MMMMMM"
    assert (t.get("x"), t.get("y"), t.get("font-size")) == ("120.125", "120.5", "5")
    expected = f"rotate({rotation} 120.125 120.5)" if rotation else None
    assert t.get("transform") == expected
    assert root.get("viewBox") == {
        0: "115.125 110.5 40 15",
        90: "115.125 115.5 15 40",
        180: "85.125 115.5 40 15",
        270: "110.125 85.5 15 40",
    }[rotation]
    clean, warnings = export_v2_svg(doc, sheet_id, ExportRequest(
        include_frame=False, include_title=False, strict_font=False),
        expected_project_sha256=digest(doc))
    assert ET.fromstring(clean).find(".//" + S + "text[@data-id='qa-text']").get("transform") == expected
    assert "FONT_RENDER_UNVERIFIED" in warnings
    assert doc == original


@pytest.mark.parametrize("bad", ["translate(1 2)", "rotate(45 120.125 120.5)",
                                  "rotate(90 120 120.5)", "rotate(90 120.125 120.5) scale(2)"])
def test_r49_annotation_transform_rejects_noncanonical_values(bad):
    doc, sheet_id = _annotation_only_document(90)
    root = ET.fromstring(render_v2_source(doc, sheet_id, expected_project_sha256=digest(doc)))
    root.find(".//" + S + "text[@data-id='qa-text']").set("transform", bad)
    with pytest.raises(ExportError, match="UNAPPROVED_ANNOTATION_TRANSFORM"):
        compose_clean_svg(ET.tostring(root), ExportRequest(include_frame=False, strict_font=False))


def test_r49_rotated_annotation_png_ink_changes_orientation():
    boxes = []
    for rotation in (0, 90):
        doc, sheet_id = _annotation_only_document(rotation)
        result = export_v2(doc, sheet_id, ExportRequest(
            include_frame=False, include_title=False, strict_font=False),
            expected_project_sha256=digest(doc))
        with Image.open(io.BytesIO(result.png)) as image:
            assert image.size == (4961, 3508)
            # Contrast threshold, independent of exact font family/antialiasing.
            mask = image.convert("RGB").convert("L").point(lambda p: 255 if p < 128 else 0)
            box = mask.getbbox()
            assert box is not None
            boxes.append((box[2]-box[0], box[3]-box[1]))
    assert boxes[0][0] > boxes[0][1] * 2
    assert boxes[1][1] > boxes[1][0] * 2


@pytest.mark.parametrize("kind", ["line", "rect", "circle", "g"])
def test_r50_annotation_rotation_cannot_authorize_shape_transform(kind):
    doc, sheet_id = _annotation_only_document(90)
    root = ET.fromstring(render_v2_source(doc, sheet_id, expected_project_sha256=digest(doc)))
    ET.SubElement(root, S + kind, {
        "data-layer": "annotations", "data-id": "qa-invalid-shape",
        "x": "120.125", "y": "120.5", "transform": "rotate(90 120.125 120.5)",
    })
    with pytest.raises(ExportError, match="UNAPPROVED_ANNOTATION_TRANSFORM"):
        compose_clean_svg(ET.tostring(root), ExportRequest(include_frame=False, strict_font=False))


def test_r50_rotated_annotation_rejects_one_micrometre_viewbox_clipping():
    doc, sheet_id = _annotation_only_document(90)
    root = ET.fromstring(render_v2_source(doc, sheet_id, expected_project_sha256=digest(doc)))
    assert root.get("viewBox") == "115.125 115.5 15 40"
    root.set("viewBox", "115.125 115.5 15 39.999")
    root.set("height", "39.999mm")
    with pytest.raises(ExportError, match="SOURCE_VIEWBOX_CLIPS_INK"):
        compose_clean_svg(ET.tostring(root), ExportRequest(include_frame=False, strict_font=False))


@pytest.mark.parametrize("value,rotation,viewbox,clipped_width", [
    ("A\U0001f680Б", 0, "115.125 110.5 25 15", "24.999"),
    ("A\U0001f680Б", 90, "115.125 115.5 15 25", "14.999"),
    ("A\U0001f680Б", 180, "100.125 115.5 25 15", "24.999"),
    ("A\U0001f680Б", 270, "110.125 100.5 15 25", "14.999"),
    ("e\u0301", 0, "115.125 110.5 20 15", "19.999"),
    ("e\u0301", 90, "115.125 115.5 15 20", "14.999"),
    ("e\u0301", 180, "105.125 115.5 20 15", "19.999"),
    ("e\u0301", 270, "110.125 105.5 15 20", "14.999"),
])
def test_r58_unicode_annotation_exact_envelope_and_one_micrometre_clip(
        value, rotation, viewbox, clipped_width):
    doc, sheet_id = _annotation_only_document(rotation)
    doc["project"]["sheets"][-1]["texts"][0]["text"] = value
    original = copy.deepcopy(doc)
    source = render_v2_source(doc, sheet_id, expected_project_sha256=digest(doc))
    root = ET.fromstring(source)
    assert root.get("viewBox") == viewbox
    item = root.find(".//" + S + "text[@data-id='qa-text']")
    assert item.text == value
    assert item.get("transform") == (
        f"rotate({rotation} 120.125 120.5)" if rotation else None
    )
    request = ExportRequest(include_frame=False, include_title=False, strict_font=False)
    clean, warnings = compose_clean_svg(source, request)
    assert ET.fromstring(clean).find(".//" + S + "text[@data-id='qa-text']").text == value
    assert "FONT_RENDER_UNVERIFIED" in warnings
    # Change only the physical viewport, not the text, anchor or rotation.
    # Width and viewBox agree, so rejection must come from the ink guard.
    x, y, _, h = viewbox.split()
    root.set("viewBox", f"{x} {y} {clipped_width} {h}")
    root.set("width", clipped_width + "mm")
    with pytest.raises(ExportError, match="SOURCE_VIEWBOX_CLIPS_INK"):
        compose_clean_svg(ET.tostring(root, encoding="utf-8"), request)
    assert doc == original
