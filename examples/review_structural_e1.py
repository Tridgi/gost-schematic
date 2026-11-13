"""Seven-block experimental typed E1 graph and matching YGO2 visual seed.

Run: python -m examples.review_structural_e1 --output-dir output/structural-e1
The model is the source of truth for semantic IDs, exact Fraction positions and
directed links; the visual seed is a provisional rendering overlay, NOT a GOST
approval or an electrically conducting Circuit.
"""

import argparse
import json
from decimal import Decimal
from fractions import Fraction
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
    validate_port_clearances,
    validate_structural_diagram,
)

IN = PortDirection.INPUT
OUT = PortDirection.OUTPUT


def specimen() -> StructuralDiagram:
    """7 functional blocks, 18 stable declared side ports and 9 process links."""
    blocks = (
        FunctionalBlock("B1", "ДАТЧИК СИГНАЛА", Point(46000, 25000), 48000, 30000),
        FunctionalBlock("B2", "ОБРАБОТКА СИГНАЛА", Point(142000, 22000), 56000, 36000),
        FunctionalBlock("B3", "МОДУЛЬ СВЯЗИ", Point(252000, 22000), 56000, 36000),
        FunctionalBlock("B4", "СИСТЕМА ИНДИКАЦИИ", Point(250000, 102000), 60000, 36000),
        FunctionalBlock("B5", "УПРАВЛЯЮЩИЙ БЛОК", Point(142000, 102000), 56000, 36000),
        FunctionalBlock("B6", "ИСПОЛНИТЕЛЬНЫЙ УЗЕЛ", Point(40000, 102000), 60000, 36000),
        FunctionalBlock("B7", "ОБРАТНАЯ СВЯЗЬ", Point(352000, 102000), 56000, 36000),
    )

    def port(b: str, i: str, side: Side, direction: PortDirection,
             fraction: Fraction = Fraction(1, 2)) -> BlockPort:
        return BlockPort(b, i, side, direction, fraction)

    ports = (
        port("B1", "data_out", Side.RIGHT, OUT),
        port("B2", "data_in", Side.LEFT, IN),
        port("B2", "a", Side.RIGHT, OUT, Fraction(1, 4)),
        port("B2", "b", Side.RIGHT, OUT),
        port("B2", "c", Side.RIGHT, OUT, Fraction(3, 4)),
        port("B3", "a", Side.LEFT, IN, Fraction(1, 4)),
        port("B3", "b", Side.LEFT, IN),
        port("B3", "c", Side.LEFT, IN, Fraction(3, 4)),
        port("B3", "out", Side.BOTTOM, OUT),
        port("B4", "in", Side.TOP, IN),
        port("B4", "out", Side.LEFT, OUT),
        port("B4", "branch_out", Side.RIGHT, OUT),
        port("B5", "in", Side.RIGHT, IN),
        port("B5", "out", Side.LEFT, OUT),
        port("B6", "in", Side.RIGHT, IN),
        port("B6", "feedback_in", Side.BOTTOM, IN),
        port("B7", "branch_in", Side.LEFT, IN),
        port("B7", "feedback_out", Side.BOTTOM, OUT),
    )
    link_pairs = (
        ("L1", "B1", "data_out", "B2", "data_in"),
        ("L2", "B2", "a", "B3", "a"),
        ("L3", "B2", "b", "B3", "b"),
        ("L4", "B2", "c", "B3", "c"),
        ("L5", "B3", "out", "B4", "in"),
        ("L6", "B4", "out", "B5", "in"),
        ("L7", "B5", "out", "B6", "in"),
        ("L8", "B4", "branch_out", "B7", "branch_in"),
        ("L9", "B7", "feedback_out", "B6", "feedback_in"),
    )
    links = tuple(
        FunctionalLink(identifier, PortRef(src, src_port), PortRef(dst, dst_port))
        for identifier, src, src_port, dst, dst_port in link_pairs
    )
    diagram = StructuralDiagram(blocks, ports, links)
    if validate_structural_diagram(diagram):
        raise AssertionError("Semantic E1 specimen invalid")
    if validate_port_clearances(diagram):
        raise AssertionError("YGO2 editorial 5mm/6mm port clearances not met")
    return diagram


def _decimal_fraction(value: Fraction) -> str:
    """Only terminating decimals are emitted for this view; no float rounding."""
    result = Decimal(value.numerator) / Decimal(value.denominator)
    if Fraction(result) != value:
        raise ValueError("Nonterminating Fraction needs a YGO2 rational view adapter")
    return str(result)


def ygo2_visual_seed() -> dict[str, object]:
    """A reproducible unrotated view input for PR78's actual validate_design.

    Only visual-specific title_lines/code, arrow_at and via_um are appended.
    Semantic fields derive EXCLUSIVELY from the typed model, not independent IDs.
    """
    diagram = specimen()
    ports_by_block: dict[str, list[BlockPort]] = {block.id: [] for block in diagram.blocks}
    for port in diagram.ports:
        ports_by_block[port.block_id].append(port)
    blocks = []
    for block in diagram.blocks:
        title_lines = block.name.split(" ", 1)
        if " ".join(title_lines) != block.name:
            raise AssertionError("Title does not reconstruct semantic block name")
        blocks.append({
            "id": block.id,
            "name": block.name,
            "title_lines": title_lines,
            "code": "ФБ" + block.id[1:],
            "center_um": [
                block.origin.x + block.width_um // 2,
                block.origin.y + block.height_um // 2,
            ],
            "size_um": [block.width_um, block.height_um],
            "ports": [
                {
                    "id": p.id, "side": p.side.name,
                    "relative_position": _decimal_fraction(p.position),
                    "direction": p.direction.value,
                }
                for p in ports_by_block[block.id]
            ],
        })
    links = []
    for link in diagram.links:
        row: dict[str, object] = {
            "id": link.id,
            "source": {"block_id": link.source.block_id, "port_id": link.source.port_id},
            "target": {"block_id": link.target.block_id, "port_id": link.target.port_id},
            "arrow_at": "target",
        }
        if link.id == "L9":
            # View-only dogleg below all second-row blocks. The chord belongs
            # to semantic inspection, not electrical or visual conductivity.
            row["via_um"] = [[380000, 180000], [70000, 180000]]
        links.append(row)
    return {
        "schema_version": 1, "diagram_type": "E1", "status": "DRAFT",
        "blocks": blocks, "links": links,
    }


def report() -> dict[str, object]:
    diagram = specimen()
    positions = resolve_port_positions(diagram)
    return {
        "status": "EXPERIMENTAL_E1_SCHEMA_NOT_ESKD_APPROVED",
        "diagram_type": diagram.diagram_type,
        "schema_version": diagram.schema_version,
        "blocks": len(diagram.blocks), "ports": len(diagram.ports),
        "links": len(diagram.links), "electrical_nets": None,
        "diagnostics": [],
        "port_anchors_um": [
            {
                "block_id": ref.block_id, "port_id": ref.port_id,
                "point_um": [pt.x, pt.y],
            }
            for ref, pt in sorted(
                positions.items(), key=lambda item: (item[0].block_id, item[0].port_id)
            )
        ],
        "inspection_chords_um": [
            {
                "link_id": link.id,
                "source": [positions[link.source].x, positions[link.source].y],
                "target": [positions[link.target].x, positions[link.target].y],
                "arrow": "source_to_target",
            }
            for link in diagram.links
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source = structural_to_json(specimen())
    if structural_to_json(structural_from_json(source)) != source:
        raise AssertionError("Structural E1 JSON roundtrip drift")
    for name, content in (
        ("structural-e1.json", source),
        ("structural-e1-review.json", json.dumps(
            report(), ensure_ascii=False, sort_keys=True, indent=2,
        ) + "\n"),
        ("ygo2-seven-view.json", json.dumps(
            ygo2_visual_seed(), ensure_ascii=False, sort_keys=True, indent=2,
        ) + "\n"),
    ):
        path = args.output_dir / name
        path.write_text(content, encoding="utf-8")
        print(f"Created {path}")


if __name__ == "__main__":
    main()
