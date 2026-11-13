"""Reproduce E1 typed-model ↔ actual YGO2 PR78 standalone view proof.

Command (from root, with PYTHONPATH=src;.):
python -m examples.verify_structural_e1_ygo2 \
    --ygo-source output/ygo2_design_qa.py --output-dir output/e1-interop

YGO2 source must be obtained from the exact PR78 HEAD, not a substitute renderer.
This independent verification does not install, merge or edit that source.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from examples.review_structural_e1 import specimen, ygo2_visual_seed
from gost_schematic.structural import (
    PortRef,
    resolve_port_positions,
    structural_from_json,
    structural_to_json,
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def verify(source: Path, output: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("_ygo2_pr78_standalone_qa", source)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load real YGO2 source for independent verification")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    model = specimen()
    view = ygo2_visual_seed()
    resolved = module.validate_design(view)
    assert (len(resolved["blocks"]), len(resolved["links"])) == (7, 9)
    assert resolved["electrical_nets"] is None
    anchors = resolve_port_positions(model)
    visual_anchors = {
        PortRef(block["id"], pid): tuple(port["point_um"])
        for block in resolved["blocks"]
        for pid, port in block["ports"].items()
    }
    assert len(visual_anchors) == 18
    assert visual_anchors == {
        ref: (point.x, point.y) for ref, point in anchors.items()
    }, "Real PR78 visual coordinates diverged from typed E1 PortRef positions"

    for item in resolved["links"]:
        authored = next(l for l in model.links if l.id == item["id"])
        assert item["source"] == {
            "block_id": authored.source.block_id,
            "port_id": authored.source.port_id,
        }
        assert item["target"] == {
            "block_id": authored.target.block_id,
            "port_id": authored.target.port_id,
        }
        assert tuple(item["path_um"][0]) == visual_anchors[authored.source]
        assert tuple(item["path_um"][-1]) == visual_anchors[authored.target]
        assert item["arrow_at"] == "target"
    assert len({l.id for l in model.links}) == 9

    projected = module.semantic_projection(view)
    # PR78 proposal currently omits the coordinator's mandatory constant E1
    # discriminator. Apply ONLY this EXPLICIT test adapter; keep strict parser.
    adapter_delta = []
    if "diagram_type" not in projected:
        projected = {"diagram_type": "E1", **projected}
        adapter_delta.append("diagram_type:E1 (required but omitted by PR78 projection)")
    else:
        assert projected["diagram_type"] == "E1"
    canonical = json.loads(structural_to_json(model))
    assert projected == canonical, "YGO2 PR78 projected schema mismatches typed E1"
    assert structural_from_json(json.dumps(projected)) == model
    assert structural_from_json(structural_to_json(model)) == model

    output.mkdir(parents=True, exist_ok=True)
    clean = module.render_svg(view)
    diagnostic = module.render_svg(view, diagnostic=True)
    (output / "ygo2-seven-clean.svg").write_text(clean, encoding="utf-8")
    (output / "ygo2-seven-diagnostic.svg").write_text(diagnostic, encoding="utf-8")

    fixture_dir = Path(__file__).resolve().parents[1] / "tests/fixtures/structural-e1"
    for name, result in (
        ("ygo2-seven-clean.svg", clean),
        ("ygo2-seven-diagnostic.svg", diagnostic),
    ):
        assert (fixture_dir / name).read_text(encoding="utf-8") == result
    data = {
        "status": "DRAFT_TYPED_E1_YGO2_PR78_INTEROP",
        "diagram_type": "E1",
        "block_count": 7,
        "port_count": len(visual_anchors),
        "link_count": len(model.links),
        "coincident_port_count": 0,
        "auto_electrical_nets": 0,
        "anchor_mismatch_count": 0,
        "ygo_source_git_blob": hashlib.sha1(
            b"blob " + str(len(source.read_bytes())).encode() + b"\0"
            + source.read_bytes(),
        ).hexdigest(),
        "ygo_source_sha256": _sha256(source.read_bytes()),
        "model_json_sha256": _sha256(structural_to_json(model).encode("utf-8")),
        "visual_fixture_sha256": _sha256(
            json.dumps(view, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
            + b"\n"
        ),
        "clean_svg_sha256": _sha256(clean.encode("utf-8")),
        "diagnostic_svg_sha256": _sha256(diagnostic.encode("utf-8")),
        "single_adapter_delta": adapter_delta,
        "notes": (
            "Only exact source and SVG geometry verified. This does not certify "
            "font ink dimensions, GOST spacing or a production routed overlay."
        ),
    }
    (output / "interop-report.json").write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ygo-source", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.ygo_source, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
