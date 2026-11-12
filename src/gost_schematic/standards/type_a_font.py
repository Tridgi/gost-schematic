"""ГОСТ 2.304-81 type А engineering typography profile.

The standard uses height of UPPERCASE GLYPHS (h), not the font's em square.
We calibrate the actual loaded face from a capital Cyrillic Н and store the
corresponding em size for BOTH SVG rendering and Pillow collision measurement.

This verifies metric scale, not conformance of a font's full outlines to ГОСТ.
No font data is copied or shipped by this module.
"""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from pathlib import Path

from gost_schematic.engines.annotation.metrics import _PIXELS_PER_EM, _load_font, font_sha256
from gost_schematic.model.annotations import TextStyle

TYPE_A_HEIGHTS_UM = frozenset((2500, 3500, 5000, 7000, 10000, 14000, 20000))


class TypeAAngle(str, Enum):
    UPRIGHT = "upright"
    INCLINED_75 = "inclined_75"


def _face_style(face: tuple[str, str]) -> str:
    return "italic" if any(
        label in face[1].casefold() for label in ("italic", "oblique", "slanted")
    ) else "normal"


@dataclass(frozen=True, slots=True)
class TypeAParameters:
    """Exact drawing dimensions for ГОСТ 2.304-81 §2.1, table 1."""

    h_um: int

    def __post_init__(self) -> None:
        if type(self.h_um) is not int or self.h_um not in TYPE_A_HEIGHTS_UM:
            raise ValueError("Type A height h must be 2.5, 3.5, 5, 7, 10, 14 or 20 mm")

    @property
    def stroke_width_um(self) -> Fraction:
        return Fraction(self.h_um, 14)

    @property
    def lowercase_height_um(self) -> Fraction:
        return Fraction(self.h_um * 10, 14)

    @property
    def letter_gap_um(self) -> Fraction:
        return Fraction(self.h_um * 2, 14)

    @property
    def word_gap_um(self) -> Fraction:
        return Fraction(self.h_um * 6, 14)

    @property
    def line_step_um(self) -> Fraction:
        return Fraction(self.h_um * 22, 14)


@dataclass(frozen=True, slots=True)
class TypeAFontInspection:
    """Result of face-size calibration; not a regulatory certificate."""

    style: TextStyle
    requested_cap_height_um: int
    measured_cap_height_um: int
    cap_height_error_um: int
    reported_face: tuple[str, str]
    font_path: str


def inspect_type_a_font(
    font_path: str | Path,
    *,
    h_um: int = 3500,
    family: str = "OpenGost Type A",
    clearance_um: int = 500,
    require_family_match: bool = True,
    angle: TypeAAngle = TypeAAngle.UPRIGHT,
) -> TypeAFontInspection:
    """Fail closed if missing, wrong-family or lacking a measurable Cyrillic capital.

    `h` is calibrated against the loaded font. The same physical font must be
    installed in the SVG viewer, which resolves `family` independently.
    """
    params = TypeAParameters(h_um)
    source = Path(font_path).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"Font path is not a regular file: {source}")
    font = _load_font(str(source))
    face = font.getname()
    if require_family_match and family.casefold() not in face[0].casefold():
        raise ValueError(
            f"Selected font is {face[0]!r}, not declared type A family {family!r}"
        )
    if not isinstance(angle, TypeAAngle):
        raise TypeError("angle must be a TypeAAngle")
    face_style = _face_style(face)
    expected_style = "italic" if angle == TypeAAngle.INCLINED_75 else "normal"
    if face_style != expected_style:
        raise ValueError(
            f"Angle {angle.value} needs an actual {expected_style} font face, "
            f"but {face[1]!r} was loaded"
        )
    # The glyph Н has a flat cap, unlike rounded characters with overshoot.
    left, top, right, bottom = font.getbbox("Н", anchor="ls")
    if left >= right or top >= bottom or top >= 0:
        raise ValueError("Font does not provide a valid Cyrillic capital Н glyph")
    reference_height = -top
    if reference_height <= 0:
        raise ValueError("Could not determine a positive Cyrillic cap height")
    # Pillow uses a 512-pixel em; SVG size follows the same em scaling.
    calibrated_em_um = max(1, round(params.h_um * _PIXELS_PER_EM / reference_height))
    measured_cap_um = round(reference_height * calibrated_em_um / _PIXELS_PER_EM)
    style = TextStyle(
        str(source), family, em_height_um=calibrated_em_um,
        clearance_um=clearance_um,
        font_style=face_style,
        font_sha256=font_sha256(str(source)),
    )
    return TypeAFontInspection(
        style=style,
        requested_cap_height_um=params.h_um,
        measured_cap_height_um=measured_cap_um,
        cap_height_error_um=measured_cap_um - params.h_um,
        reported_face=face,
        font_path=str(source),
    )
