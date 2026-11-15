"""Strict SVG-only QA for ACTUAL PAINT native output, no Cairo dependency.

Executes the shared 24 malicious XML mutations against genuine owner-produced
diagnostic bytes. This gate can pass when 300-DPI raster generation is blocked
by the host environment; it NEVER grants PNG or full 15-Net print release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from qa_tl494_cycle11_native_300dpi import (
    SVG,
    adversarial_b_native_svg,
    assess_source_b_stub_ink,
    demand,
    validate_real_b_native_layer,
)

ORIGINAL = "e695c415fdced164b0e0c39c5249d030795a0aa6"
FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"


def inspect_source_svg_only(directory: Path, witness_file: Path) -> dict:
    """Verify physical provenance of TWO native b strokes in both real SVGs."""
    witness = json.loads(witness_file.read_text(encoding="utf-8"))
    manifest = json.loads(
        (directory / "TL494_COMPACT_A3_NEW_ROUTER_DRC_MANIFEST.json")
        .read_text(encoding="utf-8")
    )
    demand(
        witness.get("immutable_original_commit") == ORIGINAL
        and witness.get("GOST_A_font_SHA256") == FONT_SHA
        and manifest.get("model_source") == ORIGINAL
        and (
            manifest.get("source_components"),
            manifest.get("source_nets"),
            manifest.get("source_net_pinrefs"),
            manifest.get("manufacturer_DA1_physical_pin_count"),
        ) == (23, 15, 62, 16),
        "QA_C14_SVG_SOURCE_AUTHORITY_OR_TYPE_A_MISSING",
    )
    nets = witness.get("true_original_nets")
    demand(
        isinstance(nets, dict) and len(nets) == 15
        and sum(len(v) for v in nets.values()) == 62
        and len({pin for members in nets.values() for pin in members}) == 62
        and nets.get("b_NEGATIVE_OUTPUT") == ["FU1.2", "X2.1", "R5.2"],
        "QA_C14_SVG_SOURCE_NET_MEMBERSHIPS_CHANGED",
    )
    pins = witness.get("signed_DA1_pin_contacts")
    demand(
        isinstance(pins, list) and len(pins) == 16
        and {item.get("number") for item in pins} ==
        {str(index) for index in range(1, 17)}
        and len({tuple(item["physical_um"]) for item in pins}) == 16,
        "QA_C14_SVG_SOURCE_IC_CONTACTS_CHANGED",
    )
    anchors = witness.get("source_b_marker_um")
    demand(isinstance(anchors, dict) and set(anchors) == {"b-X2", "b-R5"},
           "QA_C14_B_MARKER_SOURCE_MISSING")
    strokes = witness.get("source_b_stubs_um")
    demand(
        isinstance(strokes, dict) and set(strokes) == {"X2.1", "R5.2"}
        and strokes["X2.1"]["end"] == anchors["b-X2"]
        and strokes["R5.2"]["end"] == anchors["b-R5"],
        "QA_C14_B_PINREF_TO_MARKER_SOURCE_DRIFT",
    )
    full_route = manifest.get("router_attempt", {})
    completed = sum(tree.get("complete") is True
                    for tree in full_route.get("net_trees", ()))
    demand(completed < 15 and manifest.get("real_print_release") is False
           and manifest.get("printable_candidate") is False,
           "QA_C14_PARTIAL_ROUTE_FABRICATED_FULL_PRINT")
    demand(len(full_route.get("net_trees", ())) == 15 and
           completed == full_route.get("routed_net_count"),
           "QA_C14_MISSING_15_NET_TREE_PARTIAL_EVIDENCE")
    views = {}
    original_hashes = {}
    for mode in ("clean", "diagnostic"):
        path = directory / f"TL494_COMPACT_A3_NEW_ROUTE_BLOCKED_{mode}.svg"
        blob = path.read_bytes()
        original_hashes[mode] = hashlib.sha256(blob).hexdigest()
        root = ET.fromstring(blob)
        demand(
            root.tag == SVG + "svg"
            and root.get("data-release") == "BLOCKED_INCOMPLETE_OR_PRINT_DRC"
            and root.get("data-source-components") == "23"
            and root.get("data-source-nets") == "15"
            and root.get("data-route-graph-sha256") ==
            manifest.get("graph_sha256"),
            "QA_C14_REAL_OWNER_BLOCKED_SVG_METADATA_DRIFT",
        )
        validate_real_b_native_layer(root, anchors, FONT_SHA, mode)
        demand(assess_source_b_stub_ink(root, witness) ==
               "PASS_TWO_SOURCE_SIGNED_NONPHYSICAL_STROKES",
               "QA_C14_REAL_OWNER_TWO_PHYSICAL_STROKES_NOT_RENDERED")
        external = root.findall(f".//{SVG}line[@data-layer='wires']")
        leads = root.findall(
            f".//{SVG}g[@data-layer='ic-physical-pin-leads']/{SVG}line"
        )
        targets = root.findall(
            f".//{SVG}g[@data-layer='editor-connection-targets']/{SVG}rect"
        )
        demand(len(external) == manifest.get("route_segments") and
               len(leads) == 16 and
               len(targets) == (16 if mode == "diagnostic" else 0),
               "QA_C14_WIRES_IC_OR_EDITOR_TARGET_COUNT_CHANGED")
        views[mode] = {
            "svg_sha256": original_hashes[mode],
            "source_signed_b_strokes": 2,
            "manufacturer_real_16": len(leads),
            "physical_route_wires": len(external),
            "green_editor_targets": len(targets),
            "whole_sheet_release": "BLOCKED",
        }
    negatives = adversarial_b_native_svg(directory, anchors, FONT_SHA, witness)
    demand(len(negatives) == 24,
           "QA_C14_24_HOSTILE_REAL_SVG_TESTS_NOT_ALL_EXECUTED")
    for mode in ("clean", "diagnostic"):
        path = directory / f"TL494_COMPACT_A3_NEW_ROUTE_BLOCKED_{mode}.svg"
        demand(hashlib.sha256(path.read_bytes()).hexdigest() ==
               original_hashes[mode],
               "QA_C14_ORIGINAL_OWNER_SVG_BYTES_MUTATED")
    return {
        "status": "PASS_REAL_SOURCE_SVG_B_STROKES_ONLY",
        "source": ORIGINAL,
        "type_a_font_sha256": FONT_SHA,
        "original_Nets": 15,
        "physical_PinRefs": 62,
        "real_DA1_pin_count": 16,
        "source_b_members": nets["b_NEGATIVE_OUTPUT"],
        "original_nonphysical_stubs": strokes,
        "completed_route_trees": completed,
        "views": views,
        "twenty_four_real_xml_hostile_mutants": negatives,
        "PNG_300DPI": "NOT_CHECKED_BY_SVG_ONLY_GATE",
        "full_15_net_print_release": "NO_GO_PARTIAL_ROUTE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--source-b-witness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = inspect_source_svg_only(args.source_dir, args.source_b_witness)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n", encoding="utf-8",
    )
    print("QA_C14_ACTUAL_OWNER_B_SVG", json.dumps({
        "status": evidence["status"],
        "routed": evidence["completed_route_trees"],
        "strokes": sum(v["source_signed_b_strokes"]
                       for v in evidence["views"].values()),
        "negative_rejections": len(evidence["twenty_four_real_xml_hostile_mutants"]),
        "full_print": evidence["full_15_net_print_release"],
    }))


if __name__ == "__main__":
    main()
