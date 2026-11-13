"""Independently check rendered E1 SVG geometry against the real model and PNG.

This gate reads the *actual path d coordinates*, not just SVG data attributes.
"""

import argparse
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops

from gost_schematic.structural import resolve_port_positions, structural_from_json

SVG = "{http://www.w3.org/2000/svg}"
COORDS = re.compile(r"[ML] (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)")


def actual_path_um(path_data: str) -> list[list[int]]:
    points = []
    for x, y in COORDS.findall(path_data):
        coordinates = [Fraction(x) * 1000, Fraction(y) * 1000]
        if any(v.denominator != 1 for v in coordinates):
            raise ValueError("SVG path contains non-integral micrometre coordinates")
        points.append([v.numerator for v in coordinates])
    return points


def verify(folder: Path) -> dict:
    source = (folder / "structural-e1.json").read_text(encoding="utf-8")
    diagram = structural_from_json(source)
    anchor = resolve_port_positions(diagram)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if (len(diagram.blocks), len(diagram.ports), len(diagram.links)) != (7, 18, 9):
        raise ValueError("E1 shared specimen is not 7 blocks / 18 ports / 9 links")
    if (manifest["block_count"], manifest["port_count"], manifest["link_count"]) != (
        7, 18, 9,
    ):
        raise ValueError("Visual manifest cardinality differs from model")
    expected = {
        (ref.block_id, ref.port_id): [p.x, p.y] for ref, p in anchor.items()
    }
    actual = {(row["ref"]["block_id"], row["ref"]["port_id"]): row["svg_um"]
              for row in manifest["ports"]}
    if expected != actual:
        raise ValueError("Model and SVG PortRef anchors disagree at 1µm precision")
    expected_links = {link.id: link for link in diagram.links}
    hashes = {}
    for variant in ("clean", "diagnostic"):
        path = folder / f"e1-seven-{variant}.svg"
        content = path.read_bytes()
        hashes[path.name] = hashlib.sha256(content).hexdigest()
        root = ET.fromstring(content)
        paths = root.findall(f".//{SVG}path[@data-role='functional-link']")
        arrows = root.findall(f".//{SVG}path[@data-role='functional-process-arrow']")
        if len(paths) != len(arrows) != 9 or len(paths) != 9:
            raise ValueError("Missing or excess visual directed links/arrows")
        by_link = {x.get("data-link-id"): x for x in paths}
        if set(by_link) != set(expected_links):
            raise ValueError("Visual link ID inventory differs from the semantic graph")
        for link_id, link in expected_links.items():
            elem = by_link[link_id]
            p = actual_path_um(elem.attrib["d"])
            serialized = json.loads(elem.attrib["data-points-um"])
            if p != serialized or not p:
                raise ValueError(f"{link_id}: actual SVG d path differs from metadata")
            src = [anchor[link.source].x, anchor[link.source].y]
            dst = [anchor[link.target].x, anchor[link.target].y]
            if p[0] != src or p[-1] != dst:
                raise ValueError(f"{link_id}: SVG path misses a true PortRef")
            if (elem.get("data-source-ref") != f"{link.source.block_id}:{link.source.port_id}"
                or elem.get("data-target-ref") !=
                f"{link.target.block_id}:{link.target.port_id}"):
                raise ValueError(f"{link_id}: true link identity or orientation changed")
            if sum(1 for a in arrows if a.get("data-link-id") == link_id) != 1:
                raise ValueError(f"{link_id}: exactly one directed process arrow required")
        if root.findall(f".//{SVG}circle[@data-role='junction']"):
            raise ValueError("False electrical junction printed on an E1 diagram")
        if variant == "diagnostic":
            markers = root.findall(f".//{SVG}circle[@data-role='declared-functional-port']")
            if len(markers) != 18:
                raise ValueError("Missing declared-port diagnostic markers")
            for point in markers:
                ref = tuple(point.get("data-portref", "").split(":", 1))
                if ref not in expected:
                    raise ValueError("Unknown SVG PortRef marker")
                x, y = Fraction(point.attrib["cx"]) * 1000, Fraction(point.attrib["cy"]) * 1000
                if [x, y] != expected[ref]:
                    raise ValueError("Diagnostic port marker drift")
        bitmap = folder / f"e1-seven-{variant}-4200px.png"
        with Image.open(bitmap) as im:
            im.load()
            if im.width != 4200 or im.height < 900 or im.mode not in ("RGB", "RGBA"):
                raise ValueError("Invalid high-resolution E1 PNG dimensions")
            if ImageChops.difference(im.convert("RGB"), Image.new("RGB", im.size, "white")).getbbox() is None:
                raise ValueError("E1 PNG is entirely empty/white")
        hashes[bitmap.name] = hashlib.sha256(bitmap.read_bytes()).hexdigest()
    if hashes["e1-seven-clean.svg"] != manifest["svg_sha256"]:
        raise ValueError("Manifest SVG SHA256 mismatch")
    if hashes["e1-seven-diagnostic.svg"] != manifest["diagnostic_svg_sha256"]:
        raise ValueError("Diagnostic SVG SHA256 mismatch")
    (folder / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())),
        encoding="utf-8",
    )
    return {"status": "PASS", "blocks": 7, "ports": 18, "links": 9, "hashes": hashes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output_dir), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
