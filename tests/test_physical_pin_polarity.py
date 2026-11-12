"""Physical-pin polarity is a semantic field, never inferred from the UGO."""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

from gost_schematic.catalog.loader import CatalogError, load_symbol
from gost_schematic.catalog.part_loader import load_part, parse_part
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.part import PartDefinition, VoltageOrientationRule
from gost_schematic.model.pins import ElectricalType, PhysicalPin, TerminalPolarity
from gost_schematic.model.quantities import QuantityKind
from gost_schematic.validation.circuit_checks import validate_circuit


def _part(kind="polarized"):
    item = files("gost_schematic").joinpath(f"catalog/parts/capacitors/{kind}.json")
    return load_part(Path(str(item)))


def _symbol(kind="polarized"):
    item = files("gost_schematic").joinpath(f"catalog/symbols/capacitors/{kind}.json")
    return load_symbol(Path(str(item)))


def test_polarized_capacitor_has_explicit_physical_terminal_roles():
    part = _part()
    assert part.identifier == "capacitor.polarized"
    assert part.nominal_kind == QuantityKind.CAPACITANCE
    assert part.voltage_orientation_rule == VoltageOrientationRule.POSITIVE_NOT_BELOW_NEGATIVE
    assert [(pin.number, pin.name, pin.polarity) for pin in part.pins] == [
        ("1", "PLUS", TerminalPolarity.POSITIVE),
        ("2", "MINUS", TerminalPolarity.NEGATIVE),
    ]
    assert all(pin.electrical_type == ElectricalType.PASSIVE for pin in part.pins)


def test_nonpolarized_capacitor_does_not_inherit_polarity_rule():
    part = _part("fixed")
    assert part.voltage_orientation_rule == VoltageOrientationRule.NONE
    assert all(pin.polarity == TerminalPolarity.NONE for pin in part.pins)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_pin_identity_and_polarity_survive_all_orthogonal_transforms(rotation, mirror):
    part, symbol = _part(), _symbol()
    component = ComponentInstance(
        "C7", part.identifier, Point(23000, 11000),
        Transform(rotation=rotation, mirror_x=mirror),
    )
    pin_roles = {pin.number: pin.polarity for pin in part.pins}
    assert pin_roles == {"1": TerminalPolarity.POSITIVE, "2": TerminalPolarity.NEGATIVE}
    ports = pin_corridors_for_component(symbol, component)
    assert [port.pin.number for port in ports] == ["1", "2"]
    assert component.pin_positions(symbol)["1"] == ports[0].contact
    assert component.pin_positions(symbol)["2"] == ports[1].contact
    assert ports[0].contact != ports[1].contact


def test_visual_signs_are_validated_against_physical_mapping():
    part, symbol = _part(), _symbol()
    circuit = Circuit((ComponentInstance("C1", part.identifier),), ())
    valid_codes = {issue.code for issue in validate_circuit(
        circuit, {part.identifier: part}, {symbol.identifier: symbol},
    )}
    assert "GRAPHIC_POLARITY_MISMATCH" not in valid_codes
    assert "POLARITY_UNVERIFIABLE" in valid_codes

    wrong_pin = replace(symbol.pins[0], label="-")
    wrong_symbol = replace(symbol, pins=(wrong_pin, symbol.pins[1]))
    bad_codes = {issue.code for issue in validate_circuit(
        circuit, {part.identifier: part}, {symbol.identifier: wrong_symbol},
    )}
    assert "GRAPHIC_POLARITY_MISMATCH" in bad_codes


def test_invalid_polarly_annotated_part_definition_is_rejected():
    with pytest.raises(ValueError, match="exactly one positive"):
        PartDefinition(
            "bad", "C", "capacitor.polarized",
            (PhysicalPin("1", "A", ElectricalType.PASSIVE, TerminalPolarity.POSITIVE),
             PhysicalPin("2", "B", ElectricalType.PASSIVE)),
            voltage_orientation_rule=VoltageOrientationRule.POSITIVE_NOT_BELOW_NEGATIVE,
        )


def test_invalid_terminal_polarity_and_nonempty_names_required():
    with pytest.raises(TypeError, match="TerminalPolarity"):
        PhysicalPin("1", "PLUS", ElectricalType.PASSIVE, "+")
    with pytest.raises(ValueError, match="name"):
        PhysicalPin("1", " ", ElectricalType.PASSIVE)
    with pytest.raises(TypeError, match="ElectricalType"):
        PhysicalPin("1", "A", "passive")


def test_part_catalog_rejects_unsupported_polarity_value():
    with pytest.raises(CatalogError, match="Invalid physical part"):
        parse_part({
            "schema_version": 1, "id": "bad", "symbol_id": "capacitor.polarized",
            "reference_prefix": "C",
            "pins": [
                {"number": "1", "name": "+", "electrical_type": "passive",
                 "polarity": "anode"}
            ],
        })
