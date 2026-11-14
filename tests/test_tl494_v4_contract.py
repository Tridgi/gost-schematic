"""P0/P1/P2/P7 independent TL494 v4 source and exact geometric negative tests."""
import pytest

from gost_schematic.core.geometry import Point
from gost_schematic.validation.external_wire_checks import ExternalWireGraph, WireSegment

from examples.tl494_v4.model_contract import (
    PIN_ALIASES, PIN_DESCRIPTIONS, PIN_TYPES, SOURCE_SHEET_PARTS,
    frozen_inventory,
)
from examples.tl494_v4.wire_drc import (
    analyze_wire_graph, pair_clearance, right_angle_crossing,
)
from gost_schematic.model.pins import ElectricalType


def p(x,y):
    return Point(x,y)


def h(y,name):
    return WireSegment(p(0,y),p(10000,y),name)


def v(x,name):
    return WireSegment(p(x,-5000),p(x,5000),name)


def test_original_23_parts_15_nets_and_16_pinrefs():
    info=frozen_inventory()
    assert info["component_count"]==23
    assert info["net_count"]==15
    assert info["DA1_pin_count"]==16
    assert set(SOURCE_SHEET_PARTS)==set(info["source_components"])


def test_exact_source_symbol_selection():
    for ref in ("C1","C2","C3","C5","C6"):
        assert SOURCE_SHEET_PARTS[ref][0]=="capacitor.polarized"
    for ref in ("C4","C7"):
        assert SOURCE_SHEET_PARTS[ref][0]=="capacitor.fixed"
    for ref in ("L1","L2"):
        assert SOURCE_SHEET_PARTS[ref][0]=="inductor.ferromagnetic"
    assert SOURCE_SHEET_PARTS["VT1"][0]=="transistor.mosfet_n_enh"
    assert SOURCE_SHEET_PARTS["VD1"][0]=="diode.schottky"


def test_tl494_pin3_is_physical_input_not_output():
    assert PIN_TYPES["3"] is ElectricalType.INPUT
    assert PIN_DESCRIPTIONS["3"]=="FEEDBACK"
    assert PIN_ALIASES["3"]=="FB"
    assert PIN_DESCRIPTIONS["13"]=="OUTPUT CTRL"
    assert PIN_ALIASES["13"]=="OC"
    assert len(set(PIN_ALIASES.values()))==16
    assert all(0<len(x)<=6 for x in PIN_ALIASES.values())


@pytest.mark.parametrize("gap_um,accepted",[
    (1,False),
    (2990,False),
    (2999,False),
    (3000,True),
    (3001,True),
])
def test_exact_edge_clearance_including_both_0p3mm_wire_strokes(gap_um,accepted):
    a=h(0,"COMMON")
    b=h(gap_um+300,"CONTROL")
    assert pair_clearance(a,b)==gap_um
    report=analyze_wire_graph(ExternalWireGraph((a,b)))
    assert (report["parallel_violation_count"]==0)==accepted


def test_only_overlapping_parallel_distinct_nets_trigger_3mm_rule():
    a=h(0,"a")
    b=WireSegment(p(11000,300),p(21000,300),"b")
    assert pair_clearance(a,b) is None
    assert analyze_wire_graph(ExternalWireGraph((a,b)))["parallel_violation_count"]==0


def test_orthogonal_distinct_net_x_never_silently_merged():
    a=h(0,"a")
    b=v(5000,"b")
    assert right_angle_crossing(a,b)==(5000,0)
    d=analyze_wire_graph(ExternalWireGraph((a,b)))
    assert d["distinct_net_x_crossings"]==1
    assert d["status"]=="FAIL"


def test_foreign_net_crossing_at_explicit_junction_is_hard_error():
    a=h(0,"a");b=v(5000,"b")
    d=analyze_wire_graph(ExternalWireGraph((a,b),(p(5000,0),)))
    assert "UNAUTHORIZED_CROSS_NET_JUNCTION" in {v["code"] for v in d["violations"]}


def test_same_net_connected_parallel_strokes_exempt_from_foreign_net_check():
    d=analyze_wire_graph(ExternalWireGraph((h(0,"COMMON"),h(100,"COMMON"))))
    assert d["parallel_violation_count"]==0


def test_source_photo_pins_not_renamed_as_net_membership():
    info=frozen_inventory()
    assert "DA1.12" in info["source_nets"]["a_INPUT_PLUS"]
    assert "DA1.8" in info["source_nets"]["a_INPUT_PLUS"]
    assert "DA1.11" in info["source_nets"]["a_INPUT_PLUS"]
    assert "DA1.7" in info["source_nets"]["COMMON"]
    assert not any("PE"==name for name in info["source_nets"])
