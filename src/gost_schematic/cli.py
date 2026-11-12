"""Command-line symbol inspection, diagnostics, and collision-safe labels."""

import argparse
from pathlib import Path

from gost_schematic.catalog.loader import load_symbol
from gost_schematic.core.diagnostics import Severity
from gost_schematic.core.geometry import SIDE_VECTORS, Line, Point
from gost_schematic.core.units import mm
from gost_schematic.engines.annotation.layout import (
    obstacles_for_component,
    bind_component_annotations,
    place_annotations,
)
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.engines.ports import pin_corridors_for_component
from gost_schematic.engines.routing.clearance import validate_wire_clearance
from gost_schematic.model.annotations import TextStyle
from gost_schematic.model.circuit import ComponentInstance
from gost_schematic.model.nominal_display import (
    NominalDisplayConfiguration,
    NominalDisplayMode,
    NominalDisplaySettings,
)
from gost_schematic.model.quantities import Quantity, Unit
from gost_schematic.model.obstacles import WireObstacle
from gost_schematic.rendering.annotation_svg import render_annotation_svg
from gost_schematic.rendering.svg import render_symbol_svg
from gost_schematic.validation.annotation_checks import annotation_obstacles
from gost_schematic.validation.symbol_checks import validate_symbol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gost-schematic")
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render-symbol", help="Render one symbol to an SVG")
    render.add_argument("symbol", type=Path)
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--review-overlay", action="store_true")

    annotated = commands.add_parser(
        "render-annotated-symbol", help="Render a symbol with protected text and pin corridors"
    )
    annotated.add_argument("symbol", type=Path)
    annotated.add_argument("--output", type=Path, required=True)
    annotated.add_argument("--ref", default="R1")
    annotated.add_argument("--value", default=None, help="Legacy literal text, not normalized")
    annotated.add_argument("--nominal", default=None, help="Physical quantity, exact decimal")
    annotated.add_argument("--unit", choices=[unit.value for unit in Unit])
    annotated.add_argument(
        "--nominal-mode",
        choices=[mode.value for mode in NominalDisplayMode],
        default=NominalDisplayMode.ESKD_COMPACT.value,
    )
    annotated.add_argument("--hide-nominal", action="store_true")
    annotated.add_argument("--strict-compact", action="store_true")
    annotated.add_argument("--font-file", type=Path, required=True)
    annotated.add_argument("--font-family", default="DejaVu Sans")
    annotated.add_argument("--size-mm", default="3.5")
    annotated.add_argument("--clearance-mm", default="0.5")
    annotated.add_argument("--review-overlay", action="store_true")
    annotated.add_argument("--show-pin-connections", action="store_true")

    check = commands.add_parser("check-symbol", help="Validate a symbol model")
    check.add_argument("symbol", type=Path)
    args = parser.parse_args(argv)
    symbol = load_symbol(args.symbol)
    errors = False
    for issue in validate_symbol(symbol):
        print(f"{issue.severity.value}: {issue.code}: {issue.message}")
        errors |= issue.severity == Severity.ERROR
    if errors:
        return 1

    if args.command == "check-symbol":
        return 0

    if args.command == "render-symbol":
        svg = render_symbol_svg(symbol, review_overlay=args.review_overlay)
    else:
        try:
            style = TextStyle(
                str(args.font_file), args.font_family,
                em_height_um=mm(args.size_mm),
                clearance_um=mm(args.clearance_mm),
            )
            if args.value is not None and args.nominal is not None:
                raise ValueError("--value and --nominal cannot be used together")
            if args.nominal is not None and args.unit is None:
                raise ValueError("--nominal requires --unit")
            nominal = (
                Quantity.from_unit(args.nominal, args.unit)
                if args.nominal is not None else None
            )
            instance = ComponentInstance(args.ref, "draft.part", nominal=nominal)
            config = NominalDisplayConfiguration(default=NominalDisplaySettings(
                mode=NominalDisplayMode(args.nominal_mode),
                show_nominal=not args.hide_nominal,
                strict_compact=args.strict_compact,
            ))
            bound = bind_component_annotations(
                symbol, instance, style, config,
                {"value": args.value} if args.value is not None else None,
            )
            for issue in bound.diagnostics:
                print(f"{issue.severity.value}: {issue.code}: {issue.message}")
            result = place_annotations(
                bound.requests, PillowTextMeasurer(),
                boxes=obstacles_for_component(symbol, instance),
            )
        except (OSError, ValueError, RuntimeError) as error:
            print(f"annotation error: {error}")
            return 1
        for issue in result.diagnostics:
            print(f"{issue.severity.value}: {issue.code}: {issue.message}")
        if not result.valid:
            return 1
        wires: tuple[WireObstacle, ...] = ()
        if args.show_pin_connections:
            corridors = pin_corridors_for_component(symbol, instance)
            connections = []
            for port in corridors:
                direction = SIDE_VECTORS[port.side]
                end = port.contact + Point(direction.x * mm(4), direction.y * mm(4))
                connections.append(WireObstacle(
                    f"{port.identifier}.demo",
                    Line(port.contact, end),
                    attached_pin=port.pin,
                ))
            wires = tuple(connections)
            body = obstacles_for_component(symbol, instance)[:1]
            obstacles = body + annotation_obstacles(result.placements)
            problems = validate_wire_clearance(
                wires, blocked=obstacles, corridors=corridors,
            )
            if problems:
                for problem in problems:
                    print(f"{problem.severity.value}: {problem.code}: {problem.message}")
                return 1
        svg = render_annotation_svg(
            symbol, instance, result.placements,
            wires=wires,
            review_overlay=args.review_overlay,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
