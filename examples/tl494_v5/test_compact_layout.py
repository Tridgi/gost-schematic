"""Source-pinned A3 placement tests. No SVG redraw or hidden ERC acceptance."""
from dataclasses import replace

import pytest

from examples.tl494_v5.compact_layout import (
    COMPACT_A3_MM,
    actual_component_occupied_mm,
    compact_source_assembly,
)
from examples.tl494_v5.native_circuit import assemble_native_v5
from gost_schematic.core.geometry import Point
from gost_schematic.model.circuit import Circuit


def test_compact_A3_repositions_only_all_23_real_parts():
    source = assemble_native_v5()
    compact = compact_source_assembly()
    assert len(COMPACT_A3_MM) == len(compact.circuit.components) == 23
    assert source.circuit.nets == compact.circuit.nets
    assert len(compact.circuit.nets) == 15
    old_parts = {c.reference: c for c in source.circuit.components}
    for current in compact.circuit.components:
        before = old_parts[current.reference]
        assert current.part_id == before.part_id
        assert current.nominal == before.nominal
        assert current.transform == before.transform
        assert current.origin.x == 1000 * COMPACT_A3_MM[current.reference][0]
        assert current.origin.y == 1000 * COMPACT_A3_MM[current.reference][1]


def test_real_DA1_owner_placement_moves_rigidly_not_pin_numbers():
    before = assemble_native_v5()
    after = compact_source_assembly()
    old = before.owner_ic_record.placements[0]
    new = after.owner_ic_record.placements[0]
    assert (old.origin.x, old.origin.y) == (100000, 70000)
    assert (new.origin.x, new.origin.y) == (135000, 90000)
    assert new.transform == old.transform
    assert before.owner_ic_record.device == after.owner_ic_record.device
    assert len(after.parts["reference.tl494cn"].pins) == 16
    after.verify()


def test_all_13_catalog_source_profiles_rebound_after_compact_placement():
    result = compact_source_assembly()
    assert len(result.source_UGO_bindings) == 13
    for owner in result.source_UGO_bindings:
        comp = next(c for c in result.circuit.components
                    if c.reference == owner.reference)
        assert owner.instance.origin == comp.origin
        assert owner.instance.transform == comp.transform
        assert owner.part.identifier == comp.part_id
        assert owner.symbol.status.value == "draft"


def test_compact_placement_cannot_hide_physical_net_mismatch():
    original = compact_source_assembly()
    modified = replace(original, circuit=Circuit(
        original.circuit.components, original.circuit.nets[:-1]
    ))
    with pytest.raises(AssertionError, match="V5_BOM_OR_NET_COUNT_DRIFT"):
        modified.verify()


def test_old_9_drc_errors_explicitly_preserved_in_compact_model_metadata():
    result = compact_source_assembly()
    assert result.manifest()["old_known_bad_DRC"] == {
        "errors": 9, "warnings": 32,
        "wires": 91, "junctions": 37,
    }
    assert result.status == "DRAFT_MODEL_ONLY_NO_PRINT"


@pytest.mark.parametrize(
    ("delta_x_um", "delta_y_um"),
    [(25000, 0), (-25000, 0), (0, -40000), (0, 70000)],
)
def test_a3_capacity_never_approves_off_paper_ink_bbox(
    delta_x_um: int, delta_y_um: int,
):
    source = compact_source_assembly()
    original = actual_component_occupied_mm(source, source.symbols)
    assert original["A3_capacity_fit"] is True
    assert original["A3_bbox_within_margins"] is True

    # A rigid translation preserves all 23 real source strokes and their
    # total dimensions, yet moves physical ink beyond a paper margin.
    shifted = replace(source, circuit=Circuit(
        tuple(
            replace(
                part,
                origin=Point(
                    part.origin.x + delta_x_um,
                    part.origin.y + delta_y_um,
                ),
            )
            for part in source.circuit.components
        ),
        source.circuit.nets,
    ))
    measured = actual_component_occupied_mm(shifted, source.symbols)
    assert measured["width_mm"] == original["width_mm"]
    assert measured["height_mm"] == original["height_mm"]
    assert measured["A3_bbox_within_margins"] is False
    assert measured["A3_capacity_fit"] is False
    assert shifted.circuit.nets is source.circuit.nets
