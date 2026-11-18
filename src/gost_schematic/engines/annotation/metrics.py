"""Measure actual font glyphs, never approximate a string by character count."""

from functools import lru_cache
from hashlib import sha256
from math import ceil, floor
from pathlib import Path
from typing import Protocol

from gost_schematic.core.geometry import Box
from gost_schematic.model.annotations import MeasuredText, TextStyle

_PIXELS_PER_EM = 512


class TextMeasurer(Protocol):
    def measure(self, text: str, style: TextStyle) -> MeasuredText: ...


@lru_cache(maxsize=64)
def _cached_font(path: str, mtime_ns: int, size: int):
    try:
        from PIL import ImageFont
    except ImportError as error:
        raise RuntimeError(
            "Install the optional font measurement dependency: pip install 'gost-schematic[fonts]'"
        ) from error
    return ImageFont.truetype(path, _PIXELS_PER_EM)


def _load_font(path: str):
    """Cache a face by file identity, not merely a mutable pathname."""
    font_file = Path(path)
    info = font_file.stat()
    return _cached_font(str(font_file), info.st_mtime_ns, info.st_size)


@lru_cache(maxsize=64)
def _digest_for_file(path: str, mtime_ns: int, size: int) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def font_sha256(path: str) -> str:
    """Digest the local font data for controlled SVG/measurement provenance."""
    info = Path(path).stat()
    return _digest_for_file(path, info.st_mtime_ns, info.st_size)


class PillowTextMeasurer:
    """Measure actual glyph ink bounds via FreeType at a fixed high resolution.

    TextStyle.em_height_um sets typographic em size, NOT capital-letter height.
    The same font must be installed or explicitly embedded when the SVG is viewed.
    """

    def measure(self, text: str, style: TextStyle) -> MeasuredText:
        if not text or "\n" in text or "\r" in text:
            raise ValueError("Text must be one non-empty line")
        if (
            style.font_sha256 is not None
            and font_sha256(style.font_path) != style.font_sha256
        ):
            raise ValueError("The font file changed since its approved fingerprint")
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
