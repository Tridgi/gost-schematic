"""Measure actual font glyphs, never approximate a string by character count."""

from functools import lru_cache
from math import ceil, floor
from pathlib import Path
from typing import Protocol

from gost_schematic.core.geometry import Box
from gost_schematic.model.annotations import MeasuredText, TextStyle

_PIXELS_PER_EM = 512


class TextMeasurer(Protocol):
    def measure(self, text: str, style: TextStyle) -> MeasuredText: ...


@lru_cache(maxsize=32)
def _load_font(path: str):
    try:
        from PIL import ImageFont
    except ImportError as error:
        raise RuntimeError(
            "Install the optional font measurement dependency: pip install 'gost-schematic[fonts]'"
        ) from error
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"Font resource does not exist: {file}")
    return ImageFont.truetype(str(file), _PIXELS_PER_EM)


class PillowTextMeasurer:
    """Measure actual glyph ink bounds via FreeType at a fixed high resolution.

    TextStyle.em_height_um sets typographic em size, NOT capital-letter height.
    The same font must be installed or explicitly embedded when the SVG is viewed.
    """

    def measure(self, text: str, style: TextStyle) -> MeasuredText:
        if not text or "\n" in text or "\r" in text:
            raise ValueError("Text must be one non-empty line")
        font = _load_font(style.font_path)
        left, top, right, bottom = font.getbbox(text, anchor="ls")
        if left >= right or top >= bottom:
            raise ValueError("Text has no visible glyph ink")
        scale = style.em_height_um / _PIXELS_PER_EM
        bounds = Box(
            floor(left * scale),
            floor(top * scale),
            ceil(right * scale),
            ceil(bottom * scale),
        )
        return MeasuredText(bounds, ceil(font.getlength(text) * scale))
