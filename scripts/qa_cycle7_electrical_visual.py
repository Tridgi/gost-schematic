"""Independent real ELEKTRIK #97/#98 DRAFT semantic and 2-sheet SVG proof.

Executes exact original owner Python, real Circuit.Net and canonical serializer.
Only real #98 owner draws continuation; it does NOT rasterize a real vendor IC.
"""
import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from qa_cycle7_electrical_sources import (
    BLOBS,
    SOURCE_COMMITS,
    real_electrical_sources,
)

SVG = "{http://www.w3.org/2000/svg}"


def run(dest):
    import cairosvg
    from PIL import Image

    dest.mkdir(parents=True, exist_ok=True)
    files = {}
    with real_electrical_sources() as (
        ic, ic_serde, demo_ic, _net, net_serde, demo_net,
    ):
        types = []
        for kind in (ic.IcKind.ANALOG, ic.IcKind.DIGITAL):
            for count in (2, 4, 8, 14, 40, 64):
                model = demo_ic.synthetic_ic(count, kind)
                original = ic_serde.ic_to_json(model)
                assert ic_serde.ic_from_json(original) == model
                points = ic.resolve_ic_pin_positions(
                    model.device, model.specs, model.placements
                )
                assert len(points) == count
                file = dest / f"real-owner97-{kind.value}-{count:02d}.json"
                file.write_text(original, encoding="utf-8")
                types.append({
                    "kind": kind.value, "pin_count": count,
                    "authoritative_pinref_count": len(points),
                    "physical_package_source": "SYNTHETIC-ONLY",
                    "split_units": len(model.device.units),
                })
                files[file.name] = sha256(file.read_bytes()).hexdigest()
        graph = demo_net.specimen()
        source = net_serde.netrefs_to_json(graph)
        assert net_serde.netrefs_from_json(source, graph.circuit) == graph
        for sheet in graph.sheets:
            svg = demo_net.sheet_svg(graph, sheet.id)
            root = ET.fromstring(svg)
            assert root.attrib["data-approval"] == "DRAFT_UNMEASURED_FONT"
            assert len(root.findall(
                f".//{SVG}line[@data-role='explicit-real-wire-stub']"
            )) == 1
            assert len(root.findall(
                f".//{SVG}path[@data-role='DRAFT-visual-continuation-marker']"
            )) == 1
            # There is NEVER a third long conductor between sheets.
            assert len(root.findall(f".//{SVG}line")) == 1
            assert not root.findall(f".//{SVG}circle[@data-role='junction']")
            s = dest / f"real-owner98-sheet-{sheet.number}.svg"
            p = dest / f"real-owner98-sheet-{sheet.number}-300dpi.png"
            s.write_text(svg, encoding="utf-8")
            cairosvg.svg2png(
                bytestring=svg.encode("utf-8"), write_to=str(p), dpi=300
            )
            with Image.open(p) as png:
                rgb = png.convert("RGB")
                ink = sum(1 for x in rgb.getdata() if max(x) < 100)
                assert ink > 20
            for file in (s, p):
                files[file.name] = sha256(file.read_bytes()).hexdigest()
        text = dest / "real-owner98-two-sheet-ctrl.json"
        text.write_text(source, encoding="utf-8")
        files[text.name] = sha256(text.read_bytes()).hexdigest()
        report = {
            "issue": 92, "owner_source_shas": SOURCE_COMMITS,
            "git_blob_provenance": BLOBS,
            "ic_12_synthetic_model_variants": types,
            "net_ref_one_real_circuit_net": graph.circuit.nets[0].name,
            "continuation_sheets": len(graph.sheets),
            "explicit_local_stub_count": len(graph.stubs),
            "cross_sheet_conductor_count": 0,
            "svg_raster_300_dpi": True,
            "named_net_sheet_text": "BLOCKED_UNMEASURED_OPENGOST_IN_OWNER98",
            "real_vendor_ic_part": "BLOCKED",
            "new_semiconductors_and_connectors": "BLOCKED",
            "full_mixed_E3": "BLOCKED",
            "file_sha256": files,
        }
        outfile = dest / "qa-cycle7-real-elektrik97-98.json"
        outfile.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output_dir))
