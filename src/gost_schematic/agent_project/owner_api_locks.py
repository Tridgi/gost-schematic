"""Cycle12 exact current cross-owner API blob checks for read-only AI.

Inputs are trusted operator-staged bytes at fixed owner HEADs. No import of
unmerged Python, filesystem writes, URL calls or MCP-side path parameters.
"""
import hashlib
import json
import re
from importlib.resources import files
from typing import Any

from .catalog import ProjectError
from .owner_source_contract import IC_FROZEN_FIXTURE_BLOB_SHA1

_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_OWNERS = frozenset(("IC97", "RECON115", "NET114", "PAINT93"))
_PATHS = {
    "ic_frozen_fixture": ("IC97", "tests/fixtures/tl494_photo_23_frozen_cycle9.json"),
    "ic_tl494": ("IC97", "src/gost_schematic/electrical/tl494cn.py"),
    "ic_integration": ("IC97", "examples/tl494_cycle9_circuit_integration.py"),
    "recon_native": ("RECON115", "examples/tl494_v5/native_circuit.py"),
    "recon_ti_bridge": ("RECON115", "examples/tl494_v5/cycle11_ti_bridge.py"),
    "recon_b_continuation": ("RECON115", "examples/tl494_v5/cycle11_b_continuation.py"),
}
_EXPECTED_CONSTRAINTS = {
    "source_physical_components": 23,
    "source_named_nets": 15,
    "source_pinref_memberships": 62,
    "source_da1_contacts": 16,
    "source_original_wires": 91,
    "source_original_junctions": 37,
    "source_b_nonphysical_markers": ["b-X2", "b-R5"],
    "complete_15_net_route_accepted": False,
    "full_print_drc_accepted": False,
    "autonomous_write_mcp_available": False,
}
_REQUIRED_SHA = "e695c415fdced164b0e0c39c5249d030795a0aa6"


def _fail(code: str) -> None:
    raise ProjectError(code, "Pinned owner API byte contract not satisfied")


def _pairs_unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            _fail("OWNER_LOCK_DUPLICATE_KEY")
        out[key] = value
    return out


def _bad_constant(_value: str) -> None:
    _fail("OWNER_LOCK_INVALID_JSON")


def _sha1_git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw
    ).hexdigest()


def load_pinned_owner_lock_manifest(raw: bytes | None = None) -> dict[str, Any]:
    """Strict bundled manifest. Never accept its replacement from an MCP call."""
    if raw is None:
        raw = files("gost_schematic").joinpath(
            "agent_project", "data", "tl494_cycle12_owner_locks.json"
        ).read_bytes()
    if type(raw) is not bytes or not 0 < len(raw) <= 12_288:
        _fail("OWNER_LOCK_MANIFEST_SIZE_INVALID")
    try:
        manifest = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs_unique, parse_constant=_bad_constant,
        )
    except ProjectError:
        raise
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise ProjectError("OWNER_LOCK_INVALID_JSON", "Invalid owner lock bytes") from exc
    if type(manifest) is not dict or set(manifest) != {
        "schema_version", "status", "repository", "frozen_source_git_sha",
        "owner_heads", "file_locks", "constraints",
    }:
        _fail("OWNER_LOCK_SCHEMA_INVALID")
    if (
        type(manifest["schema_version"]) is not int
        or manifest["schema_version"] != 1
        or manifest["status"] != "EXACT_OWNER_SOURCE_BLOBS_READ_ONLY_CYCLE12"
        or manifest["repository"] != "Tridgi/gost-schematic"
        or manifest["frozen_source_git_sha"] != _REQUIRED_SHA
        or manifest["constraints"] != _EXPECTED_CONSTRAINTS
    ):
        _fail("OWNER_LOCK_CONTRACT_DRIFT")
    heads = manifest["owner_heads"]
    if type(heads) is not dict or set(heads) != _OWNERS or any(
        type(value) is not str or _SHA1.fullmatch(value) is None
        for value in heads.values()
    ):
        _fail("OWNER_LOCK_HEAD_INVALID")
    records = manifest["file_locks"]
    if type(records) is not dict or set(records) != set(_PATHS):
        _fail("OWNER_LOCK_FILE_SET_INVALID")
    for key, record in records.items():
        if type(record) is not dict or set(record) != {
            "owner", "path", "git_blob_sha1",
        }:
            _fail("OWNER_LOCK_FILE_RECORD_INVALID")
        if (record["owner"], record["path"]) != _PATHS[key]:
            _fail("OWNER_LOCK_PATH_OR_OWNER_CHANGED")
        digest = record["git_blob_sha1"]
        if type(digest) is not str or _SHA1.fullmatch(digest) is None:
            _fail("OWNER_LOCK_BLOB_SHA_INVALID")
    if records["ic_frozen_fixture"]["git_blob_sha1"] != IC_FROZEN_FIXTURE_BLOB_SHA1:
        _fail("OWNER_LOCK_ORIGINAL_SOURCE_DRIFT")
    return manifest


def verify_pinned_owner_api_files(owner_files: dict[str, bytes]) -> dict[str, Any]:
    """Verify actual owner blobs/contract without executing unmerged Python."""
    manifest = load_pinned_owner_lock_manifest()
    if type(owner_files) is not dict or set(owner_files) != set(_PATHS):
        _fail("OWNER_LOCK_ACTUAL_FILE_SET_INVALID")
    matches = {}
    for key in _PATHS:
        raw = owner_files[key]
        if type(raw) is not bytes or not 0 < len(raw) <= 256_000:
            _fail("OWNER_LOCK_ACTUAL_FILE_INVALID")
        digest = _sha1_git_blob(raw)
        if digest != manifest["file_locks"][key]["git_blob_sha1"]:
            _fail("OWNER_LOCK_ACTUAL_BLOB_MISMATCH")
        matches[key] = digest

    from .catalog import CatalogResolver
    from .owner_source_contract import (
        verify_cycle11_owner_bridge_surfaces,
        verify_frozen_owner_fixture,
        verify_owner_reversible_display,
        verify_pinned_owner_headers,
    )

    source = verify_frozen_owner_fixture(
        owner_files["ic_frozen_fixture"], CatalogResolver(),
    )
    headers = verify_pinned_owner_headers(
        owner_files["ic_tl494"], owner_files["recon_native"],
    )
    rename = verify_owner_reversible_display(source, headers)
    bridge = verify_cycle11_owner_bridge_surfaces(
        owner_files["ic_integration"],
        owner_files["recon_ti_bridge"],
        owner_files["recon_b_continuation"],
        source,
    )
    return {
        "status": "PASS_SOURCE_AND_OWNER_BYTES_ONLY_PRINT_BLOCKED",
        "schema_version": 1,
        "read_only": True,
        "source_git_sha": _REQUIRED_SHA,
        "owner_heads": dict(manifest["owner_heads"]),
        "verified_git_blob_sha1": matches,
        "physical_components": source["component_count"],
        "physical_nets": source["net_count"],
        "physical_pinref_memberships": source["source_physical_pinref_memberships"],
        "da1_all_16_physical_pins": source["da1_all_16_physical_pins"],
        "source_b_exact_marker_bindings": bridge["source_b_nonphysical_marker_bindings"],
        "reversible_display_nets": rename[
            "reversible_to_original_physical_15_net_memberships"
        ],
        "owner_code_executed": False,
        "new_15_of_15_route_verified": False,
        "print_ready": False,
        "mcp_arbitrary_write_enabled": False,
    }
