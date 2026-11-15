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
    assert result.manifest["source_b_two_physical_vectors_verified"]
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


def test_signed_source_b_rejects_one_micrometre_forged_physical_tip(
    real_signed_scene,
):
    geo = import_module("gost_schematic.core.geometry")
    source_b = real_signed_scene[11]
    first = source_b.stubs[0]
    moved = replace(
        first, start=geo.Point(first.start.x + 1, first.start.y),
    )
    forged = replace(source_b, stubs=(moved, *source_b.stubs[1:]))
    with pytest.raises(
        ValueError, match="SOURCE_B_PHYSICAL_PROVENANCE_INVALID.*PHYSICAL_MISMATCH",
    ):
        _invoke(real_signed_scene, source_continuation_project=forged)


def test_signed_source_b_rejects_forged_a_marker_without_new_net(
    real_signed_scene,
):
    source_b = real_signed_scene[11]
    modified = replace(
        source_b.endpoints[0], label="a",
    )
    forged = replace(
        source_b, endpoints=(modified, *source_b.endpoints[1:]),
    )
    with pytest.raises(ValueError, match="SOURCE_B_PHYSICAL_IDENTITY_DRIFT"):
        _invoke(real_signed_scene, source_continuation_project=forged)


def test_signed_source_b_rejects_missing_physical_r5_pin(
    real_signed_scene,
):
    source_b = real_signed_scene[11]
    model = import_module("gost_schematic.model.circuit")
    altered = replace(
        source_b.stubs[1], pin=model.PinRef("DA1", "16"),
    )
    forged = replace(
        source_b, stubs=(source_b.stubs[0], altered),
    )
    with pytest.raises(ValueError, match="SOURCE_B_PHYSICAL_IDENTITY_DRIFT"):
        _invoke(real_signed_scene, source_continuation_project=forged)


def test_signed_real_b_native_strokes_exact_physical_endpoints_and_not_copper(
    real_signed_scene,
):
    from xml.etree import ElementTree as ET

    source_b = real_signed_scene[11]
    expected = {stub.endpoint_id: stub for stub in source_b.stubs}
    assert {k: f"{v.pin.reference}.{v.pin.number}"
            for k, v in expected.items()} == {
        "b-X2": "X2.1", "b-R5": "R5.2",
    }
    before_nets = real_signed_scene[1].nets
    svg_ns = "{http://www.w3.org/2000/svg}"
    for svg in (_invoke(real_signed_scene).clean_svg,
                _invoke(real_signed_scene).diagnostic_svg):
        root = ET.fromstring(svg)
        lines = root.findall(
            f".//{svg_ns}g[@data-layer='typed-nonphysical-continuations']/"
            f"{svg_ns}line[@data-layer='nonphysical-continuation-stub']"
        )
        assert len(lines) == 2
        assert len(root.findall(f".//{svg_ns}line[@data-layer='wires']")) == 0
        assert {line.get("data-nonphysical-net-continuation")
                for line in lines} == set(expected)
        for line in lines:
            stub = expected[line.get("data-nonphysical-net-continuation")]
            assert line.get("data-source-pin-ref") == (
                f"{stub.pin.reference}.{stub.pin.number}"
            )
            assert line.get("data-source-stub-id") == stub.id
            assert line.get("data-nonphysical") == "true"
            assert line.get("data-electrical-junction") == "false"
            assert line.get("data-connectable") == "false"
            assert tuple(round(float(line.get(field)) * 1000) for field in (
                "x1", "y1", "x2", "y2",
            )) == (
                stub.start.x, stub.start.y, stub.end.x, stub.end.y,
            )
    assert real_signed_scene[1].nets is before_nets


@pytest.mark.parametrize("fault", ("missing", "duplicate", "off_anchor", "wrong_pin"))
def test_real_b_stroke_fail_closed_on_source_project_tampering(
    real_signed_scene, fault,
):
    from xml.etree import ElementTree as ET

    project = real_signed_scene[11]
    first, second = project.stubs
    if fault == "missing":
        changed = (first,)
    elif fault == "duplicate":
        changed = (first, first)
    elif fault == "off_anchor":
        geo = import_module("gost_schematic.core.geometry")
        changed = (
            replace(first, end=geo.Point(first.end.x + 1, first.end.y)),
            second,
        )
    else:
        pin = import_module("gost_schematic.model.circuit").PinRef
        changed = (replace(first, pin=pin("R5", "2")), second)
    altered = replace(project, stubs=changed)
    composer = import_module("gost_schematic.rendering.ic_sheet_composition")
    root = ET.Element("{http://www.w3.org/2000/svg}svg")
    with pytest.raises(ValueError, match="SHEET_CONTINUATION_SOURCE_B"):
        composer.append_verified_sheet_continuations(
            root, real_signed_scene[1], altered,
            real_signed_scene[4], diagnostic=False,
            symbols_by_part=real_signed_scene[3],
        )
    assert not list(root)


def test_modern_type_a_builder_real_declared_face_and_pinned_sha(
    real_signed_scene,
):
    import hashlib

    reference = import_module("examples.tl494_ic_paint_reference")
    paint = import_module("examples.render_tl494_full_native_cycle9")
    font_path = Path(os.environ["TL494_TYPE_A_FONT"])
    assert paint._declared_type_a_family(reference.build) == "OpenGOST type A"
    assert hashlib.sha256(font_path.read_bytes()).hexdigest() == (
        "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
    )
    assert real_signed_scene[4].font_sha256 == (
        "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
    )


def test_modern_type_a_owner_adapter_rejects_corrupted_font_and_alias(
    real_signed_scene, tmp_path, monkeypatch,
):
    reference = import_module("examples.tl494_ic_paint_reference")
    paint = import_module("examples.render_tl494_full_native_cycle9")
    named = import_module("examples.tl494_named_photo_sheet")
    original = Path(os.environ["TL494_TYPE_A_FONT"])
    corrupt = tmp_path/"corrupt-type-a.otf"
    data = original.read_bytes()
    corrupt.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    with pytest.raises(ValueError, match="PINNED_SHA_MISMATCH"):
        paint._compose_frozen_circuit_with_real_type_a(
            named.compose_circuit, corrupt,
        )
    monkeypatch.setattr(reference, "build", lambda _path: None)
    with pytest.raises(ValueError, match="BUILDER_ALIAS_DRIFT"):
        paint._compose_frozen_circuit_with_real_type_a(
            named.compose_circuit, original,
        )


def test_direct_b_composer_rejects_1um_forged_physical_start(
    real_signed_scene,
):
    from xml.etree import ElementTree as ET

    geom = import_module("gost_schematic.core.geometry")
    composer = import_module("gost_schematic.rendering.ic_sheet_composition")
    source_b = real_signed_scene[11]
    one = source_b.stubs[0]
    changed = replace(
        one, start=geom.Point(one.start.x + 1, one.start.y),
    )
    forged = replace(source_b, stubs=(changed, source_b.stubs[1]))
    root = ET.Element("{http://www.w3.org/2000/svg}svg")
    with pytest.raises(ValueError, match="SOURCE_B_PHYSICAL_TIP_DRIFT"):
        composer.append_verified_sheet_continuations(
            root, real_signed_scene[1], forged,
            real_signed_scene[4], diagnostic=False,
            symbols_by_part=real_signed_scene[3],
        )
    assert len(root) == 0
