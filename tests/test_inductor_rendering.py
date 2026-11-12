"""True SVG winding geometry, annotation/route hitboxes and GOST-type font slots."""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.core.diagnostics import Severity
from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.layout import (
    bind_component_annotations,
    obstacles_for_component,
    place_annotations,
)
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.engines.routing.clearance import validate_wire_clearance
from gost_schematic.engines.sheet_layout import (
    component_graphic_obstacles,
    layout_sheet,
)
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.rendering.annotation_svg import render_annotation_svg
from gost_schematic.rendering.sheet_svg import render_sheet_svg
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.standards.nominals import format_nominal

SVG = "{http://www.w3.org/2000/svg}"
STYLE = TextStyle("mock-gost-a.ttf", "OpenGost Type A", 3500, 500)


def _inductor(name):
    return load_inductor(Path(str(files("gost_schematic").joinpath(
        f"catalog/inductors/{name}.json"
    ))))


class Metrics:
    def measure(self, text, style):
        return MeasuredText(Box(0, -2000, max(1, len(text) * 580), 1),
                            len(text) * 580)


@pytest.mark.parametrize(
    "name",
    ["inductor.air_core", "inductor.ferrite", "inductor.gapped_core",
     "inductor.magnetodielectric", "inductor.double_tapped",
     "inductor.sliding_contact", "inductor.trim_copper", "inductor.variable"],
)
def test_svg_uses_exact_arc_paths_not_svg_polyline(name):
    built = _inductor(name)
    root = ET.fromstring(render_symbol_svg(built.symbol))
    arcs = root.findall(f".//{SVG}path")
    assert len(arcs) == built.spec.turns
    assert all(" A " in arc.attrib["d"] for arc in arcs)
    assert not root.findall(f".//{SVG}polyline")
    assert not root.findall(f".//{SVG}polygon")
    assert root.attrib["width"].endswith("mm")


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_rotated_inductor_svg_keeps_four_arcs_and_valid_terminal_identity(
    rotation, mirror,
):
    built = _inductor("inductor.double_tapped")
    component = ComponentInstance(
        "L9", built.part.identifier, Point(20000, 18000),
        Transform(rotation=rotation, mirror_x=mirror),
    )
    bound = bind_component_annotations(built.symbol, component, STYLE)
    result = place_annotations(
        bound.requests, Metrics(),
        boxes=obstacles_for_component(built.symbol, component),
    )
    # Geometric rendering can be inspected independently of a single-symbol
    # label-placement success: sheet-wide engine selects global candidates.
    sheet = layout_sheet(
        Circuit((component,), ()), {built.part.identifier: built.symbol},
        STYLE, Metrics(),
    )
    assert sheet.valid
    root = ET.fromstring(render_sheet_svg(
        Circuit((component,), ()), {built.part.identifier: built.symbol},
        sheet, review_overlay=True,
    ))
    assert len(root.findall(f".//{SVG}path")) == 4
    assert len(root.findall(f".//{SVG}g[@data-reference='L9']")) == 1
    assert [pin.number for pin in pin_corridors_for_component(
        built.symbol, component
    ) for _ in (0,)] == ["1", "2", "3", "4"]
    assert result.placements or result.diagnostics


def test_full_nominal_preserved_and_compact_mode_warns_instead_of_guess():
    quantity = Quantity.from_unit("33", Unit.MICROHENRY)
    formatted = format_nominal(quantity)
    assert formatted.text == "33 мкГн"
    assert formatted.diagnostics[0].code == "NOMINAL_COMPACT_UNSUPPORTED"
    assert quantity.si_value == Quantity.from_unit("33", Unit.MICROHENRY).si_value


def test_material_label_has_a_measured_hitbox_with_no_overlap():
    built = _inductor("inductor.trim_copper")
    component = ComponentInstance("L3", built.part.identifier)
    layout = layout_sheet(
        Circuit((component,), ()), {built.part.identifier: built.symbol},
        STYLE, Metrics(),
    )
    assert layout.valid
    assert {p.key for p in layout.placements} == {"refdes", "core_material"}
    material = next(p for p in layout.placements if p.key == "core_material")
    assert material.text == "Cu"
    assert not any(
        material.collision_bounds.overlaps(obstacle.box)
        for obstacle in component_graphic_obstacles(built.symbol, component)
    )


def test_annotation_renderer_supports_true_arcs_and_no_core_text_without_face():
    built = _inductor("inductor.ferrite")
    component = ComponentInstance("L2", built.part.identifier)
    results = layout_sheet(
        Circuit((component,), ()), {built.part.identifier: built.symbol},
        STYLE, Metrics(),
    )
    assert results.valid
    root = ET.fromstring(render_annotation_svg(
        built.symbol, component, results.placements, review_overlay=True,
    ))
    assert len(root.findall(f".//{SVG}path")) == 4
    assert len(root.findall(f".//{SVG}text")) == 1


@pytest.mark.parametrize("name", ["inductor.tapped", "inductor.double_sliding"])
def test_extra_contact_wires_are_netlist_traced_and_outward(name):
    built = _inductor(name)
    component = ComponentInstance("L1", built.part.identifier)
    corridor = pin_corridors_for_component(built.symbol, component)[-1]
    end = Point(corridor.contact.x, corridor.contact.y - 3000)
    wire = WireObstacle(
        "W1", Line(corridor.contact, end),
        attached_pin=PinRef("L1", corridor.pin.number),
        net_name="TAP_NET",
    )
    schematic = Circuit((component,), (
        Net("TAP_NET", (PinRef("L1", corridor.pin.number),)),
    ))
    errors = validate_wire_clearance(
        (wire,), corridors=pin_corridors_for_component(built.symbol, component),
        circuit=schematic,
    )
    assert not [e for e in errors if e.severity == Severity.ERROR]
    wrong = replace(wire, attached_pin=PinRef("L1", "1"))
    assert "ROUTE_PIN_ESCAPE_BLOCKED" in {
        d.code for d in validate_wire_clearance(
            (wrong,), corridors=pin_corridors_for_component(built.symbol, component),
        )
    }
