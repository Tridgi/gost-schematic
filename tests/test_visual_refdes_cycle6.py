"""Issue #68: graphics-aware measured reference designator placement review."""
from dataclasses import replace
from math import isclose
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_end_to_end_circuit import (
    authored_specimen,
    definitions,
    renderer_wires,
    specimen_svg,
)
from examples.review_visual_refdes import legacy_placements
from gost_schematic.core.geometry import Box, Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.annotation.visual_refdes import (
    VisualRefdesProfile,
    apply_visible_refdes_to_layout,
    distance_ink_to_main_ugo_um,
    legacy_keepout_label_ink,
    main_ugo_graphic_bounds,
    place_refdes_near_visible_graphics,
)
from gost_schematic.model.annotations import MeasuredText, TextStyle
from gost_schematic.model.circuit import Circuit
from gost_schematic.model.obstacles import BoxObstacle, WireObstacle, wire_intersects_box
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.rendering.sheet_svg import render_sheet_svg

STYLE = TextStyle("unit-test-face.ttf", "Measured Unit Test", 3500, 500)


class UnitInk:
    """Deterministic physical 2.5-mm ink height, variable actual text width."""

    def measure(self, text, style):
        return MeasuredText(Box(0, -2500, 800 * len(text), 1), 800 * len(text))


def _specimen():
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    return circuit, graph, {p: symbols[part.symbol_id] for p, part in parts.items()}


def test_l1_visual_main_shape_ignores_tap_stem_but_obstacles_still_protect_it():
    circuit, _, by_part = _specimen()
    l1 = next(component for component in circuit.components if component.reference == "L1")
    symbol = by_part[l1.part_id]
    visible = main_ugo_graphic_bounds(symbol, l1)
    assert visible == Box(91850, 37850, 108150, 40151)
    # Old body is pushed upwards by the tap reserve while the actual winding
    # begins at y=37.85 mm (from the real 4x radius-2-mm semicircles).
    keepout = l1.transform.box(symbol.body_keepout).translated(l1.origin)
    assert keepout.min_y == 33000
    assert min(l1.pin_positions(symbol).values(), key=lambda p: p.y).y == 31000


def test_measured_l1_gap_is_much_smaller_than_old_keepout_baseline():
    circuit, graph, by_part = _specimen()
    measurer = UnitInk()
    before = legacy_placements(circuit, by_part, STYLE, measurer)
    after = place_refdes_near_visible_graphics(
        circuit, by_part, STYLE, measurer, wires=renderer_wires(graph),
    )
    l1 = next(c for c in circuit.components if c.reference == "L1")
    main = main_ugo_graphic_bounds(by_part[l1.part_id], l1)
    ink_old = next(x.ink_bounds for x in before if x.owner == "L1")
    ink_new = next(x.ink_bounds for x in after if x.owner == "L1")
    old_gap = distance_ink_to_main_ugo_um(ink_old, main) / 1000
    new_gap = distance_ink_to_main_ugo_um(ink_new, main) / 1000
    assert isclose(old_gap, 7.349, abs_tol=.003)
    assert .8 <= new_gap <= 2.8
    assert old_gap - new_gap > 4
    assert next(x for x in after if x.owner == "L1").candidate_index >= 1
    assert len(after) == len(before) == 6
    assert len(graph.segments) == 16 and len(graph.junctions) == 3


def test_all_six_labels_are_outside_graphics_wire_and_pin_keepouts():
    circuit, graph, by_part = _specimen()
    candidate = place_refdes_near_visible_graphics(
        circuit, by_part, STYLE, UnitInk(), wires=renderer_wires(graph),
    )
    from gost_schematic.core.geometry import primitive_stroked_bounds
    from gost_schematic.engines.annotation.layout import obstacles_for_component

    for label in candidate:
        assert all(
            not wire_intersects_box(w, label.collision_bounds)
            for w in renderer_wires(graph)
        )
        assert all(
            not label.collision_bounds.overlaps(block.box)
            for component in circuit.components
            for block in obstacles_for_component(by_part[component.part_id], component)
        )
        assert all(
            not label.collision_bounds.overlaps(
                primitive_stroked_bounds(
                    component.transform.primitive(
                        primitive, component.origin
                    ),
                    by_part[component.part_id].line_width_um,
                )
            )
            for component in circuit.components
            for primitive in by_part[component.part_id].graphics
        )
    assert not any(
        left.collision_bounds.overlaps(right.collision_bounds)
        for i, left in enumerate(candidate) for right in candidate[i+1:]
    )


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_all_eight_l1_transforms_keep_upright_unobstructed_labels(angle, mirror):
    circuit, _, by_part = _specimen()
    l1 = next(c for c in circuit.components if c.reference == "L1")
    updated = replace(l1, transform=Transform(angle, mirror))
    rotated = Circuit((updated,), ())
    slots = place_refdes_near_visible_graphics(
        rotated, by_part, STYLE, UnitInk(),
    )
    assert len(slots) == 1
    assert slots[0].text == "L1"
    assert slots[0].ink_bounds.min_x < slots[0].ink_bounds.max_x
    assert slots[0].ink_bounds.min_y < slots[0].ink_bounds.max_y
    symbol = by_part[l1.part_id]
    assert not slots[0].collision_bounds.overlaps(
        updated.transform.box(symbol.body_keepout).translated(updated.origin)
    )


def test_adjacent_foreign_wire_forces_deterministic_alternative_candidate():
    circuit, _, by_part = _specimen()
    l1 = next(c for c in circuit.components if c.reference == "L1")
    small = Circuit((l1,), ())
    original = place_refdes_near_visible_graphics(
        small, by_part, STYLE, UnitInk(),
    )
    bbox = original[0].collision_bounds
    # A distinct high-voltage wire enters the originally selected candidate.
    from gost_schematic.core.geometry import Line

    wire = WireObstacle(
        "foreign-guard", Line(
            Point(bbox.min_x - 2000, (bbox.min_y + bbox.max_y)//2),
            Point(bbox.max_x + 2000, (bbox.min_y + bbox.max_y)//2),
        ), 300, net_name="FOREIGN",
    )
    adjusted = place_refdes_near_visible_graphics(
        small, by_part, STYLE, UnitInk(), wires=(wire,),
    )
    assert adjusted[0].ink_bounds != original[0].ink_bounds
    assert not wire_intersects_box(wire, adjusted[0].collision_bounds)
    assert place_refdes_near_visible_graphics(
        small, by_part, STYLE, UnitInk(), wires=(wire,),
    ) == adjusted


def test_unplaceable_long_label_is_rejected_without_shrink_or_clipping():
    circuit, _, by_part = _specimen()
    l1 = next(c for c in circuit.components if c.reference == "L1")
    long_name = replace(l1, reference="L1_WITH_A_VERY_LONG_IDENTIFIER")
    huge = Box(-1000000, -1000000, 1000000, 1000000)
    with pytest.raises(ValueError, match="REFDES_UNPLACEABLE"):
        place_refdes_near_visible_graphics(
            Circuit((long_name,), ()), by_part, STYLE, UnitInk(),
            extra_boxes=(BoxObstacle("blocked", huge),),
        )


def test_invalid_profile_and_clean_current_model_remains_untouched():
    circuit, graph, by_part = _specimen()
    frozen = (circuit, graph)
    with pytest.raises(ValueError, match="positive"):
        VisualRefdesProfile(graphic_gap_um=0)
    with pytest.raises(ValueError, match="positive"):
        VisualRefdesProfile(side_gap_um=-2)
    by_part_without_l1 = {k: v for k, v in by_part.items() if k != "inductor.tapped"}
    with pytest.raises(ValueError, match="UNKNOWN_REFDES_SYMBOL"):
        place_refdes_near_visible_graphics(
            circuit, by_part_without_l1, STYLE, UnitInk(),
        )
    assert (circuit, graph) == frozen == authored_specimen()
    assert next(c for c in circuit.components if c.reference == "C3").origin == (
        Point(100000, 80000)
    )


def test_l1_legacy_baseline_comes_from_keepout_not_visible_winding():
    circuit, _, by_part = _specimen()
    l1 = next(c for c in circuit.components if c.reference == "L1")
    metric = UnitInk().measure("L1", STYLE)
    old = legacy_keepout_label_ink(by_part[l1.part_id], l1, metric)
    assert old.max_y == 30501
    assert old.min_y == 28000


def test_r_and_c_refdes_never_get_farther_from_visible_symbol():
    circuit, graph, by_part = _specimen()
    before = {x.owner: x for x in legacy_placements(
        circuit, by_part, STYLE, UnitInk(),
    )}
    after = {x.owner: x for x in place_refdes_near_visible_graphics(
        circuit, by_part, STYLE, UnitInk(), wires=renderer_wires(graph),
    )}
    for component in circuit.components:
        if component.reference == "L1":
            continue
        main = main_ugo_graphic_bounds(by_part[component.part_id], component)
        old = distance_ink_to_main_ugo_um(
            before[component.reference].ink_bounds, main,
        )
        new = distance_ink_to_main_ugo_um(
            after[component.reference].ink_bounds, main,
        )
        assert new <= old, (component.reference, old, new)
        assert new >= 800, (component.reference, old, new)


def test_explicit_refdes_adapter_uses_ordinary_layout_and_svg_without_golden_drift():
    circuit, graph, by_part = _specimen()
    frozen = (circuit, graph)
    measure = UnitInk()
    ordinary = render_external_wire_sheet(
        circuit, graph, by_part, STYLE, measure,
    )
    assert ordinary.layout.valid
    adapted = apply_visible_refdes_to_layout(
        circuit, by_part, ordinary.layout, STYLE, measure,
        wires=ordinary.wires,
    )
    assert adapted.valid and adapted is not ordinary.layout
    assert ordinary.layout == render_external_wire_sheet(
        circuit, graph, by_part, STYLE, measure,
    ).layout
    before = {p.owner: p for p in ordinary.layout.placements if p.key == "refdes"}
    after = {p.owner: p for p in adapted.placements if p.key == "refdes"}
    assert set(before) == set(after) == {
        "R1", "R2", "C1", "C2", "L1", "C3",
    }
    assert before["L1"].ink_bounds != after["L1"].ink_bounds
    assert tuple(p for p in ordinary.layout.placements if p.key != "refdes") == (
        tuple(p for p in adapted.placements if p.key != "refdes")
    )

    original = ET.fromstring(render_sheet_svg(
        circuit, by_part, ordinary.layout, wires=ordinary.wires,
    ))
    preview = ET.fromstring(render_sheet_svg(
        circuit, by_part, adapted, wires=ordinary.wires,
    ))
    ns = "{http://www.w3.org/2000/svg}"
    for layer, tag in (("symbols", "g"), ("wires", "line")):
        old_elements = original.findall(f".//{ns}{tag}[@data-layer='{layer}']")
        new_elements = preview.findall(f".//{ns}{tag}[@data-layer='{layer}']")
        assert [ET.tostring(x) for x in old_elements] == [
            ET.tostring(x) for x in new_elements
        ]
    assert len(preview.findall(f".//{ns}line[@data-layer='wires']")) == 16
    assert [x.text for x in preview.findall(f".//{ns}text[@data-key='refdes']")]
    assert original.get("width", "").endswith("mm")
    assert preview.get("width", "").endswith("mm")

    # The default historical source is not rerendered/overwritten.
    golden = Path(__file__).parent / "fixtures" / "electrical-layout44" / (
        "end-to-end-clean.svg"
    )
    assert specimen_svg().encode("utf-8").replace(b"\r\n", b"\n") == (
        golden.read_bytes().replace(b"\r\n", b"\n")
    )
    assert (circuit, graph) == frozen == authored_specimen()


def test_non_refdes_annotations_are_reserved_by_opt_in_algorithm():
    circuit, _, by_part = _specimen()
    single = Circuit((next(c for c in circuit.components
                      if c.reference == "L1"),), ())
    first = place_refdes_near_visible_graphics(
        single, by_part, STYLE, UnitInk(),
    )[0]
    from gost_schematic.model.annotations import AnnotationPlacement

    pseudo_value = AnnotationPlacement(
        owner="other", key="value", role=first.role, text="RESERVED",
        style=STYLE, baseline=first.baseline,
        ink_bounds=first.ink_bounds, collision_bounds=first.collision_bounds,
        reservation_bounds=None, candidate_index=0,
    )
    other = place_refdes_near_visible_graphics(
        single, by_part, STYLE, UnitInk(),
        existing_placements=(pseudo_value,),
    )
    assert other[0].ink_bounds != first.ink_bounds
    assert not other[0].collision_bounds.overlaps(
        pseudo_value.collision_bounds
    )


def test_opt_in_refdes_respects_other_text_reservation_not_only_ink():
    circuit, _, by_part = _specimen()
    single = Circuit(
        (next(c for c in circuit.components if c.reference == "L1"),), (),
    )
    original = place_refdes_near_visible_graphics(
        single, by_part, STYLE, UnitInk(),
    )[0]
    from gost_schematic.model.annotations import AnnotationPlacement, AnnotationRole

    # Other text ink lives far away but reserves the original candidate's
    # 0.5mm-expanded hitbox; the refdes must not occupy its future text zone.
    reservation = original.collision_bounds
    other = AnnotationPlacement(
        owner="parameter", key="value", role=AnnotationRole.VALUE,
        text="RESERVED", style=STYLE, baseline=Point(0, 0),
        ink_bounds=Box(-5000, -5000, -4000, -4000),
        collision_bounds=Box(-5500, -5500, -3500, -3500),
        reservation_bounds=reservation, candidate_index=0,
    )
    new = place_refdes_near_visible_graphics(
        single, by_part, STYLE, UnitInk(),
        existing_placements=(other,),
    )[0]
    assert new.ink_bounds != original.ink_bounds
    assert not new.collision_bounds.overlaps(reservation)
