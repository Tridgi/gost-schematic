"""Fail-closed, read-only typed design-request audit for AI/CLI integrators.

This is NOT a generator or transaction implementation. It accepts bounded
strict JSON on stdin only; no user-selected path, shell command, arbitrary
Python/SVG patch, write capability, automatic routing or permissive Net union.

Two states:
- saved_e3_review: compare ALL physical Pins/Nets/SHA with a host-authorized
  persisted immutable P1.1 project; returns validated inspection only.
- tl494_reconstruction: syntactically source-pinned full inventory, but
  ALWAYS BLOCKED until the genuine 23/15/16/62 source and full print router
  are imported and independently approved.
"""
import json
import re
import sys
from typing import Any

from .catalog import CatalogResolver, ProjectError
from .contracts import project_uuid
from .design_assistant import (
    TL494_BASELINE,
    TL494_FROZEN_SOURCE_SHA,
    TL494_GROUPS,
    TL494_REQUIRED_PARTS,
)
from .design_selection import require_api_version, require_sha
from .read_access import ReadOnlyProjectAccess
from .service import ProjectSnapshot

_MAX_INPUT_BYTES = 131_072
_MAX_COMPONENTS = 128
_MAX_NETS = 128
_MAX_PIN_MEMBERS = 512
_REF = re.compile(r"[A-Z][A-Z0-9]{0,15}\Z")
_PIN = re.compile(r"[0-9A-Za-z_]{1,16}\Z")
_NET_NAME = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_PART = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\Z")
_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_OUTPUTS = (
    "bom", "drc", "netlist", "png_300dpi", "svg_clean", "svg_diagnostic",
)
_TL494_REFS = frozenset(
    ref for group in TL494_GROUPS.values() for ref in group
)
assert len(_TL494_REFS) == TL494_BASELINE["component_count"]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ProjectError("REQUEST_DUPLICATE_KEY", "Duplicate JSON key")
        obj[key] = value
    return obj


def _constant_bad(_value: str) -> None:
    raise ProjectError("REQUEST_JSON_INVALID", "Non-JSON numeric constant")


def _fields(value: Any, names: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != names:
        raise ProjectError("REQUEST_SCHEMA_INVALID", "Unknown or missing typed fields")
    return value


def _entries(value: Any, limit: int) -> list[Any]:
    if type(value) is not list or len(value) > limit:
        raise ProjectError("REQUEST_SCHEMA_INVALID", "Expected bounded ordered array")
    return value


def _identifier(value: Any, pattern: re.Pattern[str], code: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ProjectError(code, "Invalid typed identifier")
    return value


def decode_request(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_INPUT_BYTES:
        raise ProjectError("REQUEST_SIZE_INVALID", "Bounded JSON request required")
    try:
        data = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object, parse_constant=_constant_bad,
        )
    except ProjectError:
        raise
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise ProjectError("REQUEST_JSON_INVALID", "Invalid strict JSON") from exc
    return _fields(data, {
        "schema_version", "intent", "source_sha", "project_id",
        "expected_revision", "expected_generation", "components",
        "nets", "outputs", "max_route_attempts",
    })


def _validate_inventory(request: dict[str, Any], catalog: CatalogResolver,
                        *, tl494: bool) -> tuple[dict[str, dict[str, Any]],
                                                  dict[str, set[tuple[str, str]]]]:
    references: dict[str, dict[str, Any]] = {}
    for row in _entries(request["components"], _MAX_COMPONENTS):
        item = _fields(row, {"reference", "part_id", "part_sha256", "symbol_sha256"})
        ref = _identifier(item["reference"], _REF, "INVALID_COMPONENT_REFERENCE")
        if ref in references:
            raise ProjectError("REQUEST_DUPLICATE_COMPONENT", "Repeated BOM reference")
        part_id = item["part_id"]
        if part_id is None and tl494 and ref not in TL494_REQUIRED_PARTS:
            if item["part_sha256"] is not None or item["symbol_sha256"] is not None:
                raise ProjectError("REQUEST_CATALOG_LOCK_INVALID", "Unresolved part has no SHA")
        else:
            _identifier(part_id, _PART, "INVALID_CATALOG_SELECTOR")
            require_sha(item["part_sha256"], name="part_sha256")
            require_sha(item["symbol_sha256"], name="symbol_sha256")
            if tl494 and ref in TL494_REQUIRED_PARTS:
                if part_id != TL494_REQUIRED_PARTS[ref]:
                    raise ProjectError("SOURCE_UGO_VARIANT_MISMATCH",
                                       "Frozen TL494 profile requires an exact UGO")
            if tl494 and ref not in TL494_REQUIRED_PARTS:
                raise ProjectError("SOURCE_UNVERIFIED_PART", "No source-locked choice for ref")
            lock = catalog.lock(part_id)
            if (lock["part_sha256"] != item["part_sha256"]
                    or lock["symbol_sha256"] != item["symbol_sha256"]):
                raise ProjectError("CATALOG_REVISION_MISMATCH", "Source UGO SHA has changed")
        references[ref] = item
    if not references:
        raise ProjectError("SOURCE_COMPONENT_INVENTORY_INCOMPLETE", "Empty physical inventory")
    if tl494 and set(references) != _TL494_REFS:
        raise ProjectError("SOURCE_COMPONENT_INVENTORY_INCOMPLETE",
                           "Expected exactly 23 reviewed TL494 component references")

    nets: dict[str, set[tuple[str, str]]] = {}
    owned: set[tuple[str, str]] = set()
    total_members = 0
    for row in _entries(request["nets"], _MAX_NETS):
        item = _fields(row, {"name", "members"})
        name = _identifier(item["name"], _NET_NAME, "INVALID_NET_NAME")
        if name in nets:
            raise ProjectError("REQUEST_DUPLICATE_NET", "Repeated physical Net name")
        members: set[tuple[str, str]] = set()
        pins = _entries(item["members"], _MAX_PIN_MEMBERS)
        if not pins:
            raise ProjectError("REQUEST_NET_EMPTY", "A Net needs typed physical PinRefs")
        for pin in pins:
            p = _fields(pin, {"reference", "number"})
            ref = _identifier(p["reference"], _REF, "INVALID_COMPONENT_REFERENCE")
            num = _identifier(p["number"], _PIN, "INVALID_PHYSICAL_PIN")
            if ref not in references:
                raise ProjectError("REQUEST_FOREIGN_PINREF", "Net contains unknown component")
            target = (ref, num)
            if target in owned:
                raise ProjectError("REQUEST_PINREF_REUSED", "Physical contact in multiple Nets")
            if references[ref]["part_id"] is not None:
                part, _ = catalog.resolve(references[ref]["part_id"])
                if num not in {p.number for p in part.pins}:
                    raise ProjectError("REQUEST_INVALID_PHYSICAL_PIN",
                                       "Pin number absent from resolved physical part")
            if tl494 and ref == "DA1" and num not in {
                str(n) for n in range(1, TL494_BASELINE["da1_physical_contact_count"] + 1)
            }:
                raise ProjectError("REQUEST_INVALID_PHYSICAL_PIN",
                                   "DA1 physical pin number outside TI TL494 package")
            members.add(target)
            owned.add(target)
        total_members += len(members)
        if total_members > _MAX_PIN_MEMBERS:
            raise ProjectError("REQUEST_SCHEMA_INVALID", "Too many total physical pins")
        nets[name] = members
    if not nets:
        raise ProjectError("SOURCE_NET_INVENTORY_INCOMPLETE", "No physical Nets supplied")
    if tl494 and len(nets) != TL494_BASELINE["net_count"]:
        raise ProjectError("SOURCE_NET_INVENTORY_INCOMPLETE",
                           "Original TL494 requires exactly 15 source Nets")
    if tl494 and total_members != 62:
        raise ProjectError("SOURCE_PIN_INVENTORY_INCOMPLETE",
                           "Original TL494 contains 62 connected PinRef memberships")
    return references, nets


def review_request(request: dict[str, Any],
                   catalog: CatalogResolver | None = None) -> dict[str, Any]:
    """Validate typed source against immutable P1.1, or fail closed for TL494."""
    require_api_version(request["schema_version"])
    if request["intent"] not in ("saved_e3_review", "tl494_reconstruction"):
        raise ProjectError("REQUEST_INTENT_UNSUPPORTED", "No arbitrary write/generator intent")
    tl494 = request["intent"] == "tl494_reconstruction"
    if type(request["max_route_attempts"]) is not int or not (
        0 <= request["max_route_attempts"] <= 3
    ):
        raise ProjectError("REQUEST_RETRY_INVALID", "At most three bounded attempts")
    requested = _entries(request["outputs"], len(_OUTPUTS))
    if not requested or len(set(map(str, requested))) != len(requested) or any(
        type(v) is not str or v not in _OUTPUTS for v in requested
    ):
        raise ProjectError("REQUEST_OUTPUT_INVALID", "Only bounded known evidence products")
    if tl494:
        if (request["source_sha"] != TL494_FROZEN_SOURCE_SHA
                or request["project_id"] is not None
                or request["expected_revision"] is not None
                or request["expected_generation"] is not None):
            raise ProjectError("SOURCE_LOCK_INVALID", "Frozen source is not P1.1 revision")
    else:
        if request["source_sha"] != "saved-p11-e3":
            raise ProjectError("SOURCE_LOCK_INVALID", "Saved source tag must be exact")
        project_uuid(request["project_id"])
        require_sha(request["expected_revision"], name="expected_revision")
        if type(request["expected_generation"]) is not int or (
            request["expected_generation"] < 1
        ):
            raise ProjectError("REQUEST_GENERATION_INVALID", "CAS generation required")
    catalog = catalog if catalog is not None else CatalogResolver()
    refs, nets = _validate_inventory(request, catalog, tl494=tl494)

    if tl494:
        # 23/15/62 numerical shape is not source-authentic without the frozen
        # source's true Net UUID/member tuples, package and full placement.
        return {
            "schema_version": 1, "intent": request["intent"],
            "status": "BLOCKED_SOURCE_NOT_IMPORTABLE",
            "read_only": True, "mutated": False, "ready_to_generate": False,
            "source_git_sha": TL494_FROZEN_SOURCE_SHA,
            "component_count": len(refs), "net_count": len(nets),
            "submitted_pinref_count": sum(len(x) for x in nets.values()),
            "source_membership_verified": False,
            "reasons": [
                "TI_TL494_16_PIN_P11_ADAPTER_NOT_INSTALLED",
                "SOURCE_62_PINREF_MEMBERSHIP_NOT_VERIFIED_IN_P11",
                "GLOBAL_15_NET_ROUTER_NOT_ACCEPTED",
                "PRINT_INK_AND_A3_DRC_NOT_ACCEPTED",
                "NO_TRUSTED_TYPED_GENERATOR_OR_CAS_COMMIT",
            ],
            "requested_outputs": requested,
            "outputs_created": [],
            "route_attempts_executed": 0,
        }

    scope = ReadOnlyProjectAccess.from_environment()
    scope.require(request["project_id"])
    service = scope.service
    snapshot = service.open_project(request["project_id"], request["expected_revision"])
    if (snapshot.head.revision != request["expected_revision"]
            or snapshot.head.generation != request["expected_generation"]):
        raise ProjectError("REQUEST_STALE_REVISION", "HEAD revision/generation changed")
    original = {
        c.reference: c.part_id for c in snapshot.project.circuit.components
    }
    if set(refs) != set(original) or any(
        refs[name]["part_id"] != part_id for name, part_id in original.items()
    ):
        raise ProjectError("REQUEST_COMPONENT_INVENTORY_MISMATCH",
                           "Provided source components differ from persisted Circuit")
    actual_nets = {
        net.name: {(p.reference, p.number) for p in net.members}
        for net in snapshot.project.circuit.nets
    }
    if nets != actual_nets:
        raise ProjectError("REQUEST_NET_MEMBERSHIP_MISMATCH",
                           "Source Net/PinRef inventory changed or omitted")
    preflight = service.preflight_design(
        request["project_id"], request["expected_revision"], profile="none",
    )
    return {
        "schema_version": 1, "intent": "saved_e3_review",
        "status": "READ_ONLY_MODEL_MATCH", "read_only": True,
        "mutated": False, "ready_to_generate": False,
        "project_id": request["project_id"],
        "project_revision": snapshot.project.revision,
        "generation": snapshot.head.generation,
        "component_count": len(refs),
        "net_count": len(nets),
        "physical_pin_membership_count": sum(len(v) for v in nets.values()),
        "electrical_erc_status": preflight["electrical_erc"]["status"],
        "print_drc": preflight["print_drc"],
        "print_ready": False,
        "requested_outputs": requested,
        "outputs_created": [],
        "route_attempts_executed": 0,
        "source_membership_verified": True,
    }


def build_saved_review_request(snapshot: ProjectSnapshot, catalog: CatalogResolver
                               ) -> dict[str, Any]:
    """Trusted local fixture construction from the real model, never guessed pins."""
    return {
        "schema_version": 1,
        "intent": "saved_e3_review",
        "source_sha": "saved-p11-e3",
        "project_id": snapshot.project.project_id,
        "expected_revision": snapshot.project.revision,
        "expected_generation": snapshot.head.generation,
        "components": [
            {"reference": c.reference, "part_id": c.part_id,
             "part_sha256": catalog.lock(c.part_id)["part_sha256"],
             "symbol_sha256": catalog.lock(c.part_id)["symbol_sha256"]}
            for c in snapshot.project.circuit.components
        ],
        "nets": [{
            "name": n.name,
            "members": [{"reference": p.reference, "number": p.number}
                        for p in n.members],
        } for n in snapshot.project.circuit.nets],
        "outputs": list(_OUTPUTS),
        "max_route_attempts": 0,
    }


def main() -> int:
    """Do not open a user-selected path or write files; stdin JSON → stdout JSON."""
    try:
        raw = sys.stdin.buffer.read(_MAX_INPUT_BYTES + 1)
        report = review_request(decode_request(raw))
    except ProjectError as exc:
        print(json.dumps({
            "schema_version": 1, "status": "REJECTED",
            "code": exc.code, "read_only": True, "mutated": False,
        }, sort_keys=True))
        return 3
    except (OSError, ValueError, TypeError, RecursionError):
        print(json.dumps({
            "schema_version": 1, "status": "REJECTED",
            "code": "REQUEST_FAILED", "read_only": True, "mutated": False,
        }, sort_keys=True))
        return 3
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 2 if report["status"].startswith("BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
