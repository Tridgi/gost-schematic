"""Install an independent SIL OFL OpenGOST Type A face into the local machine.

Does not vendor font binaries into gost-schematic. Source:
https://github.com/ingenium-am/open-gost-arm, release v0.7, OFL-1.1.
The tool requires byte-pinned v0.7 archive and font SHA256 before installation;
no API release metadata and no alternative font are accepted.
"""

import argparse
import hashlib
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

RELEASE = "https://api.github.com/repos/ingenium-am/open-gost-arm/releases/tags/v0.7"
# Exact upstream v0.7 release asset confirmed on 2026-11-15. Downloading
# this immutable filename avoids GitHub's shared-IP REST API rate limit.
PINNED_ARCHIVE_URL = (
    "https://github.com/ingenium-am/open-gost-arm/releases/download/"
    "v0.7/OpenGOST_TTF_0.7.zip"
)
PINNED_ARCHIVE_SHA256 = "b666e4f139d7ea2fc55334334e117ddde4139cea33a8dc6905aba01d089569dc"
PINNED_TYPE_A_NAME = "OpenGOSTtypeA-Regular.ttf"
PINNED_TYPE_A_SHA256 = "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
MAX_ARCHIVE_BYTES = 1_000_000


def _get(url: str) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gost-schematic-font-setup",
    }
    # Actions API requests are rate-limited to a shared anonymous runner IP.
    # Use the job-scoped token only for api.github.com, never asset/CDN URLs.
    token = os.environ.get("GITHUB_TOKEN")
    if token and urllib.parse.urlparse(url).hostname == "api.github.com":
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as reply:
        return reply.read()


def _looks_like_type_a(filename: str) -> bool:
    normalized = filename.lower().replace("-", "").replace("_", "").replace(" ", "")
    return "typea" in normalized and normalized.endswith((".ttf", ".otf"))


def select_font_asset(
    assets: list[dict[str, str]], getter=_get,
) -> tuple[str, bytes]:
    """Select Type A only; never silently substitute a Type B or system font."""
    direct = next(
        (item for item in assets if _looks_like_type_a(item["name"])),
        None,
    )
    if direct is not None:
        return direct["name"], getter(direct["browser_download_url"])
    for asset in assets:
        if not asset["name"].lower().endswith(".zip"):
            continue
        payload = getter(asset["browser_download_url"])
        with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
            members = [
                item for item in bundle.namelist()
                if _looks_like_type_a(Path(item).name)
                and not item.startswith("__MACOSX/")
            ]
            if members:
                match = min(members, key=len)
                return Path(match).name, bundle.read(match)
    raise ValueError("No OpenGOST Type A TTF/OTF face found in the pinned release")


def load_verified_pinned_type_a(getter=_get) -> tuple[str, bytes]:
    """Load only SHA-pinned upstream v0.7 archive and exact Type A font.

    In particular, never query anonymous release metadata, try a different
    release, or fall back to an unrelated system font. Wrong bytes are fatal.
    """
    archive = getter(PINNED_ARCHIVE_URL)
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise ValueError("Pinned OpenGOST archive exceeds bounded size")
    if hashlib.sha256(archive).hexdigest() != PINNED_ARCHIVE_SHA256:
        raise ValueError("Pinned OpenGOST release archive SHA256 mismatch")
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        names = [
            name for name in bundle.namelist()
            if Path(name).name == PINNED_TYPE_A_NAME
            and not name.startswith("__MACOSX/")
        ]
        if len(names) != 1:
            raise ValueError("Pinned OpenGOST v0.7 exact Type A face not unique")
        entry = bundle.getinfo(names[0])
        if entry.file_size > MAX_ARCHIVE_BYTES:
            raise ValueError("Pinned Type A font exceeds bounded size")
        data = bundle.read(entry)
    if hashlib.sha256(data).hexdigest() != PINNED_TYPE_A_SHA256:
        raise ValueError("Pinned OpenGOST Type A font SHA256 mismatch")
    return PINNED_TYPE_A_NAME, data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--directory", type=Path,
        default=Path.home() / ".local/share/fonts",
    )
    parser.add_argument(
        "--expected-sha256",
        help="Optional exact hash for a controlled, reproducible installation",
    )
    parser.add_argument(
        "--manifest-out", type=Path,
        help="Write a JSON provenance receipt; no font bytes are included",
    )
    args = parser.parse_args(argv)
    try:
        name, data = load_verified_pinned_type_a()
        digest = hashlib.sha256(data).hexdigest()
        if args.expected_sha256 is not None and digest != args.expected_sha256.lower():
            raise ValueError("Font checksum does not match the specified SHA256")
        if not (data.startswith(b"OTTO") or data[:4] in (
            b"\x00\x01\x00\x00", b"true",
        )):
            raise ValueError("Downloaded asset does not look like an OpenType font")
        args.directory.mkdir(parents=True, exist_ok=True)
        destination = args.directory / f"OpenGOST-TypeA-{Path(name).name}"
        destination.write_bytes(data)
        if args.manifest_out is not None:
            args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
            receipt = {
                "schema_version": 1,
                "font_family": "OpenGOST Type A",
                "font_file": PINNED_TYPE_A_NAME,
                "font_sha256": digest,
                "archive_url": PINNED_ARCHIVE_URL,
                "archive_sha256": PINNED_ARCHIVE_SHA256,
                "upstream_tag": "v0.7",
                "license": "SIL OFL 1.1",
                "verified_exact_archive_and_face": True,
                "unverified_substitution_used": False,
            }
            # Distinct receipt name per run; never replace an old proof.
            with args.manifest_out.open("x", encoding="utf-8") as output:
                output.write(json.dumps(receipt, sort_keys=True, indent=2) + "\\n")
        print(f"Installed: {destination}")
        print(f"SHA256: {digest}")
        print("License: SIL OFL 1.1; see upstream LICENSE.txt")
        print("Run: fc-cache -f")
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"Font installation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
