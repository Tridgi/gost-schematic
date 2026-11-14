"""Adversarial tests for the independently pinned REAL-native ESKD acceptance contract.

Small constructed XML is for validator unit/negative cases only. A separate
specialized workflow runs this same validator on PAINT owner-created *real* SVGs.
"""
from __future__ import annotations

import json
from xml.etree import ElementTree as ET

import pytest

from scripts import eskd_cycle10_native_print_gate as gate

ET.register_namespace("", "http://www.w3.org/2000/svg")
SRC = "{http://www.w3.org/2000/svg}"
REFERENCES = [
    "DA1", "X1", "X2", "L1", "L2", "VT1", "VD1", "FU1",
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
    "C1", "C2", "C3", "C4", "C5", "C6", "C7",
]
PROFILE_IDS = {
    "VD1", "VT1", "FU1", "R5", "L1", "L2",
    "C1", "C2", "C3", "C4", "C5", "C6", "C7",
}


def _fake_owner_manifest():
    return {
        "source_sha": gate.FROZEN_SOURCE,
        "owner_catalog_sha": gate.YGO_HEAD,
        "components": 23, "Nets": 15, "wires": 91,
        "explicit_junctions": 37,
        "font_sha256": gate.FONT_SHA,
        "calibrated_type_a_h_mm": 3.5,
        "actual_ti_pin3_electrical": "input",
        "actual_ti_pin13_electrical": "input",
        "source_3mm_parallel_wire_failures": 5,
        "source_3mm_parallel_wire_details": [
            {"edge_gap_um": n} for n in gate.SOURCE_GAPS_UM
        ],
        "electrical_topology_changed": False,
        "route_drc_pass": False,
        "gost_ugo_approved": False,
        "native_b_graphics_from_typed_project": True,
        "fake_a_marker_created": False,
        "catalog_ugo_bindings": sorted(PROFILE_IDS),
        "paint_authoritative_points": {
            str(n): [n * 1000, n * 2000] for n in range(1, 17)
        },
        "original_b_continuations": ["b-X2", "b-R5"],
    }


def _fake_ygo():
    return {
        "reference_sha": gate.FROZEN_SOURCE,
        "status": "DRAFT",
        "profiles": [
            {"reference": n, "symbol_id": "dummy.unapproved",
             "standard_figure": "TEST_ONLY",
             "rotation": 0,
             "normative_verdict": "BLOCKED_NO_CALIBRATED_SOURCE_1TO1"}
            for n in sorted(PROFILE_IDS)
        ],
    }


def _synthetic_svg(*, diagnostic: bool):
    root = ET.Element(SRC + "svg", {
        "width": "679.3mm", "height": "220.05mm",
        "viewBox": "0 0 679.3 220.05",
        "data-native-ic-composition": "exact-circuit-pinrefs",
    })
    for ref in REFERENCES:
        group = ET.SubElement(root, SRC + "g", {
            "data-reference": ref, "data-layer": "symbols",
        })
        if ref == "DA1":
            group.set("data-composed-engine", "physical-ic-renderer")
            group.set("data-physical-pin-count", "16")
            lead_group = ET.SubElement(group, SRC + "g", {
                "data-layer": "ic-physical-pin-leads",
            })
            for i in range(1, 17):
                ET.SubElement(lead_group, SRC + "line", {
                    "data-pin-number": str(i),
                })
            ET.SubElement(group, SRC + "text", {
                "data-layer": "ic-text",
                "data-kind": "function",
                "transform": "matrix(0 -1 1 0 120 80)",
            }).text = "PWM"
    for i in range(91):
        ET.SubElement(root, SRC + "line", {
            "data-layer": "wires", "data-net": f"REAL_NET_{i % 15}",
        })
    for i in range(37):
        ET.SubElement(root, SRC + "circle", {
            "data-kind": "authored-junction", "cx": str(i),
        })
    group = ET.SubElement(root, SRC + "g", {
        "data-layer": "typed-nonphysical-continuations",
        "data-nonphysical": "true",
    })
    for name in ("b-X2", "b-R5"):
        ET.SubElement(group, SRC + "circle", {
            "data-nonphysical-net-continuation": name,
            "data-electrical-junction": "false",
        })
        ET.SubElement(group, SRC + "text", {
            "data-source": "typed-net-continuation-v2",
            "data-nonphysical": "true",
        }).text = "b"
    if diagnostic:
        marks = ET.SubElement(root, SRC + "g", {
            "data-layer": "editor-connection-targets",
            "data-layer-order": "after-all-copper",
        })
        for i in range(1, 17):
            ET.SubElement(marks, SRC + "rect", {
                "data-pin-number": str(i),
                "data-external-anchor-x-um": str(i * 1000),
                "data-external-anchor-y-um": str(i * 2000),
                "fill": "#168f78",
            })
    return root


def test_source_owner_contract_passes_with_exact_13_and_five_hard_failures():
    gate._owner_facts(_fake_owner_manifest(), gate._source_profile(_fake_ygo()))


@pytest.mark.parametrize(
    ("name", "replacement", "error"),
    [
        ("components", 13, "COMPONENTS"),
        ("Nets", 14, "NETS"),
        ("wires", 90, "WIRES"),
        ("route_drc_pass", True, "ROUTE_DRC_PASS"),
        ("gost_ugo_approved", True, "GOST_UGO_APPROVED"),
        ("actual_ti_pin3_electrical", "output", "ACTUAL_TI_PIN3"),
        ("source_3mm_parallel_wire_failures", 0, "SOURCE_3MM"),
        ("font_sha256", "fake", "FONT_SHA256"),
    ],
)
def test_owner_negative_fails_without_waiving(name, replacement, error):
    manifest = _fake_owner_manifest()
    manifest[name] = replacement
    with pytest.raises(gate.PrintEvidenceError, match=error):
        gate._owner_facts(manifest, gate._source_profile(_fake_ygo()))


def test_five_parallel_gaps_cannot_be_silently_reclassified_as_pass():
    manifest = _fake_owner_manifest()
    manifest["source_3mm_parallel_wire_details"][0]["edge_gap_um"] = 3000
    with pytest.raises(gate.PrintEvidenceError, match="GAP_CHANGED"):
        gate._owner_facts(manifest, gate._source_profile(_fake_ygo()))


@pytest.mark.parametrize("diagnostic", [False, True])
def test_bounded_positive_structural_svg_is_not_normative_approval(diagnostic):
    root = _synthetic_svg(diagnostic=diagnostic)
    result = gate._check_physical_svg(root, _fake_owner_manifest(), diagnostic)
    assert result["symbols"] == 23
    assert result["wire_segments"] == 91
    assert result["numbered_tl494_pins"] == 16
    assert result["diagnostic_only_hotspots"] == (16 if diagnostic else 0)
    assert gate._read_function(root) == (0, -1)


def test_true_top_to_bottom_old_reference_must_fail_target():
    root = _synthetic_svg(diagnostic=False)
    function = root.find(f".//{SRC}text[@data-kind='function']")
    function.set("transform", "matrix(0 1 -1 0 120 80)")
    assert gate._read_function(root) == (0, 1)
    assert gate._read_function(root) != (0, -1)


@pytest.mark.parametrize(
    ("bad_case", "error"),
    [
        ("drop_wire", "91_WIRE"),
        ("drop_part", "23_UNIQUE"),
        ("change_da1_num", "NUMBERED_LEADS"),
        ("remove_b", "B_CONTINUATION"),
        ("join_b", "PHANTOM_ELECTRICAL_JUNCTION"),
        ("fake_ground", "FABRICATED_EARTH"),
        ("editor_in_clean", "HOTSPOTS_LEAKED"),
        ("debug_geometry_in_clean", "EDITOR_GEOMETRY"),
        ("wrong_viewbox_mm", "VIEWBOX_SCALE_MISMATCH"),
    ],
)
def test_negative_fake_editor_overlays_and_corrupt_print_are_rejected(bad_case, error):
    root = _synthetic_svg(diagnostic=False)
    if bad_case == "drop_wire":
        target = root.find(f"{SRC}line[@data-layer='wires']")
        root.remove(target)
    elif bad_case == "drop_part":
        root.remove(root.find(f"{SRC}g[@data-reference='C1']"))
    elif bad_case == "change_da1_num":
        lead = root.find(f".//{SRC}g[@data-layer='ic-physical-pin-leads']/{SRC}line")
        lead.set("data-pin-number", "17")
    elif bad_case == "remove_b":
        c = root.find(f".//{SRC}circle[@data-nonphysical-net-continuation='b-X2']")
        root.find(f".//{SRC}g[@data-layer='typed-nonphysical-continuations']").remove(c)
    elif bad_case == "join_b":
        c = root.find(f".//{SRC}circle[@data-nonphysical-net-continuation='b-X2']")
        c.set("data-electrical-junction", "true")
    elif bad_case == "fake_ground":
        ET.SubElement(root, SRC + "g", {
            "data-marker-id": "net-marker.protective_earth",
        })
    elif bad_case == "editor_in_clean":
        ET.SubElement(root, SRC + "g", {
            "data-layer": "editor-connection-targets",
        })
    elif bad_case == "debug_geometry_in_clean":
        ET.SubElement(root, SRC + "g", {
            "data-layer": "geometry-review",
        })
    elif bad_case == "wrong_viewbox_mm":
        root.set("viewBox", "0 0 150 220.05")
    with pytest.raises(gate.PrintEvidenceError, match=error):
        gate._check_physical_svg(root, _fake_owner_manifest(), False)


@pytest.mark.parametrize(
    ("case", "error"),
    [
        ("missing_marker", "16_REAL_PIN_HOTSPOTS"),
        ("wrong_anchor", "MOVED_FROM_REAL_PINREF"),
        ("not_foreground", "NOT_FOREGROUND"),
    ],
)
def test_diagnostic_foreground_only_true_pinref_endpoints(case, error):
    root = _synthetic_svg(diagnostic=True)
    layer = root.find(f"./{SRC}g[@data-layer='editor-connection-targets']")
    if case == "missing_marker":
        layer.remove(layer[0])
    elif case == "wrong_anchor":
        layer[0].set("data-external-anchor-x-um", "9999")
    else:
        # Keep 91 real wires but deliberately paint one AFTER green targets.
        wire = root.find(f"{SRC}line[@data-layer='wires']")
        root.remove(wire)
        root.append(wire)
    with pytest.raises(gate.PrintEvidenceError, match=error):
        gate._check_physical_svg(root, _fake_owner_manifest(), True)


def test_real_evidence_file_set_fail_closed_when_input_missing(tmp_path):
    fake_profile = tmp_path / "profile.json"
    fake_profile.write_text(json.dumps(_fake_ygo()), encoding="utf-8")
    with pytest.raises(gate.PrintEvidenceError, match="MANIFEST_MISSING"):
        gate.audit(tmp_path, fake_profile)


def test_real_synthetic_owner_manifest_still_requires_both_SVGs(tmp_path):
    fake_profile = tmp_path / "profile.json"
    fake_profile.write_text(json.dumps(_fake_ygo()), encoding="utf-8")
    (tmp_path / "TL494_full_native_23_engine_manifest.json").write_text(
        json.dumps(_fake_owner_manifest()), encoding="utf-8"
    )
    with pytest.raises(gate.PrintEvidenceError, match="CLEAN_SVG_MISSING"):
        gate.audit(tmp_path, fake_profile)


def test_svg_matrix_reflection_and_scale_are_not_pure_pwm_rotations():
    for matrix in ["matrix(0 -2 1 0 0 0)", "matrix(0 1 1 0 0 0)"]:
        element = ET.Element(SRC + "text", {"transform": matrix})
        with pytest.raises(gate.PrintEvidenceError, match="REFLECTION_OR_SCALE"):
            gate._reading_vector(element)


def test_profile_narrowly_remains_draft():
    profile = _fake_ygo()
    profile["profiles"][0]["normative_verdict"] = "APPROVED"
    with pytest.raises(gate.PrintEvidenceError, match="UNPROVEN_NORMATIVE"):
        gate._source_profile(profile)


def _real_numeric_svg_wires(*, first_neighbor_y_mm: float,
                            neighboring_net: str = "NET_B",
                            make_crossing: bool = False) -> ET.Element:
    root = ET.Element(SRC + "svg")
    for i in range(91):
        if i == 0:
            coords = (0.0, 0.0, 10.0, 0.0)
            net = "NET_A"
        elif i == 1:
            coords = (
                (5.0, -4.0, 5.0, 4.0)
                if make_crossing else
                (0.0, first_neighbor_y_mm, 10.0, first_neighbor_y_mm)
            )
            net = neighboring_net
        else:
            coords = (0.0, float(i * 10 + 100), 10.0, float(i * 10 + 100))
            net = "OTHER"
        ET.SubElement(root, SRC + "line", {
            "data-layer": "wires",
            "data-wire-index": str(i),
            "data-net": net,
            "stroke-width": "0.3",
            "x1": str(coords[0]), "y1": str(coords[1]),
            "x2": str(coords[2]), "y2": str(coords[3]),
        })
    return root


@pytest.mark.parametrize(("gap_y", "expected"), [
    (3.3, 0),
    (3.299, 1),
    (3.0, 1),
    (2.0, 1),
])
def test_independent_actual_svg_3mm_stroke_ink_boundaries(gap_y, expected):
    data = gate._actual_svg_3mm_violations(
        _real_numeric_svg_wires(first_neighbor_y_mm=gap_y)
    )
    assert len(data) == expected
    if expected:
        assert data[0]["first_segment"] == 0
        assert data[0]["second_segment"] == 1
        assert data[0]["edge_gap_um"] == round(gap_y * 1000) - 300


def test_3mm_rule_exempts_same_net_parallel_and_nonparallel_x_not_topology():
    assert not gate._actual_svg_3mm_violations(
        _real_numeric_svg_wires(first_neighbor_y_mm=0.8,
                                neighboring_net="NET_A")
    )
    assert not gate._actual_svg_3mm_violations(
        _real_numeric_svg_wires(first_neighbor_y_mm=0.8,
                                make_crossing=True)
    )


def test_independent_svg_wire_audit_blocks_missing_net_provenance():
    root = _real_numeric_svg_wires(first_neighbor_y_mm=3.0)
    first = root.find(f"{SRC}line[@data-layer='wires']")
    first.attrib.pop("data-wire-index")
    with pytest.raises(gate.PrintEvidenceError, match="INDEX_PROVENANCE"):
        gate._actual_svg_3mm_violations(root)


def test_independent_svg_wire_audit_blocks_illegal_stroke_or_oblique():
    root = _real_numeric_svg_wires(first_neighbor_y_mm=3.0)
    first = root.find(f"{SRC}line[@data-layer='wires']")
    first.set("stroke-width", "0.1")
    with pytest.raises(gate.PrintEvidenceError, match="STROKE_OUT_OF_GOST"):
        gate._actual_svg_3mm_violations(root)
    first.set("stroke-width", "0.3")
    first.set("y2", "2.0")
    with pytest.raises(gate.PrintEvidenceError, match="NONZERO_ORTHOGONAL"):
        gate._actual_svg_3mm_violations(root)


def _png_fixture(tmp_path, *, diagnostic: bool):
    from PIL import Image

    root = ET.Element(SRC + "svg", {"viewBox": "0 0 10 10"})
    g = ET.SubElement(root, SRC + "g", {
        "data-layer": "ic-physical-pin-leads",
    })
    marks = ET.SubElement(root, SRC + "g", {
        "data-layer": "editor-connection-targets",
    })
    image = Image.new("RGB", (round(10 * 300 / 25.4),) * 2, "white")
    for i in range(1, 17):
        x = i * 0.4
        y = 2.0
        ET.SubElement(g, SRC + "line", {
            "data-pin-number": str(i),
            "x2": str(x), "y2": str(y),
        })
        ET.SubElement(marks, SRC + "rect", {
            "data-pin-number": str(i),
            "data-pin-ref": f"DA1.{i}",
            "data-connectable": "true",
            "data-manufacturer-electrical-type": "input",
            "data-net-id": "REAL_NET",
            "x": str(x - 0.35), "y": str(y - 0.35),
            "width": "0.7", "height": "0.7",
        })
        if diagnostic:
            image.putpixel(
                (round(x * 300 / 25.4), round(y * 300 / 25.4)),
                (10, 180, 40),
            )
    path = tmp_path / "real_pixels.png"
    image.save(path, dpi=(300, 300))
    return path, root


def test_png_physical_pixel_check_and_sixteen_real_sample_green(tmp_path):
    clean_path, root = _png_fixture(tmp_path, diagnostic=False)
    clean = gate._verify_png(clean_path, 10, root, diagnostic=False)
    assert clean["real_green_pin_pixels"] == 0
    diagnostic_path, root = _png_fixture(tmp_path, diagnostic=True)
    debug = gate._verify_png(diagnostic_path, 10, root, diagnostic=True)
    assert debug["real_green_pin_pixels"] == 16


def test_png_clean_rejects_actual_colored_editor_ink(tmp_path):
    from PIL import Image

    path, root = _png_fixture(tmp_path, diagnostic=False)
    with Image.open(path) as image:
        data = image.convert("RGB")
    data.putpixel((5, 5), (180, 0, 0))
    data.save(path)
    with pytest.raises(gate.PrintEvidenceError, match="CLEAN_COLORED_EDITOR_INK"):
        gate._verify_png(path, 10, root, diagnostic=False)


def test_png_diagnostic_rejects_pin_center_covered_by_copper(tmp_path):
    from PIL import Image

    path, root = _png_fixture(tmp_path, diagnostic=True)
    with Image.open(path) as image:
        data = image.convert("RGB")
    data.putpixel((round(0.4 * 300 / 25.4), round(2 * 300 / 25.4)),
                  (0, 0, 0))
    data.save(path)
    with pytest.raises(gate.PrintEvidenceError,
                       match="GREEN_ENDPOINT_COVERED_BY_COPPER"):
        gate._verify_png(path, 10, root, diagnostic=True)


def _synthetic_source_62():
    # Contract-only data, never passed off as PAINT source evidence.
    refs = [f"DA1.{n}" for n in range(1, 17)]
    refs.extend(f"{ref}.1" for ref in REFERENCES if ref != "DA1")
    refs.extend(
        f"{ref}.2" for ref in REFERENCES if ref != "DA1"
    )
    assert len(refs) == 60
    refs.extend(["R5.3", "X1.3"])
    assert len(refs) == 62
    return {
        "source_sha": gate.FROZEN_SOURCE,
        "components": sorted(REFERENCES),
        "nets": [
            {"name": f"TEST_NET_{i}",
             "members": [ref for j, ref in enumerate(refs) if j % 15 == i]}
            for i in range(15)
        ],
        "wire_segments": 91,
        "junctions": 37,
        "nonphysical_b": ["b-X2", "b-R5"],
        "all_15_nets_routed": False,
    }


def test_true_typed_source_contract_requires_23_15_62_and_all_16():
    data = gate._typed_source_62(_synthetic_source_62())
    assert data["status"] == "PASS_SOURCE_INVENTORY_ONLY"
    assert data["unique_pinref_memberships"] == 62
    assert data["legacy_route_complete"] is False


@pytest.mark.parametrize(("change", "code"), [
    ("duplicate_pin", "62_UNIQUE_PINREFS"),
    ("delete_one_pin", "62_UNIQUE_PINREFS"),
    ("drop_da1_16", "ALL_16_DA1_PINREFS"),
    ("unknown_component", "UNKNOWN_PINREF_COMPONENT"),
    ("falsify_full_route", "ORIGINAL_91_CANNOT_CLAIM_NEW_FULL_ROUTE"),
    ("change_frozen_source", "SOURCE_SHA_MISMATCH"),
    ("drop_b", "B_GRAPHIC_NOT_PHYSICAL"),
])
def test_typed_source_adversarial_inventory(change, code):
    facts = _synthetic_source_62()
    if change == "duplicate_pin":
        facts["nets"][0]["members"][0] = facts["nets"][1]["members"][0]
    elif change == "delete_one_pin":
        facts["nets"][0]["members"].pop()
    elif change == "drop_da1_16":
        for net in facts["nets"]:
            net["members"] = [
                "X1.8" if ref == "DA1.16" else ref
                for ref in net["members"]
            ]
    elif change == "unknown_component":
        for net in facts["nets"]:
            net["members"] = [
                "UNKNOWN.9" if ref == "DA1.16" else ref
                for ref in net["members"]
            ]
    elif change == "falsify_full_route":
        facts["all_15_nets_routed"] = True
    elif change == "change_frozen_source":
        facts["source_sha"] = "0" * 40
    elif change == "drop_b":
        facts["nonphysical_b"] = ["b-X2"]
    with pytest.raises(gate.PrintEvidenceError, match=code):
        gate._typed_source_62(facts)
