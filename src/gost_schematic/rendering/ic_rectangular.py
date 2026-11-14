"""DRAFT rectangular E3 IC rendering, measured typography and immutable port anchors.

ГОСТ 2.743-91 §§2.1.1–2.1.9, 2.3.12; analog profile subject to
ГОСТ 2.759-82/ESKD Issue #91 acceptance. Project mm grid, padding and
lead lengths are editorial settings, not asserted mandatory GOST figures.

Two independent phases:
  propose_ic_dimensions -> suggested layout dimensions, changes no pins.
  render_resolved_ic -> validates and uses exact externally RESOLVED pins.
Never use E1 FunctionalBlock, physical footprint or electrical net inference.
"""
from dataclasses import dataclass, field, replace
from enum import Enum
from math import ceil, floor
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import (
    SIDE_VECTORS,
    Box,
    Point,
    Side,
    enclosing_box,
)
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import format_mm
from gost_schematic.engines.annotation.metrics import TextMeasurer
from gost_schematic.model.annotations import TextStyle

_SVG = "http://www.w3.org/2000/svg"
# Never mutate the process-global ElementTree namespace table. The ordinary
# sheet renderer uses unqualified tags and its own xmlns declaration.
S = ""


def _round_grid(value: int, module: int) -> int:
    return ((value + module - 1) // module) * module


def _width(box: Box) -> int:
    return box.max_x - box.min_x


def _height(box: Box) -> int:
    return box.max_y - box.min_y


def _inverse(transform: Transform, p: Point) -> Point:
    """Exact integer inverse of discrete transform; no pin rounding."""
    x, y = p.x, p.y
    if transform.rotation == 90:
        x, y = y, -x
    elif transform.rotation == 180:
        x, y = -x, -y
    elif transform.rotation == 270:
        x, y = -y, x
    if transform.mirror_x:
        x = -x
    return Point(x, y)


class IcOrientation(str, Enum):
    """Physical port-side profile, independent of text rotation and body ratio."""

    LEFT_RIGHT = "left_right"
    TOP_BOTTOM = "top_bottom"  # ГОСТ 2.743-91 fig.3 / 2.759-82 §1.8


class IcTypographyProfile(str, Enum):
    """Explicitly versioned, non-normative renderer presentation profiles."""

    LEGACY_V1 = "legacy_v1"
    PORTRAIT_FUNCTION_V2_DRAFT = "portrait_function_v2_draft"
    TL494_PORTRAIT_V3_DRAFT = "tl494_portrait_v3_draft"


class IcFunctionReading(str, Enum):
    """Whole-word text direction in SVG's y-positive-down coordinates."""

    HORIZONTAL = "horizontal"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"

    @property
    def degrees(self) -> int:
        return {
            IcFunctionReading.HORIZONTAL: 0,
            IcFunctionReading.TOP_TO_BOTTOM: 90,
            IcFunctionReading.BOTTOM_TO_TOP: 270,
        }[self]


@dataclass(frozen=True, slots=True)
class IcRenderingPolicy:
    """Configurable editorial drawing dimensions, pending #91 source audit."""

    module_um: int = 2500
    pitch_modules: int = 2
    ink_padding_um: int = 1000
    line_width_um: int = 300
    lead_length_um: int = 8000
    main_min_width_um: int = 15000
    refdes_gap_um: int = 1600

    def __post_init__(self) -> None:
        items = (
            self.module_um, self.pitch_modules, self.ink_padding_um,
            self.line_width_um, self.lead_length_um,
            self.main_min_width_um, self.refdes_gap_um,
        )
        if any(type(x) is not int or x <= 0 for x in items):
            raise ValueError("IC_POLICY_INVALID: all dimensions must be positive")
        if self.lead_length_um < 2 * self.ink_padding_um:
            raise ValueError("IC_POLICY_INVALID: lead too short for numbers")


@dataclass(frozen=True, slots=True)
class ResolvedIcPin:
    """A physical resolved pin, NOT a speculative local electrical pin."""

    pin_id: str
    number: str
    label: str
    side: Side
    row: int
    anchor: Point  # AUTHORITATIVE WORLD external end of physical lead
    role: str = "passive"
    row_key: str | None = None  # shared logical group; not a graphic row index
    display_alias: str | None = None  # source-authoritative visible name

    @property
    def visible_label(self) -> str:
        return self.display_alias if self.display_alias is not None else self.label

    def __post_init__(self) -> None:
        if not self.pin_id or not self.number.strip():
            raise ValueError("IC_PIN_ID_MISSING")
        if not isinstance(self.side, Side) or not isinstance(self.anchor, Point):
            raise TypeError("IC_PIN_TYPED_SIDE_ANCHOR_REQUIRED")
        if type(self.row) is not int or self.row < 1:
            raise ValueError("IC_PIN_ROW_INVALID: row zero is function-only")
        if self.role not in ("in", "out", "bidir", "passive", "power", "nc"):
            raise ValueError("IC_PIN_ROLE_INVALID")
        if self.display_alias is not None and (
            not isinstance(self.display_alias, str)
            or not self.display_alias.strip()
            or "\n" in self.display_alias or "\r" in self.display_alias
        ):
            raise ValueError("IC_PIN_ALIAS_INVALID")


@dataclass(frozen=True, slots=True)
class IcFieldContent:
    function: str
    main_rows: tuple[str, ...] = ()
    left_rows: tuple[str, ...] = ()
    right_rows: tuple[str, ...] = ()
    left_zone_after: tuple[int, ...] = ()
    right_zone_after: tuple[int, ...] = ()
    analog: bool = False

    def __post_init__(self) -> None:
        if not self.function.strip():
            raise ValueError("IC_FUNCTION_REQUIRED")
        for text in (self.function, *self.main_rows, *self.left_rows, *self.right_rows):
            if "\n" in text or "\r" in text:
                raise ValueError("IC_TEXT_NEWLINE: use declared separate rows")
        if any(type(x) is not int or x < 0 for x in
               (*self.left_zone_after, *self.right_zone_after)):
            raise ValueError("IC_ZONE_ROW_INVALID")


@dataclass(frozen=True, slots=True)
class IcProposedSize:
    main_width_um: int
    left_width_um: int
    right_width_um: int
    height_um: int
    row_pitch_um: int
    row_count: int
    lead_length_um: int
    module_um: int
    body_width_um: int | None = None
    vertical_field_heights_um: tuple[int, int, int] = (0, 0, 0)
    function_row_span: int = 1

    @property
    def width_um(self) -> int:
        return (self.body_width_um if self.body_width_um is not None
                else self.left_width_um + self.main_width_um + self.right_width_um)


@dataclass(frozen=True, slots=True)
class IcResolvedUnit:
    reference: str
    body: Box  # LOCAL untransformed field enclosure, chosen by model/owner
    pins: tuple[ResolvedIcPin, ...]  # World connector anchors are FINAL
    content: IcFieldContent
    origin: Point = field(default_factory=lambda: Point(0, 0))
    transform: Transform = field(default_factory=Transform)
    orientation: IcOrientation = IcOrientation.LEFT_RIGHT
    function_rotation: int | None = None
    field_text_rotation: int = 0
    typography_profile: IcTypographyProfile = IcTypographyProfile.LEGACY_V1
    function_text_reading: IcFunctionReading | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.orientation, IcOrientation):
            raise TypeError("IC_ORIENTATION_TYPED_REQUIRED")
        if not isinstance(self.typography_profile, IcTypographyProfile):
            raise TypeError("IC_TYPOGRAPHY_PROFILE_TYPED_REQUIRED")
        if (self.function_text_reading is not None
                and not isinstance(self.function_text_reading, IcFunctionReading)):
            raise TypeError("IC_FUNCTION_READING_TYPED_REQUIRED")
        if self.function_rotation is None:
            default_rotation = (
                self.function_text_reading.degrees
                if self.function_text_reading is not None else
                270 if self.typography_profile is
                IcTypographyProfile.TL494_PORTRAIT_V3_DRAFT else
                90 if self.typography_profile is
                IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT else 0
            )
            object.__setattr__(self, "function_rotation", default_rotation)
        if (type(self.function_rotation) is not int
                or self.function_rotation not in (0, 90, 270)
                or type(self.field_text_rotation) is not int
                or self.field_text_rotation not in (0, 90)):
            raise ValueError("IC_TEXT_ROTATION_UNVERIFIED: only 0/90/270")
        if (self.function_text_reading is not None
                and self.function_text_reading.degrees != self.function_rotation):
            raise ValueError("IC_FUNCTION_READING_ROTATION_CONFLICT")
        if self.orientation is IcOrientation.LEFT_RIGHT and self.field_text_rotation:
            raise ValueError("IC_FIELD_ROTATION_REQUIRES_TOP_BOTTOM_PROFILE")
        if not self.reference:
            raise ValueError("IC_REFERENCE_REQUIRED")
        if self.typography_profile is IcTypographyProfile.TL494_PORTRAIT_V3_DRAFT:
            labels = [pin.visible_label for pin in self.pins]
            if any(len(label) > 6 for label in labels):
                raise ValueError("IC_VISIBLE_PIN_ALIAS_OVER_6")
            if len(set(labels)) != len(labels):
                raise ValueError("IC_VISIBLE_PIN_ALIAS_DUPLICATE")
        if len({p.pin_id for p in self.pins}) != len(self.pins):
            raise ValueError("IC_DUPLICATE_PIN_ID")
        if len({p.number for p in self.pins}) != len(self.pins):
            raise ValueError("IC_DUPLICATE_PHYSICAL_NUMBER")
        if len({p.anchor for p in self.pins}) != len(self.pins):
            raise ValueError("IC_DUPLICATE_RESOLVED_ANCHOR")
        if len({(p.side, p.row) for p in self.pins}) != len(self.pins):
            raise ValueError("IC_DUPLICATE_PIN_ROW")
        input_side = (Side.LEFT if self.orientation is IcOrientation.LEFT_RIGHT
                      else Side.TOP)
        output_side = (Side.RIGHT if self.orientation is IcOrientation.LEFT_RIGHT
                       else Side.BOTTOM)
        if any(p.role == "in" and p.side != input_side for p in self.pins):
            raise ValueError("IC_NONSTANDARD_INPUT_SIDE: rejected by active orientation")
        if any(p.role == "out" and p.side != output_side for p in self.pins):
            raise ValueError("IC_NONSTANDARD_OUTPUT_SIDE: rejected by active orientation")
        allowed = ({Side.LEFT, Side.RIGHT} if self.orientation is IcOrientation.LEFT_RIGHT
                   else {Side.TOP, Side.BOTTOM})
        if any(p.side not in allowed for p in self.pins):
            if self.orientation is IcOrientation.LEFT_RIGHT:
                raise ValueError(
                    "IC_UNSUPPORTED_VERTICAL_PORT: choose explicit TOP_BOTTOM profile"
                )
            raise ValueError("IC_MIXED_SIDE_PROFILE: requires source-specific ESKD card")

    def select_typography_profile(
        self, profile: IcTypographyProfile,
    ) -> "IcResolvedUnit":
        """Explicit UI-facing profile selection with its versioned defaults.

        dataclasses.replace by itself intentionally retains a previously
        authored rotation. Choosing a NEW profile resets that choice to the
        new profile default; only text settings change.
        """
        return replace(
            self, typography_profile=profile, function_rotation=None,
            function_text_reading=None,
        )

    def select_function_text_reading(
        self, reading: IcFunctionReading,
    ) -> "IcResolvedUnit":
        """Change only text direction; physical wire anchors remain immutable."""
        if not isinstance(reading, IcFunctionReading):
            raise TypeError("IC_FUNCTION_READING_TYPED_REQUIRED")
        return replace(
            self, function_rotation=reading.degrees,
            function_text_reading=reading,
        )


@dataclass(frozen=True, slots=True)
class IcInkBox:
    owner: str
    kind: str
    box: Box
    text: str = ""


@dataclass(frozen=True, slots=True)
class IcRendered:
    svg: str
    proposed: IcProposedSize
    body_world: Box
    ink: tuple[IcInkBox, ...]
    font_sha256: str | None
    pin_anchors: tuple[tuple[str, Point], ...]  # exact external ends
    glyph_ink: tuple["IcGlyphBox", ...] = ()
    connection_targets: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class IcGlyphBox:
    owner: str
    index: int
    char: str
    ink: Box


def _true_glyph_boxes(
    owner: str, text: str, baseline: Point, style: TextStyle,
) -> tuple[IcGlyphBox, ...]:
    """Kerning-aware FreeType individual visible glyph bounds in micrometres.

    Full rendered text-run ink remains authoritative for collision handling;
    per-codepoint boxes are conservative diagnostic evidence (glyph shaping
    may combine clusters in other fonts, so never use their sum as width).
    """
    from gost_schematic.engines.annotation.metrics import _PIXELS_PER_EM, _load_font

    font = _load_font(style.font_path)
    scale = style.em_height_um / _PIXELS_PER_EM
    result = []
    for index, char in enumerate(text):
        left, top, right, bottom = font.getbbox(char, anchor="ls")
        if left >= right or top >= bottom:
            continue
        kerned_x = font.getlength(text[:index]) * scale
        region = Box(
            baseline.x + floor(kerned_x + left * scale),
            baseline.y + floor(top * scale),
            baseline.x + ceil(kerned_x + right * scale),
            baseline.y + ceil(bottom * scale),
        )
        result.append(IcGlyphBox(owner, index, char, region))
    return tuple(result)


def _measure(text: str, style: TextStyle, measure: TextMeasurer) -> Box:
    return measure.measure(text, style).ink_box


def _occupied_side_rows(
    rows: tuple[str, ...], pins: tuple[ResolvedIcPin, ...],
    side: Side,
) -> tuple[str, ...]:
    result = list(rows)
    for pin in pins:
        if pin.side != side or not pin.visible_label:
            continue
        while len(result) <= pin.row:
            result.append("")
        if result[pin.row] and result[pin.row] != pin.visible_label:
            raise ValueError(f"IC_TEXT_OVERFLOW: conflict {side.value} row {pin.row}")
        result[pin.row] = pin.visible_label
    return tuple(result)


def propose_ic_dimensions(
    content: IcFieldContent,
    pins: tuple[ResolvedIcPin, ...],
    style: TextStyle,
    measurer: TextMeasurer,
    policy: IcRenderingPolicy = IcRenderingPolicy(),
    *,
    orientation: IcOrientation = IcOrientation.LEFT_RIGHT,
    function_rotation: int = 0,
    shared_function_envelope: bool = False,
) -> IcProposedSize:
    """Minimum grid-rounded box computed exclusively from real glyph ink.

    Pins are examined for text/row demands, but their anchor Point is NEVER
    altered or inferred by this sizing pass.
    """
    if function_rotation not in (0, 90, 270):
        raise ValueError("IC_TEXT_ROTATION_UNVERIFIED")
    if type(shared_function_envelope) is not bool:
        raise TypeError("IC_SHARED_FUNCTION_ENVELOPE_TYPED_REQUIRED")
    if orientation is IcOrientation.TOP_BOTTOM:
        from gost_schematic.rendering.ic_orientation import vertical_proposal

        if any(p.side not in (Side.TOP, Side.BOTTOM) for p in pins):
            raise ValueError("IC_MIXED_SIDE_PROFILE: vertical proposal")
        max_col = max((p.row for p in pins), default=0)
        virtual = tuple(replace(
            p, side=Side.LEFT if p.side is Side.TOP else Side.RIGHT,
            row=max_col + 1 - p.row,
        ) for p in pins)
        return vertical_proposal(propose_ic_dimensions(
            content, virtual, style, measurer, policy,
        ))
    if orientation is not IcOrientation.LEFT_RIGHT:
        raise ValueError("IC_ORIENTATION_UNSUPPORTED")
    left = _occupied_side_rows(content.left_rows, pins, Side.LEFT)
    right = _occupied_side_rows(content.right_rows, pins, Side.RIGHT)
    main = (content.function, *content.main_rows)
    nonempty = tuple(x for x in (*main, *left, *right) if x)
    dimensions = tuple(_measure(x, style, measurer) for x in nonempty)
    function_ink = _measure(content.function, style, measurer)
    # A 90-degree word consumes vertical rows, NOT a huge single row pitch.
    horizontal_inks = (
        dimensions[1:]
        if function_rotation in (90, 270) or shared_function_envelope
        else dimensions
    )
    tallest = max(
        (_height(b) for b in horizontal_inks),
        default=_height(function_ink),
    )
    pitch = _round_grid(max(
        policy.module_um * policy.pitch_modules,
        tallest + 2 * policy.ink_padding_um + policy.line_width_um,
    ), policy.module_um)
    # In the experimental portrait profile the accepted geometry must hold
    # both angles at any D4 pose. Under a 90/270 body pose, an upright word
    # extends along the page's X axis while the function cell spans local Y.
    # Reserve that span in BOTH render passes; never reposition physical pins.
    function_span = (
        max(1, ceil((_width(function_ink) + 2 * policy.ink_padding_um
                     + policy.line_width_um) / pitch))
        if function_rotation in (90, 270) or shared_function_envelope else 1
    )
    max_row = max((p.row for p in pins), default=0)
    nrows = max(
        2, function_span + len(content.main_rows), len(left), len(right),
        max_row + 1,
    )
    def width(strings: tuple[str, ...], mandatory: bool = False) -> int:
        occupied = tuple(t for t in strings if t)
        if not occupied and not mandatory:
            return 0
        widths = (
            max(_height(function_ink), _width(function_ink))
            if shared_function_envelope else
            _height(function_ink) if function_rotation in (90, 270) else
            _width(function_ink),
        ) if mandatory else ()
        maxink = max((
            *widths, *(
                _width(_measure(t, style, measurer))
                for t in (strings[1:] if mandatory else strings) if t
            ),
        ), default=0)
        minimum = policy.main_min_width_um if mandatory else policy.module_um
        return _round_grid(
            max(minimum, maxink + 2 * policy.ink_padding_um + policy.line_width_um),
            policy.module_um,
        )
    longest_number = max(
        (_width(_measure(p.number, style, measurer)) for p in pins), default=0,
    )
    leads = _round_grid(
        max(policy.lead_length_um, longest_number + 2 * policy.ink_padding_um),
        policy.module_um,
    )
    return IcProposedSize(
        width(main, True), width(left), width(right),
        nrows * pitch, pitch, nrows, leads, policy.module_um,
        function_row_span=function_span,
    )


def _text_placement(
    owner: str, text: str, cell: Box, horizontal: str,
    style: TextStyle, measurer: TextMeasurer, policy: IcRenderingPolicy,
    kind: str,
) -> tuple[IcInkBox, Point]:
    bounds = _measure(text, style, measurer)
    if horizontal == "left":
        left = cell.min_x + policy.ink_padding_um
    elif horizontal == "right":
        left = cell.max_x - policy.ink_padding_um - _width(bounds)
    else:
        left = (cell.min_x + cell.max_x - _width(bounds)) // 2
    top = (cell.min_y + cell.max_y - _height(bounds)) // 2
    ink = Box(left, top, left + _width(bounds), top + _height(bounds))
    if not (
        cell.min_x + policy.ink_padding_um <= ink.min_x
        and ink.max_x <= cell.max_x - policy.ink_padding_um
        and cell.min_y + policy.ink_padding_um <= ink.min_y
        and ink.max_y <= cell.max_y - policy.ink_padding_um
    ):
        raise ValueError(f"IC_TEXT_OVERFLOW: {owner} {kind} text={text!r}")
    return IcInkBox(owner, kind, ink, text), Point(
        left - bounds.min_x, top - bounds.min_y,
    )


def _rotated_function_placement(
    owner: str, text: str, cell: Box, style: TextStyle,
    measurer: TextMeasurer, policy: IcRenderingPolicy,
    rotation: int = 90,
) -> tuple[IcInkBox, Point]:
    """Rotate the WHOLE measured word around its baseline, then fit its ink.

    The returned baseline is in local micrometres; no individual letters are
    reflowed. Stroke spacing is checked against the transformed word bounds.
    """
    if rotation not in (90, 270):
        raise ValueError("IC_FUNCTION_ROTATED_DIRECTION_INVALID")
    rotated = Transform(rotation).box(_measure(text, style, measurer))
    left = (cell.min_x + cell.max_x - _width(rotated)) // 2
    top = (cell.min_y + cell.max_y - _height(rotated)) // 2
    ink = Box(left, top, left + _width(rotated), top + _height(rotated))
    p = policy.ink_padding_um
    if not (
        cell.min_x + p <= ink.min_x and ink.max_x <= cell.max_x - p
        and cell.min_y + p <= ink.min_y and ink.max_y <= cell.max_y - p
    ):
        raise ValueError(
            f"IC_TEXT_OVERFLOW: {owner} rotated function {text!r}; "
            "request a NEW authoritative IcSymbolSpec revision from ELEKTRIK"
        )
    return IcInkBox(owner, "function", ink, text), Point(
        left - rotated.min_x, top - rotated.min_y,
    )


def _line_ink(a: Point, b: Point, thickness: int) -> Box:
    d = (thickness + 1) // 2
    return Box(
        min(a.x, b.x) - d, min(a.y, b.y) - d,
        max(a.x, b.x) + d + 1, max(a.y, b.y) + d + 1,
    )


def _ink_intersects(a: Box, b: Box, separation: int) -> bool:
    return a.expanded(separation).overlaps(b)


def _svg_orthogonal_matrix(t: Transform, origin: Point) -> str:
    """Apply the same exact orthogonal transform to text that geometry uses."""
    u = t.apply(Point(1, 0))
    v = t.apply(Point(0, 1))
    return "matrix(" + " ".join((
        str(u.x), str(u.y), str(v.x), str(v.y),
        format_mm(origin.x), format_mm(origin.y),
    )) + ")"


def render_resolved_ic(
    unit: IcResolvedUnit,
    style: TextStyle,
    measurer: TextMeasurer,
    *,
    policy: IcRenderingPolicy = IcRenderingPolicy(),
    page_bounds: Box | None = None,
    other_obstacles: tuple[Box, ...] = (),
    review_overlay: bool = False,
    glyph_detail: bool = False,
    _rotate_function: bool = False,
    _rotate_fields: bool = False,
    _vertical_internal: bool = False,
    editor_targets: tuple[object, ...] = (),
    editor_overlay: bool = False,
    power_profile: object | None = None,
) -> IcRendered:
    """Fail closed if authoritative pin positions differ from the geometry.

    This is a read-only physical E3 SVG adapter. No model or PinRef mutation.
    """
    from gost_schematic.rendering.ic_hotspots import verify_ic_connection_targets

    # A logical drawing section "DD1.2" is still the physical component
    # "DD1"; reject PinRef("FOREIGN", same number/Point), never infer a Net.
    physical_ref, dot, suffix = unit.reference.rpartition(".")
    physical_ref = (
        physical_ref if dot and suffix.isdecimal() else unit.reference
    )
    targets = verify_ic_connection_targets(
        unit.pins, editor_targets, expected_component_ref=physical_ref,
    )
    power_audit = None
    if power_profile is not None:
        from gost_schematic.rendering.ic_power_profiles import (
            IcPowerLayout,
            verify_ic_power_profile,
        )

        power_audit = verify_ic_power_profile(unit, power_profile)
        if power_audit.layout is IcPowerLayout.COMMON_CONTROL_BLOCK:
            raise ValueError(
                "IC_POWER_CONTROL_OUTLINE_SOURCE_REQUIRED: "
                "source-authored fig6a contour is not an ordinary IC box"
            )
        if power_audit.layout is IcPowerLayout.FREE_SHEET_TEXT:
            raise ValueError(
                "IC_POWER_SHEET_TEXT_SOURCE_REQUIRED: "
                "do not invent a free-sheet supply note or a power connection"
            )
    if editor_overlay and not targets:
        raise ValueError("IC_EDITOR_OVERLAY_REQUIRES_EXPLICIT_TARGET_METADATA")
    if unit.orientation is IcOrientation.TOP_BOTTOM:
        from gost_schematic.rendering.ic_orientation import (
            vertical_as_canonical,
            vertical_proposal,
        )

        virtual = vertical_as_canonical(unit)
        canon = propose_ic_dimensions(
            virtual.content, virtual.pins, style, measurer, policy,
        )
        if (
            _width(unit.body) < canon.height_um
            or _height(unit.body) < canon.width_um
        ):
            raise ValueError(
                f"IC_TEXT_OVERFLOW: {unit.reference} vertical body "
                f"{_width(unit.body)}x{_height(unit.body)} um, "
                f"minimum {canon.height_um}x{canon.width_um} um"
            )
        result = render_resolved_ic(
            virtual, style, measurer,
            policy=policy, page_bounds=page_bounds,
            other_obstacles=other_obstacles,
            review_overlay=review_overlay, glyph_detail=glyph_detail,
            _rotate_function=bool(unit.function_rotation),
            _rotate_fields=bool(unit.field_text_rotation),
            _vertical_internal=True,
            editor_targets=editor_targets, editor_overlay=editor_overlay,
        )
        # The input has already been source-verified. The private rotated
        # canonical view may have different local physical power-pin sides;
        # never try to reclassify electrical PinRefs inside that view.
        if power_audit is not None:
            from xml.etree import ElementTree as _ET

            root = _ET.fromstring(result.svg)
            root.set("data-power-layout", power_audit.layout.value)
            root.set("data-power-normative", power_audit.normative_status)
            return replace(
                result,
                proposed=vertical_proposal(canon),
                svg=_ET.tostring(root, encoding="unicode") + "\n",
            )
        return replace(result, proposed=vertical_proposal(canon))
    proposed = propose_ic_dimensions(
        unit.content, unit.pins, style, measurer, policy,
        function_rotation=unit.function_rotation,
        shared_function_envelope=(
            unit.typography_profile in (
                IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
                IcTypographyProfile.TL494_PORTRAIT_V3_DRAFT,
            )
        ),
    )
    body = unit.body
    if (unit.typography_profile in (
            IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
            IcTypographyProfile.TL494_PORTRAIT_V3_DRAFT,
    ) and _height(body) <= _width(body)):
        raise ValueError(
            f"IC_PORTRAIT_BODY_REQUIRED: {unit.reference} needs height > width; "
            "request an explicit revised geometry from ELEKTRIK"
        )
    if _width(body) < proposed.width_um or _height(body) < proposed.height_um:
        raise ValueError(
            f"IC_TEXT_OVERFLOW: {unit.reference} body "
            f"{_width(body)}x{_height(body)} um < measured minimum "
            f"{proposed.width_um}x{proposed.height_um} um"
        )
    if (body.min_x % proposed.module_um or body.min_y % proposed.module_um
            or _width(body) % proposed.module_um
            or _height(body) % proposed.module_um):
        raise ValueError("IC_GRID_MISMATCH: body violates selected editorial module")
    width = _width(body)
    left_x = body.min_x + proposed.left_width_um
    right_x = body.max_x - proposed.right_width_um
    if right_x - left_x < proposed.main_width_um:
        raise ValueError("IC_TEXT_OVERFLOW: main field became too narrow")
    pitch = proposed.row_pitch_um
    if _height(body) % pitch:
        raise ValueError("IC_GRID_MISMATCH: height must preserve text/pin row pitch")
    row_count = _height(body) // pitch
    ranges = {
        "main": Box(left_x, body.min_y, right_x, body.max_y),
    }
    if proposed.left_width_um:
        ranges["left"] = Box(body.min_x, body.min_y, left_x, body.max_y)
    if proposed.right_width_um:
        ranges["right"] = Box(right_x, body.min_y, body.max_x, body.max_y)
    def world(p: Point) -> Point:
        return unit.transform.apply(p) + unit.origin
    def worldbox(b: Box) -> Box:
        return unit.transform.box(b).translated(unit.origin)
    actual_body = worldbox(body)
    frame = IcInkBox(unit.reference, "outer-frame", actual_body.expanded(
        (policy.line_width_um + 1) // 2,
    ))
    # Frame is protected in ink validation; its AABB is a coarse envelope,
    # so use stroke-only edge segments for actual interior text checks.
    strokes: list[IcInkBox] = []
    def stroke(a: Point, b: Point, key: str, kind: str) -> None:
        strokes.append(IcInkBox(
            key, kind, _line_ink(a, b, policy.line_width_um),
        ))
    corners = [
        world(Point(body.min_x, body.min_y)),
        world(Point(body.max_x, body.min_y)),
        world(Point(body.max_x, body.max_y)),
        world(Point(body.min_x, body.max_y)),
    ]
    for i in range(4):
        stroke(corners[i], corners[(i+1) % 4], f"frame{i}", "outer-stroke")
    for key, x in (("left", left_x), ("right", right_x)):
        if key in ranges:
            stroke(world(Point(x, body.min_y)),
                   world(Point(x, body.max_y)), key, "field-divider")
    for name, values in (
        ("left", unit.content.left_zone_after),
        ("right", unit.content.right_zone_after),
    ):
        for index in values:
            if index >= row_count - 1 or name not in ranges:
                raise ValueError(f"IC_ZONE_ROW_INVALID: {name} {index}")
            fieldbox = ranges[name]
            y = body.min_y + (index + 1) * pitch
            stroke(world(Point(fieldbox.min_x, y)),
                   world(Point(fieldbox.max_x, y)),
                   f"{name}zone{index}", "zone-divider")
    # All world pin anchors are compared to exact transformed LOCAL expected
    # intersections; no epsilon/rounding adjustment is permitted.
    pin_leads: list[tuple[ResolvedIcPin, Point]] = []
    for pin in unit.pins:
        if pin.row >= row_count:
            raise ValueError(f"IC_PIN_ROW_OVERFLOW: {pin.pin_id}")
        local_y = body.min_y + (pin.row * pitch + pitch // 2)
        local_x = body.min_x if pin.side == Side.LEFT else (
            body.max_x if pin.side == Side.RIGHT else
            body.min_x + _width(body) // 2
        )
        if pin.side in (Side.TOP, Side.BOTTOM):
            # Vertical pin row is not an electrical grid index; an owner must
            # supply a separate explicit x coordinate/semantic ESKD profile.
            raise ValueError("IC_UNSUPPORTED_VERTICAL_PORT: ESKD policy required")
        frame_point = world(Point(local_x, local_y))
        outward = unit.transform.side(pin.side)
        vector = SIDE_VECTORS[outward]
        expected = Point(
            frame_point.x + vector.x * proposed.lead_length_um,
            frame_point.y + vector.y * proposed.lead_length_um,
        )
        if expected != pin.anchor:
            raise ValueError(
                f"IC_PIN_ANCHOR_MISMATCH: {pin.pin_id} exact external "
                f"endpoint expected {expected}, model supplied {pin.anchor}"
            )
        pin_leads.append((pin, frame_point))
        stroke(frame_point, pin.anchor, pin.pin_id, "pin-lead")
    # Third field is an optional SVG matrix for ink rotated with the symbol.
    # External physical numbers and the reference ALWAYS stay upright.
    texts: list[tuple[IcInkBox, Point, str | None]] = []
    rotated_function_baselines: dict[str, Point] = {}
    matrix = _svg_orthogonal_matrix(unit.transform, unit.origin)

    def add(text: str, cell: Box, owner: str, kind: str,
            align: str = "center") -> None:
        if not text:
            return
        follow = (
            _rotate_function if kind == "function" else (
                _rotate_fields or (
                    unit.typography_profile in (
                        IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
                        IcTypographyProfile.TL494_PORTRAIT_V3_DRAFT,
                    )
                    and unit.transform.rotation in (90, 270)
                )
            )
        )
        if (kind == "function" and unit.function_rotation in (90, 270)
                and not _vertical_internal):
            from gost_schematic.rendering.ic_orientation import compose_transforms

            local, baseline = _rotated_function_placement(
                owner, text, cell, style, measurer, policy,
                rotation=unit.function_rotation,
            )
            rotated_function_baselines[owner] = baseline
            word_pose = compose_transforms(
                unit.transform, Transform(unit.function_rotation),
            )
            texts.append((
                IcInkBox(owner, kind, worldbox(local.box), text),
                Point(0, 0),
                _svg_orthogonal_matrix(word_pose, world(baseline)),
            ))
        elif follow:
            local, local_baseline = _text_placement(
                owner, text, cell, align, style, measurer, policy, kind,
            )
            texts.append((
                IcInkBox(owner, kind, worldbox(local.box), text),
                local_baseline, matrix,
            ))
        else:
            a, baseline = _text_placement(
                owner, text, worldbox(cell), align,
                style, measurer, policy, kind,
            )
            texts.append((a, baseline, None))
    def row_box(fieldbox: Box, index: int) -> Box:
        return Box(fieldbox.min_x, body.min_y + index * pitch,
                   fieldbox.max_x, body.min_y + (index + 1) * pitch)
    add(
        unit.content.function,
        Box(
            ranges["main"].min_x, body.min_y, ranges["main"].max_x,
            body.min_y + proposed.function_row_span * pitch,
        ),
        "main.0", "function",
    )
    for index, line in enumerate(unit.content.main_rows):
        visual_row = proposed.function_row_span + index
        add(line, row_box(ranges["main"], visual_row),
            f"main.{index + 1}", "main-text")
    for side, raw in (
        (Side.LEFT, unit.content.left_rows),
        (Side.RIGHT, unit.content.right_rows),
    ):
        lines = _occupied_side_rows(raw, unit.pins, side)
        if not lines:
            continue
        box = ranges[side.value]
        for row, txt in enumerate(lines):
            add(txt, row_box(box, row),
                f"{side.value}.{row}", "pin-label" if any(
                    p.side == side and p.row == row and p.label
                    for p in unit.pins
                ) else "field-text")
    for pin, frame_point in pin_leads:
        # ГОСТ 2.743-91 §2.3.12: numbers ABOVE the connection line.
        # For vertical rotated leads the external left is a DRAFT editorial
        # analogue; source-specific ESKD approval still required.
        side = unit.transform.side(pin.side)
        n = _measure(pin.number, style, measurer)
        width, height = _width(n), _height(n)
        middle = Point((pin.anchor.x + frame_point.x) // 2,
                       (pin.anchor.y + frame_point.y) // 2)
        pad = policy.ink_padding_um + (policy.line_width_um + 1) // 2
        if side in (Side.LEFT, Side.RIGHT):
            box = Box(middle.x - width // 2,
                      middle.y - pad - height,
                      middle.x - width // 2 + width, middle.y - pad)
        else:
            box = Box(middle.x - pad - width, middle.y - height // 2,
                      middle.x - pad, middle.y - height // 2 + height)
        baseline = Point(box.min_x - n.min_x, box.min_y - n.min_y)
        texts.append((IcInkBox(pin.pin_id, "pin-number", box, pin.number), baseline, None))
    # Refdes is separate from actual IC rectangle; fail on collision rather
    # than silently moving a component or shrinking the font.
    label = _measure(unit.reference, style, measurer)
    if (_vertical_internal or (
        unit.orientation is IcOrientation.LEFT_RIGHT
        and (unit.function_rotation in (90, 270) or
             unit.typography_profile in (
                 IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT,
                 IcTypographyProfile.TL494_PORTRAIT_V3_DRAFT,
             ))
    )):
        # Rotated function and D4 poses require reference placement on an
        # actually free WORLD perimeter side, never across the pin corridors.
        # Candidate sides must be in the same WORLD frame as transformed
        # physical leads. Never assume that paper "left" is a free side after
        # a D4 transform, and do not change any connection point to fit DA1.
        w, h, g = _width(label), _height(label), policy.refdes_gap_um
        cx = (actual_body.min_x + actual_body.max_x) // 2
        cy = (actual_body.min_y + actual_body.max_y) // 2
        choices = (
            (Side.LEFT, Box(actual_body.min_x-g-w,cy-h//2,
                            actual_body.min_x-g,cy-h//2+h)),
            (Side.RIGHT,Box(actual_body.max_x+g,cy-h//2,
                            actual_body.max_x+g+w,cy-h//2+h)),
            (Side.TOP,Box(cx-w//2,actual_body.min_y-g-h,
                          cx-w//2+w,actual_body.min_y-g)),
            (Side.BOTTOM,Box(cx-w//2,actual_body.max_y+g,
                             cx-w//2+w,actual_body.max_y+g+h)),
        )
        busy_sides = {unit.transform.side(p.side) for p in unit.pins}
        refbox = next((
            box for side, box in choices
            if side not in busy_sides
            and not any(_ink_intersects(box, edge.box, policy.ink_padding_um)
                        for edge in strokes)
            and not any(_ink_intersects(box, text.box, policy.ink_padding_um)
                        for text, _, _ in texts)
        ), None)
        if refbox is None:
            raise ValueError(
                f"IC_REFDES_UNPLACEABLE: {unit.reference} no free perimeter side"
            )
    else:
        refbox = Box(
            actual_body.min_x,
            actual_body.min_y - policy.refdes_gap_um - _height(label),
            actual_body.min_x + _width(label),
            actual_body.min_y - policy.refdes_gap_um,
        )
    texts.append((
        IcInkBox(unit.reference, "refdes", refbox, unit.reference),
        Point(refbox.min_x - label.min_x, refbox.min_y - label.min_y), None,
    ))
    ink = [i for i, _, _ in texts]
    for i, label_region in enumerate(ink):
        for stroke_region in strokes:
            if _ink_intersects(label_region.box, stroke_region.box,
                               policy.ink_padding_um):
                raise ValueError(
                    f"IC_INK_COLLISION: {label_region.owner}/{label_region.kind}"
                    f" intersects {stroke_region.owner}/{stroke_region.kind}"
                )
        for later in ink[i+1:]:
            if _ink_intersects(label_region.box, later.box,
                               policy.ink_padding_um):
                raise ValueError(
                    f"IC_INK_COLLISION: {label_region.owner} vs {later.owner}"
                )
    # A standalone glyph's FreeType bbox can differ from its shaped
    # run bbox because kerning and ligatures depend on neighbors. The full
    # measured run is authoritative; clamp per-codepoint review hints to it
    # instead of reporting false hard collisions from standalone glyph ink.
    glyph_list: list[IcGlyphBox] = []
    if glyph_detail:
        for parent, baseline, matrix_token in texts:
            for glyph in _true_glyph_boxes(
                parent.owner, parent.text, baseline, style,
            ):
                if parent.owner in rotated_function_baselines:
                    rotated_local = Transform(unit.function_rotation).box(
                        glyph.ink,
                    ).translated(
                        rotated_function_baselines[parent.owner]
                    )
                    candidate = worldbox(rotated_local)
                else:
                    candidate = (
                        worldbox(glyph.ink)
                        if matrix_token is not None else glyph.ink
                    )
                x1 = max(candidate.min_x, parent.box.min_x)
                y1 = max(candidate.min_y, parent.box.min_y)
                x2 = min(candidate.max_x, parent.box.max_x)
                y2 = min(candidate.max_y, parent.box.max_y)
                if x1 < x2 and y1 < y2:
                    glyph_list.append(replace(
                        glyph, ink=Box(x1, y1, x2, y2),
                    ))
    glyphs = tuple(glyph_list)
    for glyph in glyphs:
        for protected in strokes:
            if _ink_intersects(glyph.ink, protected.box, policy.ink_padding_um):
                raise ValueError(
                    f"IC_GLYPH_INK_COLLISION: {glyph.owner}[{glyph.index}]"
                )
    all_visible = (frame, *strokes, *ink)
    complete = enclosing_box(tuple(x.box for x in all_visible))
    if page_bounds is not None and not (
        page_bounds.min_x <= complete.min_x
        and page_bounds.min_y <= complete.min_y
        and complete.max_x <= page_bounds.max_x
        and complete.max_y <= page_bounds.max_y
    ):
        raise ValueError(
            f"IC_PAGE_OVERFLOW: {unit.reference} ink {complete} "
            f"outside {page_bounds}"
        )
    for forbidden in other_obstacles:
        if forbidden.overlaps(complete):
            raise ValueError(
                f"IC_OBSTACLE_COLLISION: {unit.reference} neighbouring geometry"
            )
    viewport = complete.expanded(2000)
    w, h = _width(viewport), _height(viewport)
    svg = ET.Element(S + "svg", {
        "xmlns": _SVG,
        "width": f"{format_mm(w)}mm",
        "height": f"{format_mm(h)}mm",
        "viewBox": " ".join(format_mm(x) for x in (
            viewport.min_x, viewport.min_y, w, h,
        )),
        "data-document-kind": "E3-physical-IC",
        "data-approval": "DRAFT",
        "data-font-sha256": style.font_sha256 or "unverified",
        "data-pin-anchor-authority": "external-resolved-only",
        "data-projected-grid-um": str(policy.module_um),
        "data-orientation": (
            "top_bottom" if _vertical_internal else "left_right"
        ),
        "data-function-text-with-symbol": str(_rotate_function).lower(),
        "data-field-text-with-symbol": str(_rotate_fields).lower(),
    })
    if unit.typography_profile is not IcTypographyProfile.LEGACY_V1:
        svg.set("data-typography-profile", unit.typography_profile.value)
    if power_audit is not None:
        svg.set("data-power-layout", power_audit.layout.value)
        svg.set("data-power-normative", power_audit.normative_status)
        svg.set("data-power-pinrefs", ",".join(
            f"{ref.reference}.{ref.number}"
            for ref in power_audit.physical_pinrefs
        ))
    reading = {
        0: IcFunctionReading.HORIZONTAL,
        90: IcFunctionReading.TOP_TO_BOTTOM,
        270: IcFunctionReading.BOTTOM_TO_TOP,
    }[unit.function_rotation]
    svg.set("data-function-reading-local", reading.value)
    if (unit.function_rotation in (90, 270) and not _vertical_internal):
        svg.set("data-function-rotation-deg", str(unit.function_rotation))
    ET.SubElement(svg, S + "title").text = (
        f"DRAFT physical E3 IC {unit.reference}; no electrical net inference"
    )
    graphics = ET.SubElement(svg, S + "g", {
        "data-layer": "ic-outline", "fill": "none",
        "stroke": "#000000",
        "stroke-width": format_mm(policy.line_width_um),
    })
    b = actual_body
    ET.SubElement(graphics, S + "rect", {
        "x": format_mm(b.min_x), "y": format_mm(b.min_y),
        "width": format_mm(_width(b)), "height": format_mm(_height(b)),
        "data-kind": "actual-stroked-outer-frame",
    })
    dividers = ET.SubElement(graphics, S + "g", {"data-layer": "ic-dividers"})
    for region in strokes:
        if region.kind not in ("field-divider", "zone-divider"):
            continue
        # Recreate exact intended stroke axis from conservative centered
        # hitbox. Width may be odd: reconstruct via center of AABB.
        box = region.box
        # For vertical/horizontal strokes a small dimension identifies axis.
        if _width(box) <= policy.line_width_um + 2:
            x1 = x2 = (box.min_x + box.max_x - 1) // 2
            y1, y2 = box.min_y + (policy.line_width_um+1)//2, (
                box.max_y - (policy.line_width_um+1)//2 - 1
            )
        else:
            y1 = y2 = (box.min_y + box.max_y - 1) // 2
            x1, x2 = box.min_x + (policy.line_width_um+1)//2, (
                box.max_x - (policy.line_width_um+1)//2 - 1
            )
        ET.SubElement(dividers, S + "line", {
            "x1": format_mm(x1), "y1": format_mm(y1),
            "x2": format_mm(x2), "y2": format_mm(y2),
            "data-kind": region.kind,
            "data-owner": region.owner,
        })
    leads = ET.SubElement(svg, S + "g", {
        "data-layer": "ic-physical-pin-leads", "fill": "none",
        "stroke": "#000000",
        "stroke-width": format_mm(policy.line_width_um),
    })
    for pin, frame_point in pin_leads:
        ET.SubElement(leads, S + "line", {
            "x1": format_mm(frame_point.x),
            "y1": format_mm(frame_point.y),
            "x2": format_mm(pin.anchor.x),
            "y2": format_mm(pin.anchor.y),
            "data-pin-id": pin.pin_id, "data-pin-number": pin.number,
            "data-role": pin.role,
            "data-real-anchor": "true",
        })
    pin_by_text_owner = {
        f"{pin.side.value}.{pin.row}": pin for pin in unit.pins
    }
    for region, baseline, matrix_token in texts:
        attrs = {
            "data-layer": "ic-text",
            "data-kind": region.kind,
            "data-owner": region.owner,
            "data-ink-um": ",".join(str(t) for t in (
                region.box.min_x, region.box.min_y,
                region.box.max_x, region.box.max_y,
            )),
            "x": format_mm(baseline.x), "y": format_mm(baseline.y),
            "font-family": style.font_family,
            "font-size": format_mm(style.em_height_um),
            "font-style": style.font_style,
            "fill": "#000000", "stroke": "none",
        }
        if region.kind == "pin-label" and region.owner in pin_by_text_owner:
            named = pin_by_text_owner[region.owner]
            attrs.update({
                "data-pin-id": named.pin_id,
                "data-physical-pin-number": named.number,
                "data-full-manufacturer-name": named.label,
                "data-visible-pin-alias": named.visible_label,
            })
        if matrix_token is not None:
            attrs["transform"] = matrix_token
        node = ET.SubElement(svg, S + "text", attrs)
        node.text = region.text
    if review_overlay:
        debug = ET.SubElement(svg, S + "g", {
            "data-layer": "ic-review-ink",
            "stroke": "#cc6600", "stroke-width": "0.09",
            "stroke-dasharray": "0.5 0.4", "fill": "none",
        })
        for region in (*strokes, *ink):
            b = region.box
            ET.SubElement(debug, S + "rect", {
                "x": format_mm(b.min_x), "y": format_mm(b.min_y),
                "width": format_mm(_width(b)), "height": format_mm(_height(b)),
                "data-owner": region.owner, "data-kind": region.kind,
            })
        if glyphs:
            glyph_layer = ET.SubElement(debug, S + "g", {
                "data-layer": "measured-individual-glyph-ink",
                "stroke": "#1358bc",
                "stroke-width": "0.08",
            })
            for glyph in glyphs:
                b = glyph.ink
                ET.SubElement(glyph_layer, S + "rect", {
                    "x": format_mm(b.min_x), "y": format_mm(b.min_y),
                    "width": format_mm(_width(b)),
                    "height": format_mm(_height(b)),
                    "data-owner": glyph.owner,
                    "data-index": str(glyph.index),
                })
    if editor_overlay:
        ui = ET.SubElement(svg, S + "g", {
            "data-layer": "editor-connection-targets",
            "data-editor-only": "true",
            "data-physical-print": "false",
        })
        pin_metadata = {pin.pin_id: pin for pin in unit.pins}
        for target in targets:
            physical_pin = pin_metadata[target.pin_id]
            # Pure diagnostic glyph in physical SVG millimetres. The FUTURE
            # interactive editor must instead hit-test a CSS-pixel radius.
            at = target.anchor
            ET.SubElement(ui, S + "rect", {
                "x": format_mm(at.x - 350), "y": format_mm(at.y - 350),
                "width": "0.7", "height": "0.7",
                "fill": "#148645" if target.connectable else "#8b1e27",
                "stroke": "#000", "stroke-width": "0.07",
                "data-pin-ref": (
                    f"{target.pin_ref.reference}.{target.pin_ref.number}"
                ),
                "data-pin-id": target.pin_id,
                "data-pin-number": target.pin_ref.number,
                "data-pin-role": physical_pin.role,
                "data-external-anchor-x-um": str(at.x),
                "data-external-anchor-y-um": str(at.y),
                "data-net-id": target.net_id or "",
                "data-connectable": str(target.connectable).lower(),
                "data-reason": target.reason or "",
            })
    return IcRendered(
        ET.tostring(svg, encoding="unicode") + "\n",
        proposed, actual_body, (*strokes, *ink),
        style.font_sha256,
        tuple((pin.pin_id, pin.anchor) for pin in unit.pins),
        glyphs,
        targets,
    )
