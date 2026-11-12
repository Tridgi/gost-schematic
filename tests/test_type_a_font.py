"""ГОСТ 2.304-81 type A dimensional profile and actual face calibration."""

from fractions import Fraction

import pytest

from gost_schematic.standards import type_a_font
from gost_schematic.standards.type_a_font import (
    TYPE_A_HEIGHTS_UM,
    TypeAParameters,
    TypeAAngle,
    inspect_type_a_font,
)


def test_standard_type_a_dimensions_use_exact_ratios():
    assert TYPE_A_HEIGHTS_UM == {2500, 3500, 5000, 7000, 10000, 14000, 20000}
    p = TypeAParameters(3500)
    assert p.stroke_width_um == Fraction(250, 1)
    assert p.lowercase_height_um == Fraction(2500, 1)
    assert p.letter_gap_um == Fraction(500, 1)
    assert p.word_gap_um == Fraction(1500, 1)
    assert p.line_step_um == Fraction(5500, 1)


@pytest.mark.parametrize("bad", [1800, 2501, 0, 3000, -3500, 3.5, True])
def test_invalid_type_a_height_is_rejected(bad):
    with pytest.raises(ValueError):
        TypeAParameters(bad)


def test_calibration_targets_capital_height_and_svg_em_matches(monkeypatch, tmp_path):
    class Font:
        def getname(self):
            return ("OpenGost Type A", "Regular")

        def getbbox(self, value, anchor):
            assert (value, anchor) == ("Н", "ls")
            return (0, -358, 350, 5)

    monkeypatch.setattr(type_a_font, "_load_font", lambda path: Font())
    source = tmp_path / "test-face.ttf"
    source.write_bytes(b"dummy-font-for-mocked-metrics")
    profile = inspect_type_a_font(source, h_um=3500)
    assert profile.style.font_family == "OpenGost Type A"
    assert profile.style.em_height_um == round(3500 * 512 / 358)
    assert abs(profile.cap_height_error_um) <= 1
    assert profile.reported_face == ("OpenGost Type A", "Regular")


def test_wrong_font_is_rejected_even_when_ttf_exists(monkeypatch, tmp_path):
    class Font:
        def getname(self):
            return ("DejaVu Sans", "Book")

        def getbbox(self, text, anchor):
            return (0, -360, 350, 0)

    monkeypatch.setattr(type_a_font, "_load_font", lambda path: Font())
    source = tmp_path / "other-font.ttf"
    source.write_bytes(b"dummy")
    with pytest.raises(ValueError, match="not declared type A family"):
        inspect_type_a_font(source)


def test_missing_font_never_silently_uses_system_fallback(tmp_path):
    with pytest.raises(FileNotFoundError):
        inspect_type_a_font(tmp_path / "missing.otf")


def test_invalid_cyrillic_cap_glyph_is_rejected(monkeypatch, tmp_path):
    class Font:
        def getname(self):
            return ("OpenGost Type A", "Regular")

        def getbbox(self, text, anchor):
            return (0, 0, 350, 350)

    monkeypatch.setattr(type_a_font, "_load_font", lambda path: Font())
    path = tmp_path / "bad.ttf"
    path.write_bytes(b"dummy")
    with pytest.raises(ValueError, match="valid Cyrillic"):
        inspect_type_a_font(path)



def test_inclined_profile_requires_real_italic_face(monkeypatch, tmp_path):
    class Face:
        def getname(self):
            return ("OpenGost Type A", "Italic")

        def getbbox(self, text, anchor):
            return (0, -360, 400, 0)

    monkeypatch.setattr(type_a_font, "_load_font", lambda path: Face())
    path = tmp_path / "type-a-italic.ttf"
    path.write_bytes(b"dummy")
    inspection = inspect_type_a_font(path, angle=TypeAAngle.INCLINED_75)
    assert inspection.style.font_style == "italic"
    with pytest.raises(ValueError, match="actual normal"):
        inspect_type_a_font(path, angle=TypeAAngle.UPRIGHT)


def test_regular_face_never_silently_becomes_75_degree_type_a(monkeypatch, tmp_path):
    class Face:
        def getname(self):
            return ("OpenGost Type A", "Regular")

        def getbbox(self, text, anchor):
            return (0, -360, 400, 0)

    monkeypatch.setattr(type_a_font, "_load_font", lambda path: Face())
    path = tmp_path / "regular.ttf"
    path.write_bytes(b"dummy")
    with pytest.raises(ValueError, match="actual italic"):
        inspect_type_a_font(path, angle=TypeAAngle.INCLINED_75)
