"""TL494 v5 compact source-typed A3 *placement*, no invented artwork.

Moves only ComponentInstance positions in an isolated new Circuit and the
same DA1 placement in its real ELEKTRIK IC record. Does not touch original
source e695c415, Net, PinRef, D4 or catalog symbol geometry.
Printing remains blocked until the full owner router passes complete DRC.
"""
from __future__ import annotations

from dataclasses import replace

from examples.tl494_v5.native_circuit import NativeV5Assembly, assemble_native_v5
from gost_schematic.core.geometry import Point
from gost_schematic.model.circuit import Circuit

# Millimetres. Exact placements are an A3 EDITORIAL DRAFT proposal, not
# manufacturer footprint dimensions, a normative symbol or a routed E3.
COMPACT_A3_MM = {
    "X1": (17, 35), "L1": (78, 35),
    "DA1": (135, 90), "VT1": (225, 141),
    "C1": (265, 20), "C2": (265, 62),
    "VD1": (300, 120), "L2": (320, 35),
    "C5": (340, 145), "C6": (365, 145),
    "FU1": (375, 35), "X2": (399, 35),
    "C3": (25, 110), "R1": (55, 110),
    "R2": (85, 110), "R3": (62, 147),
    "R4": (25, 175), "R5": (25, 215),
    "R6": (80, 215), "R7": (110, 235),
    "R8": (225, 213), "C4": (25, 147),
    "C7": (140, 235),
}

A3_LANDSCAPE_UM = (420000, 297000)
PRINT_MARGIN_UM = 10000


def compact_source_assembly() -> NativeV5Assembly:
    """Reposition true physical components without altering source identity."""
    from gost_schematic.catalog.source_profiles import bind_tl494_source

    original = assemble_native_v5()
    original.verify()
    if set(COMPACT_A3_MM) != {
        part.reference for part in original.circuit.components
    } or len(COMPACT_A3_MM) != 23:
        raise AssertionError("A3_COMPACT_SOURCE_23_PARTS_REQUIRED")
    components = tuple(
        replace(
            part,
            origin=Point(
                COMPACT_A3_MM[part.reference][0] * 1000,
                COMPACT_A3_MM[part.reference][1] * 1000,
            ),
        )
        for part in original.circuit.components
    )
    da1_x, da1_y = COMPACT_A3_MM["DA1"]
    old_record = original.owner_ic_record
    revised_places = tuple(
        replace(
            place,
            origin=Point(da1_x * 1000, da1_y * 1000),
        ) if place.component_ref == "DA1" else place
        for place in old_record.placements
    )
    revised_record = replace(old_record, placements=revised_places)
    source_nets = original.circuit.nets  # EXACT objects, no Net remapping.
    revised_circuit = Circuit(components, source_nets)
    revised_glyphs = bind_tl494_source(
        components, original.parts, original.symbols,
        allow_relayout=True,  # Explicit NEW A3 position-only drawing
    )
    result = replace(
        original,
        circuit=revised_circuit,
        owner_ic_record=revised_record,
        source_UGO_bindings=tuple(revised_glyphs),
    )
    result.verify()
    # Strict physical instance counts, D4 rotations and refdes.
    for a, b in zip(
        original.circuit.components, result.circuit.components, strict=True
    ):
        if a.reference != b.reference or a.part_id != b.part_id or (
            a.transform != b.transform or a.nominal != b.nominal
        ):
            raise AssertionError("A3_COMPACT_NOT_POSITION_ONLY")
    if result.circuit.nets != original.circuit.nets:
        raise AssertionError("A3_COMPACT_NET_EDIT_FORBIDDEN")
    return result


def actual_component_occupied_mm(
    assembly: NativeV5Assembly, symbols: dict,
) -> dict:
    """Conservative true catalog stroke bounds; no UGO scaling allowed."""
    footprints = [
        component.transform.box(
            symbols[component.part_id].stroked_bounds
        ).translated(component.origin)
        for component in assembly.circuit.components
    ]
    lowx = min(x.min_x for x in footprints)
    lowy = min(x.min_y for x in footprints)
    highx = max(x.max_x for x in footprints)
    highy = max(x.max_y for x in footprints)
    width = highx - lowx
    height = highy - lowy
    # Capacity alone is insufficient: translating every real component
    # outside the paper preserves bbox width/height. Test absolute paper
    # margins as well, before declaring any candidate A3-eligible.
    within_margins = (
        PRINT_MARGIN_UM <= lowx <= highx
        <= A3_LANDSCAPE_UM[0] - PRINT_MARGIN_UM
        and PRINT_MARGIN_UM <= lowy <= highy
        <= A3_LANDSCAPE_UM[1] - PRINT_MARGIN_UM
    )
    a3_fit = (
        width + 2 * PRINT_MARGIN_UM <= A3_LANDSCAPE_UM[0]
        and height + 2 * PRINT_MARGIN_UM <= A3_LANDSCAPE_UM[1]
        and within_margins
    )
    return {
        "owner": "V5_SOURCE_TYPED_A3_PLACEMENT_DRAFT",
        "bbox_um": [lowx, lowy, highx, highy],
        "width_mm": round(width / 1000, 3),
        "height_mm": round(height / 1000, 3),
        "paper": "A3 landscape",
        "paper_size_mm": [420, 297],
        "margin_mm": PRINT_MARGIN_UM / 1000,
        "nominal_symbols_scaled": False,
        "component_count": len(assembly.circuit.components),
        "A3_capacity_fit": a3_fit,
        "A3_bbox_within_margins": within_margins,
        "DRC_pass": False,
        "printable": False,
    }
