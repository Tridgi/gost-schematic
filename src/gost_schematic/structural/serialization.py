"""Strict, deterministic JSON v1 for experimental structural Э1 diagrams."""

import json
from fractions import Fraction
from typing import Any

from gost_schematic.core.geometry import Point, Side
from gost_schematic.structural.model import (
    BlockPort,
    FunctionalBlock,
    FunctionalLink,
    PortDirection,
    PortRef,
    StructuralDiagram,
)
from gost_schematic.structural.validation import validate_structural_diagram


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"{label}: expected keys {sorted(keys)}")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"{label}: expected JSON array")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label}: expected exact integer, not float or bool")
    return value


def _text(value: Any, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{label}: expected string")
    return value


def _fraction(value: Any) -> Fraction | None:
    if value is None:
        return None
    if type(value) is not list or len(value) != 2:
        raise ValueError("position must be null or [numerator,denominator]")
    numerator = _integer(value[0], "fraction numerator")
    denominator = _integer(value[1], "fraction denominator")
    if denominator <= 0:
        raise ValueError("fraction denominator must be positive")
    return Fraction(numerator, denominator)


def structural_to_json(diagram: StructuralDiagram) -> str:
    """Serialize ONLY a validated E1 graph, without inferred junctions/nets."""
    diagnostics = validate_structural_diagram(diagram)
    if diagnostics:
        raise ValueError("Invalid structural diagram: " + "; ".join(
            item.code for item in diagnostics
        ))
    result = {
        "schema_version": diagram.schema_version,
        "diagram_type": diagram.diagram_type,
        "blocks": [
            {
                "id": b.id, "name": b.name,
                "origin_um": [b.origin.x, b.origin.y],
                "width_um": b.width_um, "height_um": b.height_um,
            }
            for b in diagram.blocks
        ],
        "ports": [
            {
                "block_id": p.block_id, "id": p.id,
                "side": p.side.value, "direction": p.direction.value,
                "position": (
                    None if p.position is None
                    else [p.position.numerator, p.position.denominator]
                ),
            }
            for p in diagram.ports
        ],
        "links": [
            {
                "id": l.id,
                "source": {
                    "block_id": l.source.block_id, "port_id": l.source.port_id,
                },
                "target": {
                    "block_id": l.target.block_id, "port_id": l.target.port_id,
                },
            }
            for l in diagram.links
        ],
    }
    return json.dumps(
        result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False,
    ) + "\n"


def structural_from_json(raw: str) -> StructuralDiagram:
    """Strict v1 decoder: reject duplicate JSON keys and unknown model fields."""

    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError(f"Invalid nonfinite JSON constant {value}")

    data = json.loads(
        raw, object_pairs_hook=unique_keys, parse_constant=invalid_constant,
    )
    root = _object(
        data, {"schema_version", "diagram_type", "blocks", "ports", "links"}, "diagram",
    )
    version = _integer(root["schema_version"], "schema_version")
    diagram_type = _text(root["diagram_type"], "diagram_type")
    blocks: list[FunctionalBlock] = []
    for i, value in enumerate(_array(root["blocks"], "blocks")):
        item = _object(
            value, {"id", "name", "origin_um", "width_um", "height_um"},
            f"block #{i}",
        )
        position = _array(item["origin_um"], "origin_um")
        if len(position) != 2:
            raise ValueError("origin_um must contain exactly x and y")
        blocks.append(FunctionalBlock(
            _text(item["id"], "block id"),
            _text(item["name"], "block name"),
            Point(_integer(position[0], "x"), _integer(position[1], "y")),
            _integer(item["width_um"], "width_um"),
            _integer(item["height_um"], "height_um"),
        ))

    ports: list[BlockPort] = []
    for i, value in enumerate(_array(root["ports"], "ports")):
        item = _object(
            value, {"block_id", "id", "side", "direction", "position"},
            f"port #{i}",
        )
        ports.append(BlockPort(
            _text(item["block_id"], "port block_id"),
            _text(item["id"], "port id"),
            Side(_text(item["side"], "port side")),
            PortDirection(_text(item["direction"], "port direction")),
            _fraction(item["position"]),
        ))

    links: list[FunctionalLink] = []
    for i, value in enumerate(_array(root["links"], "links")):
        item = _object(value, {"id", "source", "target"}, f"link #{i}")
        refs = []
        for label in ("source", "target"):
            pair = _object(
                item[label], {"block_id", "port_id"}, f"link {label}",
            )
            refs.append(PortRef(
                _text(pair["block_id"], "port block ID"),
                _text(pair["port_id"], "port ID"),
            ))
        links.append(FunctionalLink(_text(item["id"], "link id"), *refs))

    diagram = StructuralDiagram(
        tuple(blocks), tuple(ports), tuple(links), version, diagram_type,
    )
    diagnostics = validate_structural_diagram(diagram)
    if diagnostics:
        raise ValueError("Invalid structural graph: " + "; ".join(
            item.code for item in diagnostics
        ))
    return diagram
