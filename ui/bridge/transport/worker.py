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
                "capabilities": ["hello", "unit_roundtrip", "check_symbol", "render_symbol"],
                "project_write": False, "process": "ephemeral-or-supervised"}
    if op == "unit_roundtrip":
        return {"x_um": decimal_um(args.get("x_um")),
                "y_um": decimal_um(args.get("y_um"))}
    if op == "check_symbol" or op == "render_symbol":
        return _symbol_operation(args.get("symbol"), check=op == "check_symbol")
    if op in {"source_snapshot", "position_edit", "verify_net", "render_svg", "export_png"}:
        raise ProtocolError("NOT_WIRED", "awaiting #122 canonical model and #124 export adapter")
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
        if isinstance(request, dict) and isinstance(request.get("id"), str):
            if ID_RE.fullmatch(request["id"]):
                request_id = request["id"]
        result = dispatch(request)
        answer = {"v": VERSION, "id": request_id, "ok": True, "result": result}
        if len(json.dumps(answer, ensure_ascii=False).encode("utf-8")) > MAX_RESPONSE:
            raise ProtocolError("RESPONSE_TOO_LARGE", "engine response exceeds 4 MiB")
        return answer
    except ProtocolError as exc:
        return {"v": VERSION, "id": request_id, "ok": False,
                "error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:
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
