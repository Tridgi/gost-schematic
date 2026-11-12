"""Persistent nominal preferences and electrical unit-family validation."""

import json

import pytest

from gost_schematic.model.circuit import Circuit, ComponentInstance
from gost_schematic.model.nominal_display import (
    ComponentNominalOverride,
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, PhysicalPin
from gost_schematic.model.quantities import Quantity, QuantityKind, Unit
from gost_schematic.validation.circuit_checks import validate_circuit


def test_nominal_display_settings_json_round_trip():
    before = NominalDisplayConfiguration(
        default=NominalDisplaySettings(
            mode=NominalDisplayMode.ESKD_COMPACT,
            show_nominal=True,
            decimal_separator=",",
        ),
        overrides=(
            ComponentNominalOverride("R13", mode=NominalDisplayMode.FULL_UNITS),
            ComponentNominalOverride("C2", show_nominal=False),
        ),
    )
    after = NominalDisplayConfiguration.from_record(
        json.loads(json.dumps(before.to_record(), ensure_ascii=False))
    )
    assert after == before
    assert after.for_reference("R13").mode == NominalDisplayMode.FULL_UNITS
    assert not after.for_reference("C2").show_nominal


def test_display_settings_reject_unknown_schema_and_invalid_boolean():
    with pytest.raises(ValueError, match="version"):
        NominalDisplayConfiguration.from_record({"schema_version": 2})
    record = NominalDisplayConfiguration().to_record()
    record["default"]["show_nominal"] = 1
    with pytest.raises(TypeError):
        NominalDisplayConfiguration.from_record(record)


def test_part_quantity_kind_mismatch_is_diagnosed(resistor):
    part = PartDefinition(
        identifier="generic.resistor",
        reference_prefix="R",
        symbol_id="resistor.fixed",
        pins=(
            PhysicalPin("1", "A", ElectricalType.PASSIVE),
            PhysicalPin("2", "B", ElectricalType.PASSIVE),
        ),
        nominal_kind=QuantityKind.RESISTANCE,
    )
    wrong = Circuit((
        ComponentInstance(
            "R1", part.identifier, nominal=Quantity.from_unit("100", Unit.NANOFARAD),
        ),
    ), ())
    codes = {
        issue.code
        for issue in validate_circuit(
            wrong, {part.identifier: part}, {resistor.identifier: resistor},
        )
    }
    assert "NOMINAL_KIND_MISMATCH" in codes

    correct = Circuit((
        ComponentInstance(
            "R1", part.identifier, nominal=Quantity.from_unit("2300", Unit.OHM),
        ),
    ), ())
    codes = {
        issue.code
        for issue in validate_circuit(
            correct, {part.identifier: part}, {resistor.identifier: resistor},
        )
    }
    assert "NOMINAL_KIND_MISMATCH" not in codes
