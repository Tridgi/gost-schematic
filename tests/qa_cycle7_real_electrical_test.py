"""Independent exact-SHA real ELEKTRIK #87 IC and #90 named-net regression.

Runs original owner Python and canonical JSON through installed source APIs.
No fake functional classes, no native E3 code edits, no Git fetch at pytest.
"""
import json
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest
from qa_cycle7_electrical_sources import (
    SOURCE_COMMITS,
    original_json,
    real_electrical_sources,
    verified,
)

from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.model.circuit import Circuit, ComponentInstance, Net, PinRef


@pytest.fixture(scope="module")
def actual():
    with real_electrical_sources() as sources:
        yield sources


def test_real_owners_byte_verification_and_modules_not_mocks(actual):
    ic, serde, example, net, netserde, netexample = actual
    verified()
    # SOURCE_COMMITS is pinned once in qa_cycle7_electrical_sources.py.
    # Per-file Git blob SHA-1 checks remain independent in verified().
    assert set(SOURCE_COMMITS) == {"ic", "net"}
    assert all(
        len(commit) == 40 and all(c in "0123456789abcdef" for c in commit)
        for commit in SOURCE_COMMITS.values()
    )
    assert ic.IcPhysicalPin.__module__ == "gost_schematic.electrical.ic"
    assert net.NetContinuationProject.__module__ == (
        "gost_schematic.electrical.netrefs"
    )
    assert callable(serde.ic_from_json)
    assert callable(netserde.netrefs_from_json)
    assert callable(netexample.sheet_svg)
    assert callable(example.synthetic_ic)


@pytest.mark.parametrize("kind", ("analog", "digital"))
@pytest.mark.parametrize("count", (2, 4, 8, 14, 40, 64))
def test_real_ic_12_package_variants_serde_pinref_and_split_units(
    actual, kind, count,
):
    ic, serde, example, _net, _netserde, _netexample = actual
    choice = ic.IcKind.ANALOG if kind == "analog" else ic.IcKind.DIGITAL
    record = example.synthetic_ic(count, choice)
    device = record.device
    assert device.kind is choice
    assert device.package.origin is ic.PinoutOrigin.SYNTHETIC
    assert len(device.pins) == count
    assert device.package.pin_count == count
    assert len({p.number for p in device.pins}) == count
    assert all(p.function for p in device.pins)
    assert all(p.name for p in device.pins)
    assert len({p for unit in device.units for p in unit.pin_numbers}) == count
    positions = ic.resolve_ic_pin_positions(
        device, record.specs, record.placements
    )
    assert len(positions) == count
    assert len(set(positions.values())) == count
    assert all(isinstance(ref, PinRef) for ref in positions)
    assert {
        ref.reference for ref in positions
    } == {("DA1" if kind == "analog" else "DD1")}
    json_text = serde.ic_to_json(record)
    restored = serde.ic_from_json(json_text)
    assert restored == record
    assert serde.ic_to_json(restored) == json_text
    assert len(restored.device.pins) == count
    if count >= 14:
        assert len(record.device.units) == 2
        assert len({p.component_ref for p in record.placements}) == 1
    else:
        assert len(record.device.units) == 1
    assert not hasattr(device, "nets")


def test_actual_owner_14pin_json_fixture_is_authoritative_and_reproducible(actual):
    ic, serde, _example, _net, _netserde, _netexample = actual
    frozen = original_json("ic")
    imported = serde.ic_from_json(
        json.dumps(frozen, sort_keys=True, ensure_ascii=False)
    )
    assert imported.device.identifier == "TEST_IC_DIGITAL_14"
    assert len(ic.resolve_ic_pin_positions(
        imported.device, imported.specs, imported.placements
    )) == 14
    assert json.loads(serde.ic_to_json(imported)) == frozen


def test_real_ic_wrong_physical_pin_nc_and_missing_view_fail_closed(actual):
    ic, serde, example, _net, _netserde, _netexample = actual
    record = example.synthetic_ic(14, ic.IcKind.DIGITAL)
    pins = record.device.pins
    with pytest.raises(ValueError, match="Duplicate physical IC pin numbers"):
        replace(
            record.device,
            pins=(replace(pins[0], number=pins[1].number), *pins[1:]),
        )
    with pytest.raises(ValueError, match="Non-NC physical pin missing"):
        replace(
            record.device,
            units=(replace(
                record.device.units[0],
                pin_numbers=record.device.units[0].pin_numbers[1:],
            ), *record.device.units[1:]),
        )
    with pytest.raises(ValueError, match="IC_PIN_NOT_PRESENTED"):
        ic.resolve_ic_pin_positions(
            record.device, record.specs[:-1], record.placements
        )
    with pytest.raises(ValueError, match="IC_ANCHOR_INSIDE"):
        replace(record.specs[0], rows=(
            replace(record.specs[0].rows[0], anchor=Point(10, 10)),
            *record.specs[0].rows[1:],
        ))
    component = ComponentInstance("DD1", record.device.identifier)
    no_connect = Circuit((component,), (
        Net("UNSAFE_NC", (PinRef("DD1", "14"),)),
    ))
    with pytest.raises(ValueError, match="IC_NC_CONNECTED"):
        ic.validate_ic_circuit(record.device, no_connect, "DD1")
    good = Circuit((component,), (
        Net("LIVE", (PinRef("DD1", "1"), PinRef("DD1", "2"))),
    ))
    assert ic.validate_ic_circuit(record.device, good, "DD1") is None
    raw = json.loads(serde.ic_to_json(record))
    raw["device"]["pins"][0]["number"] = "2"
    with pytest.raises(ValueError):
        serde.ic_from_json(json.dumps(raw, ensure_ascii=False))


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_split_ic_real_phys_pinref_identity_survives_d4(actual, rotation, mirror):
    ic, _serde, example, _net, _netserde, _netexample = actual
    record = example.synthetic_ic(14)
    placements = tuple(
        replace(p, transform=Transform(rotation, mirror))
        for p in record.placements
    )
    original = ic.resolve_ic_pin_positions(
        record.device, record.specs, record.placements
    )
    changed = ic.resolve_ic_pin_positions(
        record.device, record.specs, placements
    )
    assert set(original) == set(changed)
    assert len(changed) == 14
    assert all(ref.reference == "DD1" for ref in changed)
    assert len(set(changed.values())) == 14


def test_real_named_continuation_two_sheets_one_exact_physical_net_svg(actual):
    _ic, _serde, _example, net, serde, example = actual
    # Reproduce production module import order deterministically: the core
    # SVG renderer globally registers the default SVG namespace. The #98
    # owner must never serialize a second xmlns on its namespaced root.
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    project = example.specimen()
    assert net.validate_net_continuations(project) == ()
    assert len(project.circuit.nets) == 1
    assert len(project.circuit.nets[0].members) == 2
    assert len(project.pairs) == 1
    assert len(project.stubs) == len(project.endpoints) == 2
    assert len({s.id for s in project.sheets}) == 2
    dump = serde.netrefs_to_json(project)
    assert json.loads(dump) == original_json("net")
    restored = serde.netrefs_from_json(dump, project.circuit)
    assert serde.netrefs_to_json(restored) == dump
    assert restored == project
    for sheet_id in ("S1", "S2"):
        svg = ET.fromstring(example.sheet_svg(project, sheet_id))
        ns = "{http://www.w3.org/2000/svg}"
        assert svg.attrib["data-approval"] == "DRAFT_UNMEASURED_FONT"
        assert len(svg.findall(
            f".//{ns}line[@data-role='explicit-real-wire-stub']"
        )) == 1
        assert len(svg.findall(
            f".//{ns}path[@data-role='DRAFT-visual-continuation-marker']"
        )) == 1
        assert not svg.findall(f".//{ns}circle[@data-role='junction']")
        assert not svg.findall(f".//{ns}line[@data-role='cross-sheet-short']")
    assert project.circuit.nets == restored.circuit.nets


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        ("unknown_sheet", "E3_CONT_SHEET_UNKNOWN"),
        ("missing_address", "INVALID_CONSTRUCTOR"),
        ("wrong_address", "E3_CONT_ADDRESS_MISMATCH"),
        ("duplicate_id", "E3_CONT_DUPLICATE_ENDPOINT_ID"),
        ("cross_net", "E3_CONT_NET_ID_UNKNOWN"),
        ("wrong_stub_pin", "E3_CONT_STUB_WRONG_NET"),
        ("off_anchor", "E3_CONT_STUB_OFF_ANCHOR"),
        ("reused_pair", "E3_CONT_ENDPOINT_REUSED"),
    ],
)
def test_current_real_continuation_strict_negative_regressions(
    actual, mutate, expected,
):
    _ic, _serde, _example, net, _json, example = actual
    project = example.specimen()
    if mutate == "missing_address":
        with pytest.raises(ValueError, match="canonical nonblank"):
            replace(project.endpoints[0], target_address="")
        return
    ends = project.endpoints
    stubs = project.stubs
    pairs = project.pairs
    if mutate == "unknown_sheet":
        ends = (replace(ends[0], sheet_id="UNKNOWN"), ends[1])
    elif mutate == "wrong_address":
        ends = (replace(ends[0], target_address="55/NOT_HERE"), ends[1])
    elif mutate == "duplicate_id":
        ends = (ends[0], replace(ends[1], id=ends[0].id))
    elif mutate == "cross_net":
        ends = (ends[0], replace(ends[1], net_id="WRONG_NET_ID"))
    elif mutate == "wrong_stub_pin":
        stubs = (replace(stubs[0], pin=PinRef("DD1", "9")), stubs[1])
    elif mutate == "off_anchor":
        stubs = (replace(stubs[0], end=Point(80001, 40000)), stubs[1])
    elif mutate == "reused_pair":
        pairs = (*pairs, net.ContinuationPair(
            "SECOND", pairs[0].source_id, pairs[0].target_id,
            net.ContinuationScope.GLOBAL,
        ))
    damaged = replace(
        project, endpoints=ends, stubs=stubs, pairs=pairs
    )
    assert expected in {
        item.code for item in net.validate_net_continuations(damaged)
    }


def test_real_net_validation_rejects_same_visible_name_different_physical_net(actual):
    _ic, _serde, _example, net, _json, example = actual
    p = example.specimen()
    aux_members = (PinRef("DD1", "6"), PinRef("VT1", "D"))
    other = Net("AUX", aux_members)
    c = replace(p.circuit, nets=(*p.circuit.nets, other))
    other_id = net.NetIdentity("NET-AUX", "AUX", aux_members)
    src, dst = p.endpoints
    other_src = replace(
        src, id="AUX-OUT", net_id=other_id.id,
        address="1/F3", target_address="2/G5", anchor=Point(70000, 90000)
    )
    other_dst = replace(
        dst, id="AUX-IN", net_id=other_id.id,
        address="2/G5", target_address="1/F3", anchor=Point(160000, 90000)
    )
    pair = net.ContinuationPair(
        "PAIR-AUX", other_src.id, other_dst.id, net.ContinuationScope.GLOBAL
    )
    more_stubs = (
        net.ContinuationStub(
            "AUX-DD", other_src.id, aux_members[0],
            Point(60000, 90000), other_src.anchor
        ),
        net.ContinuationStub(
            "AUX-VT", other_dst.id, aux_members[1],
            Point(170000, 90000), other_dst.anchor
        ),
    )
    candidate = replace(
        p, circuit=c, nets=(*p.nets, other_id),
        endpoints=(*p.endpoints, other_src, other_dst),
        pairs=(*p.pairs, pair),
        stubs=(*p.stubs, *more_stubs),
    )
    assert "E3_CONT_LABEL_AMBIGUOUS" in {
        item.code for item in net.validate_net_continuations(candidate)
    }
    assert len(candidate.circuit.nets) == 2


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_net_continuation_real_d4_keeps_net_membership(actual, rotation, mirror):
    _ic, _serde, _example, net, _json, example = actual
    original = example.specimen()
    changed = net.transform_continuations(
        original, Transform(rotation, mirror)
    )
    assert net.validate_net_continuations(changed) == ()
    assert changed.circuit is original.circuit
    assert changed.nets == original.nets
    assert {x.net_id for x in changed.endpoints} == {"N-CTRL-001"}


def test_current_ic_legacy_bridge_fails_closed_on_nc_and_split(actual):
    _ic, _serde, example, _net, _netserde, _netexample = actual
    for size in (8, 14, 40, 64):
        device = example.synthetic_ic(size).device
        with pytest.raises(ValueError, match="IC_UNSAFE_LEGACY_ADAPTER"):
            device.to_legacy_part("DRAFT_ONLY")
    device = example.synthetic_ic(2).device
    part = device.to_legacy_part("DRAFT_ONLY")
    assert tuple(p.number for p in part.pins) == ("1", "2")
    assert tuple(p.electrical_type.value for p in part.pins) == (
        "input", "output"
    )


def test_cycle7_cross_owner_actual_pinref_handoff_requires_translation(actual):
    """Execute real #97 and #93 types together; no pretend production bridge.

    Only the simple synthetic 2-pin case has an explicit TEST-ONLY role mapping.
    This proves world anchor identity at the seam, NOT integrated drawing,
    catalog persistence, OpenGost size resolution, or multi-unit compatibility.
    """
    from qa_cycle7_support import owner_renderer

    ic, _serde, example, _net, _netserde, _netexample = actual
    paint = owner_renderer()
    record = example.synthetic_ic(2, ic.IcKind.DIGITAL)
    spec, placement = record.specs[0], record.placements[0]
    positions = ic.resolve_ic_pin_positions(
        record.device, record.specs, record.placements
    )
    owner_roles = {ic.IcPinType.INPUT: "in", ic.IcPinType.OUTPUT: "out"}
    pins = tuple(
        paint.ResolvedIcPin(
            pin_id=f"{placement.component_ref}.{row.number}",
            number=row.number,
            label=row.label,
            side=row.side,
            row=row.visual_row,
            anchor=positions[PinRef(placement.component_ref, row.number)],
            role=owner_roles[record.device.pin_map[row.number].electrical_type],
            row_key=row.row_key,
        ) for row in spec.rows
    )
    view = paint.IcResolvedUnit(
        placement.component_ref, spec.body, pins,
        paint.IcFieldContent(spec.main_field),
        placement.origin, placement.transform,
    )
    assert {
        PinRef(placement.component_ref, p.number): p.anchor
        for p in view.pins
    } == positions
    assert len(view.pins) == len(record.device.pins) == 2
    # Raw owner electrical role != PAINT's graphical role: a reviewed
    # explicit semantic adapter is indispensable for full IC integration.
    with pytest.raises(ValueError, match="IC_PIN_ROLE_INVALID"):
        paint.ResolvedIcPin(
            "DD1.1", "1", "IN", spec.rows[0].side, 1,
            positions[PinRef("DD1", "1")],
            role=record.device.pin_map["1"].electrical_type.value,
        )
