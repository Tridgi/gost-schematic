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
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

RELEASE = "https://api.github.com/repos/ingenium-am/open-gost-arm/releases/tags/v0.7"
# Upstream release v0.7 and its original SIL OFL 1.1 TTF archive.
# Use the fixed release asset directly before attempting the rate-limited API.
RELEASE_ASSET = (
    "https://github.com/ingenium-am/open-gost-arm/releases/download/v0.7/"
    "OpenGOST_TTF_0.7.zip"
)
RELEASE_ASSET_NAME = "OpenGOST_TTF_0.7.zip"
CACHED_FACE = "OpenGOST-TypeA-OpenGOSTtypeA-Regular.ttf"
PINNED_TYPE_A_SHA256 = (
    "f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a"
)


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


def _verified_face(data: bytes, expected_sha256: str | None) -> str:
    """No Type B, truncated data or changed downloaded font may be installed."""
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(
            "OpenGOST Type A SHA256 mismatch: "
            f"expected {expected_sha256}, got {digest}"
        )
    if not (data.startswith(b"OTTO") or data[:4] in (
        b"\x00\x01\x00\x00", b"true",
    )):
        raise ValueError("Downloaded asset does not look like an OpenType font")
    return digest


def _download_type_a() -> tuple[str, bytes]:
    """Pinned public release asset first, authenticated release API second.

    GitHub Actions runners share anonymous API rate limits. The original
    release archive URL is independent of the release-metadata API; both
    paths obtain the *same face* and must meet the caller's SHA lock.
    """
    primary = [{
        "name": RELEASE_ASSET_NAME, "browser_download_url": RELEASE_ASSET,
    }]
    try:
        return select_font_asset(primary, getter=_get)
    except (OSError, ValueError, zipfile.BadZipFile) as direct_error:
        try:
            release = json.loads(_get(RELEASE))
            if release.get("tag_name") != "v0.7":
                raise ValueError("Unexpected OpenGOST release tag")
            return select_font_asset(release["assets"], getter=_get)
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as api_error:
            raise OSError(
                f"OpenGOST pinned asset unavailable: direct={direct_error}; "
                f"verified-release-API={api_error}"
            ) from api_error


def install_type_a(
    directory: Path, *,
    expected_sha256: str | None = PINNED_TYPE_A_SHA256,
) -> tuple[Path, str, str]:
    """Install from an exact SHA-checked cache, or pinned original release.

    Return filename, verified digest, provenance. Never use fontconfig's
    approximate font-family substitute as a successful Type A installation.
    """
    if expected_sha256 is not None:
        if (len(expected_sha256) != 64
            or any(char not in "0123456789abcdef" for char in
                   expected_sha256.lower())):
            raise ValueError("Expected SHA256 must be a 64-character hex digest")
        expected_sha256 = expected_sha256.lower()
    destination = directory / CACHED_FACE
    if destination.exists():
        cached = destination.read_bytes()
        digest = _verified_face(cached, expected_sha256)
        return destination, digest, "LOCAL_HASH_VERIFIED_CACHE"
    name, data = _download_type_a()
    if not _looks_like_type_a(name):
        raise ValueError("Downloaded font is not OpenGOST Type A")
    digest = _verified_face(data, expected_sha256)
    directory.mkdir(parents=True, exist_ok=True)
    temp = directory / (CACHED_FACE + ".tmp")
    try:
        temp.write_bytes(data)
        if hashlib.sha256(temp.read_bytes()).hexdigest() != digest:
            raise ValueError("OpenGOST Type A temporary file was modified")
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    return destination, digest, "PINNED_UPSTREAM_V0.7_RELEASE"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--directory", type=Path,
        default=Path.home() / ".local/share/fonts",
    )
    parser.add_argument(
        "--expected-sha256",
        default=PINNED_TYPE_A_SHA256,
        help="Exact known SHA256 of the original OpenGOST v0.7 Type A face",
    )
    args = parser.parse_args(argv)
    try:
        destination, digest, provenance = install_type_a(
            args.directory, expected_sha256=args.expected_sha256,
        )
        print(f"Installed: {destination}")
        print(f"SHA256: {digest}")
        print(f"Provenance: {provenance}")
        print("License: SIL OFL 1.1; see upstream LICENSE.txt")
        print("Run: fc-cache -f")
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"Font installation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
