"""Negative and geometric regressions for two draft GOST 2.730-73 diodes.

Only the source-backed *class* is normative. All pinned numeric fixture
coordinates are editable DRAFT review profiles, not certified GOST sizes.
"""

from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.catalog.diode_review import verify_draft_diode
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.geometry import Line, Point, Side
from gost_schematic.core.transforms import Transform
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef
from gost_schematic.model.part import VoltageOrientationRule
from gost_schematic.model.pins import ElectricalType, TerminalFunction, TerminalPolarity
from gost_schematic.model.quantities import QuantityKind
from gost_schematic.model.symbol import SymbolStatus
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.circuit_checks import validate_circuit
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.dimensional_checks import check_verified_dimensions
from gost_schematic.validation.symbol_checks import validate_symbol

SRC = files("gost_schematic").joinpath("catalog")
SVG = "{http://www.w3.org/2000/svg}"
IDS = ("diode.general", "diode.zener")


def _load(name):
    suffix = name.split(".", 1)[1]
    symbol = load_symbol(Path(str(SRC.joinpath(f"symbols/diodes/{suffix}.json"))))
    part = load_part(Path(str(SRC.joinpath(f"parts/diodes/{suffix}.json"))))
    return symbol, part


@pytest.mark.parametrize("identifier", IDS)
def test_two_independent_draft_ugo_parts_and_source_evidence(identifier):
    symbol, part = _load(identifier)
    verify_draft_diode(symbol, part)
    assert symbol.identifier == part.identifier == part.symbol_id == identifier
    assert part.reference_prefix == "VD"
    assert part.nominal_kind is None
    assert part.voltage_orientation_rule == VoltageOrientationRule.NONE
    assert symbol.revision == 1
    assert symbol.status == SymbolStatus.DRAFT
    assert len(symbol.standard_refs) >= 3
    assert any("ГОСТ 2.730-73" in source for source in symbol.standard_refs)
    assert any("EDITORIAL_ASSUMPTION" in source for source in symbol.standard_refs)
    assert not [issue for issue in validate_symbol(symbol)
                if issue.severity.value == "error"]


@pytest.mark.parametrize("identifier", IDS)
def test_anode_cathode_names_are_not_absolute_voltage_polarity(identifier):
    symbol, part = _load(identifier)
    assert [(pin.number, pin.name) for pin in part.pins] == [
        ("1", "A"), ("2", "K"),
    ]
    assert [(pin.number, pin.label) for pin in symbol.pins] == [
        ("1", "A"), ("2", "K"),
    ]
    assert all(pin.polarity == TerminalPolarity.NONE for pin in part.pins)
    assert all(pin.function == TerminalFunction.GENERAL for pin in part.pins)
    assert all(pin.electrical_type == ElectricalType.PASSIVE for pin in part.pins)
    assert not check_verified_dimensions(symbol).applicable_rules
    assert check_verified_dimensions(symbol).valid


@pytest.mark.parametrize("identifier", IDS)
def test_anode_and_cathode_are_distinct_explicit_conductor_islands(identifier):
    symbol, _ = _load(identifier)
    trace = inspect_conductor_topology(symbol)
    assert trace.valid, trace.diagnostics
    assert trace.pin_islands == (("1",), ("2",))
    assert trace.visited_primitives == 2
    assert trace.explicit_junctions == 0
    assert symbol.conductor_topology.conductor_indices == (0, 1)
    assert len(symbol.graphics) == (6 if identifier.endswith("general") else 8)


def test_zener_kink_is_distinct_from_plain_bar_even_as_a_raw_svg():
    general, _ = _load("diode.general")
    zener, _ = _load("diode.zener")
    assert general.graphics[:6] == zener.graphics[:6]
    assert general.graphics[5] == Line(Point(2500, -3300), Point(2500, 3300))
    assert zener.graphics[6:] == (
        Line(Point(2500, -3300), Point(1300, -3300)),
        Line(Point(2500, 3300), Point(3700, 3300)),
    )
    assert render_symbol_svg(general) != render_symbol_svg(zener)
    for symbol in (general, zener):
        tree = ET.fromstring(render_symbol_svg(symbol))
        assert len(tree.findall(f".//{SVG}line")) == len(symbol.graphics)
        assert not tree.findall(f".//{SVG}image")


@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_all_eight_transforms_preserve_A_K_physical_roles_and_pin_escape(
    identifier, rotation, mirror,
):
    symbol, part = _load(identifier)
    transform = Transform(rotation=rotation, mirror_x=mirror)
    instance = ComponentInstance(
        "VD17", part.identifier, Point(24000, 18000), transform,
    )
    positions = instance.pin_positions(symbol)
    assert list(positions) == ["1", "2"]
    assert positions["1"] == transform.apply(symbol.pins[0].at) + instance.origin
    assert positions["2"] == transform.apply(symbol.pins[1].at) + instance.origin
    assert positions["1"] != positions["2"]
    corridors = pin_corridors_for_component(symbol, instance)
    assert [corridor.pin for corridor in corridors] == [
        PinRef("VD17", "1"), PinRef("VD17", "2"),
    ]
    assert [corridor.side for corridor in corridors] == [
        transform.side(Side.LEFT), transform.side(Side.RIGHT),
    ]
    assert part.pins[0].name == "A"
    assert part.pins[1].name == "K"
    assert inspect_conductor_topology(symbol).valid


@pytest.mark.parametrize("identifier", IDS)
def test_netlist_mapped_A_K_without_unsupported_polarity_inference(identifier):
    symbol, part = _load(identifier)
    circuit = Circuit((ComponentInstance("VD1", part.identifier),), (
        Net("ANODE_NET", (PinRef("VD1", "1"),)),
        Net("CATHODE_NET", (PinRef("VD1", "2"),)),
    ))
    issues = validate_circuit(
        circuit, {part.identifier: part}, {symbol.identifier: symbol},
    )
    assert not [issue for issue in issues if issue.severity.value == "error"]
    assert not any(issue.code == "POLARITY_REVERSED" for issue in issues)
    assert any(issue.code == "UNAPPROVED_SYMBOL" for issue in issues)


@pytest.mark.parametrize("identifier", IDS)
def test_adding_a_fake_conductive_bridge_is_an_error_not_internal_diode_wire(
    identifier,
):
    symbol, _ = _load(identifier)
    false_wire = Line(Point(-2500, 0), Point(2500, 0))
    wrong = replace(
        symbol,
        graphics=(*symbol.graphics, false_wire),
        conductor_topology=replace(
            symbol.conductor_topology,
            conductor_indices=(
                *symbol.conductor_topology.conductor_indices, len(symbol.graphics),
            ),
        ),
    )
    codes = {item.code for item in inspect_conductor_topology(wrong).diagnostics}
    assert "TOPOLOGY_UNEXPECTED_BRIDGE" in codes
    with pytest.raises(ValueError, match="geometry lost"):
        verify_draft_diode(wrong, _load(identifier)[1])


@pytest.mark.parametrize("identifier", IDS)
def test_missing_anode_lead_or_wrong_pin_number_is_not_silently_accepted(identifier):
    symbol, part = _load(identifier)
    changed = replace(symbol, graphics=(
        Line(Point(-10000, 0), Point(-4500, 0)), *symbol.graphics[1:]
    ))
    assert "TOPOLOGY_PIN_UNATTACHED" not in {
        issue.code for issue in inspect_conductor_topology(changed).diagnostics
    }  # Pin still touches its lead; geometry must be checked independently.
    with pytest.raises(ValueError, match="geometry lost"):
        verify_draft_diode(changed, part)
    invalid = replace(symbol, pins=(
        symbol.pins[0], replace(symbol.pins[1], number="99"),
    ))
    with pytest.raises(ValueError, match="graphic A/K"):
        verify_draft_diode(invalid, part)
    graph_codes = {issue.code for issue in inspect_conductor_topology(invalid).diagnostics}
    assert "TOPOLOGY_PIN_GROUP_MISMATCH" in graph_codes


@pytest.mark.parametrize("identifier", IDS)
def test_swapping_or_retyping_A_K_is_rejected_by_diode_catalog_guard(identifier):
    symbol, part = _load(identifier)
    swaps = (
        replace(part, pins=(part.pins[1], part.pins[0])),
        replace(part, pins=(
            replace(part.pins[0], name="K"),
            replace(part.pins[1], name="A"),
        )),
        replace(part, pins=(
            replace(part.pins[0], polarity=TerminalPolarity.POSITIVE),
            part.pins[1],
        )),
        replace(part, nominal_kind=QuantityKind.CAPACITANCE),
    )
    for mutant in swaps:
        with pytest.raises(ValueError):
            verify_draft_diode(symbol, mutant)
    switched_markers = replace(symbol, pins=(
        replace(symbol.pins[0], label="K"),
        replace(symbol.pins[1], label="A"),
    ))
    with pytest.raises(ValueError, match="graphic A/K"):
        verify_draft_diode(switched_markers, part)


def test_zener_and_general_substitution_and_lost_kink_fail_closed():
    general, part_general = _load("diode.general")
    zener, part_zener = _load("diode.zener")
    assert zener.graphics != general.graphics
    with pytest.raises(ValueError, match="geometry lost"):
        verify_draft_diode(replace(zener, graphics=general.graphics), part_zener)
    with pytest.raises(ValueError, match="geometry lost"):
        verify_draft_diode(replace(general, graphics=zener.graphics), part_general)
    lost_kink = replace(zener, graphics=zener.graphics[:-1])
    with pytest.raises(ValueError, match="geometry lost"):
        verify_draft_diode(lost_kink, part_zener)
    wrong_bend = replace(zener, graphics=(
        *zener.graphics[:7],
        Line(Point(2500, 3300), Point(1300, 3300)),
    ))
    with pytest.raises(ValueError, match="geometry lost"):
        verify_draft_diode(wrong_bend, part_zener)


@pytest.mark.parametrize("identifier", IDS)
def test_no_unapproved_diode_can_be_marked_approved_without_manual_signoff(identifier):
    symbol, part = _load(identifier)
    with pytest.raises(ValueError, match="DRAFT"):
        verify_draft_diode(
            replace(symbol, status=SymbolStatus.APPROVED), part,
        )



def test_catalog_audit_reports_21_independent_draft_ugo_and_both_real_diode_parts():
    from scripts.audit_symbol_catalog import audit_catalog

    report = audit_catalog()
    assert report["total_symbols"] == report["draft_count"] == 21
    assert report["hard_errors"] == 0
    assert not report["without_physical_part"]
    assert report["topologies_verified"] == 21
    assert report["symbols_with_checked_dimensions"] == 3
    diode_entries = {
        row["id"]: row for row in report["entries"]
        if row["id"].startswith("diode.")
    }
    assert set(diode_entries) == set(IDS)
    for entry in diode_entries.values():
        assert entry["approval"] == "draft"
        assert entry["physical_part_mapped"] is True
        assert entry["dimension_status"] == "not_yet_verifiable"
        assert entry["conductor_topology"]["pin_islands"] == [["1"], ["2"]]
        assert [pin["number"] for pin in entry["pins"]] == ["1", "2"]
        assert [pin["name"] for pin in entry["pins"]] == ["A", "K"]
