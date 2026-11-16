"""GOST CAD desktop transport v1: bounded NDJSON, no arbitrary shell or file paths.

This is a small isolated host adapter, NOT an implementation of gscad-project v2.
Only stdout carries JSON protocol responses; logs and engine diagnostics go to stderr.
"""
from __future__ import annotations

import contextlib
import importlib.resources
import json
import re
import sys
from pathlib import Path
from typing import Any

VERSION = 1
MAX_REQUEST = 1_048_576
MAX_RESPONSE = 4_194_304
I64_MIN, I64_MAX = -(2**63), 2**63 - 1
ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
DECIMAL_RE = re.compile(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)\Z")
CATALOG_RE = re.compile(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*\.json\Z")
HEX_SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
ALLOWED_KEYS = frozenset({"v", "id", "op", "args"})


class ProtocolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, val in pairs:
        if key in result:
            raise ProtocolError("INVALID_JSON", "duplicate JSON member")
        result[key] = val
    return result


def _invalid_constant(_: str) -> None:
    raise ProtocolError("INVALID_JSON", "non-finite JSON number")


def decimal_um(value: Any) -> str:
    if not isinstance(value, str) or not DECIMAL_RE.fullmatch(value):
        raise ProtocolError("INVALID_UNIT", "require canonical signed integer micrometre string")
    if len(value) > 21:
        raise ProtocolError("UNIT_OVERFLOW", "micrometre value exceeds signed int64")
    number = int(value)
    if number < I64_MIN or number > I64_MAX:
        raise ProtocolError("UNIT_OVERFLOW", "micrometre value exceeds signed int64")
    return value


def validate_edit_guard(*, base_revision: str, current_revision: str,
                        expected_topology_hash: str, actual_topology_hash: str) -> None:
    """Reusable fail-closed CAS preflight; no mutation is performed here.

    Integrate with the model team's canonical v2 command service only when approved.
    """
    hashes = (base_revision, current_revision, expected_topology_hash, actual_topology_hash)
    if not all(isinstance(h, str) and HEX_SHA_RE.fullmatch(h) for h in hashes):
        raise ProtocolError("INVALID_SHA", "require lowercase hexadecimal source/revision hashes")
    if base_revision != current_revision:
        raise ProtocolError("REVISION_CONFLICT", "document revision changed")
    if expected_topology_hash != actual_topology_hash:
        raise ProtocolError("SOURCE_LOCKED", "source graph differs from locked source")


def _symbol_operation(symbol: Any, *, check: bool) -> dict[str, Any]:
    if not isinstance(symbol, str) or not CATALOG_RE.fullmatch(symbol):
        raise ProtocolError("INVALID_SYMBOL", "require catalog-relative symbol path")
    try:
        from gost_schematic.catalog.loader import load_symbol
        from gost_schematic.rendering.svg import render_symbol_svg
        from gost_schematic.validation.symbol_checks import validate_symbol
        catalog = (Path(str(importlib.resources.files("gost_schematic"))) / "catalog" / "symbols").resolve()
    except (ModuleNotFoundError, ImportError) as exc:
        raise ProtocolError("ENGINE_UNAVAILABLE", "gost-schematic Python engine not installed") from exc
    path = (catalog / symbol).resolve()
    if not path.is_relative_to(catalog) or not path.is_file():
        raise ProtocolError("UNKNOWN_SYMBOL", "symbol not found in packaged catalog")
    try:
        with contextlib.redirect_stdout(sys.stderr):
            model = load_symbol(path)
            problems = validate_symbol(model)
            diagnostics = [{"code": str(x.code), "severity": x.severity.value,
                            "message": str(x.message)} for x in problems]
            if check:
                return {"diagnostics": diagnostics,
                        "has_errors": any(x["severity"] == "error" for x in diagnostics)}
            svg = render_symbol_svg(model)
    except Exception as exc:
        print(f"engine failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise ProtocolError("ENGINE_FAILURE", "engine failed; consult local log") from exc
    if not isinstance(svg, str) or not svg.lstrip().startswith("<svg"):
        raise ProtocolError("ENGINE_FAILURE", "invalid SVG from Python engine")
    return {"format": "svg", "svg": svg, "diagnostics": diagnostics}


def _project_contract():
    """Load only the app-owned #122 model; never import an ambient 'ui' package."""
    import importlib.util

    # Local checkout and signed PyInstaller bundle must contain exact same
    # ui/editor/src/model/contract.py + ui/contracts/project-v2.schema.json.
    # No request-controlled PYTHONPATH, module names, or URL imports.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        repository = Path(sys._MEIPASS)
    else:
        repository = Path(__file__).resolve().parents[3]
    canonical_path = repository / "ui" / "editor" / "src" / "model" / "contract.py"
    schema_path = repository / "ui" / "contracts" / "project-v2.schema.json"
    if not canonical_path.is_file() or not schema_path.is_file():
        raise ProtocolError(
            "MODEL_UNAVAILABLE", "canonical v2 model/schema missing from application"
        )
    spec = importlib.util.spec_from_file_location("_gscad_canonical_v2", canonical_path)
    if spec is None or spec.loader is None:
        raise ProtocolError("MODEL_UNAVAILABLE", "canonical v2 model cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (ImportError, OSError, ValueError) as exc:
        raise ProtocolError("MODEL_UNAVAILABLE", "canonical v2 model load failed") from exc
    return module



def _reject_ambiguous_wire_vertices(document: dict[str, Any]) -> None:
    """Temporary fail-closed guard for #122 colon-delimited DSU identifiers.

    The canonical v2 schema permits ':' in IDs. Until #122 route_is_complete
    switches to tuple keys, two distinct vertex triples may share a DSU key
    and incorrectly join disconnected physical pins.
    """
    project = document.get("project") if isinstance(document, dict) else None
    sheets = project.get("sheets") if isinstance(project, dict) else None
    if not isinstance(sheets, list):
        return  # canonical v2 validator will report malformed schema
    seen: dict[str, tuple[str, str, str]] = {}
    for sheet in sheets:
        if not isinstance(sheet, dict) or not isinstance(sheet.get("wires"), list):
            continue
        sid = sheet.get("id")
        for wire in sheet["wires"]:
            if not isinstance(wire, dict) or not isinstance(wire.get("vertices"), list):
                continue
            wid = wire.get("id")
            for vertex in wire["vertices"]:
                if not isinstance(vertex, dict):
                    continue
                vid = vertex.get("id")
                if not all(isinstance(item, str) for item in (sid, wid, vid)):
                    continue
                identity = (sid, wid, vid)
                legacy_key = ":".join(identity)
                previous = seen.get(legacy_key)
                if previous is not None and previous != identity:
                    raise ProtocolError(
                        "AMBIGUOUS_VERTEX_ID", "source model wire vertex key collision"
                    )
                seen[legacy_key] = identity



def _engine_projection(args: dict[str, Any]) -> dict[str, Any]:
    """Read-only exact v2→existing Python Circuit projection, not export approval."""
    import importlib.util

    if set(args) != {"document"} or type(args["document"]) is not dict:
        raise ProtocolError("INVALID_REQUEST", "exact v2 document required")
    _reject_ambiguous_wire_vertices(args["document"])
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        repository = Path(sys._MEIPASS)
    else:
        repository = Path(__file__).resolve().parents[3]
    canonical = repository / "ui" / "editor" / "src" / "model" / "contract.py"
    adapter = repository / "ui" / "editor" / "src" / "model" / "engine_adapter.py"
    if not canonical.is_file() or not adapter.is_file():
        raise ProtocolError("ENGINE_ADAPTER_UNAVAILABLE", "v2 engine projection adapter missing")
    spec = importlib.util.spec_from_file_location("_gscad_engine_projection", adapter)
    if spec is None or spec.loader is None:
        raise ProtocolError("ENGINE_ADAPTER_UNAVAILABLE", "v2 engine projection cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    if str(canonical.parent) not in sys.path:
        sys.path.insert(0, str(canonical.parent))
    # @dataclass with postponed annotations resolves cls.__module__ in sys.modules.
    # This registration is ONLY for the fixed, app-owned adapter path above;
    # a user request never supplies a module path or executable.
    previous = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except (ImportError, OSError) as exc:
        if previous is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous
        raise ProtocolError("ENGINE_ADAPTER_UNAVAILABLE", "v2 engine projection dependencies missing") from exc
    except BaseException:
        # Do not leak a half-initialized module on unexpected loader errors.
        if previous is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous
        raise
    if Path(module.validate.__code__.co_filename).resolve() != canonical.resolve():
        raise ProtocolError("ENGINE_ADAPTER_UNAVAILABLE", "untrusted model validation import")
    try:
        projection = module.project_to_engine(args["document"], require_placed=True)
    except module.ContractError as exc:
        raise ProtocolError(
            exc.code, "v2 cannot safely project to existing Python engine"
        ) from exc
    return {
        "model": "gscad-project", "format_version": 2,
        "project_sha256": projection.project_sha256,
        "source_topology_sha256": projection.source_topology_hash,
        "component_count": len(projection.circuit.components),
        "net_count": len(projection.circuit.nets),
        "authored_segment_count": sum(len(sheet.graph.segments) for sheet in projection.sheets),
        "source_b_graphic_count": sum(len(sheet.source_b_graphic_ids) for sheet in projection.sheets),
        "incomplete_net_counts": [len(sheet.unfinished_net_ids) for sheet in projection.sheets],
        "geometry_complete": projection.geometry_complete,
        "rendering_catalog_verified": projection.rendering_catalog_verified,
        "render_allowed": False,
        "project_write": False,
    }


def _wire_bridge():
    """Load MASTER-owned single-sheet wire adapter only from fixed installed files."""
    import importlib.util

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        repository = Path(sys._MEIPASS)
    else:
        repository = Path(__file__).resolve().parents[3]
    path = repository / "ui" / "integration" / "project_wire_bridge.py"
    canonical = repository / "ui" / "editor" / "src" / "model" / "contract.py"
    schema = repository / "ui" / "contracts" / "project-v2.schema.json"
    if not all(p.is_file() for p in (path, canonical, schema)):
        raise ProtocolError("BRIDGE_UNAVAILABLE", "canonical v2 wire adapter not packaged")
    spec = importlib.util.spec_from_file_location("_gscad_project_wire_adapter", path)
    if spec is None or spec.loader is None:
        raise ProtocolError("BRIDGE_UNAVAILABLE", "v2 wire adapter cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (ImportError, ValueError, OSError) as exc:
        raise ProtocolError("BRIDGE_UNAVAILABLE", "v2 wire adapter cannot be loaded") from exc
    if Path(module.model.__file__).resolve() != canonical.resolve():
        raise ProtocolError("BRIDGE_UNAVAILABLE", "wrong Python model loaded by wire adapter")
    return module


def _wire_operation(op: str, args: dict[str, Any]) -> dict[str, Any]:
    """Stateless, source-CAS checked bridge; no real edit is persisted."""
    fields = {"document", "sheet_id", "revision"} if op == "wire_snapshot" else {
        "document", "candidate", "sheet_id", "expected_project_sha256"
    }
    if not set(args) <= fields or "document" not in args or type(args["document"]) is not dict:
        raise ProtocolError("INVALID_REQUEST", "unexpected wire bridge arguments")
    if op == "validate_wire_candidate":
        if "candidate" not in args or type(args["candidate"]) is not dict:
            raise ProtocolError("INVALID_REQUEST", "typed candidate snapshot required")
        expected_sha = args.get("expected_project_sha256")
        if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            raise ProtocolError("INVALID_SHA", "expected project SHA-256 required")
    if args.get("sheet_id") is not None and (
        not isinstance(args["sheet_id"], str) or not args["sheet_id"]
    ):
        raise ProtocolError("INVALID_REQUEST", "invalid sheet ID")
    rev = args.get("revision", 0)
    if op == "wire_snapshot" and (
        type(rev) is not int or not 0 <= rev <= 9_007_199_254_740_991
    ):
        raise ProtocolError("INVALID_REVISION", "revision must be an exact safe integer")
    _reject_ambiguous_wire_vertices(args["document"])
    bridge = _wire_bridge()
    try:
        if op == "wire_snapshot":
            snapshot = bridge.to_snapshot(args["document"], sheet_id=args.get("sheet_id"),
                                          revision=rev)
            return {
                "model": "gscad-project", "format_version": 2,
                "project_sha256": bridge.model.digest(args["document"]),
                "source_topology_sha256": snapshot["source_topology_hash"],
                "wiring_snapshot": snapshot, "committed": False,
            }
        candidate = bridge.apply_snapshot(
            args["document"], args["candidate"],
            expected_sha=args["expected_project_sha256"],
            sheet_id=args.get("sheet_id"),
        )
        _reject_ambiguous_wire_vertices(candidate)
        return {
            "project_sha256": bridge.model.digest(candidate),
            "source_topology_sha256": bridge.model.source_inventory_hash(
                candidate["project"]
            ),
            "validated_document": candidate,
            "committed": False,
        }
    except (bridge.BridgeError, bridge.model.ContractError) as exc:
        code = str(exc).split(":", 1)[0]
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", code):
            code = "BRIDGE_REJECTED"
        raise ProtocolError(code, "wire candidate rejected; no state was changed") from exc


def _native_export_preview(args: dict[str, Any]) -> dict[str, Any]:
    """Canonical Python v2->physical SVG/PNG300, with NO pathname or write.

    Rust alone obtains an OS file capability and performs the atomic save.
    All Net/PinRef topology stays in the validated ProjectV2 declaration.
    The font remains visibly unverified and ESKD approval is NEVER asserted.
    """
    import base64
    import hashlib

    if set(args) != {"document", "sheet_id", "format"} or (
        type(args.get("document")) is not dict or
        type(args.get("sheet_id")) is not str or
        args.get("format") not in ("svg", "png300")
    ):
        raise ProtocolError("INVALID_REQUEST", "canonical document/sheet/format required; paths forbidden")
    document = args["document"]
    _reject_ambiguous_wire_vertices(document)
    model = _project_contract()
    try:
        model.validate(document)
        current_sha = model.digest(document)
    except model.ContractError as exc:
        raise ProtocolError(exc.code, "canonical project rejected for export") from exc
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        root = Path(sys._MEIPASS)
    else:
        root = Path(__file__).resolve().parents[3]
    exporter = root / "ui" / "bridge" / "export" / "project_v2.py"
    if not exporter.is_file():
        raise ProtocolError("EXPORT_UNAVAILABLE", "canonical Python v2 exporter is not packaged")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        import ui.bridge.export.project_v2 as bridge_export
        from ui.bridge.export.canonical import ExportError, ExportRequest
    except (ImportError, OSError) as exc:
        raise ProtocolError("EXPORT_UNAVAILABLE", "canonical preview backend dependency missing") from exc
    if Path(bridge_export.__file__).resolve() != exporter.resolve():
        raise ProtocolError("EXPORT_UNAVAILABLE", "untrusted Python export module")
    request = ExportRequest(page="A3", orientation="landscape", dpi=300,
                            include_frame=False, include_title=False,
                            strict_font=False)
    try:
        if args["format"] == "svg":
            payload, warnings = bridge_export.export_v2_svg(
                document, args["sheet_id"], request,
                expected_project_sha256=current_sha)
            pixels = [4961, 3508]
        else:
            exported = bridge_export.export_v2(
                document, args["sheet_id"], request,
                expected_project_sha256=current_sha)
            payload, warnings, pixels = exported.png, exported.warnings, list(exported.pixels)
    except (ExportError, ValueError, OSError) as exc:
        raise ProtocolError("EXPORT_BLOCKED", "canonical Python preview export rejected") from exc
    # Never silently substitute a raster screenshot or shrink physical units.
    if len(payload) > 2_600_000:
        raise ProtocolError("EXPORT_TOO_LARGE", "IPC output exceeds bounded native preview budget")
    return {
        "format": args["format"],
        "encoding": "base64",
        "payload": base64.b64encode(payload).decode("ascii"),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "project_sha256": current_sha,
        "sheet_id": args["sheet_id"],
        "sheet_size_um": [420000, 297000],
        "pixel_dimensions": pixels,
        "approval": "NOT_ESKD_CERTIFIED",
        "warnings": list(warnings),
    }


def _parse_document_blob(args: dict[str, Any]) -> dict[str, Any]:
    """Fixed canonical ProjectV2 parser for native-dialog-selected UTF-8 bytes.

    The Rust host owns file-path capabilities. This operation never sees a
    pathname or writes a file; an untrusted JSON text is validated using the
    exact Python model before the native host can persist it.
    """
    if set(args) != {"blob"} or type(args.get("blob")) is not str:
        raise ProtocolError("INVALID_REQUEST", "one UTF-8 JSON document string required")
    model = _project_contract()
    try:
        document = model.strict_loads(args["blob"])
        _reject_ambiguous_wire_vertices(document)
        model.validate(document)
        project = document["project"]
        return {
            "document": document,
            "project_id": project["id"],
            "project_sha256": model.digest(document),
            "source_topology_sha256": model.source_inventory_hash(project),
            "source_sha": project["provenance"]["source_sha"],
            "provenance_status": project["provenance"]["status"],
            "source_path": project["provenance"]["source_path"],
            "project_write": False,
        }
    except model.ContractError as exc:
        raise ProtocolError(exc.code, "native project document rejected by strict canonical v2 parser") from exc


def _project_operation(op: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validated read-only ProjectFileV2 bridge; NEVER mutates editor state."""
    expected_keys = {"document", "net_id"} if op == "verify_net" else {"document"}
    if set(args) != expected_keys or type(args.get("document")) is not dict:
        raise ProtocolError("INVALID_REQUEST", "v2 document and exact operation keys required")
    _reject_ambiguous_wire_vertices(args["document"])
    model = _project_contract()
    try:
        document = model.validate(args["document"])
        project = document["project"]
        project_sha256 = model.digest(document)  # workspace/camera excluded by #122
        source_sha256 = model.source_inventory_hash(project)
    except model.ContractError as exc:
        raise ProtocolError(exc.code, "rejected by canonical gscad-project v2 validator") from exc
    # Honest provenance: a source SHA only asserts declared source inventory,
    # not that wires have been routed/approved or a GOST font has been checked.
    if op == "verify_net":
        net_id = args["net_id"]
        if not isinstance(net_id, str) or not net_id:
            raise ProtocolError("INVALID_NET", "nonempty declared net ID required")
        net = next((item for item in project["nets"] if item["id"] == net_id), None)
        if net is None:
            raise ProtocolError("UNKNOWN_NET", "Net does not exist in project")
        is_connected = model.route_is_complete(project, net)
        return {
            "project_sha256": project_sha256,
            "source_topology_sha256": source_sha256,
            "net_id": net_id,
            "declared_route_status": net["route_status"],
            "reachability_complete": is_connected,
            "export_approved": False,
            "diagnostics": [] if is_connected else ["DECLARED_MEMBERS_NOT_ALL_CONNECTED"],
        }
    counts = {
        "components": len(project["components"]),
        "nets": len(project["nets"]),
        "memberships": sum(len(n["members"]) for n in project["nets"]),
        "wires": sum(len(s["wires"]) for s in project["sheets"]),
        "non_electrical_b": sum(
            g["kind"] == "source_b_continuation"
            for sheet in project["sheets"] for g in sheet["graphics"]
        ),
    }
    return {
        "model": "gscad-project",
        "format_version": 2,
        "source_sha": project["provenance"]["source_sha"],
        "project_sha256": project_sha256,
        "source_topology_sha256": source_sha256,
        "inventory": counts,
        "declared_routes": {
            status: sum(n["route_status"] == status for n in project["nets"])
            for status in ("unrouted", "partial", "verified")
        },
        "electrical_approval": False,
        "project_write": False,
    }


def dispatch(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) != ALLOWED_KEYS:
        raise ProtocolError("INVALID_REQUEST", "exact keys required: v, id, op, args")
    version, req_id, op, args = (request[key] for key in ("v", "id", "op", "args"))
    if type(version) is not int or version != VERSION:
        raise ProtocolError("UNSUPPORTED_VERSION", "only protocol v1 supported")
    if not isinstance(req_id, str) or not ID_RE.fullmatch(req_id):
        raise ProtocolError("INVALID_ID", "invalid correlation ID")
    if not isinstance(op, str) or not isinstance(args, dict):
        raise ProtocolError("INVALID_REQUEST", "invalid operation or args")
    if op == "hello":
        return {"protocol": VERSION, "engine": "gost-schematic",
                "capabilities": ["hello", "unit_roundtrip", "check_symbol", "render_symbol",
                                 "validate_document", "source_snapshot", "verify_net",
                                 "wire_snapshot", "validate_wire_candidate",
                                 "engine_projection"],
                "project_write": False, "process": "ephemeral-or-supervised"}
    if op == "unit_roundtrip":
        return {"x_um": decimal_um(args.get("x_um")),
                "y_um": decimal_um(args.get("y_um"))}
    if op == "check_symbol" or op == "render_symbol":
        return _symbol_operation(args.get("symbol"), check=op == "check_symbol")
    if op == "parse_document_blob":
        return _parse_document_blob(args)
    if op == "native_export_preview":
        return _native_export_preview(args)
    if op in {"validate_document", "source_snapshot", "verify_net"}:
        return _project_operation(op, args)
    if op in {"wire_snapshot", "validate_wire_candidate"}:
        return _wire_operation(op, args)
    if op == "engine_projection":
        return _engine_projection(args)
    if op in {"position_edit", "render_svg", "export_png"}:
        raise ProtocolError("NOT_WIRED", "awaiting approved transactional/export adapter")
    raise ProtocolError("UNKNOWN_OPERATION", "operation not allowlisted")


def process(line: bytes) -> dict[str, Any]:
    request_id: str | None = None
    try:
        if len(line) > MAX_REQUEST:
            raise ProtocolError("PAYLOAD_TOO_LARGE", "request exceeds 1 MiB")
        try:
            request = json.loads(line, object_pairs_hook=_unique_keys,
                                 parse_constant=_invalid_constant)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProtocolError("INVALID_JSON", "malformed JSON or UTF-8") from exc
        if (isinstance(request, dict) and isinstance(request.get("id"), str)
                and ID_RE.fullmatch(request["id"])):
            request_id = request["id"]
        result = dispatch(request)
        answer = {"v": VERSION, "id": request_id, "ok": True, "result": result}
        if len(json.dumps(answer, ensure_ascii=False).encode("utf-8")) > MAX_RESPONSE:
            raise ProtocolError("RESPONSE_TOO_LARGE", "engine response exceeds 4 MiB")
        return answer
    except ProtocolError as exc:
        return {"v": VERSION, "id": request_id, "ok": False,
                "error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:  # noqa: BLE001 - keep protocol alive on unexpected engine failure
        print(f"transport fault: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {"v": VERSION, "id": request_id, "ok": False,
                "error": {"code": "INTERNAL", "message": "internal engine transport failure"}}


def main() -> None:
    while True:
        line = sys.stdin.buffer.readline(MAX_REQUEST + 1)
        if not line:
            return
        if len(line) > MAX_REQUEST and not line.endswith(b"\n"):
            while True:
                tail = sys.stdin.buffer.readline(MAX_REQUEST + 1)
                if not tail or tail.endswith(b"\n"):
                    break
        response = process(line)
        sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
