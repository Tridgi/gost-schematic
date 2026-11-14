"""Cycle7 #90: v2 typed address proof and real three-sheet collision regressions."""

import os
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from examples.review_net_continuations_cycle7 import sheet_svg, specimen_three_sheet
from gost_schematic.core.geometry import Box, Point
from gost_schematic.electrical.netrefs import (
    ContinuationAddressBinding,
    ContinuationAddressKind,
    NetContinuationProject,
    validate_net_continuations,
)
from gost_schematic.electrical.netrefs_serde import netrefs_from_json, netrefs_to_json
from gost_schematic.model.circuit import PinRef

SVG_NS = "{http://www.w3.org/2000/svg}"
FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"


def _codes(project: NetContinuationProject, **kwargs) -> set[str]:
    return {issue.code for issue in validate_net_continuations(project, **kwargs)}


def _font() -> Path:
    value = os.environ.get("GOST_NETREF_FONT")
    if not value:
        pytest.skip("Pinned OpenGost Type A supplied in netrefs-review CI")
    from gost_schematic.engines.annotation.metrics import font_sha256

    path = Path(value)
    assert path.is_file()
    assert font_sha256(str(path)) == FONT_SHA
    return path


def test_three_sheets_three_real_nets_four_pairs_and_eight_actual_pin_stubs():
    project = specimen_three_sheet()
    assert project.schema_version == 2
    assert len(project.sheets) == 3
    assert len(project.circuit.nets) == 3
    assert len(project.pairs) == 4
    assert len(project.endpoints) == len(project.stubs) == 8
    assert len(project.address_bindings) == 8
    assert _codes(
        project, physical_pin_anchors={stub.pin: stub.start for stub in project.stubs},
    ) == set()
    assert {net.id for net in project.nets} == {"N-CTRL", "N-REF", "N-ENABLE"}
    assert len(project.circuit.nets[0].members) == 4  # CTRL spans all three sheets.
    assert {item.sheet_id for item in project.endpoints if item.label == "CTRL"} == {
        "S1", "S2", "S3",
    }
    assert project.circuit.nets is project.circuit.nets  # No hidden E3 mutation.
    encoded = netrefs_to_json(project)
    assert netrefs_from_json(encoded, project.circuit) == project
    assert netrefs_to_json(netrefs_from_json(encoded, project.circuit)) == encoded


@pytest.mark.parametrize("sheet_id, expected_lines", (("S1", 2), ("S2", 3), ("S3", 3)))
def test_real_multinet_multisheet_svg_has_only_local_authored_stubs(sheet_id, expected_lines):
    project = specimen_three_sheet()
    svg = sheet_svg(project, sheet_id)
    assert svg.count('xmlns="http://www.w3.org/2000/svg"') == 1
    root = ET.fromstring(svg)
    lines = root.findall(f".//{SVG_NS}line")
    assert len(lines) == expected_lines
    assert all(item.attrib["data-role"] == "explicit-real-wire-stub" for item in lines)
    assert not root.findall(f".//{SVG_NS}circle")
    assert all("data-net-id" in line.attrib for line in lines)
    # No nonphysical marker or printed address creates a physical connector.
    assert not any("XP1" in line.attrib.get("data-pin-ref", "") for line in lines)


def test_v2_rejects_missing_duplicate_unknown_or_wrong_real_address_provenance():
    project = specimen_three_sheet()
    binding = project.address_bindings[0]
    assert "E3_CONT_ADDRESS_BINDING_INCOMPLETE" in _codes(replace(
        project, address_bindings=project.address_bindings[1:],
    ))
    assert "E3_CONT_DUPLICATE_ADDRESS_BINDING" in _codes(replace(
        project, address_bindings=(*project.address_bindings, binding),
    ))
    assert "E3_CONT_ADDRESS_BINDING_UNKNOWN" in _codes(replace(
        project, address_bindings=(
            replace(binding, endpoint_id="MISSING"), *project.address_bindings[1:],
        ),
    ))
    el = next(x for x in project.address_bindings if x.kind is ContinuationAddressKind.ELEMENT_PIN)
    wrong_pin = replace(el, physical_pin=PinRef("DD2", "7"))
    altered = replace(project, address_bindings=tuple(
        wrong_pin if x.endpoint_id == el.endpoint_id else x
        for x in project.address_bindings
    ))
    assert "E3_CONT_ADDRESS_PIN_PROVENANCE" in _codes(altered)
    with pytest.raises(ValueError, match="E3_CONT_ADDRESS_PIN_PROVENANCE"):
        netrefs_to_json(altered)
    wrong_owner = replace(el, owner_ref="UNDECLARED")
    altered = replace(project, address_bindings=tuple(
        wrong_owner if x.endpoint_id == el.endpoint_id else x
        for x in project.address_bindings
    ))
    assert "E3_CONT_ADDRESS_ELEMENT_PROVENANCE" in _codes(altered)


def test_v2_device_or_group_requires_real_external_authoritative_owner_inventory():
    project = specimen_three_sheet()
    source = next(x for x in project.endpoints if x.id == "C2-OUT")
    address = replace(source, address="A7:X16")
    counterpart = next(x for x in project.endpoints if x.id == "C2-IN")
    peer = replace(counterpart, target_address="A7:X16")
    addresses = tuple(
        address if item.id == source.id else
        peer if item.id == counterpart.id else item
        for item in project.endpoints
    )
    bindings = tuple(
        ContinuationAddressBinding(
            "C2-OUT", ContinuationAddressKind.FUNCTIONAL_GROUP_CONTACT,
            "A7", PinRef("DD3", "1"),
        ) if item.endpoint_id == "C2-OUT" else item
        for item in project.address_bindings
    )
    staged = replace(project, endpoints=addresses, address_bindings=bindings)
    assert "E3_CONT_ADDRESS_OWNER_UNVERIFIED" in _codes(staged)
    with pytest.raises(ValueError, match="OWNER_UNVERIFIED"):
        netrefs_to_json(staged)
    owners = {
        (ContinuationAddressKind.FUNCTIONAL_GROUP_CONTACT, "A7"):
        frozenset((PinRef("DD3", "1"),)),
    }
    assert _codes(staged, verified_address_owners=owners) == set()
    data = netrefs_to_json(staged, verified_address_owners=owners)
    assert netrefs_from_json(
        data, staged.circuit, verified_address_owners=owners,
    ) == staged
    with pytest.raises(ValueError, match="OWNER_UNVERIFIED"):
        netrefs_from_json(data, staged.circuit)


def test_v2_same_visible_label_on_distinct_real_nets_fails_without_merging_them():
    project = specimen_three_sheet()
    changed = replace(project, endpoints=tuple(
        replace(e, label="CTRL") if e.label == "REF" else e
        for e in project.endpoints
    ))
    assert "E3_CONT_LABEL_AMBIGUOUS" in _codes(changed)
    assert changed.circuit is project.circuit
    assert changed.circuit.nets == project.circuit.nets
    with pytest.raises(ValueError, match="LABEL_AMBIGUOUS"):
        netrefs_to_json(changed)


def test_v2_json_rejects_silent_field_loss_or_legacy_unversioned_migration():
    project = specimen_three_sheet()
    data = netrefs_to_json(project)
    import json

    parsed = json.loads(data)
    parsed.pop("address_bindings")
    with pytest.raises(ValueError, match="exact JSON keys"):
        netrefs_from_json(json.dumps(parsed), project.circuit)
    parsed["schema_version"] = 1
    with pytest.raises(ValueError, match="exact JSON keys"):
        netrefs_from_json(json.dumps(parsed), project.circuit)
    with pytest.raises(ValueError, match="provenance requires explicit schema v2"):
        replace(project, schema_version=1)


def test_measured_three_sheet_print_is_clean_and_editor_has_nonprinting_targets():
    font = _font()
    project = specimen_three_sheet()
    for sheet in project.sheets:
        clean = sheet_svg(project, sheet.id, font_path=font)
        svg = sheet_svg(
            project, sheet.id, font_path=font, review_overlay=True,
            review_connection_zones=True,
        )
        root = ET.fromstring(svg)
        count = len([e for e in project.endpoints if e.sheet_id == sheet.id])
        assert len(root.findall(f".//{SVG_NS}line")) == count
        assert len(root.findall(f".//{SVG_NS}text")) == count * 2
        assert len(root.findall(f".//{SVG_NS}rect")) == count * 3
        assert root.attrib["data-font-sha256"] == FONT_SHA
        assert clean.count('xmlns="http://www.w3.org/2000/svg"') == 1
        assert "editor-only-connection-keepout" not in clean
        for rect in root.findall(f".//{SVG_NS}rect"):
            if rect.attrib.get("data-role") == "editor-only-connection-keepout":
                assert rect.attrib["data-print"] == "false"
        assert _codes(project) == set()


@pytest.mark.parametrize("obstacle,code", (
    (Box(64000, 39500, 66000, 40500), "E3_CONT_GRAPHIC_EXTERNAL_COLLISION"),
    (Box(79000, 39000, 81000, 41000), "E3_CONT_GRAPHIC_EXTERNAL_COLLISION"),
    (Box(78000, 31000, 82000, 34000), "E3_CONT_TEXT_EXTERNAL_COLLISION"),
))
def test_measured_external_component_obstacles_protect_wire_arrow_and_ink(obstacle, code):
    font = _font()
    with pytest.raises(ValueError, match=code):
        sheet_svg(
            specimen_three_sheet(), "S1", font_path=font,
            external_keepouts=(obstacle,),
        )


def test_measured_overlapping_other_marker_and_page_boundary_fail_closed():
    font = _font()
    project = specimen_three_sheet()
    out = next(x for x in project.endpoints if x.id == "R-OUT")
    other = next(x for x in project.stubs if x.endpoint_id == "R-OUT")
    same_xy = replace(project,
        endpoints=tuple(
            replace(out, anchor=Point(80000, 40000)) if x.id == out.id else x
            for x in project.endpoints
        ),
        stubs=tuple(
            replace(other, start=Point(60000, 40000), end=Point(80000, 40000))
            if x.id == other.id else x for x in project.stubs
        ),
    )
    assert _codes(same_xy) == set()  # Geometry must reject, not join real Nets.
    with pytest.raises(ValueError, match="E3_CONT_GRAPHIC_GRAPHIC_COLLISION"):
        sheet_svg(same_xy, "S1", font_path=font)
    source = next(x for x in project.endpoints if x.id == "C1-OUT")
    conductor = next(x for x in project.stubs if x.endpoint_id == "C1-OUT")
    edge = replace(project,
        endpoints=tuple(
            replace(source, anchor=Point(10050, 40000)) if x.id == source.id else x
            for x in project.endpoints
        ),
        stubs=tuple(
            replace(conductor, start=Point(12000, 40000), end=Point(10050, 40000))
            if x.id == conductor.id else x for x in project.stubs
        ),
    )
    with pytest.raises(ValueError, match=r"E3_CONT_(TEXT|GRAPHIC)_PAGE_OVERFLOW"):
        sheet_svg(edge, "S1", font_path=font)


def test_green_end_zone_cannot_be_emitted_as_clean_print_or_unmeasured_fallback():
    with pytest.raises(ValueError, match="E3_CONT_MEASURED_PROFILE_REQUIRED"):
        sheet_svg(specimen_three_sheet(), "S1", review_overlay=True,
                  review_connection_zones=True)
    with pytest.raises(ValueError, match="E3_CONT_EDITOR_ZONES_REQUIRE_REVIEW"):
        sheet_svg(specimen_three_sheet(), "S1", font_path="bogus.ttf",
                  review_connection_zones=True)
