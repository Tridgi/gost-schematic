"""Deterministic CI-only Type A glyph asset downloader without GitHub API quota.

Fetches the upstream OFL 0.7 release archive using its immutable release URL,
picks ONLY an OpenGOST Type A face, verifies exact SHA256, then writes it to
the isolated CI runner. Never substitute system Type B or return unverified art.
No font bytes are committed or uploaded as artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

DIRECT_ASSET = (
    "https://github.com/ingenium-am/open-gost-arm/"
    "releases/download/v0.7/OpenGOST_TTF_0.7.zip"
)
TYPE_A_SHA256 = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"


def verified_type_a_from_archive(payload: bytes) -> tuple[str, bytes]:
    """Reject Type B, missing/duplicate Type A, changed checksum or fake font."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("QA_GOST_RELEASE_ARCHIVE_INVALID") from exc
    with archive:
        faces = [
            member for member in archive.infolist()
            if not member.is_dir()
            and "typea" in Path(member.filename).name.lower().replace(
                "-", "").replace("_", "").replace(" ", "")
            and Path(member.filename).suffix.lower() in (".ttf", ".otf")
            and not member.filename.startswith("__MACOSX/")
        ]
        if not faces:
            raise ValueError("QA_GOST_RELEASE_NO_TYPE_A")
        verified = []
        for face in faces:
            if face.file_size > 20_000_000:
                raise ValueError("QA_GOST_RELEASE_FONT_SIZE_UNSAFE")
            content = archive.read(face)
            if hashlib.sha256(content).hexdigest() == TYPE_A_SHA256:
                verified.append((face, content))
    if len(verified) != 1:
        raise ValueError("QA_GOST_TYPE_A_SHA256_MISMATCH_OR_AMBIGUOUS")
    face, content = verified[0]
    if content[:4] not in (b"OTTO", b"\x00\x01\x00\x00", b"true"):
        raise ValueError("QA_GOST_RELEASE_NOT_OPENTYPE")
    return Path(face.filename).name, content

def download_true_type_a(dest: Path) -> dict:
    request = urllib.request.Request(
        DIRECT_ASSET, headers={"User-Agent": "gost-schematic-qa-font/1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        name, content = verified_type_a_from_archive(response.read())
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / ("OpenGOST-TypeA-" + name)
    path.write_bytes(content)
    return {
        "font_source": DIRECT_ASSET,
        "font_sha256": TYPE_A_SHA256,
        "destination": str(path),
        "license": "SIL OFL 1.1",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    outcome = download_true_type_a(args.directory)
    print("QA_REAL_GOST_TYPE_A_SHA256", outcome["font_sha256"],
          outcome["destination"])


if __name__ == "__main__":
    main()
