"""Owner-pinned V5 assembly checks. Run only with #97/#113 original owner files.

This is a dedicated integration test, not a skip/xfail on missing owner
implementation. It fails if native YGO glyph choice or physical TI pins drift.
"""
from dataclasses import replace
from importlib import import_module
from pathlib import Path

import pytest

from examples.tl494_v5.native_circuit import assemble_native_v5, export_source_manifest
from gost_schematic.model.circuit import Circuit, Net, PinRef


def test_v5_23_15_and_real_16_ti_pinrefs():
    result = assemble_native_v5()
    assert len(result.circuit.components) == 23
    assert len(result.circuit.nets) == 15
    assert len(result.parts["reference.tl494cn"].pins) == 16
    assert result.manifest()["print_gate"] == "BLOCKED until full router and QA"


def test_all_13_actual_catalog_symbols_and_polarity():
    a = assemble_native_v5()
    symbols = {p.reference: p.symbol.identifier for p in a.source_UGO_bindings}
    assert symbols["VD1"] == "diode.schottky"
    assert symbols["VT1"] == "transistor.mosfet_n_enh"
    assert all(symbols[p] == "inductor.ferromagnetic" for p in ("L1", "L2"))
    assert all(
        symbols[p] == "capacitor.polarized"
        for p in ("C1", "C2", "C3", "C5", "C6")
    )
    assert all(symbols[p] == "capacitor.fixed" for p in ("C4", "C7"))
    assert symbols["R5"] == "resistor.variable"
    assert symbols["FU1"] == "fuse.general"


def test_source_pin3_and_pin13_are_input_and_aliases_are_reversible():
    a = assemble_native_v5()
    physical = {p.number: p for p in a.parts["reference.tl494cn"].pins}
    assert physical["3"].name == "FEEDBACK"
    assert physical["13"].name == "OUTPUT CTRL"
    assert physical["3"].electrical_type.value == "input"
    assert physical["13"].electrical_type.value == "input"
    aliases = {
        p.physical_number: p.schematic_short_label
        for p in a.owner_aliases.labels
    }
    assert aliases["3"] == "FB"
    assert aliases["13"] == "OC"
    assert len(set(aliases.values())) == 16
    assert all(len(label) <= 6 for label in aliases.values())


def test_no_source_net_mutation_and_no_fake_pe():
    original = assemble_native_v5()
    before = original.manifest()
    original.verify()
    assert "COMMON" in before["nets"]
    assert "DA1.7" in before["nets"]["COMMON"]
    assert "PE" not in before["nets"]
    assert before["old_known_bad_DRC"] == {
        "errors": 9, "warnings": 32, "wires": 91, "junctions": 37
    }


def test_wrong_net_or_deleted_ti_contact_fails_closed():
    original = assemble_native_v5()
    broken_nets = tuple(
        Net(n.name, tuple(p for p in n.members if p != PinRef("DA1", "3")))
        if n.name == "FEEDBACK" else n for n in original.circuit.nets
    )
    bad = replace(
        original,
        circuit=Circuit(original.circuit.components, broken_nets),
    )
    with pytest.raises(AssertionError, match="V5_PINREF_NET_IDENTITY_DRIFT"):
        bad.verify()


def test_wrong_capacitor_symbol_blocked_by_true_owner_selector():
    profiles = import_module("gost_schematic.catalog.source_profiles")
    assembly = assemble_native_v5()
    changed = tuple(
        replace(p, part_id="capacitor.electrolytic")
        if p.reference == "C1" else p
        for p in assembly.circuit.components
    )
    with pytest.raises(profiles.SymbolProfileMismatch):
        profiles.bind_tl494_source(changed, assembly.parts, assembly.symbols)


def test_model_only_export_produces_no_svg(tmp_path: Path):
    result = export_source_manifest(tmp_path / "model.json")
    assert result["components"] == 23
    assert len(result["nets"]) == 15
    assert sorted(p.name for p in tmp_path.iterdir()) == ["model.json"]
