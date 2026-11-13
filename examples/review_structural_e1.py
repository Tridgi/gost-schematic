"""Seven-block structural Э1 example. Run:

python -m examples.review_structural_e1 --output-dir output/structural-e1

Functional arrows connect only declared logical side ports; this is NOT an
electrical circuit, UGO, auto-layout or approved ESKD sheet rendering.
"""

import argparse
import json
from pathlib import Path

from gost_schematic.core.geometry import Point, Side
from gost_schematic.structural import (
    BlockPort,
    FunctionalBlock,
    FunctionalLink,
    PortDirection,
    PortRef,
    StructuralDiagram,
    resolve_port_positions,
    structural_from_json,
    structural_to_json,
    validate_structural_diagram,
)

IN = PortDirection.INPUT
OUT = PortDirection.OUTPUT


def specimen() -> StructuralDiagram:
    blocks = (
        FunctionalBlock("POWER", "Питание", Point(0, 0), 20000, 12000),
        FunctionalBlock("ENTRY", "Ввод команд", Point(40000, 0), 20000, 12000),
        FunctionalBlock("CTRL", "Контроллер", Point(80000, 0), 20000, 12000),
        FunctionalBlock("SENSOR", "Датчик", Point(0, 30000), 20000, 12000),
        FunctionalBlock("ADAPT", "Согласование", Point(40000, 30000), 20000, 12000),
        FunctionalBlock("ACT", "Исполнитель", Point(80000, 30000), 20000, 12000),
        FunctionalBlock("DISPLAY", "Индикация", Point(120000, 0), 20000, 12000),
    )
    ports = (
        BlockPort("POWER", "feed", Side.RIGHT, OUT),
        BlockPort("ENTRY", "supply", Side.LEFT, IN),
        BlockPort("ENTRY", "cmd1", Side.RIGHT, OUT),
        BlockPort("ENTRY", "cmd2", Side.RIGHT, OUT),
        BlockPort("ENTRY", "feedback", Side.BOTTOM, IN),
        BlockPort("CTRL", "cmd1", Side.LEFT, IN),
        BlockPort("CTRL", "cmd2", Side.LEFT, IN),
        BlockPort("CTRL", "display", Side.RIGHT, OUT),
        BlockPort("CTRL", "actuate", Side.BOTTOM, OUT),
        BlockPort("SENSOR", "measurement", Side.RIGHT, OUT),
        BlockPort("ADAPT", "sensor", Side.LEFT, IN),
        BlockPort("ADAPT", "actuate", Side.RIGHT, OUT),
        BlockPort("ADAPT", "feedback", Side.TOP, OUT),
        BlockPort("ACT", "command", Side.LEFT, IN),
        BlockPort("ACT", "control", Side.TOP, IN),
        BlockPort("ACT", "state", Side.RIGHT, OUT),
        BlockPort("DISPLAY", "status", Side.LEFT, IN),
        BlockPort("DISPLAY", "alarm", Side.BOTTOM, IN),
    )

    def link(identifier: str, a: str, x: str, b: str, y: str) -> FunctionalLink:
        return FunctionalLink(identifier, PortRef(a, x), PortRef(b, y))

    links = (
        link("L01", "POWER", "feed", "ENTRY", "supply"),
        link("L02", "ENTRY", "cmd1", "CTRL", "cmd1"),
        link("L03", "ENTRY", "cmd2", "CTRL", "cmd2"),
        link("L04", "SENSOR", "measurement", "ADAPT", "sensor"),
        link("L05", "ADAPT", "actuate", "ACT", "command"),
        link("L06", "CTRL", "display", "DISPLAY", "status"),
        link("L07", "CTRL", "actuate", "ACT", "control"),
        link("L08", "ADAPT", "feedback", "ENTRY", "feedback"),
        link("L09", "ACT", "state", "DISPLAY", "alarm"),
    )
    result = StructuralDiagram(blocks, ports, links, schema_version=1)
    problems = validate_structural_diagram(result)
    if problems:
        raise AssertionError(f"Invalid authored E1 example: {problems}")
    return result


def report() -> dict[str, object]:
    diagram = specimen()
    ports = resolve_port_positions(diagram)
    data = {
        "status": "EXPERIMENTAL_E1_SCHEMA_NOT_ESKD_APPROVED",
        "schema_version": diagram.schema_version,
        "blocks": len(diagram.blocks),
        "ports": len(diagram.ports),
        "links": len(diagram.links),
        "diagnostics": [],
        "port_anchors_um": [
            {
                "block_id": ref.block_id, "port_id": ref.port_id,
                "point_um": [position.x, position.y],
            }
            for ref, position in sorted(
                ports.items(), key=lambda item: (item[0].block_id, item[0].port_id)
            )
        ],
        "inspection_chords_um": [
            {
                "link_id": link.id,
                "source": [ports[link.source].x, ports[link.source].y],
                "target": [ports[link.target].x, ports[link.target].y],
                "arrow": "source_to_target",
            }
            for link in diagram.links
        ],
    }
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source = structural_to_json(specimen())
    if structural_to_json(structural_from_json(source)) != source:
        raise AssertionError("Structural E1 JSON roundtrip drift")
    for name, data in (
        ("structural-e1.json", source),
        ("structural-e1-review.json", json.dumps(
            report(), ensure_ascii=False, sort_keys=True, indent=2,
        ) + "\n"),
    ):
        path = args.output_dir / name
        path.write_text(data, encoding="utf-8")
        print(f"Created {path}")


if __name__ == "__main__":
    main()
