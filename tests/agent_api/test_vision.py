"""Issue #65: actual PNG, exact viewport, authoring model and fail-closed inputs."""

import hashlib
import io
import json
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from gost_schematic.agent_api.specimen import load_specimen
from gost_schematic.agent_api.vision import (
    VisionError,
    diagnostics,
    inspect_component,
    inspect_connection,
    inspect_region,
    list_views,
    render_overview,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _png(result):
    assert result.png.startswith(PNG_MAGIC)
    with Image.open(io.BytesIO(result.png)) as im:
        assert im.format == "PNG"
        assert list(im.size) == result.metadata["pixels"]
        assert im.convert("RGB").getbbox()
        assert im.convert("RGB").getextrema() != ((255, 255),) * 3
        return im.size


def test_live_c3_is_authored_80_mm_with_16_segments():
    case = load_specimen("six-part")
    c3 = next(part for part in case.circuit.components if part.reference == "C3")
    assert c3.origin.y == 80_000
    assert len(case.circuit.components) == 6
    assert len(case.graph.segments) == 16
    assert len(case.circuit.nets) == 5
    assert len(case.graph.junctions) == 3


def test_overview_is_real_png_metadata_and_reproducible():
    first = render_overview()
    second = render_overview()
    assert _png(first) == (1600, first.metadata["pixels"][1])
    assert first.png == second.png
    assert first.metadata["view_svg_sha256"] == hashlib.sha256(
        first.svg.encode()
    ).hexdigest()
    assert first.metadata["project_revision"] == second.metadata["project_revision"]
    assert first.metadata["mime_type"] == "image/png"
    assert first.metadata["wire_segment_count"] == 16
    assert first.metadata["rasterizer"] in ("resvg_py", "CairoSVG")
    assert first.metadata["status"].startswith("DRAFT")


def test_component_and_pin_zoom_rasterize_vector_source():
    whole = render_overview()
    detail = inspect_component("six-part", "C3", target_dpi=500)
    assert _png(detail)[0] < whole.metadata["pixels"][0]
    assert detail.metadata["effective_dpi"][0] > whole.metadata["effective_dpi"][0]
    bbox = list(map(float, detail.metadata["bbox_mm"]))
    assert bbox[0] < 100 < bbox[2]
    assert bbox[1] < 80 < bbox[3]
    svg = ET.fromstring(detail.svg)
    x, y, w, h = map(float, svg.get("viewBox").split())
    assert abs(x - bbox[0]) < 0.001
    assert abs(y - bbox[1]) < 0.001
    assert abs(x + w - bbox[2]) < 0.001
    assert abs(y + h - bbox[3]) < 0.001
    assert "data-layer=\"geometry-review\"" in detail.svg
    assert "data-owner=\"C3\"" in detail.svg
    pin = inspect_region("six-part", {"pin": {"component": "C3", "number": "1"}})
    assert _png(pin)[0] >= 50
    assert detail.metadata["geometry_sha256"] != whole.metadata["geometry_sha256"]


def test_explicit_mm_bbox_exact_clipping():
    view = inspect_region("six-part", {"bbox_mm": [65, 35, 75, 45]}, padding_mm=2)
    assert view.metadata["bbox_mm"] == ["63", "33", "77", "47"]
    assert _png(view)[0] > 100
    # A right-hand sheet-edge bbox is safely clipped to the source viewport.
    overview = render_overview()
    max_x = float(overview.metadata["sheet_bbox_mm"][2])
    v2 = inspect_region("six-part", {"bbox_mm": [max_x - 1, 35, max_x + 6, 45]})
    assert float(v2.metadata["bbox_mm"][2]) == max_x


def test_clean_vs_diagnostic_and_semantic_net_selector():
    clean = inspect_region("six-part", {"reference": "C3"}, mode="clean")
    debug = inspect_region("six-part", {"net": "TOP"})
    assert "geometry-review" not in clean.svg
    assert "geometry-review" in debug.svg
    assert _png(debug)[0] > 100
    assert debug.metadata["selector"] == {"net": "TOP"}


def test_connection_uses_actual_physical_pins_not_svg():
    view = inspect_connection(
        "six-part",
        {"component": "R1", "number": "2"},
        {"component": "C3", "number": "1"},
    )
    assert _png(view)[0] > 100
    assert view.metadata["connection"]["declared_net"] == "TOP"
    assert view.metadata["connection"]["related_segments"] > 0
    with pytest.raises(VisionError, match="PINS_NOT_CONNECTED"):
        inspect_connection(
            "six-part", {"component": "C3", "number": "1"},
            {"component": "C3", "number": "2"},
        )


def test_independent_short_diagnostic_is_not_pixel_analysis():
    valid = diagnostics("six-part", "geometry")
    assert not any(x["code"] == "WIRE_NET_SHORT" for x in valid["diagnostics"])
    short = diagnostics("six-part:short_at_unmarked_crossing", "geometry")
    assert any(x["code"] == "WIRE_NET_SHORT" for x in short["diagnostics"])
    image = render_overview("six-part:short_at_unmarked_crossing", mode="diagnostic")
    assert _png(image)[0] == 1600
    assert "authored-junction" in image.svg
    assert diagnostics("six-part", "labels")["labels_check_status"] == "not implemented"


@pytest.mark.parametrize(("selector", "code"), [
    ({"reference": "UNKNOWN"}, "UNKNOWN_COMPONENT"),
    ({"pin": {"component": "C3", "number": "999"}}, "UNKNOWN_PIN"),
    ({"pin": {"component": "UNKNOWN", "number": "1"}}, "UNKNOWN_COMPONENT"),
    ({"net": "NOT_A_NET"}, "UNKNOWN_NET"),
    ({"bbox_mm": [4, 4, 4, 5]}, "INVALID_BBOX"),
    ({"bbox_mm": [float("nan"), 1, 3, 4]}, "INVALID_COORDINATE"),
    ({"bbox_mm": [1.0001, 1, 3, 4]}, "INVALID_COORDINATE"),
    ({"bbox_mm": [10000, 10000, 10001, 10001]}, "REGION_OUTSIDE_SHEET"),
    ({"reference": "C3", "net": "TOP"}, "INVALID_SELECTOR"),
    ({"hacked": "../x.py"}, "INVALID_SELECTOR"),
])
def test_invalid_selector_fails_closed(selector, code):
    with pytest.raises(VisionError) as exc:
        inspect_region("six-part", selector)
    assert exc.value.code == code


@pytest.mark.parametrize(("func", "code"), [
    (lambda: render_overview("../../../etc/passwd"), "UNKNOWN_PROJECT"),
    (lambda: render_overview(max_px=100_000), "IMAGE_TOO_LARGE"),
    (lambda: render_overview(max_px=True), "IMAGE_TOO_LARGE"),
    (lambda: render_overview(mode="untrusted"), "INVALID_MODE"),
    (lambda: inspect_component("six-part", "C3", padding_mm=100), "INVALID_PADDING"),
    (lambda: inspect_component("six-part", "C3", target_dpi=10000), "INVALID_DPI"),
    (lambda: inspect_region("six-part", {"bbox_mm": [0, 0, 1, 1]},
                            padding_mm=float("inf")), "INVALID_COORDINATE"),
])
def test_invalid_requests(func, code):
    with pytest.raises(VisionError) as exc:
        func()
    assert exc.value.code == code


def test_review_artifacts_only_inside_trusted_workspace(tmp_path):
    view = render_overview(output_root=tmp_path)
    png = tmp_path / "artifacts" / "ai-mcp" / ("view-" + view.metadata["view_id"] + ".png")
    assert png.read_bytes() == view.png
    assert str(png) == view.metadata["artifact_png"]
    assert (png.with_suffix(".svg")).read_text(encoding="utf8") == view.svg
    assert list_views("six-part")["project_revision"] == view.metadata["project_revision"]
    assert json.loads(json.dumps(diagnostics()))["authoritative_sources"] == [
        "Circuit", "ExternalWireGraph",
    ]
