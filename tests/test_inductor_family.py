"""ГОСТ 2.723-68 winding family: independent variant specs, real arcs and pins."""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

from gost_schematic.catalog.inductors import (
    AdjustmentKind,
    CoreKind,
    InductorSpec,
    build_inductor,
    load_inductor,
    parse_inductor_spec,
)
from gost_schematic.catalog.loader import CatalogError
from gost_schematic.core.geometry import Semicircle, Side, StyledLine
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.quantities import QuantityKind
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.symbol_checks import validate_symbol

SPEC_ROOT = files("gost_schematic").joinpath("catalog/inductors")
VARIANTS = (
    "inductor.air_core", "inductor.ferromagnetic", "inductor.gapped_core",
    "inductor.ferrite", "inductor.magnetodielectric",
    "inductor.trim_magnetodielectric", "inductor.trim_copper",
    "inductor.tapped", "inductor.double_tapped",
    "inductor.sliding_contact", "inductor.double_sliding",
    "inductor.variable", "choke.air_core", "choke.ferromagnetic",
    "choke.ferrite",
)


def variant(name: str):
    return load_inductor(Path(str(SPEC_ROOT.joinpath(f"{name}.json"))))


@pytest.mark.parametrize("name", VARIANTS)
def test_every_variant_has_separate_draft_part_and_one_source_of_truth(name):
    built = variant(name)
    assert built.symbol.identifier == built.part.identifier == name
    assert built.part.symbol_id == name
    assert built.part.nominal_kind == QuantityKind.INDUCTANCE
    assert built.symbol.status == SymbolStatus.DRAFT
    assert built.symbol.standard_refs[0].startswith("ГОСТ 2.723-68")
    assert len(built.symbol.graphics) >= 6
    assert len([g for g in built.symbol.graphics if isinstance(g, Semicircle)]) == 4
    assert {p.number for p in built.part.pins} == {p.number for p in built.symbol.pins}
    assert all(pin.polarity.value == "none" for pin in built.part.pins)
    diagnostics = validate_symbol(built.symbol)
    assert not [d for d in diagnostics if d.severity.value == "error"]


def test_air_core_is_four_exact_semicircles_and_two_leads():
    built = variant("inductor.air_core")
    coils = [item for item in built.symbol.graphics if isinstance(item, Semicircle)]
    assert [coil.center.x for coil in coils] == [-6000, -2000, 2000, 6000]
    assert all(coil.radius == 2000 and coil.bulge == Side.TOP for coil in coils)
    assert len(built.part.pins) == 2
    assert built.symbol.pins[0].at.x == -12000
    assert built.symbol.pins[1].at.x == 12000
    assert not any(isinstance(item, StyledLine) for item in built.symbol.graphics)


@pytest.mark.parametrize(
    ("name", "expected_strokes", "width", "dashed"),
    [
        ("inductor.ferromagnetic", 1, 300, False),
        ("inductor.gapped_core", 2, 300, False),
        ("inductor.ferrite", 1, 600, False),
        ("inductor.magnetodielectric", 1, 300, True),
        ("inductor.trim_magnetodielectric", 1, 300, True),
        ("inductor.trim_copper", 1, 300, True),
    ],
)
def test_magnetic_core_styles_are_semantic_and_numerically_exact(
    name, expected_strokes, width, dashed,
):
    pieces = [g for g in variant(name).symbol.graphics if isinstance(g, StyledLine)]
    assert len(pieces) == expected_strokes
    assert all(g.stroke_width_um == width for g in pieces)
    assert all(bool(g.dash_pattern_um) is dashed for g in pieces)


def test_gapped_core_has_visible_airgap_and_zero_unspecified_contacts():
    symbol = variant("inductor.gapped_core").symbol
    pieces = [g for g in symbol.graphics if isinstance(g, StyledLine)]
    assert pieces[0].end.x < pieces[1].start.x
    assert pieces[1].start.x - pieces[0].end.x >= 1500
    assert len(symbol.pins) == 2


@pytest.mark.parametrize(
    ("name", "names"),
    [
        ("inductor.tapped", ["START", "END", "TAP1"]),
        ("inductor.double_tapped", ["START", "END", "TAP1", "TAP2"]),
        ("inductor.sliding_contact", ["START", "END", "SLIDER1"]),
        ("inductor.double_sliding", ["START", "END", "SLIDER1", "SLIDER2"]),
    ],
)
def test_extra_contacts_are_really_in_physical_part_and_netlist(name, names):
    built = variant(name)
    assert [p.name for p in built.part.pins] == names
    members = tuple(PinRef("L1", str(index + 1)) for index in range(len(names)))
    circuit = Circuit((ComponentInstance("L1", built.part.identifier),),
                      (Net("COMMON", members),))
    errors = validate_circuit(
        circuit, {built.part.identifier: built.part},
        {built.symbol.identifier: built.symbol},
    )
    assert not [issue for issue in errors if issue.severity.value == "error"]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_all_contacts_and_core_arcs_rotate_and_mirror_without_renumbering(
    rotation, mirror,
):
    built = variant("inductor.double_tapped")
    component = ComponentInstance(
        "L7", built.part.identifier, transform=Transform(rotation, mirror),
    )
    assert set(component.pin_positions(built.symbol)) == {"1", "2", "3", "4"}
    for pin in built.symbol.pins:
        assert component.pin_positions(built.symbol)[pin.number] == (
            component.transform.apply(pin.at)
        )
    for primitive in built.symbol.graphics:
        rotated = component.transform.primitive(primitive)
        if isinstance(primitive, Semicircle):
            assert isinstance(rotated, Semicircle)
            assert rotated.bulge == component.transform.side(primitive.bulge)


def test_copper_core_uses_independent_constant_text_slot():
    built = variant("inductor.trim_copper")
    assert built.symbol.constant_annotations == (("core_material", "Cu"),)
    assert "core_material" in [item.key for item in built.symbol.annotation_slots]
    assert built.spec.adjustment == AdjustmentKind.CORE_TRIM
    assert built.spec.core == CoreKind.NONMAGNETIC_COPPER


def test_core_variants_can_change_turn_count_without_copying_shapes():
    base = variant("inductor.ferrite")
    custom = build_inductor(replace(base.spec, turns=7, revision=2))
    assert len([item for item in custom.symbol.graphics
                if isinstance(item, Semicircle)]) == 7
    assert custom.symbol.revision == 2
    assert custom.part.pins == base.part.pins


@pytest.mark.parametrize(
    "data",
    [
        {"schema_version": 2, "id": "inductor.bad"},
        {"schema_version": 1, "id": "inductor.bad", "core": "unicorn"},
        {"schema_version": 1, "id": "inductor.bad", "turns": 0},
        {"schema_version": 1, "id": "inductor.bad", "tap_turns": [0, 0]},
        {"schema_version": 1, "id": "inductor.bad", "tap_turns": [9]},
        {"schema_version": 1, "id": "inductor.bad", "radius_mm": "0.1"},
        {"schema_version": 1, "id": "inductor.bad", "adjustment": "core_trim"},
        {
            "schema_version": 1, "id": "inductor.bad",
            "tap_turns": [1], "slider_turns": [1],
        },
        {
            "schema_version": 1, "id": "inductor.bad",
            "core": "ferrite", "tap_turns": [1],
        },
    ],
)
def test_invalid_or_ambiguous_inductor_config_never_silently_normalizes(data):
    with pytest.raises(CatalogError):
        parse_inductor_spec(data)


def test_typed_inductor_spec_rejects_invalid_ids_and_separate_core_tuning():
    with pytest.raises(ValueError):
        InductorSpec("transformer.fake")
    with pytest.raises(ValueError):
        InductorSpec("inductor.fake", adjustment=AdjustmentKind.CORE_TRIM)
