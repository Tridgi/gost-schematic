"""Cycle12 true source-backed signed IC97 snapshot -> PAINT native wire gate.

A zero-segment graph is a deliberate NEGATIVE proof, never accepted as a
routed TL494. No handwritten or edited SVG, guessed pin positions or Net.
"""
from __future__ import annotations

import os
from dataclasses import replace
from importlib import import_module
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def real_signed_scene():
    font = os.getenv("TL494_TYPE_A_FONT")
    if not font or not Path(font).is_file():
        pytest.fail("CYCLE12_TRUE_TYPE_A_FONT_REQUIRED")
    native = import_module("examples.tl494_v5.compact_layout")
    driver = import_module("examples.tl494_v5.route_candidate_driver")
    bridge = import_module("examples.tl494_v5.cycle11_ti_bridge")
    painter = import_module("examples.render_tl494_compact_new_router_cycle10")
    paint_bridge = import_module("gost_schematic.electrical.ic_paint_bridge")
    type_a = import_module("gost_schematic.standards.type_a_font")
    metrics = import_module("gost_schematic.engines.annotation.metrics")
    model = import_module("gost_schematic.model.circuit")
    assembly = native.compact_source_assembly()
    fixture, _source = driver.load_original_owner_fixture()
    original = driver.restore_original_named_nets(assembly, fixture)
    signed = bridge.bind_verified_compact_ti(assembly, original)
    signed.verify()
    style = type_a.inspect_type_a_font(
        Path(font), h_um=3500, family="OpenGOST type A",
        require_family_match=True,
    ).style
    measurer = metrics.PillowTextMeasurer()
    proposal = paint_bridge.propose_ic_paint_binding(
        assembly.owner_ic_record, style, measurer,
    )
    revised, snapshot = signed.seal_paint(proposal)
    snapshot.verify_against(revised, proposal)
    (clean,) = snapshot.render(
        revised, proposal, style, measurer, diagnostics=False,
    )
    (diagnostic,) = snapshot.render(
        revised, proposal, style, measurer, diagnostics=True,
    )
    circuit = revised.circuit
    da1 = next(c for c in circuit.components if c.reference == "DA1")
    original_ic = import_module("examples.tl494_v5.route_preflight")
    surrogate = original_ic._owner_ic_obstacle(
        proposal.views[0], clean.svg, da1,
    )
    symbols = {
        key: assembly.symbols[part.symbol_id]
        for key, part in assembly.parts.items()
        if part.symbol_id in assembly.symbols
    }
    symbols[revised.part.identifier] = replace(
        surrogate, identifier=revised.part.symbol_id,
    )
    parts = {**assembly.parts, revised.part.identifier: revised.part}
    project = painter._bind_verified_source_b(Path(font), circuit, symbols)
    assert circuit.nets is original.nets
    assert len(circuit.components) == 23
    assert len(circuit.nets) == 15
    assert sum(len(net.members) for net in circuit.nets) == 62
    assert len(snapshot.per_unit_targets) == 1
    assert len(snapshot.per_unit_targets[0]) == 16
    assert {p.id for p in project.endpoints} == {"b-X2", "b-R5"}
    return (
        model, circuit, parts, symbols, style, measurer, clean, diagnostic,
        revised, proposal, snapshot, project,
    )


def _invoke(scene, **updates):
    geo = import_module("gost_schematic.core.geometry")
    checks = import_module("gost_schematic.validation.external_wire_checks")
    native = import_module("gost_schematic.rendering.routed_native_sheet")
    (
        _model, circuit, parts, symbols, style, measurer, clean, diagnostic,
        revised, proposal, snapshot, b,
    ) = scene
    kwargs = {
        "physical_ic_renderings_clean": {"DA1": clean},
        "physical_ic_renderings_diagnostic": {"DA1": diagnostic},
        "verified_ic_source": revised,
        "verified_ic_paint_binding": proposal,
        "verified_ic_snapshot": snapshot,
        "source_continuation_project": b,
        "physical_page_box": geo.Box(0, 0, 420000, 297000),
        "expected_component_count": 23,
        "expected_net_count": 15,
        "expected_net_pinrefs": 62,
    }
    kwargs.update(updates)
    return native.render_routed_native_sheet(
        circuit, checks.ExternalWireGraph(()), parts,
        symbols, style, measurer, **kwargs,
    )


def test_signed_16_true_source_render_is_blocked_on_empty_route(real_signed_scene):
    result = _invoke(real_signed_scene)
    assert result.manifest["signed_manufacturer_ic_16_verified"]
    assert not result.printable_candidate
    assert "TL494_SIGNED_MANUFACTURER_PHYSICAL_BINDING_MISSING" not in (
        result.manifest["blockers"]
    )
    assert "TL494_NEW_ROUTER_OWNER_PROVENANCE_MISSING" in result.manifest["blockers"]
    assert "A3_SOURCE_CONTINUATION_BINDING_UNRESOLVED" not in result.manifest[
        "blockers"
    ]
    assert "ELECTRICAL:WIRE_NET_DISCONNECTED" in result.manifest["blockers"]
    assert "data-release=\"BLOCKED_INCOMPLETE_OR_PRINT_DRC\"" in result.clean_svg
    assert "data-release=\"BLOCKED_INCOMPLETE_OR_PRINT_DRC\"" in (
        result.diagnostic_svg
    )


def test_real_snapshot_cannot_authenticate_modified_clean_svg(real_signed_scene):
    clean = real_signed_scene[6]
    forged = replace(clean, svg=clean.svg + "<!-- modified signed ink -->")
    with pytest.raises(ValueError, match="SIGNED_IC_SERIALIZED_INK_CHANGED"):
        _invoke(
            real_signed_scene,
            physical_ic_renderings_clean={"DA1": forged},
        )


def test_real_snapshot_rejects_foreign_provenance_digest(real_signed_scene):
    snapshot = real_signed_scene[10]
    forged = replace(snapshot, circuit_sha256="0" * 64)
    with pytest.raises(ValueError, match="PROVENANCE_OR_TARGET_MISMATCH"):
        _invoke(real_signed_scene, verified_ic_snapshot=forged)


def test_raw_sixteen_pin_overlay_is_not_trusted(real_signed_scene):
    raw = _invoke(
        real_signed_scene,
        verified_ic_source=None,
        verified_ic_paint_binding=None,
        verified_ic_snapshot=None,
    )
    assert not raw.manifest["signed_manufacturer_ic_16_verified"]
    assert "TL494_SIGNED_MANUFACTURER_PHYSICAL_BINDING_MISSING" in (
        raw.manifest["blockers"]
    )
    assert not raw.printable_candidate
