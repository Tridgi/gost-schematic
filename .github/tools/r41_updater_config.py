"""Generate a public-key-only Tauri release overlay; never generate or store secrets."""
import argparse
import base64
import json
from pathlib import Path

FEED = "https://github.com/Tridgi/gost-schematic/releases/latest/download/latest.json"


def release_overlay(public_key):
    key = public_key.strip()
    lines = base64.b64decode(key, validate=True).decode("utf-8").splitlines()
    if len(lines) != 2 or not lines[0].startswith("untrusted comment:"):
        raise ValueError("invalid Tauri public key envelope")
    raw = base64.b64decode(lines[1], validate=True)
    if len(raw) != 42 or raw[:2] != b"Ed" or not any(raw[10:]):
        raise ValueError("invalid minisign public key")
    return {
        "plugins": {"updater": {
            "pubkey": key, "endpoints": [FEED],
            "requireSignedVersion": True, "allowDowngrades": False,
            "dangerousInsecureTransportProtocol": False,
            "dangerousAcceptInvalidCerts": False,
            "dangerousAcceptInvalidHostnames": False,
            "windows": {"installMode": "passive"},
        }},
        "bundle": {"createUpdaterArtifacts": True, "windows": {"allowDowngrades": False}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    overlay = release_overlay(args.public_key.read_text(encoding="utf-8"))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(overlay, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
