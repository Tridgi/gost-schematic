"""Install an independent SIL OFL OpenGOST Type A face into the local machine.

Does not vendor font binaries into gost-schematic. Source:
https://github.com/ingenium-am/open-gost-arm, release v0.7, OFL-1.1.
The tool prints the resulting SHA256 for provenance; reproducible/regulated
builds should pin and verify this hash before deploying schematics.
"""

import argparse
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

RELEASE = "https://api.github.com/repos/ingenium-am/open-gost-arm/releases/tags/v0.7"


def _get(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "gost-schematic-font-setup",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as reply:  # noqa: S310
        return reply.read()


def _looks_like_type_a(filename: str) -> bool:
    normalized = filename.lower().replace("-", "").replace("_", "").replace(" ", "")
    return "typea" in normalized and (normalized.endswith(".ttf") or normalized.endswith(".otf"))


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
                match = sorted(members, key=len)[0]
                return Path(match).name, bundle.read(match)
    raise ValueError("No OpenGOST Type A TTF/OTF face found in the pinned release")


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
    args = parser.parse_args(argv)
    try:
        release = json.loads(_get(RELEASE))
        name, data = select_font_asset(release["assets"])
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
