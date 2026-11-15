"""Dependency-free canonical SHA-256 for typed UGO physical geometry.

Uses the same algorithm as agent_project.catalog.value_digest, intentionally
without importing the higher-level AI/MCP project package. This keeps source
footprints consumable by real NET / PAINT / IC owner worktrees which have no
agent_project module. A compatibility regression pins the identical digest.
"""
import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any


def _normalized(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return format(value, "f")
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _normalized(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, (tuple, list)):
        return [_normalized(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _normalized(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise ValueError(
        f"UGO_DIGEST_UNSUPPORTED_TYPED_VALUE:{type(value).__name__}"
    )


def value_digest(value: Any) -> str:
    """Exact, deterministic old project SHA256 format, no sketchy fallback."""
    record = _normalized(value)
    encoded = json.dumps(
        record, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
