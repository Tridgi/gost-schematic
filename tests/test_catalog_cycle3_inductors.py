"""Issue #24: GOST 2.723 Cu stroke and honest adaptation provenance.

The clean graphic shape is distinct from electrical conduction: a solid Cu
*magnetic core* does not establish an electrical node across the winding.
This file deliberately asserts the immutable catalog contract, while full
normative visual sign-off stays BLOCKED / DRAFT.
"""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.catalog.inductors import (
    CoreKind,
    NormativeRelation,
    load_inductor,
)
from gost_schematic.core.geometry import Line, Point, StyledLine
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import ComponentInstance, PinRef
from gost_schematic.model.pins import TerminalFunction
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.symbol_checks import validate_symbol

ROOT = files("gost_schematic").joinpath("catalog/inductors")
SVG = "{http://www.w3.org/2000/svg}"


def _build(identifier):
    return load_inductor(Path(str(ROOT.joinpath(f"{identifier}.json"))))


def _core(built):
    matches = [(i, graphic) for i, graphic in enumerate(built.symbol.graphics)
               if isinstance(graphic, StyledLine)]
    assert len(matches) == 1
    return matches[0]


def _assert_material_contract(symbol, kind):
    """Mutation-killing test guard, not a claim of full GOST certification."""
    cores = [item for item in symbol.graphics if isinstance(item, StyledLine)]
    assert len(cores) == 1
    assert cores[0].stroke_width_um == symbol.line_width_um
    if kind == CoreKind.NONMAGNETIC_COPPER:
        assert cores[0].dash_pattern_um == ()
        assert symbol.constant_annotations == (("core_material", "Cu"),)
        assert sum(
            slot.key == "core_material" and slot.required
            for slot in symbol.annotation_slots
        ) == 1
    elif kind == CoreKind.MAGNETODIELECTRIC:
        assert cores[0].dash_pattern_um == (2000, 1100)
        assert not symbol.constant_annotations
    else:
        raise AssertionError(f"unexpected review material {kind}")


@pytest.mark.parametrize("name,kind", [
    ("inductor.trim_copper", CoreKind.NONMAGNETIC_COPPER),
    ("inductor.magnetodielectric", CoreKind.MAGNETODIELECTRIC),
    ("inductor.trim_magnetodielectric", CoreKind.MAGNETODIELECTRIC),
])
def test_core_styles_match_distinct_material_categories(name, kind):
    built = _build(name)
    _assert_material_contract(built.symbol, kind)
    assert built.spec.core == kind
    assert built.symbol.status == SymbolStatus.DRAFT
    assert not [d for d in validate_symbol(built.symbol) if d.severity.value == "error"]


@pytest.mark.parametrize("name,kind", [
    ("inductor.trim_copper", CoreKind.NONMAGNETIC_COPPER),
    ("inductor.magnetodielectric", CoreKind.MAGNETODIELECTRIC),
])
def test_svg_core_dash_is_present_only_for_magnetodielectric(name, kind):
    symbol = _build(name).symbol
    root = ET.fromstring(render_symbol_svg(symbol))
    styled = [element for element in root.findall(f".//{SVG}line")
              if "stroke-width" in element.attrib]
    assert len(styled) == 1
    if kind == CoreKind.NONMAGNETIC_COPPER:
        assert "stroke-dasharray" not in styled[0].attrib
    else:
        assert styled[0].attrib["stroke-dasharray"] == "2,1.1"


@pytest.mark.parametrize("mutation", ["copper_dashed", "copper_missing_Cu",
                                        "copper_not_required"])
def test_negative_regression_copper_material_mutants_must_fail(mutation):
    built = _build("inductor.trim_copper")
    symbol = built.symbol
    if mutation == "copper_dashed":
        index, core = _core(built)
        strokes = list(symbol.graphics)
        strokes[index] = replace(core, dash_pattern_um=(2000, 1100))
        symbol = replace(symbol, graphics=tuple(strokes))
    elif mutation == "copper_missing_Cu":
        symbol = replace(symbol, constant_annotations=())
    else:
        changed = tuple(replace(slot, required=False)
                        if slot.key == "core_material" else slot
                        for slot in symbol.annotation_slots)
        symbol = replace(symbol, annotation_slots=changed)
    with pytest.raises(AssertionError):
        _assert_material_contract(symbol, CoreKind.NONMAGNETIC_COPPER)


def test_negative_regression_magnetodielectric_must_not_be_solid():
    built = _build("inductor.magnetodielectric")
    symbol = built.symbol
    index, core = _core(built)
    strokes = list(symbol.graphics)
    strokes[index] = replace(core, dash_pattern_um=())
    with pytest.raises(AssertionError):
        _assert_material_contract(
            replace(symbol, graphics=tuple(strokes)),
            CoreKind.MAGNETODIELECTRIC,
        )


def test_solid_core_must_not_be_treated_as_electrically_conducting():
    built = _build("inductor.trim_copper")
    symbol = built.symbol
    result = inspect_conductor_topology(symbol)
    assert result.valid
    assert result.pin_islands == (("1", "2"),)
    index, core = _core(built)
    assert core.dash_pattern_um == ()
    assert symbol.conductor_topology is not None
    assert index not in symbol.conductor_topology.conductor_indices
    bad = replace(symbol, conductor_topology=replace(
        symbol.conductor_topology,
        conductor_indices=(*symbol.conductor_topology.conductor_indices, index),
    ))
    issues = inspect_conductor_topology(bad)
    assert not issues.valid
    assert "TOPOLOGY_ORPHAN_CONDUCTOR" in {d.code for d in issues.diagnostics}


def test_copper_trim_arrow_is_never_part_of_winding_net():
    built = _build("inductor.trim_copper")
    symbol = built.symbol
    assert symbol.conductor_topology is not None
    assert set(symbol.conductor_topology.conductor_indices) == set(range(6))
    assert all(
        isinstance(shape, Line) for shape in symbol.graphics[7:]
    )
    assert inspect_conductor_topology(symbol).pin_islands == (("1", "2"),)


@pytest.mark.parametrize("name,expected_count,third_function", [
    ("inductor.double_tapped", 4, TerminalFunction.WINDING_TAP),
    ("inductor.sliding_contact", 3, TerminalFunction.WINDING_SLIDER),
])
def test_adaptation_provenance_does_not_change_pin_or_shape_semantics(
    name, expected_count, third_function,
):
    built = _build(name)
    assert built.spec.normative_relation == NormativeRelation.EDITORIAL_ADAPTATION
    assert "editorial_adaptation" in built.symbol.standard_refs[-1]
    assert built.symbol.status == SymbolStatus.DRAFT
    assert len(built.part.pins) == len(built.symbol.pins) == expected_count
    assert [p.number for p in built.symbol.pins] == [
        str(i) for i in range(1, expected_count + 1)
    ]
    assert [p.number for p in built.part.pins] == [
        str(i) for i in range(1, expected_count + 1)
    ]
    assert built.part.pins[2].function == third_function
    assert {p.number: p.function for p in built.part.pins} == {
        "1": TerminalFunction.WINDING_START,
        "2": TerminalFunction.WINDING_END,
        **{str(i): third_function for i in range(3, expected_count + 1)},
    }
    assert tuple(p.at for p in built.symbol.pins[:2]) == (
        Point(-12000, 0), Point(12000, 0),
    )
    expected_taps = (Point(-6000, -9000), Point(6000, -9000)) if (
        expected_count == 4
    ) else (Point(-2000, -9000),)
    assert tuple(p.at for p in built.symbol.pins[2:]) == expected_taps
    graph = inspect_conductor_topology(built.symbol)
    assert graph.valid
    assert graph.pin_islands == (tuple(str(i) for i in range(1, expected_count + 1)),)


@pytest.mark.parametrize("name,source_fragment", [
    ("inductor.double_tapped", "«или»"),
    ("inductor.sliding_contact", "«например, двумя»"),
])
def test_adaptation_source_explains_why_not_a_literal_single_figure(
    name, source_fragment,
):
    built = _build(name)
    assert source_fragment in built.spec.normative_basis
    assert "ГОСТ 2.723-68" in built.spec.normative_basis
    with pytest.raises(AssertionError):
        assert built.spec.normative_relation == NormativeRelation.TABLE_2_EXAMPLE


@pytest.mark.parametrize("name", ["inductor.double_tapped",
                                   "inductor.sliding_contact",
                                   "inductor.trim_copper"])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_cycle3_edit_preserves_physical_pin_map_across_transforms(
    name, rotation, mirror,
):
    built = _build(name)
    component = ComponentInstance(
        "L24", built.part.identifier, transform=Transform(rotation, mirror),
    )
    positions = component.pin_positions(built.symbol)
    assert list(positions) == [pin.number for pin in built.part.pins]
    assert set(positions.values()) == {
        component.transform.apply(pin.at) for pin in built.symbol.pins
    }
    assert {PinRef("L24", pin.number) for pin in built.part.pins} == {
        PinRef("L24", number) for number in positions
    }
    assert inspect_conductor_topology(built.symbol).valid
