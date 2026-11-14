"""Real cross-PR E3 integration: ELEKTRIK #97 model -> PAINT #93 SVG.

In the normal isolated #97 suite this is skipped because the other unmerged
module is absent. The dedicated pinned two-source GitHub Actions workflow
REQUIRES both modules and measured real OpenGost Type A; skips are disallowed.
All test pinouts are explicitly SYNTHETIC, never manufacturer identities.
"""
import os
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_ic_cycle7 import synthetic_ic
from gost_schematic.core.geometry import Box, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.core.units import format_mm
from gost_schematic.electrical.ic import (
    IcKind,
    IcPinType,
    resolve_ic_pin_positions,
    validate_ic_circuit,
)
from gost_schematic.electrical.ic_paint_bridge import (
    IcPaintBinding,
    propose_ic_paint_binding,
)
from gost_schematic.electrical.ic_serde import IcLibraryRecord, ic_from_json, ic_to_json
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.standards.type_a_font import inspect_type_a_font

PAINT = pytest.importorskip("gost_schematic.rendering.ic_rectangular")
render_resolved_ic = PAINT.render_resolved_ic

SVG = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def typography():
    font = os.environ.get("IC_TYPE_A_FONT_PATH")
    assert font and Path(font).is_file(), (
        "IC_TYPE_A_FONT_PATH must point to the measured real OpenGost Type A; "
        "this test must not silently substitute synthetic font metrics"
    )
    verified = inspect_type_a_font(Path(font), h_um=3500)
    assert verified.measured_cap_height_um == 3500
    assert verified.style.font_sha256
    return verified.style, PillowTextMeasurer()


@pytest.mark.parametrize("kind", (IcKind.ANALOG, IcKind.DIGITAL))
@pytest.mark.parametrize("count", (2, 4, 8, 14, 40, 64))
def test_real_model_to_real_paint_exact_svg_endpoints(typography, count, kind):
    style, measurer = typography
    source = synthetic_ic(count, kind)
    saved_original = ic_to_json(source)
    binding = propose_ic_paint_binding(source, style, measurer)
    binding.verify_endpoints()
    assert ic_to_json(source) == saved_original
    assert binding.record.device == source.device
    assert binding.record.placements == source.placements
    assert all(new.revision == old.revision + 1 for old, new
               in zip(source.specs, binding.record.specs, strict=True))
    physical = resolve_ic_pin_positions(
        binding.record.device, binding.record.specs, binding.record.placements,
    )
    assert len(physical) == count
    assert ic_from_json(ic_to_json(binding.record)) == binding.record
    if count >= 14:
        assert len(binding.views) == 2
    numbers = set()
    for view, placement in zip(binding.views, binding.record.placements, strict=True):
        image = render_resolved_ic(view, style, measurer, glyph_detail=True)
        root = ET.fromstring(image.svg)
        assert root.get("data-approval") == "DRAFT"
        assert root.get("data-font-sha256") == style.font_sha256
        lines = root.findall(
            f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
        )
        assert len(lines) == len(view.pins)
        for line in lines:
            number = line.get("data-pin-number")
            assert number not in numbers
            numbers.add(number)
            expected = physical[PinRef(placement.component_ref, number)]
            assert line.get("x2") == format_mm(expected.x)
            assert line.get("y2") == format_mm(expected.y)
            assert (number, expected) in {
                (p.number, p.anchor) for p in view.pins
            }
            assert line.get("data-real-anchor") == "true"
        assert all(x.kind != "pin-number" or not image.body_world.overlaps(x.box)
                   for x in image.ink)
    assert numbers == {pin.number for pin in source.device.pins}
    assert set(physical) == {
        PinRef(kind.reference_prefix + "1", str(index))
        for index in range(1, count + 1)
    }


def test_exact_one_micrometre_disagreement_is_rejected(typography):
    style, measurer = typography
    binding = propose_ic_paint_binding(synthetic_ic(8), style, measurer)
    view = binding.views[0]
    first = view.pins[0]
    invalid_pin = replace(first, anchor=Point(first.anchor.x + 1, first.anchor.y))
    broken = replace(view, pins=(invalid_pin, *view.pins[1:]))
    with pytest.raises(ValueError, match="IC_PIN_ANCHOR_MISMATCH"):
        render_resolved_ic(broken, style, measurer)


def test_resize_changes_geometry_only_not_circuit_nets_or_pin_numbers(typography):
    style, measurer = typography
    source = synthetic_ic(14)
    circuit = Circuit(
        (ComponentInstance("DD1", source.device.identifier),),
        (
            Net("DATA", (PinRef("DD1", "1"),)),
            Net("VDD", (PinRef("DD1", "13"),)),
            Net("OPEN_COLLECTOR", (PinRef("DD1", "12"),)),
        ),
    )
    validate_ic_circuit(source.device, circuit, "DD1")
    original_nets = circuit.nets
    first = propose_ic_paint_binding(source, style, measurer)
    first_positions = resolve_ic_pin_positions(
        first.record.device, first.record.specs, first.record.placements,
    )
    modified = replace(
        source.specs[0],
        main_field="ФУНКЦИОНАЛЬНЫЙ_РЕГИСТР_С_ОЧЕНЬ_ДЛИННЫМ_ИМЕНЕМ",
    )
    modified_source = IcLibraryRecord(
        source.device, (modified, *source.specs[1:]), source.placements,
    )
    second = propose_ic_paint_binding(modified_source, style, measurer)
    second_positions = resolve_ic_pin_positions(
        second.record.device, second.record.specs, second.record.placements,
    )
    assert second.record.specs[0].body.max_x > first.record.specs[0].body.max_x
    assert second_positions != first_positions
    assert set(second_positions) == set(first_positions)
    assert tuple(x.number for x in second.record.device.pins) == tuple(
        x.number for x in source.device.pins
    )
    assert circuit.nets is original_nets
    validate_ic_circuit(second.record.device, circuit, "DD1")
    for view in second.views:
        render_resolved_ic(view, style, measurer)


def test_power_open_collector_nc_and_split_units_are_physical_not_svg_nets(typography):
    style, measurer = typography
    source = synthetic_ic(14)
    binding = propose_ic_paint_binding(source, style, measurer)
    assert len(binding.views) == 2
    pin_types = source.device.pin_map
    assert pin_types["12"].electrical_type is IcPinType.OPEN_COLLECTOR
    assert pin_types["13"].electrical_type is IcPinType.POWER_INPUT
    assert pin_types["14"].electrical_type is IcPinType.NC
    assert all(p.role in ("out", "power", "nc") for view in binding.views
               for p in view.pins if p.number in ("12", "13", "14"))
    circuit = Circuit(
        (ComponentInstance("DD1", source.device.identifier),),
        (Net("ILLEGAL_NC", (PinRef("DD1", "14"),)),),
    )
    with pytest.raises(ValueError, match="IC_NC_CONNECTED"):
        validate_ic_circuit(source.device, circuit, "DD1")
    rendered = [render_resolved_ic(v, style, measurer) for v in binding.views]
    assert sum(len(r.pin_anchors) for r in rendered) == 14


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_real_paint_d4_split_identity_and_fail_closed_views(
    typography, rotation, mirror,
):
    style, measurer = typography
    source = synthetic_ic(14)
    placements = tuple(replace(
        p, transform=Transform(rotation, mirror),
    ) for p in source.placements)
    transformed = IcLibraryRecord(source.device, source.specs, placements)
    binding = propose_ic_paint_binding(transformed, style, measurer)
    base = propose_ic_paint_binding(source, style, measurer)
    refs = resolve_ic_pin_positions(
        binding.record.device, binding.record.specs, binding.record.placements,
    )
    original_refs = resolve_ic_pin_positions(
        base.record.device, base.record.specs, base.record.placements,
    )
    assert set(refs) == set(original_refs)
    assert len(refs) == 14
    binding.verify_endpoints()
    for view in binding.views:
        try:
            svg = render_resolved_ic(view, style, measurer).svg
        except ValueError as error:
            # PAINT currently refuses some upright-text D4 cases; that is
            # a documented DRAFT layout gate, not a permission to move pins.
            assert any(marker in str(error) for marker in (
                "IC_INK_COLLISION", "IC_TEXT_OVERFLOW",
            )), str(error)
        else:
            lines = ET.fromstring(svg).findall(
                f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
            )
            for line in lines:
                ref = PinRef("DD1", line.get("data-pin-number"))
                assert line.get("x2") == format_mm(refs[ref].x)
                assert line.get("y2") == format_mm(refs[ref].y)


def test_undeclared_top_bottom_mix_is_rejected_before_paint(typography):
    source = synthetic_ic(2)
    spec = source.specs[0]
    top_row = replace(
        spec.rows[0], side=Side.TOP, anchor=Point(5000, -4000),
    )
    # Fail immediately at the authoritative model boundary. A mixed-side
    # view without an explicit TOP_BOTTOM profile must never reach PAINT.
    with pytest.raises(ValueError, match="IC_PORT_LAYOUT_MISMATCH"):
        replace(spec, rows=(top_row, spec.rows[1]))


def test_source_side_reflow_is_explicit_not_hidden_or_physical(typography):
    style, measurer = typography
    source = synthetic_ic(14)
    before = ic_to_json(source)
    binding = propose_ic_paint_binding(source, style, measurer)
    assert ic_to_json(source) == before
    assert len(binding.side_reflows) == 5
    for reflow in binding.side_reflows:
        source_spec = next(s for s in source.specs if s.unit_id == reflow.unit_id)
        target_spec = next(s for s in binding.record.specs
                           if s.unit_id == reflow.unit_id)
        old_row = next(r for r in source_spec.rows
                       if r.number == reflow.pin_ref.number)
        new_row = next(r for r in target_spec.rows
                       if r.number == reflow.pin_ref.number)
        assert old_row.side == reflow.old_side
        assert new_row.side == reflow.new_side
        assert old_row.visual_row == new_row.visual_row
        assert old_row.row_key == new_row.row_key
        assert old_row.label == new_row.label
        assert source.device.pin_map[old_row.number] == (
            binding.record.device.pin_map[new_row.number]
        )


@pytest.mark.parametrize("corruption", (
    "number", "pin_id", "role", "label", "row", "row_key",
    "side", "anchor", "reference", "body", "origin", "transform",
    "function", "pin-order", "unit-identity",
))
def test_semantic_seam_catches_mutation_even_when_terminal_matches(
    typography, corruption,
):
    style, measurer = typography
    binding = propose_ic_paint_binding(synthetic_ic(8), style, measurer)
    view = binding.views[0]
    # A normal INPUT on RIGHT is rejected by PAINT already at object
    # construction. Probe the *extra* electrical guard using a POWER pin:
    # PAINT accepts both drawing sides for POWER, whereas the model contract
    # still must reject a side change at an identical immutable endpoint.
    index = 6 if corruption == "side" else 0
    original = view.pins[index]
    edits = {
        "number": {"number": "999"},
        "pin_id": {"pin_id": "WRONG.P1"},
        "role": {"role": "passive"},
        "label": {"label": "FALSE_FUNCTION"},
        "row": {"row": 100},
        "row_key": {"row_key": "FAKE_BUS"},
        "side": {"side": Side.RIGHT},
        "anchor": {"anchor": Point(original.anchor.x + 1, original.anchor.y)},
    }
    if corruption in edits:
        altered = list(view.pins)
        altered[index] = replace(original, **edits[corruption])
        view = replace(view, pins=tuple(altered))
    elif corruption == "pin-order":
        view = replace(view, pins=(
            view.pins[1], view.pins[0], *view.pins[2:],
        ))
    elif corruption == "reference":
        view = replace(view, reference="DD999")
    elif corruption == "body":
        view = replace(view, body=Box(
            view.body.min_x, view.body.min_y,
            view.body.max_x + 2500, view.body.max_y,
        ))
    elif corruption == "origin":
        view = replace(view, origin=Point(view.origin.x + 1, view.origin.y))
    elif corruption == "transform":
        view = replace(view, transform=Transform(90, False))
    elif corruption == "function":
        view = replace(view, content=replace(
            view.content, function="NOT_SOURCE_FUNCTION",
        ))
    else:
        assert corruption == "unit-identity"
        invalid = IcPaintBinding(
            binding.record, binding.views, ("UNKNOWN_UNIT",),
        )
        with pytest.raises(ValueError, match="IC_PAINT_UNIT_COUNT_MISMATCH"):
            invalid.verify_endpoints()
        return
    invalid = replace(binding, views=(view,))
    expected = (
        "IC_PIN_ANCHOR_MISMATCH"
        if corruption == "anchor" else
        "IC_PAINT_VIEW_SEMANTIC_MISMATCH"
        if corruption in ("reference", "body", "origin", "transform", "function")
        else "IC_PAINT_PIN_SEMANTIC_MISMATCH"
    )
    with pytest.raises(ValueError, match=expected):
        invalid.verify_endpoints()


def test_explicit_resizing_preserves_existing_large_valid_body(typography):
    style, measurer = typography
    source = synthetic_ic(8)
    spec = source.specs[0]
    expanded = Box(
        spec.body.min_x, spec.body.min_y, 200000, 205000,
    )
    rows = tuple(replace(
        row, anchor=Point(
            expanded.max_x + 4000 if row.side is Side.RIGHT else -4000,
            row.anchor.y,
        ),
    ) for row in spec.rows)
    large = IcLibraryRecord(
        source.device, (replace(spec, body=expanded, rows=rows),),
        source.placements,
    )
    binding = propose_ic_paint_binding(large, style, measurer)
    updated = binding.record.specs[0].body
    assert updated.max_x >= expanded.max_x
    assert updated.max_y >= expanded.max_y
    assert binding.record.specs[0].revision == spec.revision + 1
    render_resolved_ic(binding.views[0], style, measurer)
