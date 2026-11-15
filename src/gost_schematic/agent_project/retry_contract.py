"""Machine-readable fail-closed recovery advice for read-only AI consumers.

Only a trusted host may refresh a saved project snapshot. This module NEVER
modifies source BOM, physical Net/PinRef, revisions, or project storage.
No general MCP authoring/retry endpoint is implied by these diagnostics.
"""
from typing import Any

_STAGES = {
    "TI_TL494_16_PIN_P11_ADAPTER_NOT_INSTALLED": "SOURCE_MODEL",
    "SOURCE_62_PINREF_MEMBERSHIP_NOT_VERIFIED_IN_P11": "SOURCE_MODEL",
    "GLOBAL_15_NET_ROUTER_NOT_ACCEPTED": "ROUTING",
    "PRINT_INK_AND_A3_DRC_NOT_ACCEPTED": "ERC_DRC",
    "NO_TRUSTED_TYPED_GENERATOR_OR_CAS_COMMIT": "COMMIT_GATE",
}
_SAFE_READ_REFRESH = frozenset({"REQUEST_STALE_REVISION"})


def readonly_error_diagnostic(code: str) -> dict[str, Any]:
    """Only an authorized fresh read can be retried, once; never retry writes.

    An obsolete expected_revision/generation is not automatically replaced:
    the host must obtain a NEW authorized snapshot and rerun full source,
    physical PinRef/Net and catalogue SHA verification first.
    Unknown codes and invalid input always fail closed.
    """
    if type(code) is not str or not code:
        code = "REQUEST_FAILED"
    refresh = code in _SAFE_READ_REFRESH
    return {
        "code": code,
        "stage": "SOURCE_MODEL",
        "severity": "ERROR",
        "retryable_read_only": refresh,
        "retry_mode": "REFETCH_AUTHORIZED_SNAPSHOT" if refresh else "NO_RETRY",
        "max_retry_attempts": 1 if refresh else 0,
        "requires_full_source_revalidation": refresh,
        "source_model_mutation_allowed": False,
        "net_or_pinref_mutation_allowed": False,
        "mcp_write_allowed": False,
    }


def blocked_generation_diagnostics(reasons: list[str]) -> list[dict[str, Any]]:
    """Map unavailable generator stages to immutable, non-retryable blockers."""
    if type(reasons) is not list or any(type(code) is not str for code in reasons):
        raise ValueError("BLOCKER_REASONS_INVALID")
    return [{
        "code": code,
        "stage": _STAGES.get(code, "SOURCE_MODEL"),
        "severity": "BLOCKED",
        "retryable_read_only": False,
        "retry_mode": "AWAIT_INDEPENDENT_ACCEPTANCE",
        "max_retry_attempts": 0,
        "source_model_mutation_allowed": False,
        "net_or_pinref_mutation_allowed": False,
        "mcp_write_allowed": False,
    } for code in reasons]
