"""Executable Windows smoke against the *packaged* fixed Python sidecar.

No user-controlled file path or subprocess command enters the IPC request.
Both formats must come from the same real E695 source ProjectV2; PNG must
be rasterized by the canonical Python export backend, not a browser screenshot.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from PIL import Image


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def request(exe: Path, op: str, args: dict, rid: str) -> dict:
    payload = json.dumps({"v": 1, "id": rid, "op": op, "args": args}, separators=(",", ":")) + "\n"
    proc = subprocess.run(
        [str(exe)], input=payload, text=True, capture_output=True, timeout=90,
        check=False, encoding="utf-8",
    )
    require(proc.returncode == 0, f"{op}: sidecar exited {proc.returncode}: {proc.stderr[-600:]}")
    rows = [row for row in proc.stdout.splitlines() if row.strip()]
    require(len(rows) == 1, f"{op}: expected one bounded JSON reply")
    result = json.loads(rows[0])
    require(result.get("id") == rid and result.get("ok") is True,
            f"{op}: error returned {result.get('error')}")
    return result["result"]


def smoke(root: Path, executable: Path) -> None:
    require(executable.is_file(), "MISSING_PACKAGED_SIDECAR")
    fixture = root / "ui" / "fixtures" / "tl494-source-e695-v2.gscad.json"
    project = json.loads(fixture.read_text(encoding="utf-8"))
    require(len(project["project"]["components"]) == 23, "E695_COMPONENT_DRIFT")
    require(len(project["project"]["nets"]) == 15, "E695_NET_DRIFT")
    sheet = project["project"]["sheets"][0]["id"]
    hello = request(executable, "hello", {}, "packaged_hello")
    require(isinstance(hello, dict), "BAD_PACKAGED_HELLO")
    for format_ in ("svg", "png300"):
        exported = request(executable, "native_export_preview", {
            "document": project, "sheet_id": sheet, "format": format_
        }, "packaged_" + format_)
        require(exported.get("approval") == "NOT_ESKD_CERTIFIED", "FALSE_GOST_APPROVAL")
        require(exported.get("format") == format_, "FORMAT_MISMATCH")
        require(exported.get("sheet_size_um") == [420000, 297000], "PHYSICAL_SHEET_MISMATCH")
        blob = base64.b64decode(exported["payload"], validate=True)
        require(len(blob) > 100, "EMPTY_EXPORT")
        require(hashlib.sha256(blob).hexdigest() == exported["payload_sha256"], "EXPORT_SHA_MISMATCH")
        if format_ == "svg":
            root_svg = ET.fromstring(blob)
            require(root_svg.attrib.get("width") == "420mm", "WRONG_SVG_MM_WIDTH")
            require(root_svg.attrib.get("height") == "297mm", "WRONG_SVG_MM_HEIGHT")
        else:
            require(blob.startswith(b"\x89PNG\r\n\x1a\n"), "NOT_PNG")
            with Image.open(io.BytesIO(blob)) as im:
                require(im.size == (4961, 3508), f"WRONG_PNG_PIXELS:{im.size}")
                x, y = im.info.get("dpi", (0, 0))
                require(abs(x - 300) < 0.1 and abs(y - 300) < 0.1,
                        f"PNG_DPI_MISSING:{x}:{y}")
        print(f"PACKAGED_{format_.upper()}_PASS bytes={len(blob)} source_nets=15"
              " font=NOT_ESKD_CERTIFIED")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: smoke-packed-sidecar.py <checkout-root> <packaged-exe>")
    smoke(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
