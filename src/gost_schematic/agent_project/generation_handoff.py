"""Strict source-locked read-only handoff for future TL494 generator owners.

This is NOT an electrical editor or a route/print approval. It refuses any
mismatch to the independently bundled frozen source; downstream owners must
verify actual native route and printed sheet before producing success.
"""
import hashlib
import json
from typing import Any

from .agent_readiness import _OUTPUTS, review_request
from .catalog import CatalogResolver, ProjectError
from .design_assistant import TL494_FROZEN_SOURCE_SHA, TL494_REQUIRED_PARTS

_STAGE_ORDER = (
    "SOURCE_MODEL", "UGO_SELECTION", "PLACEMENT", "ROUTING",
    "ERC_DRC", "RENDER", "REPORT",
)
_HEX = frozenset("0123456789abcdef")


def _sha(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(char in _HEX for char in value)
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def build_readonly_tl494_handoff(
    request: dict[str, Any],
    cli_report: dict[str, Any],
    catalog_glyphs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Produce an immutable handoff description, never an auth/print success.

    Exact returned CLI bytes may be independently compared by its caller;
    the contract itself revalidates the submitted source, to reject a
    spoofed/mismatched report, and rechecks every selected catalogue SHA.
    """
    if type(request) is not dict or type(cli_report) is not dict:
        raise ProjectError("HANDOFF_SCHEMA_INVALID", "Typed request/report required")
    expected = review_request(request)
    if cli_report != expected or expected["status"] != "BLOCKED_SOURCE_NOT_IMPORTABLE":
        raise ProjectError("HANDOFF_REPORT_FORGED", "CLI result differs from frozen source")
    if request["source_sha"] != TL494_FROZEN_SOURCE_SHA:
        raise ProjectError("HANDOFF_SOURCE_MISMATCH", "Unexpected frozen source")
    if (type(request["outputs"]) is not list
            or len(request["outputs"]) != len(_OUTPUTS)
            or set(request["outputs"]) != set(_OUTPUTS)):
        raise ProjectError("HANDOFF_OUTPUTS_INCOMPLETE", "Six bounded outputs required")
    if type(catalog_glyphs) is not dict or (
        set(catalog_glyphs) != set(TL494_REQUIRED_PARTS.values())
    ):
        raise ProjectError("HANDOFF_CATALOG_INCOMPLETE", "Seven exact source UGO required")
    catalog = CatalogResolver()
    locked_glyphs = {}
    for part_id, image in sorted(catalog_glyphs.items()):
        if type(image) is not dict:
            raise ProjectError("HANDOFF_CATALOG_INVALID", "Invalid physical UGO evidence")
        lock = catalog.lock(part_id)
        if (image.get("part_sha256") != lock["part_sha256"]
                or image.get("symbol_sha256") != lock["symbol_sha256"]
                or image.get("normative_approval") is not False
                or not _sha(image.get("real_svg_sha256"))
                or not _sha(image.get("real_png_sha256"))):
            raise ProjectError("HANDOFF_CATALOG_INVALID", "Ungrounded UGO SHA or approval")
        locked_glyphs[part_id] = {
            "part_sha256": lock["part_sha256"],
            "symbol_sha256": lock["symbol_sha256"],
            "preview_svg_sha256": image["real_svg_sha256"],
            "preview_png_sha256": image["real_png_sha256"],
            "normative_status": "DRAFT",
        }
    members = sorted(
        (net["name"], pin["reference"], pin["number"])
        for net in request["nets"] for pin in net["members"]
    )
    if len(members) != 62 or len(set(members)) != 62:
        raise ProjectError("HANDOFF_SOURCE_MISMATCH", "Source physical PinRefs changed")
    chosen = {
        row["reference"]: row["part_id"]
        for row in request["components"] if row["part_id"] is not None
    }
    if chosen != TL494_REQUIRED_PARTS:
        raise ProjectError("HANDOFF_SOURCE_MISMATCH", "UGO choices not source verified")
    return {
        "schema_version": 1,
        "contract": "tl494.future_generator_handoff.read_only.v1",
        "status": "BLOCKED_GENERATOR_NOT_INTEGRATED",
        "source_git_sha": TL494_FROZEN_SOURCE_SHA,
        "source_typed_manifest_sha256": expected["frozen_source_typed_manifest_sha256"],
        "source_request_sha256": _digest(request),
        "source_physical_membership_sha256": _digest(members),
        "source_component_count": 23,
        "source_net_count": 15,
        "source_pinref_memberships": 62,
        "source_da1_pin_count": 16,
        "source_net_names": sorted(net["name"] for net in request["nets"]),
        "required_exact_ugo_refs": dict(sorted(chosen.items())),
        "locked_catalog_glyphs": locked_glyphs,
        "stages": [
            {
                "stage": name,
                "state": (
                    "SOURCE_VALIDATED_NOT_IMPORTED" if name == "SOURCE_MODEL"
                    else "CATALOG_SOURCE_LOCKED_DRAFT" if name == "UGO_SELECTION"
                    else "BLOCKED_NOT_EXECUTED"
                ),
                "verified_complete": False,
            }
            for name in _STAGE_ORDER
        ],
        "requested_outputs": list(_OUTPUTS),
        "stage_blocker_codes": list(expected["reasons"]),
        "source_netlist_user_approval": "USER_REVIEW_REQUIRED",
        "native_persisted_source_circuit_verified": False,
        "all_15_nets_routed": False,
        "global_print_drc_verified": False,
        "complete_sheet_svg_png300_generated": False,
        "mcp_write_tools_enabled": False,
        "read_only": True,
        "mutated": False,
        "ready_to_generate": False,
        "print_ready": False,
        "trusted_commit_authorized": False,
        "authorized_model_generation_executed": False,
    }
