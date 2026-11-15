"""Cycle12 real PAINT compact-driver source+typed b integration, positive/hostile.

These tests run ONLY in dedicated owner-pinned CI with the real frozen
e695 source, IC97, RECON115 and NETREF106; no fake positive SVG fixture.
"""
from __future__ import annotations

import os
from dataclasses import replace
from importlib import import_module
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def compact_source():
    font = os.getenv("TL494_TYPE_A_FONT")
    if not font or not Path(font).is_file():
        pytest.fail("CYCLE12_REAL_OWNER_TYPE_A_FONT_MISSING")
    compact = import_module("examples.tl494_v5.compact_layout")
    driver = import_module("examples.tl494_v5.route_candidate_driver")
    bridge = import_module("examples.tl494_v5.cycle11_ti_bridge")
    assembly = compact.compact_source_assembly()
    frozen, owner = driver.load_original_owner_fixture()
    original = driver.restore_original_named_nets(assembly, frozen)
    signed = bridge.bind_verified_compact_ti(assembly, original)
    signed.verify()
    assert signed.signed.circuit.nets is original.nets
    assert len(signed.signed.circuit.components) == 23
    assert len(signed.signed.circuit.nets) == 15
    assert sum(len(n.members) for n in original.nets) == 62
    assert len(signed.signed.contacts) == 16
    assert len(owner.contacts) == 16
    return Path(font), assembly, original, signed


def test_compact_driver_real_source_b_is_physical_typed_and_no_new_net(
    compact_source,
):
    font, assembly, original, signed = compact_source
    paint = import_module("examples.render_tl494_compact_new_router_cycle10")
    netrefs = import_module("gost_schematic.electrical.netrefs")
    rebound = paint._bind_verified_source_b(
        font, signed.signed.circuit, assembly.symbols,
    )
    assert rebound.circuit.nets is signed.signed.circuit.nets is original.nets
    assert len(rebound.endpoints) == len(rebound.stubs) == 2
    assert {e.id for e in rebound.endpoints} == {"b-X2", "b-R5"}
    assert {e.label for e in rebound.endpoints} == {"b"}
    assert len(rebound.nets) == 1
    assert rebound.nets[0].net_name == "b_NEGATIVE_OUTPUT"
    assert {
        (stub.pin.reference, stub.pin.number) for stub in rebound.stubs
    } == {("X2", "1"), ("R5", "2")}
    assert netrefs.validate_net_continuations(
        rebound, physical_pin_anchors={
            stub.pin: stub.start for stub in rebound.stubs
        },
    ) == ()


def test_compact_driver_rejects_wrong_original_b_net(compact_source):
    font, assembly, _original, signed = compact_source
    paint = import_module("examples.render_tl494_compact_new_router_cycle10")
    model = import_module("gost_schematic.model.circuit")
    bad_nets = tuple(
        model.Net("OUTPUT_NEG", n.members)
        if n.name == "b_NEGATIVE_OUTPUT" else n
        for n in signed.signed.circuit.nets
    )
    with pytest.raises(ValueError, match="SOURCE_23_15_62_IDENTITY_DRIFT"):
        paint._bind_verified_source_b(
            font,
            model.Circuit(signed.signed.circuit.components, bad_nets),
            assembly.symbols,
        )


def test_compact_driver_rejects_missing_real_r5_symbol(compact_source):
    font, assembly, _original, signed = compact_source
    paint = import_module("examples.render_tl494_compact_new_router_cycle10")
    r5 = next(c for c in signed.signed.circuit.components
              if c.reference == "R5")
    bad_symbols = dict(assembly.symbols)
    del bad_symbols[r5.part_id]
    with pytest.raises(ValueError, match="MISSING_REAL_SOURCE_SYMBOL"):
        paint._bind_verified_source_b(
            font, signed.signed.circuit, bad_symbols,
        )


def test_compact_driver_rejects_outside_A3_without_forged_relocation(
    compact_source,
):
    font, assembly, _original, signed = compact_source
    paint = import_module("examples.render_tl494_compact_new_router_cycle10")
    geo = import_module("gost_schematic.core.geometry")
    model = import_module("gost_schematic.model.circuit")
    shifted = tuple(
        replace(c, origin=geo.Point(470000, c.origin.y))
        if c.reference == "X2" else c
        for c in signed.signed.circuit.components
    )
    with pytest.raises(ValueError, match="ORIGINAL_VECTOR_OUTSIDE_COMPACT_A3"):
        paint._bind_verified_source_b(
            font, model.Circuit(shifted, signed.signed.circuit.nets),
            assembly.symbols,
        )


def test_actual_compact_driver_fails_closed_on_corrupt_frozen_fixture(
    compact_source, tmp_path, monkeypatch,
):
    font, _assembly, _original, _signed = compact_source
    owner = import_module("examples.tl494_v5.route_candidate_driver")
    paint = import_module("examples.render_tl494_compact_new_router_cycle10")
    monkeypatch.setattr(
        owner, "load_original_owner_fixture",
        lambda: ({"components": (), "nets": {}}, object()),
    )
    with pytest.raises(ValueError, match="V5_CANDIDATE_SOURCE_BOM_REFS_DRIFT"):
        paint.generate_compact_attempt(tmp_path, font, node_cap=100)
    assert not list(tmp_path.glob("*.svg"))
