"""Safe ERC: explicit net voltage evidence and physical pin identity only."""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.diagnostics import Severity
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import VoltageOrientationRule
from gost_schematic.model.pins import TerminalPolarity
from gost_schematic.model.potentials import NetPotential, PotentialScenario, parse_voltage
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.polarity_checks import (
    PolarityStatus,
    assess_polarity,
    polarity_diagnostics,
)


@pytest.fixture
def part():
    path = files("gost_schematic").joinpath("catalog/parts/capacitors/polarized.json")
    return load_part(Path(str(path)))


@pytest.fixture
def symbol():
    path = files("gost_schematic").joinpath("catalog/symbols/capacitors/polarized.json")
    return load_symbol(Path(str(path)))


def circuit(part_id="capacitor.polarized", plus_net="A", minus_net="B"):
    return Circuit(
        (ComponentInstance("C1", part_id),),
        (
            Net(plus_net, (PinRef("C1", "1"),)),
            Net(minus_net, (PinRef("C1", "2"),)),
        ),
    )


def scenario(a="5", b="0", *, a_reference="common", b_reference="common"):
    return PotentialScenario("normal supply", (
        NetPotential.from_volts("A", a, reference_id=a_reference),
        NetPotential.from_volts("B", b, reference_id=b_reference),
    ))


def evaluate(part, schematic=None, case=None):
    return assess_polarity(schematic or circuit(), {part.identifier: part},
                           scenario=case)[0]


def test_forward_bias_is_not_an_error(part, symbol):
    result = evaluate(part, case=scenario())
    assert result.status == PolarityStatus.FORWARD
    assert result.differential_volts == 5
    assert result.positive_pin == PinRef("C1", "1")
    assert result.negative_pin == PinRef("C1", "2")
    assert polarity_diagnostics((result,)) == ()
    assert not [issue for issue in validate_circuit(
        circuit(), {part.identifier: part}, {symbol.identifier: symbol},
        scenario=scenario(),
    ) if issue.severity == Severity.ERROR]


def test_reversed_polarized_capacitor_is_error(part, symbol):
    result = evaluate(part, case=scenario("0", "5"))
    assert result.status == PolarityStatus.REVERSED
    assert result.differential_volts == -5
    assert [item.code for item in polarity_diagnostics((result,))] == [
        "POLARITY_REVERSED",
    ]
    errors = validate_circuit(
        circuit(), {part.identifier: part}, {symbol.identifier: symbol},
        scenario=scenario("0", "5"),
    )
    assert any(issue.code == "POLARITY_REVERSED"
               and issue.severity == Severity.ERROR for issue in errors)


def test_unknown_with_named_nets_but_no_declared_voltage(part):
    schematic = circuit(plus_net="+12V", minus_net="GND")
    result = evaluate(part, schematic)
    assert result.status == PolarityStatus.UNKNOWN
    assert result.differential_volts is None
    assert [issue.code for issue in polarity_diagnostics((result,))] == [
        "POLARITY_UNVERIFIABLE",
    ]


def test_unknown_if_one_terminal_has_no_net(part):
    schematic = Circuit(
        (ComponentInstance("C1", part.identifier),),
        (Net("A", (PinRef("C1", "1"),)),),
    )
    assert evaluate(part, schematic, scenario()).status == PolarityStatus.UNKNOWN


def test_unknown_if_one_net_has_no_potential(part):
    case = PotentialScenario("partial", (
        NetPotential.from_volts("A", "5", reference_id="common"),
    ))
    result = evaluate(part, case=case)
    assert result.status == PolarityStatus.UNKNOWN
    assert result.differential_volts is None


def test_unknown_if_voltage_reference_frames_differ(part):
    result = evaluate(part, case=scenario(a_reference="domain1", b_reference="domain2"))
    assert result.status == PolarityStatus.UNKNOWN
    assert result.differential_volts is None


def test_zero_bias_not_counted_as_verified_orientation(part):
    result = evaluate(part, case=scenario("3.3", "3.3"))
    assert result.status == PolarityStatus.ZERO_BIAS
    assert result.differential_volts == 0
    assert polarity_diagnostics((result,))[0].severity == Severity.INFO


def test_negative_supply_potentials_compare_by_difference(part):
    result = evaluate(part, case=scenario("-2,5", "-12,5"))
    assert result.status == PolarityStatus.FORWARD
    assert result.differential_volts == 10


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("mirror", [False, True])
def test_transform_does_not_reverse_semantic_pin_orientation(part, rotation, mirror):
    original = circuit()
    rotated = Circuit((
        replace(original.components[0], origin=Point(22000, 8000),
                transform=Transform(rotation, mirror)),
    ), original.nets)
    assert evaluate(part, rotated, scenario()).status == PolarityStatus.FORWARD
    assert evaluate(part, rotated, scenario("0", "5")).status == PolarityStatus.REVERSED


def test_same_net_on_both_pins_means_zero_bias_not_reverse(part):
    schematic = Circuit(
        (ComponentInstance("C1", part.identifier),),
        (Net("A", (PinRef("C1", "1"), PinRef("C1", "2"))),),
    )
    result = evaluate(part, schematic, scenario())
    assert result.status == PolarityStatus.ZERO_BIAS
    assert result.differential_volts == 0


def test_ambiguous_multiple_net_ownership_is_unknown_not_guessed(part):
    schematic = Circuit(
        (ComponentInstance("C1", part.identifier),),
        (
            Net("A", (PinRef("C1", "1"),)),
            Net("B", (PinRef("C1", "2"),)),
            Net("C", (PinRef("C1", "1"),)),
        ),
    )
    assert evaluate(part, schematic, scenario()).status == PolarityStatus.UNKNOWN


def test_opt_in_rule_is_required_not_inferred_from_plus_minus(part):
    passive = replace(part, voltage_orientation_rule=VoltageOrientationRule.NONE)
    assert all(pin.polarity in (TerminalPolarity.POSITIVE, TerminalPolarity.NEGATIVE)
               for pin in passive.pins)
    assert assess_polarity(circuit(), {passive.identifier: passive}, scenario=scenario()) == ()


def test_voltage_parser_rejects_unsafe_inputs():
    for value in (0.2, True, float("inf"), "NaN", "-Infinity", "1,2.3", ""):
        with pytest.raises((ValueError, TypeError)):
            parse_voltage(value)
    assert parse_voltage("-0,125") == parse_voltage("-0.125")


def test_scenario_requires_unique_nets_and_reference_ids():
    with pytest.raises(ValueError, match="Duplicate potential"):
        PotentialScenario("bad", (
            NetPotential.from_volts("A", "5", reference_id="ground"),
            NetPotential.from_volts("A", "6", reference_id="ground"),
        ))
    with pytest.raises(ValueError, match="reference"):
        NetPotential.from_volts("A", "5", reference_id="")
    with pytest.raises(ValueError, match="scenario"):
        PotentialScenario("", ())


def test_reversed_graphic_labels_do_not_change_electrical_semantics(part, symbol):
    graphic = replace(symbol, pins=(
        replace(symbol.pins[0], label="-"),
        replace(symbol.pins[1], label="+"),
    ))
    assert evaluate(part, case=scenario()).status == PolarityStatus.FORWARD
    issues = validate_circuit(
        circuit(), {part.identifier: part}, {symbol.identifier: graphic},
        scenario=scenario(),
    )
    assert "GRAPHIC_POLARITY_MISMATCH" in {issue.code for issue in issues}
    assert "POLARITY_REVERSED" not in {issue.code for issue in issues}



def test_duplicate_net_names_do_not_produce_false_forward_approval(part):
    schematic = Circuit(
        (ComponentInstance("C1", part.identifier),),
        (
            Net("A", (PinRef("C1", "1"),)),
            Net("A", (PinRef("C1", "1"),)),
            Net("B", (PinRef("C1", "2"),)),
        ),
    )
    assessment = evaluate(part, schematic, scenario())
    assert assessment.status == PolarityStatus.UNKNOWN
    assert "duplicated" in assessment.explanation
