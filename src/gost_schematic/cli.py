"""Minimal command-line symbol inspection and geometry validation."""
import argparse
from pathlib import Path

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.diagnostics import Severity
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.symbol_checks import validate_symbol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gost-schematic")
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render-symbol", help="Render one catalog symbol to SVG")
    render.add_argument("symbol", type=Path)
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--review-overlay", action="store_true")
    check = commands.add_parser("check-symbol", help="Validate symbol model")
    check.add_argument("symbol", type=Path)
    args = parser.parse_args(argv)
    symbol = load_symbol(args.symbol)
    errors = False
    for issue in validate_symbol(symbol):
        print(f"{issue.severity.value}: {issue.code}: {issue.message}")
        errors |= issue.severity == Severity.ERROR
    if errors:
        return 1
    if args.command == "render-symbol":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            render_symbol_svg(symbol, review_overlay=args.review_overlay),
            encoding="utf-8",
        )
        print(f"Created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
