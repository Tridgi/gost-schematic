"""ГОСТ 2.743-91 fig.3 E3 top-in/bottom-out *view*, no PinRef mutation.

Maps a separately declared TOP/BOTTOM physical IC view to the existing
LEFT/RIGHT measured SVG compositor by a strictly geometric 90-degree change
of coordinates. This is NOT merely rotating a left/right view: source rows
are truly typed TOP/BOTTOM, and the external Point remains authoritative.
"""
from dataclasses import replace

from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.transforms import Transform


def compose_transforms(outer: Transform, inner: Transform) -> Transform:
    """Return the unique orthogonal transform equivalent to outer(inner(p))."""
    basis = (Point(1, 0), Point(0, 1))
    desired = tuple(outer.apply(inner.apply(p)) for p in basis)
    for mirror in (False, True):
        for angle in (0, 90, 180, 270):
            candidate = Transform(angle, mirror)
            if tuple(candidate.apply(p) for p in basis) == desired:
                return candidate
    raise AssertionError("D4 closure was violated")


def vertical_as_canonical(unit):
    """Return same exact world endpoints with a rotated local geometry.

    The physical original `unit.body` is a vertical-oriented Box.
    Its x/y extents are exchanged only in a private rendering view.
    Each source column is numbered left-to-right, not guessed from its label.
    """
    from gost_schematic.rendering.ic_rectangular import IcOrientation, IcResolvedUnit

    if unit.orientation is not IcOrientation.TOP_BOTTOM:
        raise ValueError("IC_ORIENTATION_NOT_TOP_BOTTOM")
    if any(p.side not in (Side.TOP, Side.BOTTOM) for p in unit.pins):
        raise ValueError("IC_MIXED_SIDE_PROFILE")
    max_col = max(p.row for p in unit.pins)
    candidates = tuple(replace(
        p, side=Side.LEFT if p.side is Side.TOP else Side.RIGHT,
        row=max_col + 1 - p.row,
    ) for p in unit.pins)
    width = unit.body.max_x - unit.body.min_x
    height = unit.body.max_y - unit.body.min_y
    # (canonical x,y)->(vertical x,y)=(vertical.max_x-y, vertical.min_y+x)
    origin_shift = Point(unit.body.max_x, unit.body.min_y)
    new_origin = unit.origin + unit.transform.apply(origin_shift)
    rotation = compose_transforms(unit.transform, Transform(90))
    return IcResolvedUnit(
        unit.reference, Box(0, 0, height, width), candidates, unit.content,
        new_origin, rotation, IcOrientation.LEFT_RIGHT,
    )


def vertical_proposal(canonical):
    """Return oriented body dimensions without relabeling physical terminals."""
    from gost_schematic.rendering.ic_rectangular import IcProposedSize

    return IcProposedSize(
        canonical.main_width_um, canonical.left_width_um,
        canonical.right_width_um, canonical.width_um,
        canonical.row_pitch_um, canonical.row_count,
        canonical.lead_length_um, canonical.module_um,
        body_width_um=canonical.height_um,
        vertical_field_heights_um=(
            canonical.left_width_um, canonical.main_width_um,
            canonical.right_width_um,
        ),
    )
