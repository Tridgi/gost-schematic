"""Cycle12: exact frozen physical Net regression and hostile ink-rule cases."""
from __future__ import annotations

from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest

from scripts import eskd_cycle12_routed_source_gate as gate

TRACED_NETS = {
    "ADJUSTED_DIVIDER": ["R4.2", "R5.1", "R5.3"],
    "COMMON": [
        "X1.2", "X2.2", "VT1.3", "VD1.2", "C5.1", "C6.1",
        "DA1.7", "DA1.1", "DA1.16", "DA1.13", "R6.2", "R7.2",
        "R8.2", "C7.2",
    ],
    "CONTROL_REFERENCE": ["DA1.14", "DA1.15", "R1.1", "R2.1", "C3.1"],
    "ERROR_INPUT": ["DA1.2", "R2.2", "R4.1", "C4.1"],
    "FEEDBACK": ["R3.2", "DA1.3"],
    "GATE_DRIVE": ["DA1.9", "DA1.10", "R8.1", "VT1.1"],
    "OSCILLATOR_CT": ["C7.1", "DA1.5"],
    "OSCILLATOR_RT": ["R7.1", "DA1.6"],
    "OUT_BEFORE_FUSE": ["L2.2", "FU1.1", "C5.2", "C6.2"],
    "RC_CORRECTION": ["C4.2", "R3.1"],
    "SOFT_START": ["DA1.4", "R1.2", "C3.2", "R6.1"],
    "SWITCH": ["L1.2", "VT1.2", "C1.1", "C2.1"],
    "TRANSFER": ["C1.2", "C2.2", "VD1.1", "L2.1"],
    "a_INPUT_PLUS": ["X1.1", "L1.1", "DA1.12", "DA1.8", "DA1.11"],
    "b_NEGATIVE_OUTPUT": ["FU1.2", "X2.1", "R5.2"],
}


def fixture_source():
    names = {ref.split(".")[0] for pins in TRACED_NETS.values() for ref in pins}
    assert len(names) == 23
    assert sum(map(len, TRACED_NETS.values())) == 62
    return {
        "full_component_count": 23,
        "net_count": 15,
        "physical_pin_memberships": 62,
        "elements": [{"ref": ref} for ref in sorted(names)],
        "nets": deepcopy(TRACED_NETS),
        "routed": False,
        "rendered_full_e3": False,
    }


def fixture_owner():
    original = fixture_source()
    aliases = {v: k for k, v in gate.SOURCE_ALIASES.items()}
    return {
        "source_sha": gate.FROZEN,
        "source_components": 23, "source_nets": 15,
        "all_Circuit_PinRef_memberships": 62,
        "physical_DA1_pin_count": 16,
        "font_sha256": gate.FONT_SHA,
        "net_members": {
            aliases.get(name, name): list(members)
            for name, members in original["nets"].items()
        },
        "source_net_diff": {
            "added": [], "removed": [], "physical_members_changed": [],
        },
    }


def test_15_frozen_original_net_trees_and_62_pinrefs_are_identical():
    original = fixture_source()
    data = gate._source_model(fixture_owner(), original)
    assert data["original_pinref_memberships_exact_after_alias"] is True
    assert data["physical_pinrefs"] == 62
    assert data["da1_pin_numbers"] == [str(i) for i in range(1, 17)]
    assert data["source_name_parity"].startswith("BLOCKED_")
    assert set(data["source_named_nets"]) == gate.SOURCE_NETS


@pytest.mark.parametrize(("mutation", "message"), [
    ("swap_physical_pin", "ORIGINAL_15_NET_PINREF_MEMBERSHIPS_DRIFT"),
    ("rename_noncanonical", "SOURCE_NET_NAMES_NOT_REVERSIBLY_MAPPABLE"),
    ("forge_protective_earth", "SOURCE_NET_NAMES_NOT_REVERSIBLY_MAPPABLE"),
    ("duplicate_pin", "SOURCE_62_PINREFS_NOT_UNIQUE"),
    ("remove_da1", "SOURCE_62_PINREFS_NOT_UNIQUE"),
    ("wrong_original_net", "ORIGINAL_15_NET_PINREF_MEMBERSHIPS_DRIFT"),
    ("wrong_source_sha", "FROZEN_SOURCE_SHA_CHANGED"),
    ("bad_font", "TRUE_TYPE_A_FONT_SHA_MISSING"),
])
def test_frozen_source_negative_contract(mutation, message):
    original = fixture_source()
    owner = fixture_owner()
    nets = owner["net_members"]
    if mutation == "swap_physical_pin":
        nets["GATE_DRIVE"][0], nets["FEEDBACK"][0] = (
            nets["FEEDBACK"][0], nets["GATE_DRIVE"][0]
        )
    elif mutation == "rename_noncanonical":
        nets["IMAGINARY_NET"] = nets.pop("INPUT_POS")
    elif mutation == "forge_protective_earth":
        nets["PE"] = nets.pop("COMMON")
    elif mutation == "duplicate_pin":
        nets["GATE_DRIVE"][0] = nets["COMMON"][0]
    elif mutation == "remove_da1":
        nets["GATE_DRIVE"].remove("DA1.9")
    elif mutation == "wrong_original_net":
        original["nets"]["SWITCH"].append("DA1.12")
    elif mutation == "wrong_source_sha":
        owner["source_sha"] = "0" * 40
    elif mutation == "bad_font":
        owner["font_sha256"] = "0" * 64
    with pytest.raises(gate.EvidenceError, match=message):
        gate._source_model(owner, original)


def _wire(index, net, start, end, width=300):
    return {
        "index": index, "net": net, "stroke": width,
        "coords": (*start, *end),
    }


@pytest.mark.parametrize(("delta_um", "expected_bad"), [
    (3299, True),
    (3300, False),
    (3301, False),
])
def test_strict_3mm_printed_ink_not_wire_center(delta_um, expected_bad):
    wires = [
        _wire(0, "COMMON", (0, 0), (10000, 0)),
        _wire(1, "GATE_DRIVE", (0, delta_um), (10000, delta_um)),
    ]
    result = gate.parallel_gaps(wires)
    assert result["distinct_net_parallel_projected_pairs"] == 1
    assert bool(result["hard_3mm_edge_violations"]) is expected_bad


def test_true_x_crossing_is_not_falsely_subjected_to_parallel_3mm():
    wires = [
        _wire(0, "COMMON", (0, 0), (20000, 0)),
        _wire(1, "GATE_DRIVE", (10000, -10000), (10000, 10000)),
    ]
    assert gate.parallel_gaps(wires) == {
        "distinct_net_parallel_projected_pairs": 0,
        "hard_3mm_edge_violations": [],
        "rule": "PROJECTED_OVERLAP_PARALLEL_DIFFERENT_NET_ONLY",
    }


def test_nonoverlapping_parallel_and_same_net_not_forged_3mm():
    wires = [
        _wire(0, "COMMON", (0, 0), (10000, 0)),
        _wire(1, "FEEDBACK", (10000, 400), (20000, 400)),
        _wire(2, "COMMON", (0, 400), (10000, 400)),
    ]
    assert gate.parallel_gaps(wires)["distinct_net_parallel_projected_pairs"] == 0


@pytest.mark.parametrize(("scale", "reason"), [
    (1, None),
    (2, "REAL_PHYSICAL_MM_VIEWBOX_SCALE_CHANGED"),
])
def test_true_svg_physical_mm_not_a_rescaled_print(scale, reason):
    r = ET.Element("svg", {
        "width": "420mm", "height": "297mm",
        "viewBox": f"0 0 {420 * scale} {297 * scale}",
    })
    if reason:
        with pytest.raises(gate.EvidenceError, match=reason):
            gate._dimension_mm(r)
    else:
        assert gate._dimension_mm(r) == (0, 0, 420, 297)


def test_source_ugo_figure_contract_retains_draft():
    assert len(gate.SOURCE_UGO) == 13
    assert gate.SOURCE_UGO["VD1"] == "diode.schottky"
    assert gate.SOURCE_UGO["VT1"] == "transistor.mosfet_n_enh"
    assert {gate.SOURCE_UGO[part] for part in (
        "C1", "C2", "C3", "C5", "C6"
    )} == {"capacitor.polarized"}
    assert gate.SOURCE_UGO["R5"] == "resistor.variable"


def test_pinned_real_owner_artifact_set_is_exact_and_complete(tmp_path):
    assert len(gate.PINNED_OWNER_BLOBS) == 5
    assert gate.PINNED_ROUTER_SHA == "5c6feb90580ed846aa297c71d3c91afacfc3f0bc"
    assert gate.PINNED_RECON_SHA == "e56397300875ac155a316a9bfebe2601358a4147"
    with pytest.raises(gate.EvidenceError, match="REAL_ARTIFACT_MISSING"):
        gate._verify_pinned_owner_bytes(tmp_path)


@pytest.mark.parametrize("bad_bytes", [b"", b"<svg/>", b"PNG", b"\x00\x01"])
def test_fake_replaced_owner_svg_or_png_never_passes_sha256(
    tmp_path, bad_bytes
):
    for name in gate.PINNED_OWNER_BLOBS:
        (tmp_path / name).write_bytes(bad_bytes)
    with pytest.raises(gate.EvidenceError, match="ARTIFACT_SHA256_MISMATCH"):
        gate._verify_pinned_owner_bytes(tmp_path)


def fixture_ygo_current():
    return {
        "reference_sha": gate.FROZEN,
        "status": "DRAFT",
        "profiles": [
            {"reference": ref, "symbol_id": symbol,
             "normative_verdict": "BLOCKED_NO_CALIBRATED_SOURCE_1TO1"}
            for ref, symbol in gate.SOURCE_UGO.items()
        ],
    }


def test_real_ygo_source_is_13_draft_with_zero_formal_approved():
    proof = gate._source_ygo_current_review(
        fixture_ygo_current(), "a" * 40
    )
    assert proof["sources_13"] == 13
    assert proof["formal_approved"] == 0
    assert proof["actual_ygo_head_sha"] == "a" * 40


@pytest.mark.parametrize(("change", "reason"), [
    ("approve_one", "YGO_CURRENT_FIGURE_SIGNOFF_NOT_EVIDENCED"),
    ("wrong_schottky", "YGO_CURRENT_SCHOTTKY_MOS_CAP_FERRO_ID_DRIFT"),
    ("drop_one", "YGO_CURRENT_NOT_13_SOURCE_UGO"),
    ("reference_drift", "YGO_CURRENT_SOURCE_REFERENCE_SHA_MISMATCH"),
    ("declare_approved", "YGO_CURRENT_UNPROVEN_APPROVAL"),
])
def test_ygo_source_profile_negative_ugo_cases(change, reason):
    owner = fixture_ygo_current()
    if change == "approve_one":
        owner["profiles"][0]["normative_verdict"] = "APPROVED"
    elif change == "wrong_schottky":
        owner["profiles"][0]["symbol_id"] = "diode.general"
    elif change == "drop_one":
        owner["profiles"].pop()
    elif change == "reference_drift":
        owner["reference_sha"] = "0" * 40
    elif change == "declare_approved":
        owner["status"] = "APPROVED"
    with pytest.raises(gate.EvidenceError, match=reason):
        gate._source_ygo_current_review(owner, "a" * 40)


def _realistic_23_ugo_group_fixture(second_x: float = 20.0) -> ET.Element:
    root = ET.Element(f"{gate.SVG}svg")
    refs = sorted(
        ref for ref in (row["ref"] for row in fixture_source()["elements"])
        if ref != "DA1"
    )
    assert len(refs) == 22
    for i, ref in enumerate(refs):
        x = second_x if i == 1 else 20.0 * i
        group = ET.SubElement(root, f"{gate.SVG}g", {
            "data-layer": "symbols", "data-reference": ref,
            "stroke-width": "0.3",
        })
        ET.SubElement(group, f"{gate.SVG}line", {
            "x1": str(x), "y1": "0", "x2": str(x), "y2": "10",
        })
    ic = ET.SubElement(root, f"{gate.SVG}g", {
        "data-owner": "DA1",
        "data-ink-source": "real-native-PAINT-original-16leads",
    })
    stroke = ET.SubElement(ic, f"{gate.SVG}g", {
        "stroke-width": "0.3", "data-layer": "ic-physical-pin-leads",
    })
    ET.SubElement(stroke, f"{gate.SVG}line", {
        "x1": "440", "y1": "0", "x2": "440", "y2": "10",
    })
    return root


@pytest.mark.parametrize(("distance", "status", "gap_um"), [
    (2.299, "BLOCKED_CONSERVATIVE_AABB_NOT_EXACT_INK", 1999),
    (2.3, "PASS_CONSERVATIVE_2MM_23_UGO_PARTIAL_SOURCE_PRINT", 2000),
    (2.301, "PASS_CONSERVATIVE_2MM_23_UGO_PARTIAL_SOURCE_PRINT", 2001),
])
def test_true_two_mm_distinct_ugo_stroke_edge_threshold(
    distance, status, gap_um
):
    check = gate.distinct_ugo_2mm_envelopes(
        _realistic_23_ugo_group_fixture(distance)
    )
    assert check["actual_distinct_symbol_count"] == 23
    assert check["all_distinct_symbol_pairs"] == 253
    assert check["minimum_conservative_ink_gap_um"] == gap_um
    assert check["verdict"] == status
    assert check["minimum_pair"] == ["C1", "C2"] or len(
        check["minimum_pair"]
    ) == 2


def test_2mm_ugo_envelope_excludes_unproved_text_and_rejects_missing_ic():
    root = _realistic_23_ugo_group_fixture()
    original = gate.distinct_ugo_2mm_envelopes(root)
    assert original["minimum_conservative_ink_gap_um"] > 2000
    ic = next(g for g in root if g.get("data-owner") == "DA1")
    root.remove(ic)
    with pytest.raises(gate.EvidenceError, match="UGO_PHYSICAL_DA1_REQUIRED"):
        gate.distinct_ugo_2mm_envelopes(root)


@pytest.mark.parametrize(("primitive", "properties", "reason"), [
    ("path", {"d": "M 0 0 L 10 10"}, "UGO_ARC_PATH_NOT_SIMPLE_SOURCE_ARC"),
    ("rect", {"x": "0", "y": "0", "width": "-1", "height": "2"},
     "UGO_RECT_NONPOSITIVE_SIZE"),
    ("circle", {"cx": "0", "cy": "0", "r": "-2"},
     "UGO_CIRCLE_NONPOSITIVE_RADIUS"),
    ("line", {"x1": "NaN", "y1": "0", "x2": "10", "y2": "0"},
     "UGO_PRIMITIVE_NONFINITE_GEOMETRY"),
])
def test_unknown_ugo_shape_and_unphysical_primitive_fail_closed(
    primitive, properties, reason
):
    group = ET.Element(f"{gate.SVG}g", {"stroke-width": "0.3"})
    ET.SubElement(group, f"{gate.SVG}{primitive}", properties)
    with pytest.raises(gate.EvidenceError, match=reason):
        gate._conservative_ugo_envelope(group)


def test_true_source_ferro_inductor_arc_ink_envelope_is_conservative():
    group = ET.Element(f"{gate.SVG}g", {"stroke-width": "0.3"})
    ET.SubElement(group, f"{gate.SVG}path", {
        "d": "M 70 35 A 2 2 0 0 1 74 35",
    })
    assert gate._conservative_ugo_envelope(group) == (
        67850, 32850, 76150, 37150
    )


@pytest.mark.parametrize("d", [
    "M 70 35 A 2 3 0 0 1 74 35",
    "M 70 35 A 2 2 30 0 1 74 35",
])
def test_non_pinned_rotated_or_elliptic_svg_arc_cannot_fake_2mm_pass(d):
    group = ET.Element(f"{gate.SVG}g", {"stroke-width": "0.3"})
    ET.SubElement(group, f"{gate.SVG}path", {"d": d})
    with pytest.raises(gate.EvidenceError,
                       match="UGO_ARC_NONCIRCULAR_NOT_CALIBRATED"):
        gate._conservative_ugo_envelope(group)
