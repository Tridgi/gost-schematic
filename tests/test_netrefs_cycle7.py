"""Cycle7 DRAFT named continuation: never infer connectivity from identical labels."""

import json
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree

import pytest

from examples.review_net_continuations_cycle7 import sheet_svg, specimen
from gost_schematic.core.geometry import Point
from gost_schematic.core.transforms import Transform
from gost_schematic.electrical.netrefs import (
    ContinuationDirection,
    ContinuationPair,
    ContinuationScope,
    ContinuationSheet,
    ContinuationStub,
    NetContinuationEndpoint,
    NetContinuationProject,
    NetIdentity,
    transform_continuations,
    validate_net_continuations,
)
from gost_schematic.electrical.netrefs_serde import (
    netrefs_from_json,
    netrefs_to_json,
)
from gost_schematic.model.circuit import (
    Circuit,
    ComponentInstance,
    Net,
    PinRef,
)

FIXTURES = Path(__file__).parent / "fixtures" / "electrical-netrefs-cycle7"
ANCHORS = {
    PinRef("DD1", "5"): Point(60000, 40000),
    PinRef("VT1", "G"): Point(160000, 40000),
}


def codes(project, anchors=None):
    return {d.code for d in validate_net_continuations(
        project, physical_pin_anchors=anchors,
    )}


def test_two_sheet_one_real_net_exact_identity_and_no_invisible_conductor():
    project = specimen()
    assert project.circuit.nets == (Net(
        "CTRL", (PinRef("DD1", "5"), PinRef("VT1", "G")),
    ),)
    assert len(project.circuit.components) == 2
    assert len(project.endpoints) == len(project.stubs) == 2
    assert {e.sheet_id for e in project.endpoints} == {"S1", "S2"}
    assert project.pairs[0].scope is ContinuationScope.GLOBAL
    assert codes(project, ANCHORS) == set()
    assert not hasattr(project, "PartDefinition")
    assert not hasattr(project, "physical_connector")
    assert not hasattr(project.endpoints[0], "pin")
    assert project.circuit.nets[0].members is project.nets[0].members


def test_strict_json_roundtrip_needs_real_circuit_and_original_pinrefs():
    project = specimen()
    encoded = netrefs_to_json(project)
    assert encoded == (FIXTURES / "two-sheet-ctrl.json").read_text("utf-8")
    assert json.loads(encoded)["record_type"] == "DRAFT_E3_NET_CONTINUATIONS"
    assert netrefs_from_json(encoded, project.circuit) == project
    assert netrefs_to_json(netrefs_from_json(encoded, project.circuit)) == encoded
    fake = Circuit(
        project.circuit.components,
        (Net("CTRL", (PinRef("DD1", "8"), PinRef("VT1", "G"))),),
    )
    with pytest.raises(ValueError, match="MEMBERS_MISMATCH"):
        netrefs_from_json(encoded, fake)


def test_svg_has_only_one_real_wire_stub_per_sheet_and_exact_marker_anchor():
    project = specimen()
    for sheet in project.sheets:
        name = f"sheet-{sheet.number}"
        svg = sheet_svg(project, sheet.id)
        assert svg == (FIXTURES / f"{name}.svg").read_text("utf-8")
        root = ElementTree.fromstring(svg)
        assert root.attrib["data-approval"] == "DRAFT_UNMEASURED_FONT"
        lines = [x for x in root.iter() if x.attrib.get("data-role") ==
                 "explicit-real-wire-stub"]
        markers = [x for x in root.iter() if x.attrib.get("data-role") ==
                   "DRAFT-visual-continuation-marker"]
        texts = [x for x in root.iter() if x.attrib.get("data-role", "").startswith(
            "unmeasured-"
        )]
        assert len(lines) == len(markers) == 1
        assert len(texts) == 2
        stub = next(s for s in project.stubs if s.endpoint_id == markers[0].attrib[
            "data-marker-id"
        ])
        assert lines[0].attrib["data-net-id"] == "N-CTRL-001"
        assert lines[0].attrib["data-pin-ref"] == (
            f"{stub.pin.reference}.{stub.pin.number}"
        )
        assert Point(int(lines[0].attrib["x2"]), int(lines[0].attrib["y2"])) == stub.end
        assert "foreign-part" not in svg


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_d4_only_changes_graphical_anchor_not_semantic_net_members(rotation, mirror):
    project = specimen()
    before = project.circuit.nets
    transform = Transform(rotation, mirror)
    changed = transform_continuations(project, transform)
    assert changed.circuit is project.circuit and changed.circuit.nets is before
    assert changed.nets == project.nets and changed.pairs == project.pairs
    assert codes(changed, {p: transform.apply(pt) for p, pt in ANCHORS.items()}) == set()
    for a, b in zip(project.endpoints, changed.endpoints, strict=True):
        assert a.id == b.id and a.net_id == b.net_id
        assert transform.apply(a.anchor) == b.anchor
    assert netrefs_from_json(netrefs_to_json(changed), project.circuit) == changed


def test_unknown_net_binding_source_pair_and_target_address_fail_closed():
    project = specimen()
    bad = replace(project, endpoints=(
        replace(project.endpoints[0], net_id="MISSING"), project.endpoints[1],
    ))
    assert {"E3_CONT_NET_ID_UNKNOWN", "E3_CONT_CROSS_NET"} <= codes(bad)
    bad = replace(project, pairs=(replace(project.pairs[0], target_id="GHOST"),))
    assert {"E3_CONT_ENDPOINT_UNKNOWN", "E3_CONT_UNPAIRED_MARKER"} <= codes(bad)
    bad = replace(project, endpoints=(
        replace(project.endpoints[0], target_address="INCORRECT"),
        project.endpoints[1],
    ))
    assert codes(bad) == {"E3_CONT_ADDRESS_MISMATCH"}


def test_sheet_local_two_fragments_share_real_net_without_cross_sheet_address():
    project = specimen()
    second = replace(
        project.endpoints[1], sheet_id="S1", sheet_number=1,
    )
    pair = replace(project.pairs[0], scope=ContinuationScope.SHEET_LOCAL)
    local = replace(
        project, endpoints=(project.endpoints[0], second), pairs=(pair,),
    )
    assert codes(local) == set()
    assert local.circuit is project.circuit
    assert local.circuit.nets[0] == project.circuit.nets[0]
    assert len(local.stubs) == 2


def test_svg_png_300dpi_review_artifacts_present_and_not_font_certified():
    from PIL import Image

    for sheet_number in (1, 2):
        filepath = FIXTURES / f"sheet-{sheet_number}-300dpi.png"
        with Image.open(filepath) as image:
            assert image.format == "PNG"
            assert image.width >= 2400 and image.height >= 3500
            assert image.mode in ("RGB", "RGBA")
    assert "DRAFT_UNMEASURED_FONT" in sheet_svg(specimen(), "S1")


def test_scope_direction_sheet_number_and_connector_impersonation_fail():
    project = specimen()
    assert "E3_CONT_SCOPE" in codes(replace(project, pairs=(
        replace(project.pairs[0], scope=ContinuationScope.SHEET_LOCAL),
    )))
    assert "E3_CONT_DIRECTION" in codes(replace(project, endpoints=(
        replace(project.endpoints[0], direction=ContinuationDirection.TARGET),
        project.endpoints[1],
    )))
    assert "E3_CONT_SHEET_UNKNOWN" in codes(replace(project, endpoints=(
        replace(project.endpoints[0], sheet_number=42), project.endpoints[1],
    )))
    assert "E3_CONT_PHYSICAL_CONNECTOR_IMPERSONATION" in codes(replace(
        project, endpoints=(
            replace(project.endpoints[0], label="XP1"),
            replace(project.endpoints[1], label="XP1"),
        ),
    ))


def test_same_label_distinct_real_nets_never_join_and_fail_ambiguity():
    project = specimen()
    new_parts = (
        *project.circuit.components,
        ComponentInstance("DD2", "SYNTHETIC_DD2"),
        ComponentInstance("VT2", "SYNTHETIC_VT2"),
    )
    other = Net("CTRL_B", (PinRef("DD2", "5"), PinRef("VT2", "G")))
    circuit = Circuit(new_parts, (*project.circuit.nets, other))
    net2 = NetIdentity("N-CTRL-B", other.name, other.members)
    sheets = (*project.sheets, ContinuationSheet("S3", 3),
              ContinuationSheet("S4", 4))
    endpoints = (
        *project.endpoints,
        NetContinuationEndpoint(
            "B-OUT", "N-CTRL-B", "S3", 3,
            "3/C4", "4/A2", Point(80000, 70000), "CTRL",
            ContinuationDirection.SOURCE,
        ),
        NetContinuationEndpoint(
            "B-IN", "N-CTRL-B", "S4", 4,
            "4/A2", "3/C4", Point(140000, 70000), "CTRL",
            ContinuationDirection.TARGET,
        ),
    )
    stubs = (
        *project.stubs,
        ContinuationStub("B-WIRE1", "B-OUT", PinRef("DD2", "5"),
                         Point(60000, 70000), Point(80000, 70000)),
        ContinuationStub("B-WIRE2", "B-IN", PinRef("VT2", "G"),
                         Point(160000, 70000), Point(140000, 70000)),
    )
    mixed = NetContinuationProject(
        circuit, (*project.nets, net2), sheets, endpoints,
        (*project.pairs, ContinuationPair(
            "PAIR-B", "B-OUT", "B-IN", ContinuationScope.GLOBAL,
        )), stubs,
    )
    assert "E3_CONT_LABEL_AMBIGUOUS" in codes(mixed)
    assert project.circuit.nets[0] == mixed.circuit.nets[0]
    assert len(mixed.circuit.nets) == 2
    assert len({p for net in mixed.circuit.nets for p in net.members}) == 4
    with pytest.raises(ValueError, match="E3_CONT_LABEL_AMBIGUOUS"):
        netrefs_to_json(mixed)


def test_conductive_X_crossing_does_not_mutate_net_even_if_segments_cross():
    project = specimen()
    source = project.stubs[0]
    altered = replace(project, stubs=(
        replace(source, start=Point(70000, 40000)), project.stubs[1],
    ))
    # There is no line intersection→netlist inference *anywhere* in this overlay.
    assert codes(altered) == set()
    assert altered.circuit.nets is project.circuit.nets
    assert altered.pairs == project.pairs


def test_exact_1um_stub_end_mismatch_and_wrong_actual_physical_pin_fails():
    project = specimen()
    source = project.stubs[0]
    wrong_end = replace(project, stubs=(
        replace(source, end=Point(source.end.x + 1, source.end.y)),
        project.stubs[1],
    ))
    assert "E3_CONT_STUB_OFF_ANCHOR" in codes(wrong_end)
    with pytest.raises(ValueError, match="STUB_OFF_ANCHOR"):
        netrefs_to_json(wrong_end)
    wrong_ref = replace(project, stubs=(
        replace(source, pin=PinRef("DD1", "999")), project.stubs[1],
    ))
    assert "E3_CONT_STUB_WRONG_NET" in codes(wrong_ref)
    wrong_physical_coordinate = replace(project, stubs=(
        replace(source, start=Point(source.start.x + 1, source.start.y)),
        project.stubs[1],
    ))
    assert "E3_CONT_STUB_PHYSICAL_MISMATCH" in codes(
        wrong_physical_coordinate, ANCHORS,
    )


def test_duplicate_marker_page_number_and_pair_label_or_reuse_rejected():
    project = specimen()
    duplicate = replace(project, endpoints=(
        *project.endpoints, replace(project.endpoints[0], net_id="N-CTRL-001"),
    ))
    assert "E3_CONT_DUPLICATE_ENDPOINT_ID" in codes(duplicate)
    invalid = replace(project, sheets=(
        project.sheets[0], replace(project.sheets[1], number=1),
    ))
    assert "E3_CONT_DUPLICATE_SHEET_NUMBER" in codes(invalid)
    mismatch = replace(project, endpoints=(
        project.endpoints[0], replace(project.endpoints[1], label="OTHER"),
    ))
    assert "E3_CONT_LABEL_MISMATCH" in codes(mismatch)
    repeated = replace(project, pairs=(*project.pairs, replace(
        project.pairs[0], id="PAIR2",
    )))
    assert "E3_CONT_ENDPOINT_REUSED" in codes(repeated)


def test_same_printed_label_cannot_fabricate_net_without_known_real_net():
    project = specimen()
    wrong_binding = replace(project, nets=(replace(
        project.nets[0], net_name="NONEXISTENT"
    ),))
    assert "E3_CONT_NET_UNKNOWN" in codes(wrong_binding)
    wrong_members = replace(project, nets=(replace(
        project.nets[0], members=(PinRef("DD1", "5"),)
    ),))
    assert "E3_CONT_NET_MEMBERS_MISMATCH" in codes(wrong_members)
    wrong_duplicate = replace(project, nets=(
        *project.nets, replace(project.nets[0], id="N-ANOTHER"),
    ))
    assert "E3_CONT_NET_DUPLICATE_BINDING" in codes(wrong_duplicate)


def test_real_XP_XS_pinref_possible_but_marker_must_not_impersonate_plug():
    project = specimen()
    # Real plug is only valid upstream when a genuine physical PartDefinition
    # and actual PinRef were added to the Circuit; marker alone isn't a part.
    actual = ComponentInstance("XP1", "SYNTHETIC_PHYSICAL_CONNECTOR")
    extra_ref = PinRef("XP1", "2")
    updated = Net("CTRL", (*project.circuit.nets[0].members, extra_ref))
    modified = replace(
        project, circuit=Circuit((*project.circuit.components, actual), (updated,)),
        nets=(replace(project.nets[0], members=updated.members),),
    )
    assert codes(modified) == set()
    assert extra_ref in modified.circuit.nets[0].members
    assert not any(e.label == "XP1" for e in modified.endpoints)


@pytest.mark.parametrize("mutation", [
    lambda r: {**r, "schema_version": 2},
    lambda r: {**r, "schema_version": True},
    lambda r: {**r, "record_type": "E1"},
    lambda r: {**r, "device": "FAKE_PART"},
    lambda r: {**r, "endpoints": [
        {**r["endpoints"][0], "anchor_um": [10000.5, 40000]},
        *r["endpoints"][1:],
    ]},
    lambda r: {**r, "endpoints": [
        {**r["endpoints"][0], "direction": "fake_wire"},
        *r["endpoints"][1:],
    ]},
    lambda r: {**r, "pairs": [
        {**r["pairs"][0], "target_id": "NO_TARGET"},
    ]},
])
def test_strict_json_fails_closed_on_invalid_schema_or_values(mutation):
    project = specimen()
    raw = json.loads(netrefs_to_json(project))
    with pytest.raises((ValueError, TypeError)):
        netrefs_from_json(json.dumps(mutation(raw)), project.circuit)


def test_json_duplicates_NaN_and_wrong_circuit_rejected():
    project = specimen()
    with pytest.raises(ValueError, match="Duplicate"):
        netrefs_from_json('{"schema_version":1,"schema_version":1}', project.circuit)
    with pytest.raises(ValueError):
        netrefs_from_json(netrefs_to_json(project).replace(
            '"schema_version": 1', '"schema_version": NaN',
        ), project.circuit)
    with pytest.raises(TypeError):
        netrefs_from_json(netrefs_to_json(project), None)


def test_full_unicode_is_preserved_but_ink_measurement_not_claimed():
    project = specimen()
    ends = tuple(replace(e, label="СИГНАЛ_УПРАВЛЕНИЯ_ОЧЕНЬ_ДЛИННЫЙ")
                 for e in project.endpoints)
    modified = replace(project, endpoints=ends)
    assert codes(modified) == set()
    assert "СИГНАЛ_УПРАВЛЕНИЯ_ОЧЕНЬ_ДЛИННЫЙ" in netrefs_to_json(modified)
    assert "DRAFT_UNMEASURED_FONT" in sheet_svg(modified, "S1")
