"""Independent XML/geometry checks; a parseable SVG is NOT normative approval."""

from importlib.resources import files
from pathlib import Path
from random import Random
from xml.etree import ElementTree as ET

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import (
    Box,
    Circle,
    Line,
    Point,
    Rectangle,
    Semicircle,
    Side,
    StyledLine,
)
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import format_mm, mm
from gost_schematic.engines.sheet_layout import SheetLayout
from gost_schematic.model.annotations import AnnotationPlacement, AnnotationRole, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.rendering.svg import render_symbol_svg

_SVG = "{http://www.w3.org/2000/svg}"


def _symbols():
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    result = [load_symbol(path) for path in sorted((root / "symbols").rglob("*.json"))]
    result += [
        load_inductor(path).symbol
        for path in sorted((root / "inductors").glob("*.json"))
    ]
    return tuple(result)


def _expect_attrs(shape, node):
    if isinstance(shape, (Line, StyledLine)):
        assert node.tag == f"{_SVG}line"
        expected = {
            "x1": format_mm(shape.start.x),
            "y1": format_mm(shape.start.y),
            "x2": format_mm(shape.end.x),
            "y2": format_mm(shape.end.y),
        }
        for key, value in expected.items():
            assert node.attrib[key] == value
        if isinstance(shape, StyledLine):
            assert node.attrib["stroke-width"] == format_mm(shape.stroke_width_um)
            if shape.dash_pattern_um:
                assert node.attrib["stroke-dasharray"] == ",".join(
                    format_mm(value) for value in shape.dash_pattern_um
                )
    elif isinstance(shape, Rectangle):
        assert node.tag == f"{_SVG}rect"
        assert node.attrib["x"] == format_mm(shape.box.min_x)
        assert node.attrib["y"] == format_mm(shape.box.min_y)
        assert node.attrib["width"] == format_mm(shape.box.max_x - shape.box.min_x)
        assert node.attrib["height"] == format_mm(shape.box.max_y - shape.box.min_y)
    elif isinstance(shape, Circle):
        assert node.tag == f"{_SVG}circle"
        assert node.attrib["cx"] == format_mm(shape.center.x)
        assert node.attrib["cy"] == format_mm(shape.center.y)
        assert node.attrib["r"] == format_mm(shape.radius)
    elif isinstance(shape, Semicircle):
        assert node.tag == f"{_SVG}path"
        x, y, radius = shape.center.x, shape.center.y, shape.radius
        if shape.bulge in (Side.TOP, Side.BOTTOM):
            first, last = Point(x - radius, y), Point(x + radius, y)
        else:
            first, last = Point(x, y - radius), Point(x, y + radius)
        sweep = 1 if shape.bulge in (Side.TOP, Side.RIGHT) else 0
        assert node.attrib["d"] == (
            f"M {format_mm(first.x)} {format_mm(first.y)} "
            f"A {format_mm(radius)} {format_mm(radius)} 0 0 {sweep} "
            f"{format_mm(last.x)} {format_mm(last.y)}"
        )
    else:
        raise TypeError(f"Unsupported primitive {type(shape)}")


def test_all_catalog_ugo_svg_shapes_preserve_integer_source_coordinates():
    for symbol in _symbols():
        root = ET.fromstring(render_symbol_svg(symbol))
        group = root.find(f"{_SVG}g")
        assert group is not None
        assert len(group) == len(symbol.graphics)
        for shape, node in zip(symbol.graphics, group, strict=True):
            _expect_attrs(shape, node)


def test_sheet_svg_renders_eight_transformed_resistors_with_exact_pin_overlay():
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    part = load_part(root / "parts/resistors/fixed.json")
    symbol = load_symbol(root / "symbols/resistors/fixed.json")
    components = []
    expected = set()
    for mirror in (False, True):
        for rotation in (0, 90, 180, 270):
            number = len(components) + 1
            instance = ComponentInstance(
                f"R{number}", part.identifier,
                Point(number * 50_000, number * -20_000),
                Transform(rotation, mirror),
            )
            components.append(instance)
            expected.update(
                (format_mm(point.x), format_mm(point.y))
                for point in instance.pin_positions(symbol).values()
            )
    circuit = Circuit(tuple(components), ())
    symbols = {part.identifier: symbol}
    layout = SheetLayout((), ())
    clean = ET.fromstring(render_sheet_svg(circuit, symbols, layout))
    review = ET.fromstring(render_sheet_svg(circuit, symbols, layout, review_overlay=True))
    groups = clean.findall(f".//{_SVG}g[@data-layer='symbols']")
    assert len(groups) == 8
    assert [g.attrib["data-reference"] for g in groups] == [f"R{i}" for i in range(1, 9)]
    assert all(len(group) == len(symbol.graphics) for group in groups)
    assert clean.find(f".//{_SVG}g[@data-layer='geometry-review']") is None
    debug = review.find(f".//{_SVG}g[@data-layer='geometry-review']")
    assert debug is not None
    actual = {(node.attrib["cx"], node.attrib["cy"]) for node in debug.findall(f"{_SVG}circle")}
    assert actual == expected


def test_svg_escapes_untrusted_reference_attribute_and_label_text():
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    part = load_part(root / "parts/resistors/fixed.json")
    symbol = load_symbol(root / "symbols/resistors/fixed.json")
    instance = ComponentInstance('R<&"1', part.identifier)
    style = TextStyle("unused.ttf", "QA Font")
    label = AnnotationPlacement(
        owner=instance.reference, key="refdes", role=AnnotationRole.REFDES,
        text='R<&"1', style=style, baseline=Point(125, -456),
        ink_bounds=Box(0, -1000, 1000, 1),
        collision_bounds=Box(-100, -1100, 1100, 101),
        reservation_bounds=None, candidate_index=0,
    )
    result = render_sheet_svg(
        Circuit((instance,), ()), {part.identifier: symbol}, SheetLayout((label,), ())
    )
    root = ET.fromstring(result)
    assert root.find(f".//{_SVG}g[@data-layer='symbols']").attrib["data-reference"] == (
        instance.reference
    )
    text = root.find(f".//{_SVG}text[@data-layer='annotations']")
    assert text is not None and text.text == label.text
    assert text.attrib["data-owner"] == instance.reference
    assert "&lt;" in result and "&amp;" in result


def test_finite_seeded_svg_coordinate_format_round_trips_without_float():
    rng = Random(360427)
    samples = [-1_000_000_001, -1001, -1, 0, 1, 1001, 1_000_000_001]
    samples.extend(rng.randrange(-(10**12), 10**12) for _ in range(40))
    for number in samples:
        assert mm(format_mm(number)) == number
        assert format_mm(number) == format_mm(number)
