"""Architectural constraints: no upward or cross-engine imports in shared layers."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "gost_schematic"

RESTRICTIONS = {
    "core": (
        "gost_schematic.model",
        "gost_schematic.engines",
        "gost_schematic.rendering",
        "gost_schematic.validation",
    ),
    "model": (
        "gost_schematic.engines",
        "gost_schematic.rendering",
        "gost_schematic.validation",
    ),
    "engines/routing": ("gost_schematic.engines.annotation",),
}


def test_dependency_direction_is_explicit():
    violations = []
    for area, forbidden in RESTRICTIONS.items():
        for source in sorted((ROOT / area).rglob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported = (node.module or "").strip()
                    modules = (imported,)
                elif isinstance(node, ast.Import):
                    modules = tuple(alias.name for alias in node.names)
                else:
                    continue
                for module in modules:
                    if any(
                        module == prefix or module.startswith(f"{prefix}.")
                        for prefix in forbidden
                    ):
                        violations.append(f"{source.relative_to(ROOT)} imports {module}")
    assert not violations, "\n".join(violations)
