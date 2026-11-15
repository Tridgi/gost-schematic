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
