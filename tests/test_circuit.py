from gost_schematic.core.diagnostics import Severity
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.pins import ElectricalType, PhysicalPin
from gost_schematic.validation.circuit_checks import validate_circuit


def _resistor_part():
    return PartDefinition(
        identifier="generic.resistor", reference_prefix="R",
        symbol_id="resistor.fixed",
        pins=(PhysicalPin("1", "A", ElectricalType.PASSIVE),
              PhysicalPin("2", "B", ElectricalType.PASSIVE)),
    )


def test_netlist_independent_of_graphical_placement(resistor):
    part = _resistor_part()
    first = ComponentInstance("R1", part.identifier, Point(0, 0))
    second = ComponentInstance("R2", part.identifier, Point(20000, 0),
                               Transform(rotation=180))
    assert second.pin_positions(resistor)["1"] == Point(28000, 0)
    circuit = Circuit(
        (first, second),
        (Net("MID", (PinRef("R1", "2"), PinRef("R2", "1"))),),
    )
    issues = validate_circuit(circuit, {part.identifier: part}, {resistor.identifier: resistor})
    assert not [issue for issue in issues if issue.severity == Severity.ERROR]


def test_one_physical_pin_cannot_be_on_two_nets(resistor):
    part = _resistor_part()
    circuit = Circuit(
        (ComponentInstance("R1", part.identifier),),
        (Net("A", (PinRef("R1", "1"),)), Net("B", (PinRef("R1", "1"),))),
    )
    codes = {d.code for d in validate_circuit(
        circuit, {part.identifier: part}, {resistor.identifier: resistor})}
    assert "MULTIPLE_NET_OWNERSHIP" in codes


def test_missing_pin_and_reference_are_reported(resistor):
    part = _resistor_part()
    circuit = Circuit(
        (ComponentInstance("R1", part.identifier),),
        (Net("BAD", (PinRef("R1", "999"), PinRef("R999", "1"))),),
    )
    codes = {d.code for d in validate_circuit(
        circuit, {part.identifier: part}, {resistor.identifier: resistor})}
    assert {"UNKNOWN_PIN", "UNKNOWN_COMPONENT"} <= codes


def test_symbol_and_physical_pin_mismatch_is_reported(resistor):
    wrong = PartDefinition(
        "generic.wrong", "R", "resistor.fixed",
        (PhysicalPin("1", "A", ElectricalType.PASSIVE),),
    )
    issues = validate_circuit(
        Circuit((ComponentInstance("R1", "generic.wrong"),), ()),
        {wrong.identifier: wrong}, {resistor.identifier: resistor},
    )
    assert "PIN_MAPPING_MISMATCH" in {issue.code for issue in issues}
