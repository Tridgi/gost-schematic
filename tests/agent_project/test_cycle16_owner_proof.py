"""Cycle16 actual-format C15 proof consumer: synthetic adversarial tests ONLY.

These generated SVGs are test fixtures, NOT user-printable owner outputs.
A separate production invocation must consume the real RECON C15 manifest.
"""
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from importlib.resources import files

import pytest

from examples.agent_tl494_cycle11_pipeline import _request
from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.agent_project.cycle16_owner_proof import review_c15_owner_proof
from gost_schematic.agent_project.owner_source_contract import (
    RECON_DISPLAY_RENAMES,
    verify_frozen_owner_fixture,
)

_SVG = "http://www.w3.org/2000/svg"
_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"
_FONT = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
_B = {
    "b-X2": {
        "physical_PinRef": "X2.1", "start_um": [1000, 2000],
        "end_um": [1000, 3000], "electrical": False,
    },
    "b-R5": {
        "physical_PinRef": "R5.2", "start_um": [4000, 5000],
        "end_um": [5000, 5000], "electrical": False,
    },
}


def _request_from_original():
    source = verify_frozen_owner_fixture(
        files("gost_schematic").joinpath(
            "agent_project", "data", "tl494_ic97_frozen_source.json",
        ).read_bytes(), CatalogResolver(),
    )
    return _request(source)


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _xml(diagnostic, real_net_name):
    root = ET.Element(f"{{{_SVG}}}svg", {
        "data-original-source-names-restored-in-manifest": "true",
        "data-source-physical-pinrefs": "62",
        "data-source-electrical-net-count": "15",
        "data-release": "BLOCKED_PARTIAL",
    })
    leads = ET.SubElement(root, f"{{{_SVG}}}g", {
        "data-layer": "ic-physical-pin-leads",
    })
    for pin in range(1, 17):
        ET.SubElement(leads, f"{{{_SVG}}}line", {
            "data-pin-ref": f"DA1.{pin}",
        })
    for label, stub in _B.items():
        ET.SubElement(root, f"{{{_SVG}}}line", {
            "data-layer": "nonphysical-continuation-stub",
            "data-nonphysical-net-continuation": label,
            "data-source-pin-ref": stub["physical_PinRef"],
            "data-nonphysical": "true", "data-electrical-junction": "false",
            "data-connectable": "false",
            "x1": str(stub["start_um"][0] / 1000),
            "y1": str(stub["start_um"][1] / 1000),
            "x2": str(stub["end_um"][0] / 1000),
            "y2": str(stub["end_um"][1] / 1000),
        })
    for i in range(41):
        ET.SubElement(root, f"{{{_SVG}}}line", {
            "data-layer": "wires",
            "data-net": real_net_name, "data-wire-index": str(i),
            "x1": str(i + 5), "x2": str(i + 6), "y1": "30", "y2": "30",
        })
    if diagnostic:
        layer = ET.SubElement(root, f"{{{_SVG}}}g", {
            "data-layer": "editor-connection-targets",
        })
        for pin in range(1, 17):
            ET.SubElement(layer, f"{{{_SVG}}}rect", {
                "data-pin-ref": f"DA1.{pin}", "fill": "#148645",
            })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _make_owner(tmp_path, completed=9):
    """Synthetic actual-shape C15 proof, never submitted as real owner evidence."""
    request = _request_from_original()
    nets = {
        row["name"]: [
            f'{p["reference"]}.{p["number"]}' for p in row["members"]
        ] for row in request["nets"]
    }
    progress = {}
    trees = []
    for i, (name, pins) in enumerate(nets.items()):
        complete = i < completed
        connected = pins[:] if complete else pins[:1]
        progress[name] = {
            "source_pinrefs": pins, "connected_pinrefs": connected,
            "complete": complete, "diagnostics": [] if complete else ["SEARCH_BLOCKED"],
            "segments": [],
        }
        trees.append({
            "net": RECON_DISPLAY_RENAMES.get(name, name),
            "pin_refs": pins, "connected_pin_refs": connected, "complete": complete,
        })
    native = {
        "source_sha": _SHA, "source_components": 23, "source_nets": 15,
        "all_Circuit_PinRef_memberships": 62, "physical_DA1_pin_count": 16,
        "routed_nets": completed, "routed_segments": 41,
        "actual_new_drc_errors": [], "routing": {"net_trees": trees},
        "net_members": {
            RECON_DISPLAY_RENAMES.get(k, k): v for k, v in nets.items()
        },
    }
    _write_json(tmp_path / "native" / "TL494-compact-A3-route-drc.json", native)
    for name, diagnostic in (
        ("TL494-A3-clean-source-b.svg", False),
        ("TL494-A3-diagnostic-source-b.svg", True),
    ):
        (tmp_path / name).write_bytes(_xml(diagnostic, next(iter(nets))))
    artifact_files = {
        "TL494-A3-clean-source-b.svg":
            tmp_path / "TL494-A3-clean-source-b.svg",
        "TL494-A3-diagnostic-source-b.svg":
            tmp_path / "TL494-A3-diagnostic-source-b.svg",
        "TL494-compact-A3-route-drc.json":
            tmp_path / "native" / "TL494-compact-A3-route-drc.json",
    }
    proof = {
        "schema": "GOST_TL494_CYCLE15_ONE_COMMAND_SOURCE_LOCKED_DELIVERY_V1",
        "source_sha": _SHA,
        "owner_exact_shas": {
            "ELEKTRIK_NET_PR114": "a" * 40, "RECON_PR115": "b" * 40,
            "PAINT_PR93": "c" * 40, "ELEKTRIK_IC_PR97": "d" * 40,
        },
        "source_font_sha256": _FONT, "source_23_components": 23,
        "source_15_literal_names": list(nets),
        "source_62_physical_pinrefs": nets, "source_16_signed_DA1": 16,
        "source_b_nonphysical": copy.deepcopy(_B),
        "paper": {"true_b_source_stubs": copy.deepcopy(_B)},
        "native_ugo_bbox_um": [0, 0, 500, 500],
        "route_config": {
            "format": "A3", "component_moves_mm": [["C1", "0", "2.5"]],
            "node_cap": 4000,
        },
        "original_named_net_route_progress": progress,
        "completed_original_nets": completed, "required_original_nets": 15,
        "routed_native_segments": 41, "routed_native_drc_errors": 0,
        "native_paper_frame_errors": [],
        "artifacts": {
            key: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for key, path in artifact_files.items()
        },
        "full_SVG_PNG300_release": "BLOCKED_UNTIL_15_15_GLOBAL_DRC_QA",
        "source_photo_pixel_parity": "NOT_VERIFIED",
        "main_or_integration_merge": False,
    }
    _write_json(tmp_path / "C15_REAL_TL494_DELIVERY.json", proof)
    return request, proof


def test_no_external_owner_proof_remains_honestly_blocked():
    result = review_c15_owner_proof(_request_from_original(), None)
    assert result["status"] == "BLOCKED_NO_OWNER_C15_PROOF"
    assert result["source_snapshot"]["physical_pinrefs"] == 62
    assert result["print_ready"] is False
    assert result["mcp_write_tools_enabled"] is False


def test_true_format_partial_proof_is_rechecked_and_blocked(tmp_path):
    request, _ = _make_owner(tmp_path)
    result = review_c15_owner_proof(request, tmp_path)
    assert result["status"] == "BLOCKED_PARTIAL"
    assert result["routed_nets"] == 9
    assert result["route_candidate"]["source_original_named_net_count"] == 15
    assert result["route_candidate"]["physical_pinrefs_in_complete_trees"] > 0
    assert result["route_candidate"]["native_partial_drc_error_count"] == 0
    assert result["rendered_proof"]["full_png300_verified"] is False
    assert result["qa_gate"]["print_ready"] is False
    assert len(result["rendered_proof"]["owner_artifacts_with_verified_bytes"]) == 3
    assert result["read_only"] and result["mutated"] is False


def test_external_full_15_of_15_still_requires_independent_qa(tmp_path):
    request, _ = _make_owner(tmp_path, completed=15)
    result = review_c15_owner_proof(request, tmp_path)
    assert result["routed_nets"] == 15
    assert result["status"] == "BLOCKED_INDEPENDENT_QA"
    assert result["print_ready"] is False
    assert result["qa_gate"]["global_post_render_3_2_1mm_checked"] is False


@pytest.mark.parametrize("mutation,code", [
    ("net_extra", "C16_C15_SOURCE_MEMBERSHIP_DRIFT"),
    ("net_removed", "C16_C15_SOURCE_MEMBERSHIP_DRIFT"),
    ("physical_member", "C16_C15_SOURCE_MEMBERSHIP_DRIFT"),
    ("manufacturer_missing", "C16_C15_SOURCE_MEMBERSHIP_DRIFT"),
    ("font_wrong", "C16_C15_PROOF_SPOOFED_RELEASE"),
    ("extra_pin_override_1um", "C16_C15_UNDECLARED_PROOF_FIELDS"),
    ("green_claim", "C16_C15_PROOF_SPOOFED_RELEASE"),
    ("fake_15_count", "C16_C15_ROUTE_COUNTS_CONTRADICT"),
    ("forged_tree_pin", "C16_C15_PINREF_MEMBERSHIP_DRIFT"),
    ("fake_dummy", "C16_C15_NET_INVENTORY_DRIFT"),
    ("dummy_component", "C16_C15_MOVED_FOREIGN_PART"),
    ("1um_component_shift", "C16_C15_MOVEMENT_PRECISION_VIOLATION"),
    ("path_traversal", "C16_C15_ARTIFACT_SET_INVALID"),
    ("file_sha_tamper", "C16_ARTIFACT_CONTENT_SHA_MISMATCH"),
    ("missing_real_svg", "C16_PROOF_FILE_MISSING_OR_OVERSIZED"),
    ("native_alias_rebind", "C16_C15_NATIVE_NETS_REBOUND"),
])
def test_c16_untrusted_owner_negative_cases(tmp_path, mutation, code):
    request, proof = _make_owner(tmp_path)
    if mutation == "net_extra":
        proof["source_62_physical_pinrefs"]["PHANTOM"] = ["X1.99"]
    elif mutation == "net_removed":
        del proof["source_62_physical_pinrefs"][next(iter(proof["source_62_physical_pinrefs"]))]
    elif mutation == "physical_member":
        name = next(iter(proof["source_62_physical_pinrefs"]))
        proof["source_62_physical_pinrefs"][name][0] = "DA1.13.001"
    elif mutation == "manufacturer_missing":
        proof["source_16_signed_DA1"] = 15
    elif mutation == "extra_pin_override_1um":
        proof["native_da1_override_um"] = {"DA1.13": [125001, 146250]}
    elif mutation == "font_wrong":
        proof["source_font_sha256"] = "a" * 64
    elif mutation == "green_claim":
        proof["full_SVG_PNG300_release"] = "PRINT_APPROVED"
    elif mutation == "fake_15_count":
        proof["completed_original_nets"] = 15
    elif mutation == "forged_tree_pin":
        name = next(iter(proof["original_named_net_route_progress"]))
        proof["original_named_net_route_progress"][name]["source_pinrefs"][0] = "FAKE.1"
    elif mutation == "fake_dummy":
        proof["original_named_net_route_progress"]["$d_0"] = {
            "source_pinrefs": [], "complete": True,
        }
    elif mutation == "dummy_component":
        proof["route_config"]["component_moves_mm"] = [["$d_0", "0", "2.5"]]
    elif mutation == "1um_component_shift":
        proof["route_config"]["component_moves_mm"] = [["DA1", "0.001", "0"]]
    elif mutation == "path_traversal":
        proof["artifacts"]["../../evil.svg"] = {"sha256": "a" * 64}
    elif mutation == "file_sha_tamper":
        path = tmp_path / "TL494-A3-clean-source-b.svg"
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "missing_real_svg":
        (tmp_path / "TL494-A3-clean-source-b.svg").unlink()
    elif mutation == "native_alias_rebind":
        path = tmp_path / "native" / "TL494-compact-A3-route-drc.json"
        native = json.loads(path.read_text())
        native["net_members"]["PHANTOM"] = ["X1.99"]
        _write_json(path, native)
        proof["artifacts"][path.name]["sha256"] = hashlib.sha256(
            path.read_bytes(),
        ).hexdigest()
    _write_json(tmp_path / "C15_REAL_TL494_DELIVERY.json", proof)
    with pytest.raises(ProjectError) as caught:
        review_c15_owner_proof(request, tmp_path)
    assert caught.value.code == code


def test_native_clean_svg_rejects_diagnostic_editor_marks(tmp_path):
    request, proof = _make_owner(tmp_path)
    path = tmp_path / "TL494-A3-clean-source-b.svg"
    path.write_bytes(_xml(diagnostic=True, real_net_name=request["nets"][0]["name"]))
    proof["artifacts"][path.name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write_json(tmp_path / "C15_REAL_TL494_DELIVERY.json", proof)
    with pytest.raises(ProjectError, match="C16_CLEAN_SVG_EDITOR_MARKERS"):
        review_c15_owner_proof(request, tmp_path)


def test_native_diagnostic_rejects_fake_da1_contact(tmp_path):
    request, proof = _make_owner(tmp_path)
    path = tmp_path / "TL494-A3-diagnostic-source-b.svg"
    raw = path.read_bytes().replace(b'DA1.16', b'DA1.99')
    path.write_bytes(raw)
    proof["artifacts"][path.name]["sha256"] = hashlib.sha256(raw).hexdigest()
    _write_json(tmp_path / "C15_REAL_TL494_DELIVERY.json", proof)
    with pytest.raises(ProjectError, match="C16_DIAGNOSTIC_DA1_TARGETS_FORGED"):
        review_c15_owner_proof(request, tmp_path)


def test_symlink_to_external_evidence_is_rejected(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    request, _ = _make_owner(target)
    link = tmp_path / "redirect"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("OS forbids user-created symbolic links")
    with pytest.raises(ProjectError, match="C16_PATH_REDIRECT_FORBIDDEN"):
        review_c15_owner_proof(request, link)


def test_forged_or_missing_source_pin_rejected_even_with_valid_owner_files(tmp_path):
    request, _ = _make_owner(tmp_path)
    wrong = copy.deepcopy(request)
    wrong["nets"][0]["members"][0]["number"] = "1.001"
    with pytest.raises(ProjectError, match="C16_SOURCE_REQUEST_UNTRUSTED"):
        review_c15_owner_proof(wrong, tmp_path)


def test_real_b_stub_1um_change_must_fail_even_with_rehashed_svg(tmp_path):
    request, proof = _make_owner(tmp_path)
    name = "TL494-A3-clean-source-b.svg"
    path = tmp_path / name
    altered = path.read_bytes().replace(b'x1="1.0"', b'x1="1.001"')
    assert altered != path.read_bytes()
    path.write_bytes(altered)
    proof["artifacts"][name]["sha256"] = hashlib.sha256(altered).hexdigest()
    _write_json(tmp_path / "C15_REAL_TL494_DELIVERY.json", proof)
    with pytest.raises(ProjectError, match="C16_NATIVE_B_COORDINATE_1UM_DRIFT"):
        review_c15_owner_proof(request, tmp_path)


def test_b_stubs_cannot_become_electric_or_foreign(tmp_path):
    request, proof = _make_owner(tmp_path)
    proof["source_b_nonphysical"]["b-X2"]["electrical"] = True
    proof["paper"]["true_b_source_stubs"]["b-X2"]["electrical"] = True
    _write_json(tmp_path / "C15_REAL_TL494_DELIVERY.json", proof)
    with pytest.raises(ProjectError, match="C16_C15_B_STUB_PROVENANCE_INVALID"):
        review_c15_owner_proof(request, tmp_path)


def test_duplicated_json_field_in_external_owner_is_rejected(tmp_path):
    request, _ = _make_owner(tmp_path)
    path = tmp_path / "C15_REAL_TL494_DELIVERY.json"
    body = path.read_text(encoding="utf-8")
    assert body.startswith("{")
    path.write_text('{"schema": "FORGED", ' + body[1:], encoding="utf-8")
    with pytest.raises(ProjectError, match="C16_DUPLICATE_JSON_FIELD"):
        review_c15_owner_proof(request, tmp_path)


def test_forged_extra_wire_in_native_svg_is_rejected(tmp_path):
    request, proof = _make_owner(tmp_path)
    name = "TL494-A3-clean-source-b.svg"
    path = tmp_path / name
    tree = ET.fromstring(path.read_bytes())
    ET.SubElement(tree, f"{{{_SVG}}}line", {
        "data-layer": "wires", "data-net": request["nets"][0]["name"],
        "data-wire-index": "41", "x1": "40", "y1": "50",
        "x2": "50", "y2": "50",
    })
    path.write_bytes(ET.tostring(tree))
    proof["artifacts"][name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write_json(tmp_path / "C15_REAL_TL494_DELIVERY.json", proof)
    with pytest.raises(ProjectError, match="C16_SVG_ROUTE_WIRE_COUNT_DRIFT"):
        review_c15_owner_proof(request, tmp_path)


def test_diagnostic_and_clean_cannot_disagree_about_wire_geometry(tmp_path):
    request, proof = _make_owner(tmp_path)
    name = "TL494-A3-diagnostic-source-b.svg"
    path = tmp_path / name
    tree = ET.fromstring(path.read_bytes())
    first = tree.findall(f".//{{{_SVG}}}line[@data-layer='wires']")[0]
    first.set("x2", "6.001")
    path.write_bytes(ET.tostring(tree))
    proof["artifacts"][name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write_json(tmp_path / "C15_REAL_TL494_DELIVERY.json", proof)
    with pytest.raises(ProjectError, match="C16_SVG_CLEAN_DIAGNOSTIC_COPPER_DRIFT"):
        review_c15_owner_proof(request, tmp_path)
