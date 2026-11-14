"""Regression checks for the TL494 source photo reference.

No full E3 conformance claim: assertions cover typed source consistency,
real physical PinRef membership and a source-derived electrical contradiction.
"""
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.external_wire_checks import validate_external_wires

from examples.tl494_native_rework import build as build_power, source_graph
from examples.tl494_full_native_model import (
    MANUFACTURER_PIN_MAP, TRACED_NETS, SPEC, build as build_full,
)


def test_real_native_power_stage_and_graph():
    circuit, parts, symbols, poses = build_power()
    assert len(circuit.components) == 11
    assert len(circuit.nets) == 6
    assert len(source_graph().segments) == 26
    assert validate_external_wires(circuit, source_graph(), parts, symbols) == ()
    assert not [i for i in validate_circuit(circuit, parts, symbols)
                if i.severity.value == "error"]
    assert poses["VT1"] == {"1": (159, 135), "2": (170, 117), "3": (170, 146)}


def test_authoritative_diode_direction():
    _, _, _, coords = build_power()
    assert coords["VD1"]["2"][1] < coords["VD1"]["1"][1]


def test_negative_output_capacitors_are_not_reversed_in_source_model():
    circuit, _, _, _ = build_power()
    nets = {net.name: {(p.reference, p.number) for p in net.members}
            for net in circuit.nets}
    assert {("C5", "1"), ("C6", "1")} <= nets["COMMON"]
    assert {("C5", "2"), ("C6", "2")} <= nets["OUT_BEFORE_FUSE"]


def test_full_23_part_typed_circuit():
    circuit, parts, symbols, seen = build_full()
    assert len(circuit.components) == len(SPEC) == 23
    assert len(circuit.nets) == len(TRACED_NETS) == 15
    assert len(seen) == sum(len(net.members) for net in circuit.nets)
    assert len(seen) == 62
    assert not [d for d in validate_circuit(circuit, parts, symbols)
                if d.severity.value == "error"]


def test_all_tl494_physical_numbers_and_functions():
    assert set(MANUFACTURER_PIN_MAP) == {str(i) for i in range(1, 17)}
    assert MANUFACTURER_PIN_MAP["12"][0] == "VCC"
    assert MANUFACTURER_PIN_MAP["13"][0] == "OUTPUT CTRL"
    assert MANUFACTURER_PIN_MAP["14"][0] == "REF"
    assert MANUFACTURER_PIN_MAP["7"][0] == "GND"


def test_source_a_b_named_continuations_are_not_open_unknowns():
    a = set(TRACED_NETS["a_INPUT_PLUS"])
    b = set(TRACED_NETS["b_NEGATIVE_OUTPUT"])
    assert {("X1", "1"), ("DA1", "12"), ("DA1", "8"), ("DA1", "11")} <= a
    assert {("FU1", "2"), ("X2", "1"), ("R5", "2")} <= b
    assert a.isdisjoint(b)


def test_photo_bom_oscillator_frequency_conflict():
    _, r, runit = SPEC["R7"]
    _, c, cunit = SPEC["C7"]
    from gost_schematic.model.quantities import Quantity
    resistance = Quantity.from_unit(r, runit).si_value
    capacitance = Quantity.from_unit(c, cunit).si_value
    observed = 1 / (resistance * capacitance)
    assert 1400 < observed < 1500
    assert observed < 100000 / 50
