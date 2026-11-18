"""Issue #72: measure the REAL six-part preview text versus visible ink.

Two independent measurements:
  1. font-independent SVG-baseline-to-stroked-primitive clearances;
  2. real FreeType font ink to stroke-AABB proximity (identified sans-serif face).
The actual example uses SVG sans-serif, not a packaged/approved OpenGost font.
These are reproducible geometry observations, NOT normative minimum distances.
"""

import json
import shutil
import subprocess
import warnings
from math import hypot
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_end_to_end_circuit import (
    authored_specimen,
    definitions,
    specimen_svg,
)
from gost_schematic.core.geometry import (
    Line,
    Rectangle,
    Semicircle,
    primitive_stroked_bounds,
)
from gost_schematic.engines.annotation.metrics import (
    PillowTextMeasurer,
    font_sha256,
)
from gost_schematic.model.annotations import TextStyle

_SVG = "{http://www.w3.org/2000/svg}"
COMPARISON = ("R1", "R2", "C1", "C2", "C3", "L1")


def _scene():
    circuit, _graph = authored_specimen()
    parts, symbols = definitions()
    image = ET.fromstring(specimen_svg())
    labels = {
        tag.attrib["data-owner"]: tag
        for tag in image.findall(f".//{_SVG}g[@data-layer='specimen-refdes']/{_SVG}text")
    }
    byref = {part.reference: part for part in circuit.components}
    assert set(labels) == set(byref) == set(COMPARISON)
    return byref, parts, symbols, labels


def _primitives(part, part_definition, symbol):
    return tuple(
        part.transform.primitive(shape, part.origin)
        for shape in symbol.graphics
    )


def _aabb_distance(a, b):
    """Lower bound on genuine curved-stroke distance, using stroke AABBs."""
    dx = max(a.min_x - b.max_x, b.min_x - a.max_x, 0)
    dy = max(a.min_y - b.max_y, b.min_y - a.max_y, 0)
    return hypot(dx, dy)


def _face():
    command = shutil.which("fc-match")
    if command is None:
        pytest.skip("No fontconfig: measured ink font cannot be certified")
    name = subprocess.run(
        (command, "-f", "%{file}", "sans-serif"),
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    path = Path(name)
    if not path.is_file():
        pytest.skip("Fontconfig did not return a usable sans-serif face")
    return path


def _ink_measurements():
    byref, parts, symbols, labels = _scene()
    font_path = _face()
    style = TextStyle(str(font_path), "sans-serif", em_height_um=3500)
    measurer = PillowTextMeasurer()
    data = {}
    for reference in COMPARISON:
        instance = byref[reference]
        symbol = symbols[parts[instance.part_id].symbol_id]
        text = labels[reference]
        assert text.text == reference
        x = round(float(text.attrib["x"]) * 1000)
        y = round(float(text.attrib["y"]) * 1000)
        measured = measurer.measure(reference, style)
        # SVG text-anchor=middle centers on the advance width, not ink center.
        baseline_origin = (x - measured.advance_um // 2, y)
        ink = measured.ink_box.translated(
            type(instance.origin)(*baseline_origin)
        )
        shapes = _primitives(instance, parts[instance.part_id], symbol)
        all_inks = tuple(
            primitive_stroked_bounds(shape, symbol.line_width_um)
            for shape in shapes
        )
        visible_distance_um = min(
            _aabb_distance(ink, shape) for shape in all_inks
        )
        main_shapes = tuple(
            shape for shape in shapes
            if (
                isinstance(shape, Semicircle)
                if reference == "L1"
                else isinstance(shape, Rectangle)
                if reference.startswith("R")
                else isinstance(shape, Line)
                and shape.start.x == shape.end.x
                and abs(shape.end.y - shape.start.y) >= 7000
            )
        )
        assert main_shapes, reference
        main_distance_um = min(
            _aabb_distance(
                ink, primitive_stroked_bounds(shape, symbol.line_width_um)
            ) for shape in main_shapes
        )
        body = instance.transform.box(symbol.body_keepout).translated(
            instance.origin
        )
        data[reference] = {
            "baseline_um": [x, y],
            "label_ink_um": [
                ink.min_x, ink.min_y, ink.max_x, ink.max_y,
            ],
            "body_top_um": body.min_y,
            "baseline_to_body_um": body.min_y - y,
            "nearest_visible_stroke_aabb_gap_um": round(visible_distance_um, 3),
            "main_visible_ugo_aabb_gap_um": round(main_distance_um, 3),
            "font_sha256": font_sha256(str(font_path)),
            "font_face": font_path.name,
        }
    return data


def test_exact_sixpart_svg_baselines_not_conflated_with_body_and_top_tap():
    byref, parts, symbols, labels = _scene()
    for reference in COMPARISON:
        instance = byref[reference]
        symbol = symbols[parts[instance.part_id].symbol_id]
        top = instance.transform.box(symbol.body_keepout).translated(
            instance.origin
        ).min_y
        baseline = round(float(labels[reference].attrib["y"]) * 1000)
        assert top - baseline == 2500

    l1 = byref["L1"]
    symbol = symbols["inductor.tapped"]
    assert l1.origin.x == 100000 and l1.origin.y == 40000
    assert symbol.body_keepout.min_y == -7000
    assert round(float(labels["L1"].attrib["y"]) * 1000) == 30500
    tips = l1.pin_positions(symbol)
    assert tips["3"] == type(l1.origin)(98000, 31000)
    body = l1.transform.box(symbol.body_keepout).translated(l1.origin)
    assert body.min_y == 33000
    shapes = _primitives(l1, parts[l1.part_id], symbol)
    windings = [
        primitive_stroked_bounds(shape, symbol.line_width_um)
        for shape in shapes if isinstance(shape, Semicircle)
    ]
    assert len(windings) == 4
    assert min(box.min_y for box in windings) == 37850
    # The TAP (stroke included) protrudes ABOVE nominal keepout top.
    tap_shape = next(
        shape for shape in shapes
        if isinstance(shape, Line)
        and shape.start.x == shape.end.x == tips["3"].x
        and tips["3"] in (shape.start, shape.end)
    )
    assert primitive_stroked_bounds(tap_shape, symbol.line_width_um).min_y == 30850
    assert 37850 - 30500 == 7350  # L1 baseline to visible turns
    assert 30850 - 30500 == 350   # L1 baseline to upper tap
    assert 33000 - 30500 == 2500  # baseline to non-ink body keepout
    # Real C3 is already at the revised y=80 mm, never the old y=75.
    assert byref["C3"].origin == type(l1.origin)(100000, 80000)


def test_sixpart_actual_free_type_ink_gap_to_visible_ugo():
    values = _ink_measurements()
    assert set(values) == set(COMPARISON)
    for ref in COMPARISON:
        assert values[ref]["baseline_to_body_um"] == 2500
        assert values[ref]["nearest_visible_stroke_aabb_gap_um"] >= 0
    assert values["L1"]["main_visible_ugo_aabb_gap_um"] > values["R1"][
        "main_visible_ugo_aabb_gap_um"
    ]
    assert values["L1"]["main_visible_ugo_aabb_gap_um"] > values["C1"][
        "main_visible_ugo_aabb_gap_um"
    ]
    assert values["L1"]["nearest_visible_stroke_aabb_gap_um"] < values["L1"][
        "main_visible_ugo_aabb_gap_um"
    ]
    warnings.warn(
        "Issue72 real six-part SVG text ink-to-UGO measurements (um): "
        + json.dumps(values, ensure_ascii=False, sort_keys=True),
        stacklevel=1,
    )
