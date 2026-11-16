"""MASTER development CLI: validated gscad-project v2 -> genuine SVG + PNG300.

This is a local developer preview, NOT a Tauri/remote file-write IPC.
A legal, verified GOST Type A font is not bundled; --preview-font explicitly
allows an unverified replacement and records that warning in the manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ui.bridge.export.canonical import ExportRequest  # noqa: E402
from ui.bridge.export.project_v2 import export_v2  # noqa: E402
from ui.editor.src.model.contract import digest, strict_loads  # noqa: E402


def _replace(path: Path, data: bytes) -> None:
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".gscad-", suffix=".tmp",
            dir=path.parent, delete=False
        ) as stream:
            tmp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def export_local(project_path: Path, output_dir: Path, *, sheet: str = "sheet-1",
                 expected_sha: str | None = None, preview_font: bool = False) -> dict:
    document = strict_loads(project_path.read_bytes())
    revision = digest(document)
    if expected_sha is not None and revision != expected_sha:
        raise ValueError("SOURCE_SHA_CONFLICT: project changed before export")
    request = ExportRequest(page="A3", orientation="landscape", dpi=300,
                            include_frame=False, include_title=False,
                            strict_font=not preview_font)
    result = export_v2(document, sheet, request, expected_project_sha256=revision)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = sheet + (".unverified-font-preview" if preview_font else ".verified")
    paths = {"svg": output_dir / (stem + ".svg"),
             "png": output_dir / (stem + ".png"),
             "manifest": output_dir / (stem + ".manifest.json")}
    manifest = {
        "format": "gscad-export-preview-v1",
        "approval": "NOT_ESKD_CERTIFIED",
        "project_sha256": revision,
        "source_origin": document["project"]["provenance"]["source_sha"],
        "sheet_id": sheet,
        "pixel_dimensions": list(result.pixels),
        "sheet_um": list(result.size_um),
        "svg_sha256": hashlib.sha256(result.svg).hexdigest(),
        "png_sha256": hashlib.sha256(result.png).hexdigest(),
        "warnings": list(result.warnings),
        "svg_file": paths["svg"].name,
        "png_file": paths["png"].name,
    }
    _replace(paths["svg"], result.svg)
    _replace(paths["png"], result.png)
    # Manifest is published last: incomplete/interrupted export has no receipt.
    _replace(paths["manifest"], (json.dumps(manifest, sort_keys=True,
                                            ensure_ascii=False, indent=2)+"\n").encode())
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sheet", default="sheet-1")
    parser.add_argument("--expected-sha")
    parser.add_argument("--preview-font", action="store_true",
                        help="Allow unverified font in non-normative preview only")
    args = parser.parse_args()
    try:
        manifest = export_local(args.project, args.out, sheet=args.sheet,
                                expected_sha=args.expected_sha,
                                preview_font=args.preview_font)
    except (ValueError, OSError) as exc:
        print(f"EXPORT_BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
