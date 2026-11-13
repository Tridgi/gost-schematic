"""Deterministic, package-wide GOST Schematic catalogue audit.

This is a STRUCTURAL gate, not a claim that the drawings satisfy ГОСТ.
The program intentionally reports DRAFT and unmodeled physical parts.
"""

import argparse
import json
from hashlib import sha256
from importlib.resources import files
from pathlib import Path

from gost_schematic.catalog.inductors import load_inductor
from gost_schematic.catalog.loader import load_symbol
from gost_schematic.catalog.part_loader import load_part
from gost_schematic.core.diagnostics import Diagnostic, Severity
from gost_schematic.core.units import format_mm
from gost_schematic.model.part import PartDefinition
from gost_schematic.model.symbol import SymbolDefinition
from gost_schematic.validation.conductor_checks import inspect_conductor_topology
from gost_schematic.validation.dimensional_checks import check_verified_dimensions
from gost_schematic.validation.symbol_checks import validate_symbol


def _box_mm(box) -> list[str]:
    return [
        format_mm(value)
        for value in (box.min_x, box.min_y, box.max_x, box.max_y)
    ]


def _entry(
    symbol: SymbolDefinition, source: Path, path: str,
    part: PartDefinition | None,
) -> dict[str, object]:
    checks = list(validate_symbol(symbol))
    traced = inspect_conductor_topology(symbol)
    normative = check_verified_dimensions(symbol)
    checks.extend(normative.diagnostics)
    if symbol.conductor_topology is None:
        checks.append(Diagnostic(
            "TOPOLOGY_REQUIRED_IN_CATALOG", Severity.ERROR,
            "Catalog symbol must declare its conducting-ink graph",
            symbol.identifier,
        ))
    graphic = {pin.number for pin in symbol.pins}
    if part is not None and (
        part.symbol_id != symbol.identifier
        or part.identifier != symbol.identifier
        or graphic != {pin.number for pin in part.pins}
    ):
        checks.append(Diagnostic(
            "PIN_MAPPING_MISMATCH", Severity.ERROR,
            f"Physical part and graphic pin map disagree for {symbol.identifier}",
            symbol.identifier,
        ))
    source_hash = sha256(source.read_bytes()).hexdigest()
    roles = {pin.number: pin for pin in part.pins} if part is not None else {}
    problems = [
        {"code": item.code, "severity": item.severity.value}
        for item in checks
    ]
    return {
        "id": symbol.identifier,
        "source": path,
        "source_sha256": source_hash,
        "revision": symbol.revision,
        "approval": symbol.status.value,
        "physical_part_mapped": part is not None,
        "physical_model_gap": (
            "Physical part model not supplied yet"
            if part is None else None
        ),
        "pin_count": len(symbol.pins),
        "pins": [
            {
                "number": pin.number,
                "side": pin.side.value,
                "at_mm": [format_mm(pin.at.x), format_mm(pin.at.y)],
                "name": roles[pin.number].name if pin.number in roles else None,
                "function": (
                    roles[pin.number].function.value
                    if pin.number in roles else None
                ),
            }
            for pin in symbol.pins
        ],
        "strokes": len(symbol.graphics),
        "conductor_topology": {
            "declared": symbol.conductor_topology is not None,
            "checked_strokes": traced.visited_primitives,
            "authored_junctions": traced.explicit_junctions,
            "pin_islands": [list(group) for group in traced.pin_islands],
            "valid": traced.valid if symbol.conductor_topology is not None else False,
            "diagnostics": [
                {"code": issue.code, "severity": issue.severity.value}
                for issue in traced.diagnostics
            ],
        },
        "un-stroked_bounds_mm": _box_mm(symbol.bounds),
        "stroked_bounds_mm": _box_mm(symbol.stroked_bounds),
        "normative_references": list(symbol.standard_refs),
        "verified_dimension_rules": list(normative.passed_rules),
        "applicable_dimension_rules": list(normative.applicable_rules),
        "dimension_status": (
            "verified_selected_dimensions" if normative.applicable_rules and normative.valid
            else "dimension_mismatch" if normative.applicable_rules
            else "not_yet_verifiable"
        ),
        "diagnostics": problems,
    }


def audit_catalog() -> dict[str, object]:
    root = Path(str(files("gost_schematic").joinpath("catalog")))
    source_symbols = sorted((root / "symbols").rglob("*.json"))
    source_inductors = sorted((root / "inductors").glob("*.json"))
    entries = []

    for source in source_symbols:
        symbol = load_symbol(source)
        # Match *every* static UGO to its independently versioned physical
        # passport by its catalog-relative path. Never special-case resistor/
        # capacitor families: new diodes (and later families) must not appear
        # as physically unmodelled in an otherwise green structural audit.
        physical_source = root / "parts" / source.relative_to(root / "symbols")
        part = load_part(physical_source) if physical_source.is_file() else None
        path = "catalog/" + source.relative_to(root).as_posix()
        entries.append(_entry(symbol, source, path, part))

    for source in source_inductors:
        variant = load_inductor(source)
        path = "catalog/" + source.relative_to(root).as_posix()
        entries.append(_entry(variant.symbol, source, path, variant.part))

    entries.sort(key=lambda item: item["id"])
    errors = [
        f"{item['id']}: {issue['code']}"
        for item in entries
        for issue in item["diagnostics"]
        if issue["severity"] == "error"
    ]
    return {
        "schema_version": 1,
        "audit_scope": "structural and geometric only; NOT normative certification",
        "total_symbols": len(entries),
        "hard_errors": len(errors),
        "error_details": errors,
        "draft_count": sum(item["approval"] == "draft" for item in entries),
        "topologies_verified": sum(
            bool(item["conductor_topology"]["valid"]) for item in entries
        ),
        "symbols_with_checked_dimensions": sum(
            bool(item["applicable_dimension_rules"]) for item in entries
        ),
        "without_physical_part": [
            item["id"] for item in entries if not item["physical_part_mapped"]
        ],
        "entries": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=Path("output/catalog-integrity-audit.json"),
    )
    args = parser.parse_args(argv)
    report = audit_catalog()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Audited {report['total_symbols']} symbols; "
        f"{report['draft_count']} draft; {report['hard_errors']} hard errors"
    )
    print(f"Created {args.output}")
    return 1 if report["hard_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
