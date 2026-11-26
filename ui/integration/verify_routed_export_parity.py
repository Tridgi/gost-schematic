"""Compare actual routed browser evidence with canonical Python SVG/PNG300.

This uses the native export engine, not an installed Windows GUI. The
browser and Python renderers may rasterize preview fonts differently.
Require matching label geometry and semantic inventory, not PNG byte parity.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ui.bridge.export.canonical import ExportRequest
from ui.bridge.export.project_v2 import export_v2
from ui.editor.src.model.contract import digest, strict_loads

S = "{http://www.w3.org/2000/svg}"


def labels(root):
    result = {}
    for group in root.findall(".//" + S + "g[@data-layer='component-labels']"):
        for text in group.findall(S + "text"):
            key = group.get("data-instance-id"), text.get("data-label-role")
            assert key not in result, f"duplicate label: {key}"
            result[key] = (
                text.text, Decimal(text.get("x")), Decimal(text.get("y")),
                Decimal(text.get("font-size")), text.get("text-anchor"),
            )
    return result


def net_inventory(root):
    metadata = root.find(".//" + S + "metadata[@data-kind='source-netlist']")
    return json.loads(metadata.text)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.evidence / "report.json").read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    report = {"scope": "native Python preview export, not Windows GUI acceptance",
              "font_status": "unverified-preview", "stages": []}
    for stage in manifest["stages"]:
        name = stage["name"]
        project_bytes = (args.evidence / (name+".gscad.json")).read_bytes()
        browser_bytes = (args.evidence / (name+".svg")).read_bytes()
        assert sha(project_bytes) == stage["sha256"]["project"]
        assert sha(browser_bytes) == stage["sha256"]["svg"]
        doc = strict_loads(project_bytes)
        revision = digest(doc)
        sheet = doc["project"]["sheets"][0]
        req = ExportRequest(page="A3", orientation="landscape", dpi=300,
                            include_frame=False, include_title=False, strict_font=False)
        exported = export_v2(doc, sheet["id"], req, expected_project_sha256=revision)
        native = ET.fromstring(exported.svg)
        browser = ET.fromstring(browser_bytes)
        expected = labels(browser)
        actual = labels(native)
        assert len(expected) == len(actual) == 23, (name, len(expected), len(actual))
        assert actual == expected, (name, {k: (expected.get(k), actual.get(k))
                                        for k in expected.keys() | actual.keys()
                                        if expected.get(k) != actual.get(k)})
        assert native.get("data-component-label-count") == "23"
        assert native.get("data-unplaced-label-count") == "0"
        assert native.get("data-source-project-sha256") == revision
        assert net_inventory(native) == net_inventory(browser)
        assert len(net_inventory(native)) == 15
        assert sum(len(n["members"]) for n in net_inventory(native)) == 62
        assert len(native.findall(".//"+S+"g[@data-kind='source_b_continuation']")) == 2
        assert len(native.findall(".//"+S+"g[@data-layer='wires']")) == len(sheet["wires"])
        assert len(native.findall(".//"+S+"circle[@data-layer='explicit-junctions']")) == len(sheet["junctions"])
        assert exported.pixels == (4961, 3508)
        with Image.open(io.BytesIO(exported.png)) as png:
            assert png.size == (4961, 3508)
            assert all(abs(d-300) < 0.02 for d in png.info["dpi"])
        assert "FONT_RENDER_UNVERIFIED" in exported.warnings
        assert "COMPONENT_LABELS_UNPLACED" not in exported.warnings
        assert digest(doc) == revision
        (args.out / (name+".native.svg")).write_bytes(exported.svg)
        (args.out / (name+".native.png")).write_bytes(exported.png)
        report["stages"].append({"name": name, "labels": 23, "label_geometry_parity": True,
                                 "nets": 15, "pinrefs": 62, "project_sha256": revision,
                                 "png_pixels": list(exported.pixels), "dpi": 300,
                                 "svg_sha256": sha(exported.svg), "png_sha256": sha(exported.png),
                                 "warnings": list(exported.warnings)})
    assert [s["name"] for s in report["stages"]] == [
        "01-inset-routing", "02-functional-routing", "03-refined-routing",
        "04-extended-routing", "05-common-trunks",
    ]
    (args.out / "report.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print("TL494_R32L_NATIVE_PARITY "+json.dumps(report))


if __name__ == "__main__":
    main()
