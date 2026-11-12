"""Sheet-level ESKD label placement across component boundaries."""

from dataclasses import replace

from gost_schematic.core.geometry import Box, Line, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.sheet_layout import (
    SheetLabelProfile,
    layout_sheet,
    sheet_label_requests,
)
from gost_schematic.model.annotations import AnnotationRole, MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.nominal_display import (
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.obstacles import BoxObstacle, WireObstacle
from gost_schematic.model.quantities import Quantity, Unit


class TextMetrics:
    def measure(self, text, style):
        width = len(text) * 600
        return MeasuredText(Box(0, -2000, width, 1), width)


STYLE = TextStyle("/some/test-font.ttf", "Test", 3200, 500)
SYMBOLS = None


def resistor(reference="R1", x=0, y=0, rotation=0):
    return ComponentInstance(
        reference, "resistor", Point(x, y), Transform(rotation=rotation),
        nominal=Quantity.from_unit("2300", Unit.OHM),
    )


def layout(resistor_symbol, components, **options):
    return layout_sheet(
        Circuit(tuple(components), ()), {"resistor": resistor_symbol},
        STYLE, TextMetrics(), **options,
    )


def get_label(scene, reference, key):
    return next(
        item for item in scene.placements
        if item.owner == reference and item.key == key
    )


def test_designator_above_and_value_below_for_horizontal_resistor(resistor):
    result = layout(resistor, (resistor(),))
    assert result.valid
    reference = get_label(result, "R1", "refdes")
    nominal = get_label(result, "R1", "value")
    assert reference.text == "R1"
    assert reference.candidate_index == 0
    assert reference.collision_bounds.max_y < -2000
    assert nominal.text == "2,3к"
    assert nominal.collision_bounds.min_y > 2000
    assert not reference.collision_bounds.overlaps(nominal.collision_bounds)


def test_rotated_resistor_has_refdes_above_in_page_coordinates(resistor):
    instance = resistor("R7", 15000, 15000, rotation=90)
    result = layout(resistor, (instance,))
    assert result.valid
    ref = get_label(result, "R7", "refdes")
    value = get_label(result, "R7", "value")
    assert ref.collision_bounds.max_y < 10000
    assert value.collision_bounds.min_y > 20000
    assert ref.text == "R7" and value.text == "2,3к"


def test_blocked_above_moves_refdes_right_not_below(resistor):
    unavailable = BoxObstacle("other-note", Box(-6000, -7000, 6000, -3000))
    result = layout(resistor, (resistor(),), forbidden_boxes=(unavailable,))
    assert result.valid
    reference = get_label(result, "R1", "refdes")
    assert reference.candidate_index == 1
    assert reference.ink_bounds.min_x > 8000
    assert reference.ink_bounds.max_y < -2000


def test_multiple_parts_avoid_foreign_body_and_text(resistor):
    result = layout(resistor, (
        resistor("R1", 0, 0),
        resistor("R2", 30000, 0),
        resistor("R3", 60000, 0),
    ))
    assert result.valid
    assert len(result.placements) == 6
    for index, label in enumerate(result.placements):
        for other in result.placements[index + 1:]:
            assert not label.collision_bounds.overlaps(other.collision_bounds)


def test_symbol_collision_is_explicit_error(resistor):
    result = layout(resistor, (resistor("R1"), resistor("R2", 10000)))
    assert not result.valid
    assert "SYMBOL_GEOMETRY_OVERLAP" in {
        item.code for item in result.diagnostics
    }


def test_duplicate_reference_is_explicit_error(resistor):
    result = layout(resistor, (resistor("R1"), resistor("R1", 30000)))
    assert not result.valid
    assert "DUPLICATE_REFERENCE" in {item.code for item in result.diagnostics}


def test_missing_symbol_is_explicit_error(resistor):
    instance = replace(resistor(), part_id="unknown")
    result = layout(resistor, (instance,))
    assert not result.valid
    assert "UNKNOWN_SHEET_SYMBOL" in {item.code for item in result.diagnostics}


def test_full_units_remeasure_text_hitbox_without_mutating_nominal(resistor):
    item = resistor()
    compact = layout(resistor, (item,))
    full = layout(
        resistor, (item,),
        configuration=NominalDisplayConfiguration(
            NominalDisplaySettings(mode=NominalDisplayMode.FULL_UNITS)
        ),
    )
    c = get_label(compact, "R1", "value")
    f = get_label(full, "R1", "value")
    assert c.text == "2,3к"
    assert f.text == "2,3 кОм"
    assert (f.collision_bounds.max_x - f.collision_bounds.min_x) > (
        c.collision_bounds.max_x - c.collision_bounds.min_x
    )
    assert item.nominal.si_value == 2300


def test_hidden_nominal_removes_its_hitbox(resistor):
    item = resistor()
    hidden = layout(
        resistor, (item,),
        configuration=NominalDisplayConfiguration(
            NominalDisplaySettings(show_nominal=False)
        ),
    )
    assert hidden.valid
    assert [(p.owner, p.key) for p in hidden.placements] == [("R1", "refdes")]


def test_existing_wire_blocks_text_candidate_and_triggers_fallback(resistor):
    wire = WireObstacle("TEST", Line(Point(-6000, -4200), Point(6000, -4200)))
    result = layout(resistor, (resistor(),), wires=(wire,))
    assert result.valid
    assert get_label(result, "R1", "refdes").candidate_index == 1


def test_unplaceable_label_is_diagnostic_not_silent_overlap(resistor):
    blocker = BoxObstacle("occupied", Box(-25000, -12000, 25000, 12000))
    result = layout(resistor, (resistor(),), forbidden_boxes=(blocker,))
    assert not result.valid
    assert "ANNOTATION_UNPLACEABLE" in {issue.code for issue in result.diagnostics}


def test_corridor_blocked_by_neighbor_detected(resistor):
    # Symbol bodies do not touch, but the first right-hand pin escape
    # intrudes into the second graphic extents.
    result = layout(resistor, (resistor("R1"), resistor("R2", 15500)))
    assert not result.valid
    assert "PIN_EXIT_OBSTRUCTED" in {issue.code for issue in result.diagnostics}


def test_configuration_validated(resistor):
    try:
        SheetLabelProfile(body_gap_um=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected invalid profile dimensions to fail")


def test_empty_circuit_is_reported(resistor):
    result = layout(resistor, ())
    assert not result.valid
    assert result.diagnostics[0].code == "SHEET_EMPTY"
