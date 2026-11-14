"""Cycle11 source-faithful cross-owner *read-only* TL494 contract.

Inspect pinned Git-owner source data as untrusted bytes; NEVER import/execute
scripts from another PR or reinterpret image pixels as wire membership.
The returned source map is for planning, NOT P1.1 persistence/print approval.
"""
import ast
import hashlib
import json
from typing import Any

from .catalog import CatalogResolver, ProjectError, canonical_bytes
from .design_assistant import (
    TL494_BASELINE,
    TL494_FROZEN_SOURCE_SHA,
    TL494_GROUPS,
    TL494_REQUIRED_PARTS,
)

# SHA-1 is Git's content-addressed blob identity (not for authentication).
IC_FROZEN_FIXTURE_BLOB_SHA1 = "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65"
IC_SOURCE_NETLIST_BLOB_SHA1 = "c4cfd515782bf856a7a44fbe2c2ceacd303208d6"
SOURCE_DEVICE_ALIAS = "reference.tl494cn"
IC_MANUFACTURER_DEVICE_ID = "ti.tl494cn.pdip16"
RECON_DISPLAY_RENAMES = {
    "a_INPUT_PLUS": "INPUT_POS",
    "b_NEGATIVE_OUTPUT": "OUTPUT_NEG",
    "TRANSFER": "ENERGY_TRANSFER",
}
_REF_SET = frozenset(ref for refs in TL494_GROUPS.values() for ref in refs)
_EXPECTED_16 = frozenset(f"DA1.{n}" for n in range(1, 17))
assert len(_REF_SET) == TL494_BASELINE["component_count"]


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\x00" + data
    ).hexdigest()


def _source_error(code: str) -> None:
    raise ProjectError(code, "Immutable cross-owner source data failed verification")


def _read_literal_assignment(module_bytes: bytes, name: str) -> Any:
    """Static AST literal, never import an unmerged owner Python module."""
    if type(module_bytes) is not bytes or not 0 < len(module_bytes) < 256_000:
        _source_error("OWNER_MODULE_INVALID")
    try:
        tree = ast.parse(module_bytes.decode("utf-8", errors="strict"))
    except (UnicodeError, SyntaxError, ValueError) as exc:
        raise ProjectError("OWNER_MODULE_INVALID", "Non-readable owner source") from exc
    found = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    found.append(ast.literal_eval(statement.value))
                except (ValueError, TypeError, RecursionError) as exc:
                    raise ProjectError("OWNER_LITERAL_NOT_STATIC",
                                       "Owner contract is not a literal") from exc
    if len(found) != 1:
        _source_error("OWNER_CONTRACT_MISSING_OR_AMBIGUOUS")
    return found[0]


def verify_pinned_owner_headers(
    ti_contract_py: bytes, recon_contract_py: bytes,
) -> dict[str, Any]:
    """Exact names and reversible presentation renames, no lossy rebind."""
    manufacturer = _read_literal_assignment(ti_contract_py, "TI_DEVICE_ID")
    original_commit = _read_literal_assignment(recon_contract_py, "SOURCE_SHA")
    renames = _read_literal_assignment(recon_contract_py, "NET_RENAMES")
    if manufacturer != IC_MANUFACTURER_DEVICE_ID:
        _source_error("OWNER_TI_PART_ID_DRIFT")
    if original_commit != TL494_FROZEN_SOURCE_SHA:
        _source_error("OWNER_FROZEN_SOURCE_DRIFT")
    if renames != RECON_DISPLAY_RENAMES:
        _source_error("OWNER_NET_DISPLAY_RENAMES_DRIFT")
    if len(set(renames.values())) != len(renames):
        _source_error("OWNER_NET_DISPLAY_RENAMES_NONBIJECTIVE")
    return {
        "source_part_id": SOURCE_DEVICE_ALIAS,
        "manufacturer_part_id": manufacturer,
        "part_id_bridge": "DISPLAY_TRANSLATION_ONLY_NOT_A_P11_PART_DEFINITION",
        "recon_display_renames": renames,
        "reversible": True,
        "source_git_sha": original_commit,
        "read_only": True,
    }


def verify_frozen_owner_fixture(
    raw: bytes, catalog: CatalogResolver,
) -> dict[str, Any]:
    """Validate real literal source BOM, complete physical Net and nominals.

    Original Git blob must be EXACT, not merely the same counts. Source
    photo electrical semantics remain DRAFT/REVIEW despite the fingerprint.
    """
    if type(raw) is not bytes or not 1 <= len(raw) <= 131_072:
        _source_error("SOURCE_FIXTURE_SIZE_INVALID")
    if _git_blob_sha1(raw) != IC_FROZEN_FIXTURE_BLOB_SHA1:
        _source_error("SOURCE_FIXTURE_BLOB_SHA_MISMATCH")
    try:
        src = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as exc:
        raise ProjectError("SOURCE_FIXTURE_JSON_INVALID", "Bad frozen fixture") from exc
    if type(src) is not dict or set(src) != {
        "schema_version", "status", "source_commit", "source_path",
        "source_blob_sha", "limitations", "components", "nets",
    }:
        _source_error("SOURCE_FIXTURE_SCHEMA_INVALID")
    if (src["schema_version"] != 1
            or src["source_commit"] != TL494_FROZEN_SOURCE_SHA
            or src["source_blob_sha"] != IC_SOURCE_NETLIST_BLOB_SHA1
            or src["status"] != "FROZEN_SOURCE_PHOTO_TOPOLOGY_DRAFT_NOT_ENGINEERING_APPROVED"):
        _source_error("SOURCE_PROVENANCE_INVALID")
    parts = src["components"]
    nets = src["nets"]
    if type(parts) is not list or len(parts) != 23:
        _source_error("SOURCE_COMPONENT_INVENTORY_INCOMPLETE")
    if type(nets) is not dict or len(nets) != 15:
        _source_error("SOURCE_NET_INVENTORY_INCOMPLETE")
    inventory: dict[str, dict[str, Any]] = {}
    for p in parts:
        if type(p) is not dict or set(p) != {"ref", "part_id", "nominal_si"}:
            _source_error("SOURCE_COMPONENT_FORMAT_INVALID")
        ref, part = p["ref"], p["part_id"]
        if type(ref) is not str or ref not in _REF_SET or ref in inventory:
            _source_error("SOURCE_COMPONENT_IDENTITY_INVALID")
        if type(part) is not str or len(part) > 80:
            _source_error("SOURCE_PART_ID_INVALID")
        value = p["nominal_si"]
        if value is not None and (type(value) is not str or len(value) > 60):
            _source_error("SOURCE_NOMINAL_INVALID")
        if ref in TL494_REQUIRED_PARTS and part != TL494_REQUIRED_PARTS[ref]:
            _source_error("SOURCE_UGO_VARIANT_MISMATCH")
        elif ref in ("X1", "X2", "DA1"):
            if part != {
                "DA1": SOURCE_DEVICE_ALIAS, "X1": "reference.connector.x1",
                "X2": "reference.connector.x2",
            }[ref]:
                _source_error("SOURCE_EXTERNAL_PART_ID_DRIFT")
        elif part != "resistor.fixed":
            _source_error("SOURCE_SOURCE_RESISTOR_ID_DRIFT")
        inventory[ref] = p
    if set(inventory) != _REF_SET:
        _source_error("SOURCE_COMPONENT_INVENTORY_INCOMPLETE")
    membership: dict[str, list[tuple[str, str]]] = {}
    seen: set[tuple[str, str]] = set()
    da1 = set()
    for name, refs in nets.items():
        if (type(name) is not str or not name or len(name) > 80
                or type(refs) is not list or not refs):
            _source_error("SOURCE_NET_FORMAT_INVALID")
        members = []
        for string in refs:
            if type(string) is not str or string.count(".") != 1:
                _source_error("SOURCE_PINREF_FORMAT_INVALID")
            ref, num = string.split(".")
            if ref not in inventory or not num or len(num) > 16:
                _source_error("SOURCE_FOREIGN_PINREF")
            pair = (ref, num)
            if pair in seen:
                _source_error("SOURCE_PINREF_DUPLICATED_ACROSS_NETS")
            if ref == "DA1":
                if f"DA1.{num}" not in _EXPECTED_16:
                    _source_error("SOURCE_DA1_PIN_INVALID")
                da1.add(f"DA1.{num}")
            elif ref not in ("X1", "X2"):
                physical_part, _ = catalog.resolve(inventory[ref]["part_id"])
                if num not in {pin.number for pin in physical_part.pins}:
                    _source_error("SOURCE_PIN_NOT_IN_PHYSICAL_CATALOG")
            else:
                if num not in ("1", "2"):
                    _source_error("SOURCE_CONNECTOR_PIN_INVALID")
            seen.add(pair)
            members.append(pair)
        membership[name] = members
    if len(seen) != 62:
        _source_error("SOURCE_PIN_INVENTORY_INCOMPLETE")
    if da1 != _EXPECTED_16:
        _source_error("SOURCE_DA1_16_PINS_INCOMPLETE")
    if "PE" in nets or "CHASSIS" in nets:
        _source_error("SOURCE_INVENTED_PROTECTIVE_EARTH")
    installed = {}
    for ref, part in inventory.items():
        if part["part_id"] in catalog.parts:
            installed[ref] = catalog.lock(part["part_id"])
    normalized = {
        "components": [{"reference": ref, "part_id": inventory[ref]["part_id"],
                        "nominal_si": inventory[ref]["nominal_si"]}
                       for ref in sorted(inventory)],
        "nets": {name: [f"{a}.{b}" for a, b in membership[name]]
                 for name in sorted(membership)},
    }
    return {
        "schema_version": 1,
        "status": "SOURCE_TYPED_MEMBERSHIP_LOCKED_PRINT_BLOCKED",
        "source_commit": src["source_commit"],
        "source_fixture_git_blob_sha1": _git_blob_sha1(raw),
        "source_typed_manifest_sha256": hashlib.sha256(
            canonical_bytes(normalized)
        ).hexdigest(),
        "component_count": len(parts),
        "net_count": len(nets),
        "source_physical_pinref_memberships": len(seen),
        "da1_all_16_physical_pins": True,
        "source_components": normalized["components"],
        "source_nets": normalized["nets"],
        "installed_part_locks": installed,
        "non_installed_parts": {
            ref: part["part_id"] for ref, part in sorted(inventory.items())
            if part["part_id"] not in catalog.parts
        },
        "source_nominals_preserved_as_literals": True,
        "source_circuit_approved": False,
        "source_photo_pixel_verified": False,
        "print_ready": False,
        "read_only": True,
    }


def verify_owner_reversible_display(source: dict[str, Any],
                                    owner_headers: dict[str, Any]) -> dict[str, Any]:
    names = set(source["source_nets"])
    pairs = owner_headers["recon_display_renames"]
    if set(pairs) - names or set(pairs.values()) & (names - set(pairs)):
        _source_error("OWNER_NET_RENAME_COLLISION")
    rendered = {pairs.get(name, name): list(pins)
                for name, pins in source["source_nets"].items()}
    recovered = {next((name for name, mapped in pairs.items()
                       if mapped == shown), shown): list(pins)
                 for shown, pins in rendered.items()}
    if recovered != source["source_nets"]:
        _source_error("OWNER_NET_RENAME_NOT_REVERSIBLE")
    return {
        "source_net_count": len(names), "display_net_count": len(rendered),
        "reversible_to_original_physical_15_net_memberships": True,
        "display_net_names": sorted(rendered),
        "no_net_union": True,
    }


def _owner_ast(raw: bytes) -> ast.Module:
    """Inspect unmerged Python as AST only; never import or execute it."""
    if type(raw) is not bytes or not 0 < len(raw) < 256_000:
        _source_error("OWNER_MODULE_INVALID")
    try:
        return ast.parse(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, SyntaxError, ValueError) as exc:
        raise ProjectError("OWNER_MODULE_INVALID", "Unparseable owner module") from exc


def _static_pinref(node: ast.AST) -> str:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "PinRef"
        and len(node.args) == 2
        and not node.keywords
        and all(isinstance(a, ast.Constant) and type(a.value) is str
                for a in node.args)
    ):
        _source_error("OWNER_PINREF_STATIC_CONTRACT_UNVERIFIED")
    return f"{node.args[0].value}.{node.args[1].value}"


def _assigned(tree: ast.Module, name: str) -> ast.AST:
    found = [
        item.value for item in tree.body
        if isinstance(item, ast.Assign)
        and len(item.targets) == 1
        and isinstance(item.targets[0], ast.Name)
        and item.targets[0].id == name
    ]
    if len(found) != 1:
        _source_error("OWNER_CONTRACT_MISSING_OR_AMBIGUOUS")
    return found[0]


def verify_cycle11_owner_bridge_surfaces(
    ic_integration_py: bytes, recon_ti_bridge_py: bytes,
    recon_b_continuation_py: bytes, authentic_source: dict[str, Any],
) -> dict[str, Any]:
    """Prove current owner *interface shape*, NOT executable joint approval.

    Read safe literal and def names from pinned HEAD source files as AST;
    no import-time effects, phantom pins, or silent b-Net aliases.
    """
    ic_tree = _owner_ast(ic_integration_py)
    ti_tree = _owner_ast(recon_ti_bridge_py)
    b_tree = _owner_ast(recon_b_continuation_py)
    ic_functions = {row.name for row in ic_tree.body
                    if isinstance(row, (ast.FunctionDef, ast.AsyncFunctionDef))}
    ti_functions = {row.name for row in ti_tree.body
                    if isinstance(row, (ast.FunctionDef, ast.AsyncFunctionDef))}
    b_functions = {row.name for row in b_tree.body
                   if isinstance(row, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if "bind_positioned_photo_circuit_from_catalog" not in ic_functions:
        _source_error("OWNER_IC_TYPED_BINDING_API_MISSING")
    if "bind_verified_compact_ti" not in ti_functions:
        _source_error("OWNER_RECON_SIGNED_TI_BRIDGE_MISSING")
    if "rebind_true_source_b" not in b_functions:
        _source_error("OWNER_RECON_TRUE_B_REBIND_MISSING")
    if (
        ast.literal_eval(_assigned(ti_tree, "SOURCE_PART_ID")) != SOURCE_DEVICE_ALIAS
        or ast.literal_eval(_assigned(ti_tree, "PHYSICAL_REF")) != "DA1"
        or ast.literal_eval(_assigned(b_tree, "OLD_B_NAME")) != "OUTPUT_NEG"
        or ast.literal_eval(_assigned(b_tree, "SOURCE_B_NAME")) != "b_NEGATIVE_OUTPUT"
    ):
        _source_error("OWNER_IC_B_PHYSICAL_SOURCE_NAMES_CHANGED")

    pins = _assigned(b_tree, "B_PHYSICAL")
    if not (
        isinstance(pins, ast.Call)
        and isinstance(pins.func, ast.Name)
        and pins.func.id == "frozenset"
        and len(pins.args) == 1
        and isinstance(pins.args[0], ast.Set)
        and not pins.keywords
    ):
        _source_error("OWNER_B_PHYSICAL_SET_UNVERIFIED")
    physical_b = {_static_pinref(node) for node in pins.args[0].elts}
    required_b = {"FU1.2", "X2.1", "R5.2"}
    if physical_b != required_b or set(
        authentic_source["source_nets"]["b_NEGATIVE_OUTPUT"]
    ) != required_b:
        _source_error("OWNER_B_PHYSICAL_THREE_TERMINALS_DRIFT")

    markers = _assigned(b_tree, "SOURCE_B_STUBS")
    if not isinstance(markers, ast.Dict):
        _source_error("OWNER_B_TWO_SOURCE_MARKERS_UNVERIFIED")
    stub_map = {}
    for key, value in zip(markers.keys, markers.values, strict=True):
        if not isinstance(key, ast.Constant) or type(key.value) is not str:
            _source_error("OWNER_B_SOURCE_MARKER_ID_UNVERIFIED")
        if key.value in stub_map:
            _source_error("OWNER_B_DUPLICATE_MARKER")
        stub_map[key.value] = _static_pinref(value)
    if stub_map != {"b-X2": "X2.1", "b-R5": "R5.2"}:
        _source_error("OWNER_B_TWO_SOURCE_MARKERS_CHANGED")
    return {
        "status": "PINNED_OWNER_AST_INTERFACES_MATCH",
        "read_only": True,
        "owner_code_imported_or_executed": False,
        "owner_cross_branch_runtime_import_verified": False,
        "manufacturer_typed_bind_api": "bind_positioned_photo_circuit_from_catalog",
        "recon_typed_adapter_api": "bind_verified_compact_ti",
        "recon_b_rebind_api": "rebind_true_source_b",
        "b_source_name": "b_NEGATIVE_OUTPUT",
        "b_physical_pins": sorted(physical_b),
        "source_b_nonphysical_marker_bindings": stub_map,
        "source_15_net_62_pin_memberships_preserved": True,
    }
