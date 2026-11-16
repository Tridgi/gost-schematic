"""R1 clean export bridge: positive and negative exact-geometry tests."""

import hashlib
import struct
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from ui.bridge.export.canonical import (
    ExportError,
    ExportRequest,
    compose_clean_svg,
    export,
    mm,
    pixels,
)

SVG = "{http://www.w3.org/2000/svg}"


def engine_svg(*, with_text: bool = False, review: bool = False) -> bytes:
    """Mimics the *output* of the current Python engine, not an editor screenshot."""
    text = ('<text x="20" y="10" font-family="OpenGost Type A" '
            'font-size="3.5" data-font-sha256="' + 'a' * 64 + '">R1</text>') if with_text else ""
    diagnostics = ('<g data-layer="geometry-review"><circle cx="50" cy="10" '
                   'r="0.5" fill="#00ff00"/></g>') if review else ""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="80mm" height="40mm" '
        'viewBox="10 5 80 40" data-approval-status="DRAFT">'
        '<g data-layer="symbols" stroke="#000000" fill="none" stroke-width="0.3">'
        '<rect x="20" y="15" width="14" height="4" data-reference="R1"/></g>'
        '<g data-layer="wires" stroke="#000000" stroke-width="0.3">'
        '<line x1="34" y1="17" x2="60" y2="17" data-net="Net_A"/>'
        '<line x1="55" y1="10" x2="55" y2="30" data-net="Net_B"/></g>'
        '<g data-layer="explicit-junctions" fill="#000000"/>'
        '<g data-layer="graphics" stroke="#000000" stroke-width="0.3">'
        '<line x1="61.001" y1="30" x2="70" y2="30" data-electrical="false" '
        'data-id="b-X2"/></g>' + diagnostics + text + '</svg>'
    ).encode()


def test_exact_mm_and_page_dpi():
    assert mm(1) == "0.001"
    assert mm(-1) == "-0.001"
    for page, expected in (("A4", (2480, 3508)), ("A3", (4961, 3508)),
                           ("A2", (7016, 4961))):
        req = ExportRequest(page=page, orientation=("portrait" if page == "A4" else
                                                   "landscape"))
        svg, warnings = compose_clean_svg(engine_svg(), req)
        root = ET.fromstring(svg)
        expected_w_um = {"A4": 210000, "A3": 420000, "A2": 594000}[page]
        expected_h_um = {"A4": 297000, "A3": 297000, "A2": 420000}[page]
        assert root.attrib["width"] == mm(expected_w_um) + "mm"
        assert root.attrib["height"] == mm(expected_h_um) + "mm"
        assert not warnings
        assert (pixels(int(root.attrib["width"][:-2].split('.')[0]) * 1000, 300),
                pixels(int(root.attrib["height"][:-2].split('.')[0]) * 1000, 300)) == expected


def test_clean_svg_retains_source_identity_and_explicit_only_junctions():
    svg, _ = compose_clean_svg(engine_svg(), ExportRequest())
    root = ET.fromstring(svg)
    assert root.attrib["viewBox"] == "0 0 420 297"
    assert root.find(f".//{SVG}g[@data-layer='geometry-review']") is None
    assert root.find(f".//{SVG}g[@data-layer='selection']") is None
    assert {item.attrib["data-net"] for item in root.findall(f".//{SVG}line[@data-net]")} == {
        "Net_A", "Net_B"
    }
    # Distinct wires cross at (55,17); no generated junction or dot.
    assert not root.findall(f".//{SVG}g[@data-layer='explicit-junctions']/{SVG}circle")
    b = root.find(f".//{SVG}line[@data-id='b-X2']")
    assert b is not None and b.attrib["data-electrical"] == "false"
    assert b.attrib["x1"] == "61.001"
    content = root.find(f".//{SVG}g[@data-layer='schematic-content']")
    assert content is not None and content.attrib["data-scale"] == "1:1"
    assert "scale(" not in content.attrib["transform"]
    assert not root.findall(f".//{SVG}image")


def test_region_crop_is_physical_and_without_frame():
    req = ExportRequest(region_um=(60_000, 35_000, 160_000, 80_000),
                        include_frame=False, include_title=False)
    root = ET.fromstring(compose_clean_svg(engine_svg(), req)[0])
    assert root.attrib["width"] == "160mm"
    assert root.attrib["height"] == "80mm"
    assert root.attrib["viewBox"] == "60 35 160 80"
    assert root.find(f".//{SVG}g[@data-layer='frame']") is None


def test_actual_png_300_dpi_physical_metadata_and_reproducibility(tmp_path: Path):
    req = ExportRequest()
    a, b = export(engine_svg(), req), export(engine_svg(), req)
    assert (a.svg, a.png, a.svg_sha256, a.png_sha256) == (
        b.svg, b.png, b.svg_sha256, b.png_sha256)
    assert a.pixels == (4961, 3508)
    assert a.svg_sha256 == hashlib.sha256(a.svg).hexdigest()
    png_path = tmp_path / "render.png"
    png_path.write_bytes(a.png)
    with Image.open(png_path) as im:
        assert im.size == (4961, 3508)
        assert im.info["dpi"] == pytest.approx((300, 300), abs=0.02)
    # Real PNG pHYs chunk (integer pixels/m) and metre unit marker, not a string.
    position = a.png.index(b"pHYs")
    assert struct.unpack(">IIB", a.png[position + 4:position + 13]) == (
        11811, 11811, 1)


def test_region_png_pixels():
    req = ExportRequest(region_um=(60_000, 35_000, 160_000, 80_000),
                        include_frame=False, include_title=False)
    result = export(engine_svg(), req)
    assert result.pixels == (1890, 945)


@pytest.mark.parametrize("bad", [
    (b'<svg xmlns="http://www.w3.org/2000/svg" width="80mm" height="40mm" '
     b'viewBox="10 5 80 40"><script/></svg>'),
    (b'<svg xmlns="http://www.w3.org/2000/svg" width="80mm" height="40mm" '
     b'viewBox="10 5 80 40"><image href="evil"/></svg>'),
    (b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
     b'<svg xmlns="http://www.w3.org/2000/svg" width="80mm" height="40mm" '
     b'viewBox="10 5 80 40"/>'),
    (b'<svg xmlns="http://www.w3.org/2000/svg" width="80mm" height="41mm" '
     b'viewBox="10 5 80 40"/>'),
])
def test_unsafe_or_mismatched_svg_fails_closed(bad):
    with pytest.raises(ExportError):
        compose_clean_svg(bad, ExportRequest())


def test_review_overlays_rejected_not_silently_filtered():
    with pytest.raises(ExportError, match="Diagnostic/editor layer"):
        compose_clean_svg(engine_svg(review=True), ExportRequest())


def test_missing_or_unverified_fonts_fail_closed():
    with pytest.raises(ExportError, match="FONT_NOT_OUTLINED"):
        compose_clean_svg(engine_svg(with_text=True), ExportRequest(strict_font=True))
    _, warnings = compose_clean_svg(engine_svg(with_text=True),
                                    ExportRequest(strict_font=False))
    assert warnings == ("FONT_RENDER_UNVERIFIED",)


def test_bad_layout_and_parameter_failure():
    with pytest.raises(ExportError, match="OVERFLOW"):
        compose_clean_svg(engine_svg(), ExportRequest(page="A4", offset_um=(300000, 0)))
    with pytest.raises(ExportError, match="Region crop"):
        ExportRequest(region_um=(0, 0, 1000, 1000), include_frame=True)
    with pytest.raises(ExportError, match="outside page"):
        ExportRequest(region_um=(419000, 0, 2000, 1000), include_frame=False)
    with pytest.raises(ExportError, match="DPI"):
        ExportRequest(dpi=1200)
    with pytest.raises(ExportError):
        ExportRequest(source_project_sha256="invalid")


def test_title_uses_engine_geometry_or_fails_closed():
    # The true engine import is available when running on the repo's CI.
    request = ExportRequest(include_title=True)
    try:
        import gost_schematic  # noqa: F401
    except ImportError:
        with pytest.raises(ExportError, match="TITLE_BLOCK_ENGINE_UNAVAILABLE"):
            compose_clean_svg(engine_svg(), request)
    else:
        root = ET.fromstring(compose_clean_svg(engine_svg(), request)[0])
        assert root.find(f".//{SVG}g[@data-layer='title-block']") is not None
        assert root.find(f".//{SVG}g[@data-layer='title-block-grid']") is not None


@pytest.mark.parametrize("page,orientation,expected", [
    ("A4", "portrait", (2480, 3508)),
    ("A2", "landscape", (7016, 4961)),
])
def test_actual_png_all_page_sizes(page, orientation, expected):
    result = export(engine_svg(), ExportRequest(page=page, orientation=orientation))
    assert result.pixels == expected
    with Image.open(__import__("io").BytesIO(result.png)) as image:
        assert image.size == expected
        assert image.info["dpi"] == pytest.approx((300, 300), abs=0.02)


def test_source_ink_outside_declared_viewbox_rejected():
    """A fabricated undersized viewport must not hide cropped conductors."""
    mismatched = engine_svg().replace(b'x2="60"', b'x2="100"')
    with pytest.raises(ExportError, match="SOURCE_VIEWBOX_CLIPS_INK"):
        compose_clean_svg(mismatched, ExportRequest())


def test_source_stroke_outside_viewbox_rejected():
    """Stroke extends beyond the geometric centreline and requires margin."""
    bad = engine_svg().replace(b'x1="34"', b'x1="10"')
    with pytest.raises(ExportError, match="SOURCE_VIEWBOX_CLIPS_INK"):
        compose_clean_svg(bad, ExportRequest())


def test_absolute_v2_page_coordinates_are_not_recentred():
    """Geometry authored on a paper sheet must not move during export."""
    req = ExportRequest(page_coords=True, include_frame=False)
    root = ET.fromstring(compose_clean_svg(engine_svg(), req)[0])
    content = root.find(f".//{SVG}g[@data-layer='schematic-content']")
    assert content is not None and content.get("transform") == "translate(0 0)"
    assert root.find(f".//{SVG}line[@data-id='b-X2']").get("x1") == "61.001"
    with pytest.raises(ExportError, match="Page coordinates"):
        ExportRequest(page_coords=True, offset_um=(1000, 0))


def test_absolute_sheet_off_page_fails_without_implicit_fit():
    source = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
        b'viewBox="415 5 10 10">'
        b'<circle cx="420" cy="10" r="1" stroke="none" fill="#000000"/></svg>'
    )
    with pytest.raises(ExportError, match="OVERFLOW"):
        compose_clean_svg(source, ExportRequest(page_coords=True, include_frame=False))


def test_polyline_stroked_ink_outside_viewbox_fails():
    source = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
        b'viewBox="0 0 10 10"><polyline points="2,2 9.95,2" stroke="#000000" '
        'stroke-width="0.3" fill="none"/></svg>'
    )
    with pytest.raises(ExportError, match="SOURCE_VIEWBOX_CLIPS_INK"):
        compose_clean_svg(source, ExportRequest(include_frame=False))


def test_semicircle_ink_bounds_and_unverifiable_bezier_rejected():
    arc = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" '
        b'viewBox="0 0 10 10"><path d="M 2 5 A 3 3 0 0 1 8 5" '
        b'stroke="#000000" stroke-width="0.3" fill="none"/></svg>'
    )
    root = ET.fromstring(compose_clean_svg(
        arc, ExportRequest(include_frame=False))[0])
    assert root.find(f".//{SVG}path") is not None
    too_tight = arc.replace(b'viewBox="0 0 10 10"', b'viewBox="0 3 10 10"')
    # The arc source now violates physical extent even if width/height agree.
    with pytest.raises(ExportError, match="SOURCE_VIEWBOX_CLIPS_INK"):
        compose_clean_svg(too_tight, ExportRequest(include_frame=False))
    cubic = arc.replace(b'M 2 5 A 3 3 0 0 1 8 5', b'M 2 5 C 3 4 5 6 8 5')
    with pytest.raises(ExportError, match="UNVERIFIABLE_SVG_PATH"):
        compose_clean_svg(cubic, ExportRequest(include_frame=False))
