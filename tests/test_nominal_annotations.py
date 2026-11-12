"""A format switch recalculates hitboxes, placement and router obstacles."""

from dataclasses import replace

import pytest

from gost_schematic.core.geometry import Box
from gost_schematic.engines.annotation.layout import (
    bind_component_annotations,
    obstacles_for_component,
    place_annotations,
)
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.document import SchematicDocument
from gost_schematic.model.nominal_display import (
    ComponentNominalOverride,
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.validation.annotation_checks import annotation_obstacles


class TextMetrics:
    def measure(self, text, style):
        return MeasuredText(Box(0, -1600, len(text) * 600, 1), len(text) * 600)


@pytest.fixture
def face():
    return TextStyle("test.ttf", "Demo", 2200, 300)


def _component():
    return ComponentInstance(
        "R1", "part.resistor", nominal=Quantity.from_unit("2300", Unit.OHM),
    )


def _layout(resistor, face, component, policy):
    bound = bind_component_annotations(resistor, component, face, policy)
    result = place_annotations(
        bound.requests, TextMetrics(),
        boxes=obstacles_for_component(resistor, component),
    )
    return bound, result


def test_default_compact_and_full_mode_change_text_hitbox(resistor, face):
    component = _component()
    compact, placed_compact = _layout(
        resistor, face, component, NominalDisplayConfiguration(),
    )
    full_settings = NominalDisplaySettings(mode=NominalDisplayMode.FULL_UNITS)
    full, placed_full = _layout(
        resistor, face, component,
        NominalDisplayConfiguration(default=full_settings),
    )
    assert [item.text for item in compact.requests] == ["R1", "2,3к"]
    assert [item.text for item in full.requests] == ["R1", "2,3 кОм"]
    assert placed_compact.valid and placed_full.valid
    a = placed_compact.placements[1].collision_bounds
    b = placed_full.placements[1].collision_bounds
    assert b.max_x - b.min_x > a.max_x - a.min_x
    assert annotation_obstacles(placed_full.placements)[1].box == b
    assert component.nominal.si_value == Quantity.from_unit("2300", Unit.OHM).si_value


def test_hidden_value_removes_label_and_router_hitbox(resistor, face):
    component = _component()
    policy = NominalDisplayConfiguration(
        default=NominalDisplaySettings(show_nominal=False),
    )
    bound, placement = _layout(resistor, face, component, policy)
    assert [request.text for request in bound.requests] == ["R1"]
    assert placement.valid
    assert len(annotation_obstacles(placement.placements)) == 1


def test_per_component_override_can_hide_or_expand_only_selected_label(resistor, face):
    sheet = NominalDisplayConfiguration(overrides=(
        ComponentNominalOverride("R2", mode=NominalDisplayMode.FULL_UNITS),
    ))
    first = _component()
    second = replace(first, reference="R2")
    one = bind_component_annotations(resistor, first, face, sheet)
    two = bind_component_annotations(resistor, second, face, sheet)
    assert one.requests[-1].text == "2,3к"
    assert two.requests[-1].text == "2,3 кОм"


def test_unsupported_eskd_has_warning_and_can_still_relayout(resistor, face):
    component = replace(
        _component(), nominal=Quantity.from_unit("999.5", Unit.OHM),
    )
    bound, placements = _layout(
        resistor, face, component, NominalDisplayConfiguration(),
    )
    assert bound.diagnostics[0].code == "NOMINAL_COMPACT_UNSUPPORTED"
    assert bound.requests[-1].text == "999,5 Ом"
    assert placements.valid


def test_literal_and_typed_value_cannot_both_override_one_label(resistor, face):
    with pytest.raises(ValueError, match="both a typed nominal"):
        bind_component_annotations(
            resistor, _component(), face, literal_values={"value": "fake"},
        )


def test_document_rejects_override_for_unknown_reference():
    circuit = Circuit((_component(),), ())
    with pytest.raises(ValueError, match="unknown components"):
        SchematicDocument(
            circuit,
            NominalDisplayConfiguration(overrides=(
                ComponentNominalOverride("R999", show_nominal=False),
            )),
        )
    assert SchematicDocument(circuit).nominal_display.default.show_nominal
