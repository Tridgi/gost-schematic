"""Cycle9 independent ESKD source contract and adversarial numeric examples.

Source-anchored tests do NOT certify owner rendered sheets or original paper 1:1.
PDF page indices were inspected independently; CI has no external PDF dependency.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs/standards/issue107-ugo-normative-matrix.json"
SNAPSHOTS_PATH = ROOT / "docs/standards/issue107-ugo-source-snapshots.json"

# One-based PDF page anchors, NOT printed running standard page numbers.
# Verified in scanned ГОСТ 2.723, 2.721 and 2.701 figures/clauses.
PDF_PAGE_FIXTURE = {
    "inductor.ferromagnetic": 6,
    "choke.ferromagnetic": 6,
    "inductor.magnetodielectric": 6,
    "net-marker.common": 11,
    "net-marker.earth": 11,
    "net-marker.noiseless": 11,
    "net-marker.protective_earth": 11,
    "net-marker.chassis": 11,
    "net-marker.equipotential": 11,
    "net-continuation.other-sheet": 9,
    "net-continuation.same-sheet": 10,
    "drc.clearances": 8,
}


def _matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _snapshot() -> dict:
    return json.loads(SNAPSHOTS_PATH.read_text(encoding="utf-8"))


def _card(identifier: str) -> dict:
    return next(card for card in _matrix()["cards"] if card["id"] == identifier)


def _pdf_page(uri: str) -> int:
    return int(parse_qs(urlparse(uri).fragment)["page"][0])


def _git_blob_sha(data: bytes) -> str:
    prefix = f"blob {len(data)}".encode("ascii") + bytes([0])
    return hashlib.sha1(prefix + data).hexdigest()


@pytest.mark.parametrize(("identifier", "page"), PDF_PAGE_FIXTURE.items())
def test_correct_source_pdf_page_anchor_and_preserved_correction(identifier, page):
    card = _card(identifier)
    assert _pdf_page(card["source_figure_url"]) == page
    audit = card["cycle9_page_correction"]
    assert audit["verified_page"] == page
    assert audit["previous_page"] != page
    assert card["status_full_1to1"] == "BLOCKED"
    assert card["approval"] == "DRAFT"


@pytest.mark.parametrize(("identifier", "page"), PDF_PAGE_FIXTURE.items())
def test_wrong_old_pdf_page_is_detected_by_independent_fixture(identifier, page):
    card = _card(identifier)
    previous = card["cycle9_page_correction"]["previous_page"]
    # Regression: older test only required the occurrence of "#page=".
    malformed_uri = card["source_figure_url"].split("#", 1)[0] + f"#page={previous}"
    assert "#page=" in malformed_uri
    assert _pdf_page(malformed_uri) != page


def test_actual_owner_source_bytes_match_git_blob_snapshots():
    snapshots = _snapshot()["cards"]
    assert len(snapshots) == 12
    for s in snapshots:
        path = ROOT / s["owner_file"]
        body = path.read_bytes()
        assert _git_blob_sha(body) == s["owner_blob_sha"], s["id"]
        owner = json.loads(body)
        if s["geometry"] is not None:
            assert owner["status"] == "draft", s["id"]
            assert owner["geometry"] == s["geometry"], s["id"]
            assert owner["pins"] == s["pins"], s["id"]
        else:
            assert owner["core"] == s["coil_profile"]["core"], s["id"]
            assert owner["turns"] == s["coil_profile"]["turns"], s["id"]
            assert str(owner["radius_mm"]) == str(s["coil_profile"]["radius_mm"]), s["id"]


def test_schottky_8_d4_source_geometry_preserves_A_K_and_hook_chirality():
    geometry = _card("diode.schottky")["signature_mm"]
    a = geometry["anode_mm"]
    k = geometry["cathode_pin_mm"]
    upper = geometry["upper_hook"]
    lower = geometry["lower_hook"]

    def rotate(point, count):
        x, y = point
        for _ in range(count):
            x, y = -y, x
        return (x, y)

    poses = []
    for reflected in (False, True):
        for count in range(4):
            def transform(point, *, mirror=reflected, quarter_turns=count):
                x, y = point
                if mirror:
                    x = -x
                return rotate((x, y), quarter_turns)
            new_a, new_k = transform(a), transform(k)
            new_upper = [transform(p) for p in upper]
            new_lower = [transform(p) for p in lower]
            assert new_a != new_k
            assert len(set(new_upper)) == len({tuple(p) for p in upper}) == 3
            assert len(set(new_lower)) == len({tuple(p) for p in lower}) == 3
            # A transform cannot collapse the two distinct asymmetric hook ends.
            assert new_upper[-1] != new_lower[-1]
            poses.append((new_a, new_k, tuple(new_upper), tuple(new_lower)))
    assert len(set(poses)) == 8


@pytest.mark.parametrize(
    ("start_angle", "expected_direction"),
    [(-90, "bottom_to_top"), (0, "left_to_right"), (90, "top_to_bottom")],
)
def test_function_word_baseline_direction_is_not_unsigned_angle(start_angle, expected_direction):
    theta = math.radians(start_angle)
    # Page coordinates: X to right, Y downward.
    vx, vy = round(math.cos(theta)), round(math.sin(theta))
    if (vx, vy) == (0, -1):
        actual_direction = "bottom_to_top"
    elif (vx, vy) == (0, 1):
        actual_direction = "top_to_bottom"
    else:
        actual_direction = "left_to_right"
    assert actual_direction == expected_direction
    assert _card("ic.TL494CN")["function_text_bottom_to_top"]["gost_approval"] == "BLOCKED"


def _parallel_vertical_print_gap(a, b) -> float | None:
    """Diagnostic *example*, not a production routing/legal engine.

    a,b: (x_mm, y_start_mm, y_end_mm, stroke_mm).
    Returns edge gap iff different vertical geometric lines share a positive
    interval along Y; X/T, collinear shared lines and point-touch are excluded
    from THIS particular check, not otherwise declared error-free.
    """
    x1, a1, a2, w1 = a
    x2, b1, b2, w2 = b
    overlap = min(max(a1, a2), max(b1, b2)) - max(min(a1, a2), min(b1, b2))
    if overlap <= 0 or math.isclose(x1, x2, abs_tol=1e-12):
        return None
    return abs(x1 - x2) - (w1 + w2) / 2


@pytest.mark.parametrize(
    ("a", "b", "gap_expected"),
    [
        ((0, 0, 15, 0.3), (3.3, 1, 14, 0.3), 3.0),
        ((0, 0, 15, 0.3), (3.0, 1, 14, 0.3), 2.7),
        ((0, 0, 15, 0.2), (3.0, 1, 14, 0.4), 2.7),
        ((0, 0, 5, 0.3), (0, 5, 10, 0.3), None),
        ((0, 0, 5, 0.3), (2.0, 5, 10, 0.3), None),
    ],
)
def test_3mm_rule_is_ink_edge_and_requires_projected_parallel_overlap(a, b, gap_expected):
    measured = _parallel_vertical_print_gap(a, b)
    if gap_expected is None:
        assert measured is None
    else:
        assert math.isclose(measured, gap_expected, abs_tol=1e-10)
        assert (measured + 1e-10 >= 3.0) == (gap_expected >= 3.0)


def test_1_2_3_mm_are_separate_categories_and_not_all_crossings():
    rules = _card("drc.clearances")["hard_mm"]
    assert rules["adjacent_ugo_line_gap"] == 1
    assert rules["distinct_ugo_gap"] == 2
    assert rules["parallel_interconnect_gap"] == 3
    assert rules["adjacent_ugo_line_gap"] != rules["parallel_interconnect_gap"]
    assert _matrix()["cycle9_independent_audit"]["status"].startswith("DRAFT")


@pytest.mark.parametrize("h", [2.5, 3.5])
def test_gost_type_a_print_font_stroke_uses_h_over_14(h):
    d = h / 14
    assert math.isclose(d, 0.1785714286 if h == 2.5 else 0.25, abs_tol=1e-8)
    # The 2.5/3.5mm text heights are height, not wire stroke thickness.
    assert d < 0.3


def test_300dpi_is_a_pixel_density_not_an_ugo_size_standard():
    assert math.isclose(3 / 25.4 * 300, 35.433070866, abs_tol=1e-8)
    assert math.isclose(2 / 25.4 * 300, 23.622047244, abs_tol=1e-8)
    assert math.isclose(1 / 25.4 * 300, 11.811023622, abs_tol=1e-8)


def test_common_and_pe_can_never_be_auto_aliased_from_same_marker():
    common = _card("net-marker.common")
    pe = _card("net-marker.protective_earth")
    assert common["status_source_shape"] == "BLOCKED"
    assert pe["status_full_1to1"] == "BLOCKED"
    assert common["marker_may_create_physical_part"] is False
    assert pe["marker_may_create_physical_part"] is False
    assert common["id"] != pe["id"]


def test_fuse_remains_a_separate_unapproved_catalog_candidate():
    owner_path = ROOT / "src/gost_schematic/catalog/symbols/fuses/general.json"
    owner_bytes = owner_path.read_bytes()
    assert _git_blob_sha(owner_bytes) == "6af105eb850211b0f86e5fc7df59da28719d2e76"
    fuse = json.loads(owner_bytes)
    assert fuse["id"] == "fuse.general"
    assert fuse["status"] == "draft"
    assert len(fuse["pins"]) == 2
    assert len(fuse["geometry"]["rectangles"]) == 1
    assert len(fuse["geometry"]["lines"]) == 3


def test_zero_approvals_and_real_print_gates_still_blocked():
    m = _matrix()
    assert m["approved"] == 0
    assert all(card["approval"] == "DRAFT" for card in m["cards"])
    assert all(card["status_full_1to1"] == "BLOCKED" for card in m["cards"])
    assert m["reference_head"] == "e695c415fdced164b0e0c39c5249d030795a0aa6"


def test_frozen_actual_pwm_svg_is_detectably_wrong_relative_to_target():
    """Negative regression: historical real print must not be promoted to PASS."""
    ic = _card("ic.TL494CN")
    e = ic["cycle9_reference_print_evidence"]
    assert e["reference_svg_blob"] == "69fa5d18f0844b080d8f1574c686e5c1156ae1f9"
    assert e["reference_manifest_blob"] == "b2375feb43ad18b8a8e5a515bfc007d169b26908"
    assert e["reference_manifest_function_rotation_degrees"] == 90
    assert e["observed_print_svg_function_matrix"].startswith("matrix(0 1 -1 0 ")
    assert e["observed_baseline_direction"] == "top_to_bottom"
    assert e["requested_baseline_direction"] == "bottom_to_top"
    assert e["source_target_comparison"] == "FAIL_CURRENT_FROZEN_REFERENCE_NOT_TARGET"
    assert e["normative_approval"] == "BLOCKED"
    # The expected function reading direction needs a new REAL owner output.
    assert ic["function_text_bottom_to_top"]["svg_local_angle_degrees"] == -90
