"""Explicit, reproducible selection of active Russian ESKD document editions.

A document never silently upgrades a future-effective rule before its
introduction date; early adoption must be opted into by exact standard ID.
Edition selection is distinct from compliance verification.
"""

from dataclasses import dataclass
from datetime import date

from gost_schematic.validation.dimensional_checks import load_requirements


_PREDECESSORS = {
    "ГОСТ Р 2.301-2026": "ГОСТ 2.301-68",
    "ГОСТ Р 2.303-2026": "ГОСТ 2.303-68",
    "ГОСТ Р 2.304-2026": "ГОСТ 2.304-81",
    "ГОСТ Р 2.105-2026": "ГОСТ Р 2.105-2019",
}


@dataclass(frozen=True, slots=True)
class StandardSelection:
    """Applied, pending and explicitly early-applied document designations."""

    as_of: date
    applied: tuple[str, ...]
    future_pending: tuple[str, ...]
    early_applied: tuple[str, ...]
    profile_id: str
    jurisdiction: str = "RU"


def resolve_standard_selection(
    document_date: date, *,
    early_adopt: tuple[str, ...] = (),
) -> StandardSelection:
    """Resolve only the versions already present in the saved registry.

    Forward-dated standards may require dedicated technical implementations.
    Their selection alone DOES NOT certify text, UGO or layout support.
    """
    if not isinstance(document_date, date):
        raise TypeError("Document date must be datetime.date")
    rules = load_requirements()
    pending = rules["pending_standards"]
    known = {item["designation"] for item in pending}
    if len(early_adopt) != len(set(early_adopt)) or set(early_adopt) - known:
        raise ValueError("Unknown or repeated early-adopted standard")
    active = set(rules["active_standards"])
    future = []
    opted = []
    for item in pending:
        standard = item["designation"]
        in_force = document_date >= date.fromisoformat(item["effective_on"])
        early = standard in early_adopt and not in_force
        if early and not item["early_application_permitted"]:
            raise ValueError(f"Early adoption forbidden for {standard}")
        if early or in_force:
            old = _PREDECESSORS.get(standard)
            if old is None or old not in active:
                raise ValueError(f"Missing or unknown predecessor for {standard}")
            active.remove(old)
            active.add(standard)
            if early:
                opted.append(standard)
        else:
            future.append(standard)

    return StandardSelection(
        as_of=document_date,
        applied=tuple(sorted(active)),
        future_pending=tuple(sorted(future)),
        early_applied=tuple(sorted(opted)),
        profile_id=rules["profile_id"],
    )
