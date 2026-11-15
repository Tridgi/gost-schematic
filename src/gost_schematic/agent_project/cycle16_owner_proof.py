"""Cycle16 read-only consumer of REAL RECON C15/NET/PAINT TL494 evidence.

External JSON/SVG, ELK layouts and source-independent routing output are
UNTRUSTED. This verifier never writes a Project/Circuit and never grants
print approval. It checks original frozen physical membership afresh, real
owner partial route records, artifact bytes and visible physical SVG marks.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .agent_readiness import review_request
from .catalog import ProjectError
from .design_assistant import TL494_FROZEN_SOURCE_SHA
from .owner_source_contract import RECON_DISPLAY_RENAMES

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SVG = "{http://www.w3.org/2000/svg}"
_FONT_SHA = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
_MAX_JSON = 4_000_000
_MAX_SVG = 12_000_000


def _reject(code: str) -> None:
    raise ProjectError(code, "Untrusted C15 owner evidence rejected")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_path(path: Path) -> Path:
    """No symlink/junction on the input chain; never resolve external file links."""
    if not path.is_absolute():
        path = Path.cwd() / path
    if any(
        part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction())
        for part in (path, *path.parents)
    ):
        _reject("C16_PATH_REDIRECT_FORBIDDEN")
    return path


def _bytes(path: Path, limit: int) -> bytes:
    path = _safe_path(path)
    if not path.is_file() or path.stat().st_size > limit:
        _reject("C16_PROOF_FILE_MISSING_OR_OVERSIZED")
    return path.read_bytes()


def _unique_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out = {}
    for name, value in items:
        if name in out:
            _reject("C16_DUPLICATE_JSON_FIELD")
        out[name] = value
    return out


def _json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_pairs,
            parse_constant=lambda _: _reject("C16_NONFINITE_JSON"),
        )
    except ProjectError:
        raise
    except (UnicodeError, ValueError) as error:
        raise ProjectError("C16_INVALID_JSON", "Invalid owner JSON document") from error
    if type(value) is not dict:
        _reject("C16_INVALID_JSON_ROOT")
    return value


def _exact_sha(value: Any, length: int = 64) -> bool:
    return type(value) is str and bool((_HEX64 if length == 64 else _HEX40).fullmatch(value))


def _canonical_source(source_request: dict[str, Any]) -> dict[str, list[str]]:
    if type(source_request) is not dict:
        _reject("C16_SOURCE_REQUEST_UNTRUSTED")
    try:
        checked = review_request(source_request)
    except (ProjectError, KeyError, TypeError) as error:
        raise ProjectError("C16_SOURCE_REQUEST_UNTRUSTED", "Frozen source mismatch") from error
    if (
        checked["status"] != "BLOCKED_SOURCE_NOT_IMPORTABLE"
        or source_request["source_sha"] != TL494_FROZEN_SOURCE_SHA
        or checked["component_count"] != 23
        or checked["net_count"] != 15
        or checked["submitted_pinref_count"] != 62
    ):
        _reject("C16_SOURCE_REQUEST_UNTRUSTED")
    expected = {}
    for net in source_request["nets"]:
        pins = [f'{pin["reference"]}.{pin["number"]}' for pin in net["members"]]
        expected[net["name"]] = pins
    if len(expected) != 15 or sum(map(len, expected.values())) != 62:
        _reject("C16_SOURCE_REQUEST_UNTRUSTED")
    return expected


def _svg_checks(
    raw: bytes, *, diagnostic: bool, b_stubs_expected: dict[str, Any],
    source_net_names: frozenset[str], expected_wire_count: int,
) -> dict[str, Any]:
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        _reject("C16_EXTERNAL_XML_ENTITIES_FORBIDDEN")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ProjectError("C16_INVALID_NATIVE_SVG", "Unreadable source SVG") from error
    if root.tag != f"{_SVG}svg":
        _reject("C16_NOT_NATIVE_SVG")
    if any(x.tag in (f"{_SVG}script", f"{_SVG}foreignObject") for x in root.iter()):
        _reject("C16_ACTIVE_SVG_CONTENT_FORBIDDEN")
    if (
        root.get("data-original-source-names-restored-in-manifest") != "true"
        or root.get("data-source-physical-pinrefs") != "62"
        or root.get("data-source-electrical-net-count") != "15"
    ):
        _reject("C16_NATIVE_SVG_SOURCE_DRIFT")
    b_stubs = root.findall(f".//{_SVG}line[@data-layer='nonphysical-continuation-stub']")
    leads = root.findall(
        f".//{_SVG}g[@data-layer='ic-physical-pin-leads']/{_SVG}line"
    )
    if len(b_stubs) != 2 or len(leads) != 16:
        _reject("C16_NATIVE_SVG_PHYSICAL_GRAPHICS_DRIFT")
    by_id = {
        x.get("data-nonphysical-net-continuation"): x for x in b_stubs
    }
    if len(by_id) != 2 or set(by_id) != set(b_stubs_expected):
        _reject("C16_NATIVE_B_IDS_DRIFT")
    for name, stroke in by_id.items():
        original = b_stubs_expected[name]
        if (
            stroke.get("data-source-pin-ref") != original["physical_PinRef"]
            or stroke.get("data-nonphysical") != "true"
            or stroke.get("data-electrical-junction") != "false"
            or stroke.get("data-connectable") != "false"
        ):
            _reject("C16_NATIVE_B_ELECTRICALLY_FORGED")
        for field, value in zip(
            ("x1", "y1", "x2", "y2"),
            (*original["start_um"], *original["end_um"]), strict=True,
        ):
            try:
                parsed = Decimal(stroke.get(field, "")) * 1000
            except InvalidOperation as error:
                raise ProjectError(
                    "C16_NATIVE_B_COORDINATE_INVALID", "Invalid b SVG coordinate",
                ) from error
            if not parsed.is_finite() or parsed != value:
                _reject("C16_NATIVE_B_COORDINATE_1UM_DRIFT")
    # The *actual* native route lines must be the same on clean and debug.
    # Strict source Net identity and explicit wire indices prevent a visual
    # extra electrical wire from being disguised as an accepted owner route.
    wires = root.findall(f".//{_SVG}line[@data-layer='wires']")
    if len(wires) != expected_wire_count:
        _reject("C16_SVG_ROUTE_WIRE_COUNT_DRIFT")
    wire_signature = []
    for index, wire in enumerate(wires):
        if (
            wire.get("data-net") not in source_net_names
            or wire.get("data-wire-index") != str(index)
        ):
            _reject("C16_SVG_ROUTE_WIRE_NET_OR_ID_DRIFT")
        coords = []
        for field in ("x1", "y1", "x2", "y2"):
            try:
                coord = Decimal(wire.get(field, "")) * 1000
            except InvalidOperation as error:
                raise ProjectError(
                    "C16_SVG_ROUTE_COORDINATE_INVALID", "Malformed wire geometry",
                ) from error
            if not coord.is_finite() or coord != coord.to_integral_value():
                _reject("C16_SVG_ROUTE_1UM_COORDINATE_DRIFT")
            coords.append(int(coord))
        if coords[:2] == coords[2:] or (
            coords[0] != coords[2] and coords[1] != coords[3]
        ):
            _reject("C16_SVG_ROUTE_NONORTHOGONAL")
        wire_signature.append([wire.get("data-net"), *coords])
    targets = root.findall(f".//{_SVG}g[@data-layer='editor-connection-targets']")
    if diagnostic:
        if len(targets) != 1:
            _reject("C16_DIAGNOSTIC_DA1_TARGETS_MISSING")
        markers = list(targets[0])
        if (
            len(markers) != 16
            or any(x.tag != f"{_SVG}rect" for x in markers)
            or {x.get("data-pin-ref") for x in markers}
            != {f"DA1.{i}" for i in range(1, 17)}
            or any(x.get("fill") != "#148645" for x in markers)
        ):
            _reject("C16_DIAGNOSTIC_DA1_TARGETS_FORGED")
    elif targets or any(
        node.get("fill") == "#148645" for node in root.iter()
    ):
        _reject("C16_CLEAN_SVG_EDITOR_MARKERS")
    return {
        "native_da1_leads": 16,
        "non_electrical_b_strokes": 2,
        "editor_markers": 16 if diagnostic else 0,
        "wire_signature": wire_signature,
        "xml_parsed": True,
    }


def review_c15_owner_proof(
    source_request: dict[str, Any], candidate_directory: Path | None,
) -> dict[str, Any]:
    """Inspect a real external RECON C15 folder, without importing owner code.

    No external manifest can promote itself to trusted electrical model or
    QA-approved print. Even a purported 15/15 remains BLOCKED_QA_UNVERIFIED.
    """
    source_nets = _canonical_source(source_request)
    source = {
        "source_git_sha": TL494_FROZEN_SOURCE_SHA,
        "components": 23, "original_nets": 15,
        "physical_pinrefs": 62, "da1_physical_pins": 16,
        "original_named_memberships": source_nets,
        "non_electrical_b_count": 2,
    }
    common = {
        "schema_version": 1,
        "contract": "tl494.c16.c15_owner_proof_consumer.read_only.v1",
        "source_snapshot": source,
        "read_only": True, "mutated": False,
        "mcp_write_tools_enabled": False, "print_ready": False,
        "independent_qa_performed": False,
        "source_original_negative_drc": {"errors": 9, "warnings": 32},
    }
    if candidate_directory is None:
        return {
            **common, "status": "BLOCKED_NO_OWNER_C15_PROOF",
            "routed_nets": 0,
            "reason_codes": ["C15_OWNER_MANIFEST_NOT_PROVIDED"],
            "native_route_executed_here": False,
            "native_paint_executed_here": False,
        }
    folder = _safe_path(candidate_directory)
    if not folder.is_dir():
        _reject("C16_OWNER_DIRECTORY_MISSING")
    manifest_bytes = _bytes(folder / "C15_REAL_TL494_DELIVERY.json", _MAX_JSON)
    proof = _json(manifest_bytes)
    if proof.get("schema") != "GOST_TL494_CYCLE15_ONE_COMMAND_SOURCE_LOCKED_DELIVERY_V1":
        _reject("C16_NOT_REAL_C15_PROOF")
    # This exactly matches the published RECON C15 producer contract. Reject
    # silent 1um pin override, extra electrical dummy Net and forged QA fields.
    if set(proof) != {
        "schema", "source_sha", "owner_exact_shas", "source_font_sha256",
        "source_23_components", "source_15_literal_names",
        "source_62_physical_pinrefs", "source_16_signed_DA1",
        "source_b_nonphysical", "paper", "native_ugo_bbox_um",
        "route_config", "original_named_net_route_progress",
        "completed_original_nets", "required_original_nets",
        "routed_native_segments", "routed_native_drc_errors",
        "native_paper_frame_errors", "artifacts",
        "full_SVG_PNG300_release", "source_photo_pixel_parity",
        "main_or_integration_merge",
    }:
        _reject("C16_C15_UNDECLARED_PROOF_FIELDS")
    if (
        proof.get("source_sha") != TL494_FROZEN_SOURCE_SHA
        or type(proof.get("source_23_components")) is not int
        or proof["source_23_components"] != 23
        or type(proof.get("source_16_signed_DA1")) is not int
        or proof["source_16_signed_DA1"] != 16
        or type(proof.get("source_15_literal_names")) is not list
        or len(proof["source_15_literal_names"]) != 15
        or set(proof["source_15_literal_names"]) != set(source_nets)
        or type(proof.get("source_62_physical_pinrefs")) is not dict
        or set(proof["source_62_physical_pinrefs"]) != set(source_nets)
        or any(
            type(proof["source_62_physical_pinrefs"][n]) is not list
            or len(proof["source_62_physical_pinrefs"][n]) != len(pins)
            or set(proof["source_62_physical_pinrefs"][n]) != set(pins)
            for n, pins in source_nets.items()
        )
    ):
        _reject("C16_C15_SOURCE_MEMBERSHIP_DRIFT")
    if (
        not _exact_sha(proof.get("source_font_sha256"))
        or proof["source_font_sha256"] != _FONT_SHA
        or type(proof.get("source_b_nonphysical")) is not dict
        or set(proof["source_b_nonphysical"]) != {"b-X2", "b-R5"}
        or proof.get("main_or_integration_merge") is not False
        or proof.get("full_SVG_PNG300_release")
        != "BLOCKED_UNTIL_15_15_GLOBAL_DRC_QA"
    ):
        _reject("C16_C15_PROOF_SPOOFED_RELEASE")
    for ident, pin in (("b-X2", "X2.1"), ("b-R5", "R5.2")):
        stub = proof["source_b_nonphysical"][ident]
        if (
            type(stub) is not dict
            or set(stub) != {
                "physical_PinRef", "start_um", "end_um", "electrical",
            }
            or stub["physical_PinRef"] != pin
            or stub["electrical"] is not False
            or any(
                type(at) is not list or len(at) != 2
                or any(type(coord) is not int for coord in at)
                for at in (stub["start_um"], stub["end_um"])
            )
        ):
            _reject("C16_C15_B_STUB_PROVENANCE_INVALID")
    heads = proof.get("owner_exact_shas")
    if type(heads) is not dict or len(heads) < 3 or any(
        not _exact_sha(value, 40) for value in heads.values()
    ):
        _reject("C16_OWNER_SHA_PROVENANCE_INVALID")
    config = proof.get("route_config")
    if (
        type(config) is not dict
        or config.get("format") not in ("A3", "A2")
        or type(config.get("node_cap")) is not int
        or not 100 <= config["node_cap"] <= 100000
        or type(config.get("component_moves_mm")) is not list
    ):
        _reject("C16_C15_ROUTE_CONFIG_INVALID")
    paper = proof.get("paper")
    if (
        type(paper) is not dict
        or paper.get("true_b_source_stubs") != proof["source_b_nonphysical"]
    ):
        _reject("C16_C15_GRAPHIC_B_SOURCE_DRIFT")
    progress = proof.get("original_named_net_route_progress")
    if type(progress) is not dict or set(progress) != set(source_nets):
        _reject("C16_C15_NET_INVENTORY_DRIFT")
    completed = 0
    full_contacts = 0
    per_net = {}
    for name, pins in source_nets.items():
        item = progress[name]
        if (
            type(item) is not dict
            or type(item.get("source_pinrefs")) is not list
            or len(item["source_pinrefs"]) != len(pins)
            or set(item["source_pinrefs"]) != set(pins)
            or type(item.get("connected_pinrefs")) is not list
            or type(item.get("complete")) is not bool
            or not isinstance(item.get("diagnostics"), list)
        ):
            _reject("C16_C15_PINREF_MEMBERSHIP_DRIFT")
        connected = item["connected_pinrefs"]
        if len(connected) != len(set(connected)) or not set(connected) <= set(pins):
            _reject("C16_C15_CONNECTED_PINREF_FORGED")
        if item["complete"] and set(connected) != set(pins):
            _reject("C16_C15_FALSE_COMPLETE_NET")
        completed += item["complete"]
        full_contacts += len(connected) if item["complete"] else 0
        per_net[name] = {
            "complete": item["complete"],
            "source_members": len(pins),
            "connected_members": len(connected),
            "missing_pinrefs": sorted(set(pins) - set(connected)),
            "diagnostics": item["diagnostics"][:8],
        }
    if (
        type(proof.get("completed_original_nets")) is not int
        or proof["completed_original_nets"] != completed
        or proof.get("required_original_nets") != 15
        or type(proof.get("routed_native_segments")) is not int
        or proof["routed_native_segments"] < 0
        or type(proof.get("routed_native_drc_errors")) is not int
        or proof["routed_native_drc_errors"] < 0
    ):
        _reject("C16_C15_ROUTE_COUNTS_CONTRADICT")
    paper_name = config["format"]
    expected_files = (
        f"TL494-{paper_name}-clean-source-b.svg",
        f"TL494-{paper_name}-diagnostic-source-b.svg",
        f"TL494-compact-{paper_name}-route-drc.json",
    )
    artifacts = proof.get("artifacts")
    if type(artifacts) is not dict or set(artifacts) != set(expected_files):
        _reject("C16_C15_ARTIFACT_SET_INVALID")
    accepted_artifacts = {}
    for filename in expected_files:
        if (
            Path(filename).name != filename
            or "/" in filename or "\\" in filename
            or type(artifacts[filename]) is not dict
            or not _exact_sha(artifacts[filename].get("sha256"))
        ):
            _reject("C16_ARTIFACT_PATH_OR_HASH_INVALID")
        relative = (
            Path("native") / filename if filename.endswith(".json")
            else Path(filename)
        )
        raw_bytes = _bytes(folder / relative, _MAX_SVG)
        measured_sha = _sha256(raw_bytes)
        if measured_sha != artifacts[filename]["sha256"]:
            _reject("C16_ARTIFACT_CONTENT_SHA_MISMATCH")
        accepted_artifacts[filename] = {
            "sha256": measured_sha, "bytes": len(raw_bytes),
            "source": "OWNER_SUBMITTED_CONTENT_NOT_INDEPENDENT_QA",
        }
        if filename.endswith(".svg"):
            accepted_artifacts[filename].update(_svg_checks(
                raw_bytes, diagnostic=("diagnostic" in filename),
                b_stubs_expected=proof["source_b_nonphysical"],
                source_net_names=frozenset(source_nets),
                expected_wire_count=proof["routed_native_segments"],
            ))
    clean = accepted_artifacts[expected_files[0]]["wire_signature"]
    debug = accepted_artifacts[expected_files[1]]["wire_signature"]
    if clean != debug:
        _reject("C16_SVG_CLEAN_DIAGNOSTIC_COPPER_DRIFT")
    raw_route = _json(_bytes(
        folder / "native" / expected_files[-1], _MAX_JSON,
    ))
    if (
        raw_route.get("source_sha") != TL494_FROZEN_SOURCE_SHA
        or (raw_route.get("source_components"),
            raw_route.get("source_nets"),
            raw_route.get("all_Circuit_PinRef_memberships"),
            raw_route.get("physical_DA1_pin_count")) != (23, 15, 62, 16)
        or raw_route.get("routed_nets") != completed
        or raw_route.get("routed_segments") != proof["routed_native_segments"]
        or type(raw_route.get("actual_new_drc_errors")) is not list
        or len(raw_route["actual_new_drc_errors"]) != proof["routed_native_drc_errors"]
    ):
        _reject("C16_C15_NATIVE_ROUTE_REPORT_DRIFT")
    native_members = raw_route.get("net_members")
    if type(native_members) is not dict:
        _reject("C16_C15_NATIVE_NETS_MISSING")
    aliases = {RECON_DISPLAY_RENAMES.get(k, k): v for k, v in source_nets.items()}
    if len(aliases) != 15 or native_members != aliases:
        _reject("C16_C15_NATIVE_NETS_REBOUND")
    trees = raw_route.get("routing", {}).get("net_trees")
    if type(trees) is not list or len(trees) != 15:
        _reject("C16_C15_NATIVE_ROUTE_TREES_INVALID")
    by_alias = {t.get("net"): t for t in trees if type(t) is dict}
    if len(by_alias) != 15 or set(by_alias) != set(aliases):
        _reject("C16_C15_NATIVE_ROUTE_TREES_INVALID")
    for original, item in progress.items():
        alias = RECON_DISPLAY_RENAMES.get(original, original)
        tree = by_alias[alias]
        if (
            type(tree.get("pin_refs")) is not list
            or len(tree["pin_refs"]) != len(item["source_pinrefs"])
            or set(tree["pin_refs"]) != set(item["source_pinrefs"])
            or tree.get("connected_pin_refs") != item["connected_pinrefs"]
            or tree.get("complete") is not item["complete"]
        ):
            _reject("C16_C15_NATIVE_TREE_PROOF_MISMATCH")
    reason_codes = (
        ["INCOMPLETE_ORIGINAL_SOURCE_NETS", "GLOBAL_PRINT_QA_NOT_PERFORMED",
         "PNG300_NOT_PRESENT_IN_C15_OWNER_ARTIFACT_SET"]
        if completed < 15 else
        ["ROUTE_15_OF_15_OWNER_CLAIM_NOT_INDEPENDENTLY_APPROVED",
         "GLOBAL_PRINT_QA_NOT_PERFORMED",
         "PNG300_NOT_PRESENT_IN_C15_OWNER_ARTIFACT_SET"]
    )
    if proof["routed_native_drc_errors"]:
        reason_codes.append("NATIVE_ROUTE_DRC_ERRORS_PRESENT")
    return {
        **common,
        "status": ("BLOCKED_PARTIAL" if completed < 15
                   else "BLOCKED_INDEPENDENT_QA"),
        "source_owner_provenance": heads,
        "source_owner_commits_reverified_from_git_here": False,
        "candidate_manifest_sha256": _sha256(manifest_bytes),
        "placement_proposal": {
            "paper": paper_name,
            "component_moves_mm": config["component_moves_mm"],
            "producer_report_only_no_placement_authorization": True,
        },
        "route_candidate": {
            "source_original_named_net_count": 15,
            "completed_original_nets": completed,
            "physical_pinrefs_in_complete_trees": full_contacts,
            "native_segment_count": proof["routed_native_segments"],
            "native_partial_drc_error_count": proof["routed_native_drc_errors"],
            "native_drc_not_independent_final_print": True,
            "per_original_net": per_net,
        },
        "rendered_proof": {
            "source_font_sha256_reported": proof["source_font_sha256"],
            "font_bytes_independently_verified_here": False,
            "owner_artifacts_with_verified_bytes": accepted_artifacts,
            "full_png300_verified": False,
            "source_photo_parity_verified": False,
        },
        "qa_gate": {
            "status": "BLOCKED",
            "source_photo_validated": False,
            "global_post_render_3_2_1mm_checked": False,
            "all_15_real_nets_complete": completed == 15,
            "print_ready": False,
        },
        "routed_nets": completed,
        "reason_codes": reason_codes,
        "native_route_executed_here": False,
        "native_paint_executed_here": False,
    }
