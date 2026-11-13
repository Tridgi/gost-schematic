"""DRAFT rectangular E3 IC rendering, measured typography and immutable port anchors.

ГОСТ 2.743-91 §§2.1.1–2.1.9, 2.3.12; analog profile subject to
ГОСТ 2.759-82/ESKD Issue #91 acceptance. Project mm grid, padding and
lead lengths are editorial settings, not asserted mandatory GOST figures.

Two independent phases:
  propose_ic_dimensions -> suggested layout dimensions, changes no pins.
  render_resolved_ic -> validates and uses exact externally RESOLVED pins.
Never use E1 FunctionalBlock, physical footprint or electrical net inference.
"""
from dataclasses import dataclass, field
from math import ceil
from xml.etree import ElementTree as ET

from gost_schematic.core.geometry import (
    Box, Line, Point, Side, SIDE_VECTORS, enclosing_box,
)
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import format_mm
from gost_schematic.engines.annotation.metrics import TextMeasurer
from gost_schematic.model.annotations import TextStyle

_SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", _SVG)
S = "{" + _SVG + "}"


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


@dataclass(frozen=True, slots=True)
class IcRenderingPolicy:
    """Configurable editorial drawing dimensions, pending #91 source audit."""

    module_um: int = 2500
    pitch_modules: int = 2
    ink_padding_um: int = 500
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
    anchor: Point  # AUTHORITATIVE resolved WORLD connector point
    role: str = "passive"

    def __post_init__(self) -> None:
        if not self.pin_id or not self.number.strip():
            raise ValueError("IC_PIN_ID_MISSING")
        if not isinstance(self.side, Side) or not isinstance(self.anchor, Point):
            raise TypeError("IC_PIN_TYPED_SIDE_ANCHOR_REQUIRED")
        if type(self.row) is not int or self.row < 1:
            raise ValueError("IC_PIN_ROW_INVALID: row zero is function-only")
        if self.role not in ("in", "out", "bidir", "passive", "power", "nc"):
            raise ValueError("IC_PIN_ROLE_INVALID")


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

    @property
    def width_um(self) -> int:
        return self.left_width_um + self.main_width_um + self.right_width_um


@dataclass(frozen=True, slots=True)
class IcResolvedUnit:
    reference: str
    body: Box  # LOCAL untransformed field enclosure, chosen by model/owner
    pins: tuple[ResolvedIcPin, ...]  # World connector anchors are FINAL
    content: IcFieldContent
    origin: Point = field(default_factory=lambda: Point(0, 0))
    transform: Transform = field(default_factory=Transform)

    def __post_init__(self) -> None:
        if not self.reference:
            raise ValueError("IC_REFERENCE_REQUIRED")
        if len({p.pin_id for p in self.pins}) != len(self.pins):
            raise ValueError("IC_DUPLICATE_PIN_ID")
        if len({p.number for p in self.pins}) != len(self.pins):
            raise ValueError("IC_DUPLICATE_PHYSICAL_NUMBER")
        if len({p.anchor for p in self.pins}) != len(self.pins):
            raise ValueError("IC_DUPLICATE_RESOLVED_ANCHOR")
        if len({(p.side, p.row) for p in self.pins}) != len(self.pins):
            raise ValueError("IC_DUPLICATE_PIN_ROW")
        if any(p.role == "in" and p.side != Side.LEFT for p in self.pins):
            raise ValueError("IC_NONSTANDARD_INPUT_SIDE: needs separate profile")
        if any(p.role == "out" and p.side != Side.RIGHT for p in self.pins):
            raise ValueError("IC_NONSTANDARD_OUTPUT_SIDE: needs separate profile")


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
    pin_anchors: tuple[tuple[str, Point], ...]


def _measure(text: str, style: TextStyle, measure: TextMeasurer) -> Box:
    return measure.measure(text, style).ink_box


def _occupied_side_rows(
    rows: tuple[str, ...], pins: tuple[ResolvedIcPin, ...],
    side: Side,
) -> tuple[str, ...]:
    result = list(rows)
    for pin in pins:
        if pin.side != side or not pin.label:
            continue
        while len(result) <= pin.row:
            result.append("")
        if result[pin.row] and result[pin.row] != pin.label:
            raise ValueError(f"IC_TEXT_OVERFLOW: conflict {side.value} row {pin.row}")
        result[pin.row] = pin.label
    return tuple(result)


def propose_ic_dimensions(
    content: IcFieldContent,
    pins: tuple[ResolvedIcPin, ...],
    style: TextStyle,
    measurer: TextMeasurer,
    policy: IcRenderingPolicy = IcRenderingPolicy(),
) -> IcProposedSize:
    """Minimum grid-rounded box computed exclusively from real glyph ink.

    Pins are examined for text/row demands, but their anchor Point is NEVER
    altered or inferred by this sizing pass.
    """
    left = _occupied_side_rows(content.left_rows, pins, Side.LEFT)
    right = _occupied_side_rows(content.right_rows, pins, Side.RIGHT)
    main = (content.function, *content.main_rows)
    nonempty = tuple(x for x in (*main, *left, *right) if x)
    dimensions = tuple(_measure(x, style, measurer) for x in nonempty)
    tallest = max(_height(b) for b in dimensions)
    pitch = _round_grid(max(
        policy.module_um * policy.pitch_modules,
        tallest + 2 * policy.ink_padding_um + policy.line_width_um,
    ), policy.module_um)
    max_row = max((p.row for p in pins), default=0)
    nrows = max(2, len(main), len(left), len(right), max_row + 1)
    def width(strings: tuple[str, ...], mandatory: bool = False) -> int:
        occupied = tuple(t for t in strings if t)
        if not occupied and not mandatory:
            return 0
        maxink = max((_width(_measure(t, style, measurer)) for t in occupied), default=0)
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


def _line_ink(a: Point, b: Point, thickness: int) -> Box:
    d = (thickness + 1) // 2
    return Box(
        min(a.x, b.x) - d, min(a.y, b.y) - d,
        max(a.x, b.x) + d + 1, max(a.y, b.y) + d + 1,
    )


def _ink_intersects(a: Box, b: Box, separation: int) -> bool:
    return a.expanded(separation).overlaps(b)


def render_resolved_ic(
    unit: IcResolvedUnit,
    style: TextStyle,
    measurer: TextMeasurer,
    *,
    policy: IcRenderingPolicy = IcRenderingPolicy(),
    page_bounds: Box | None = None,
    other_obstacles: tuple[Box, ...] = (),
    review_overlay: bool = False,
) -> IcRendered:
    """Fail closed if authoritative pin positions differ from the geometry.

    This is a read-only physical E3 SVG adapter. No model or PinRef mutation.
    """
    proposed = propose_ic_dimensions(
        unit.content, unit.pins, style, measurer, policy,
    )
    body = unit.body
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
    obstacles: list[IcInkBox] = [frame]
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
        expected = world(Point(local_x, local_y))
        if expected != pin.anchor:
            raise ValueError(
                f"IC_PIN_ANCHOR_MISMATCH: {pin.pin_id} exact "
                f"expected {expected}, model supplied {pin.anchor}"
            )
        outward = unit.transform.side(pin.side)
        vector = SIDE_VECTORS[outward]
        lead = Point(
            pin.anchor.x + vector.x * proposed.lead_length_um,
            pin.anchor.y + vector.y * proposed.lead_length_um,
        )
        pin_leads.append((pin, lead))
        stroke(pin.anchor, lead, pin.pin_id, "pin-lead")
    texts: list[tuple[IcInkBox, Point]] = []
    def add(text: str, cell: Box, owner: str, kind: str,
            align: str = "center") -> None:
        if not text:
            return
        a, baseline = _text_placement(
            owner, text, worldbox(cell), align,
            style, measurer, policy, kind,
        )
        texts.append((a, baseline))
    def row_box(fieldbox: Box, index: int) -> Box:
        return Box(fieldbox.min_x, body.min_y + index * pitch,
                   fieldbox.max_x, body.min_y + (index + 1) * pitch)
    for index, line in enumerate(
        (unit.content.function, *unit.content.main_rows)
    ):
        add(line, row_box(ranges["main"], index),
            f"main.{index}", "function" if index == 0 else "main-text")
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
    for pin, lead in pin_leads:
        # ГОСТ 2.743-91 §2.3.12: numbers ABOVE the connection line.
        # For vertical rotated leads the external left is a DRAFT editorial
        # analogue; source-specific ESKD approval still required.
        side = unit.transform.side(pin.side)
        n = _measure(pin.number, style, measurer)
        width, height = _width(n), _height(n)
        middle = Point((pin.anchor.x + lead.x) // 2,
                       (pin.anchor.y + lead.y) // 2)
        pad = policy.ink_padding_um + (policy.line_width_um + 1) // 2
        if side in (Side.LEFT, Side.RIGHT):
            box = Box(middle.x - width // 2,
                      middle.y - pad - height,
                      middle.x - width // 2 + width, middle.y - pad)
        else:
            box = Box(middle.x - pad - width, middle.y - height // 2,
                      middle.x - pad, middle.y - height // 2 + height)
        baseline = Point(box.min_x - n.min_x, box.min_y - n.min_y)
        texts.append((IcInkBox(pin.pin_id, "pin-number", box, pin.number), baseline))
    # Refdes is separate from actual IC rectangle; fail on collision rather
    # than silently moving a component or shrinking the font.
    label = _measure(unit.reference, style, measurer)
    refbox = Box(actual_body.min_x,
                 actual_body.min_y - policy.refdes_gap_um - _height(label),
                 actual_body.min_x + _width(label),
                 actual_body.min_y - policy.refdes_gap_um)
    texts.append((IcInkBox(unit.reference, "refdes", refbox, unit.reference),
                  Point(refbox.min_x - label.min_x,
                        refbox.min_y - label.min_y)))
    ink = [i for i, _ in texts]
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
    })
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
    for pin, lead in pin_leads:
        ET.SubElement(leads, S + "line", {
            "x1": format_mm(pin.anchor.x), "y1": format_mm(pin.anchor.y),
            "x2": format_mm(lead.x), "y2": format_mm(lead.y),
            "data-pin-id": pin.pin_id, "data-pin-number": pin.number,
            "data-role": pin.role,
            "data-real-anchor": "true",
        })
    for region, baseline in texts:
        node = ET.SubElement(svg, S + "text", {
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
        })
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
    return IcRendered(
        ET.tostring(svg, encoding="unicode") + "\n",
        proposed, actual_body, tuple((*strokes, *ink)),
        style.font_sha256,
        tuple((pin.pin_id, pin.anchor) for pin in unit.pins),
    )
