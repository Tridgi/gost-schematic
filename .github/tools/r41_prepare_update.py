"""Prepare (never publish) a signed GitHub Releases bundle from accepted NSIS bytes.

Requires the owner-provisioned Tauri public key and a real minisign executable.
The private key is deliberately not accepted by this tool.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


REPO = "https://github.com/Tridgi/gost-schematic"
STABLE = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", re.ASCII)


def version_tuple(version):
    if not isinstance(version, str) or not STABLE.fullmatch(version):
        raise ValueError("stable numeric version required")
    return tuple(map(int, version.split(".")))


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_acceptance(manifest, source_sha, version, previous_version):
    if version_tuple(version) <= version_tuple(previous_version):
        raise ValueError("new release version must be greater")
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise ValueError("expected exact source SHA")
    if (manifest.get("schema") != 1
            or manifest.get("source_sha") != source_sha
            or manifest.get("app_version") != version
            or manifest.get("target") != "windows-x86_64"
            or manifest.get("native_acceptance") != "PASS"
            or manifest.get("full_tl494") != "PASS"):
        raise ValueError("wrong or incomplete native acceptance manifest")
    name = manifest.get("installer")
    if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9 ._()-]+-setup\.exe", name)
            or name.startswith(".") or ".." in name):
        raise ValueError("unsafe NSIS filename")
    digest = manifest.get("sha256")
    size = manifest.get("size_bytes")
    if (not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
            or type(size) is not int or size <= 0):
        raise ValueError("invalid accepted installer size or SHA")
    return name


def decode_tauri(value):
    return base64.b64decode(value.strip(), validate=True).decode("utf-8")


def verify_signature(installer, signature, public_key, version):
    """Use minisign, then require the cryptographically covered version field."""
    sig_text = decode_tauri(signature)
    key_text = decode_tauri(public_key)
    with tempfile.TemporaryDirectory(prefix="gscad-signature-") as directory:
        sig = Path(directory) / "update.minisig"
        key = Path(directory) / "update.pub"
        sig.write_text(sig_text, encoding="utf-8")
        key.write_text(key_text, encoding="utf-8")
        subprocess.run(["minisign", "-V", "-m", str(installer.resolve()),
                        "-x", str(sig), "-p", str(key)],
                       check=True, timeout=120, capture_output=True)
    lines = sig_text.splitlines()
    if len(lines) != 4 or not lines[2].startswith("trusted comment: "):
        raise ValueError("missing trusted signature comment")
    versions = [field[8:] for field in lines[2][len("trusted comment: "):].split("\t")
                if field.startswith("version:")]
    if versions != [version]:
        raise ValueError("signed version missing or mismatched")


def prepare(accepted_dir, signature_path, public_key_path, output, source_sha,
            version, previous_version):
    manifest = json.loads((accepted_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    name = validate_acceptance(manifest, source_sha, version, previous_version)
    installer = accepted_dir / name
    if installer.is_symlink() or not installer.is_file():
        raise ValueError("accepted installer is not a regular file")
    if installer.stat().st_size != manifest["size_bytes"] or sha256(installer) != manifest["sha256"]:
        raise ValueError("accepted installer bytes do not match manifest")
    signature = signature_path.read_text(encoding="utf-8").strip()
    public_key = public_key_path.read_text(encoding="utf-8").strip()
    verify_signature(installer, signature, public_key, version)

    # Fixed safe asset name avoids GitHub's filename normalization.
    asset = f"schematik-{version}-x64-setup.exe"
    output.mkdir(parents=False, exist_ok=False)
    staged = output / asset
    shutil.copyfile(installer, staged)
    if sha256(staged) != manifest["sha256"] or staged.stat().st_size != manifest["size_bytes"]:
        raise ValueError("staged installer changed")
    # Verify the exact staged bytes, not just the input path.
    verify_signature(staged, signature, public_key, version)
    (output / (asset + ".sig")).write_text(signature, encoding="utf-8")
    (output / "SHA256SUMS.txt").write_text(f'{manifest["sha256"]}  {asset}\n', encoding="utf-8")
    (output / "acceptance.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    latest = {"version": version, "platforms": {"windows-x86_64": {
        "signature": signature,
        "url": f"{REPO}/releases/download/v{version}/{asset}"}}}
    # Emit feed only after all checks; this tool does not contact GitHub.
    (output / "latest.json").write_text(json.dumps(latest, indent=2) + "\n", encoding="utf-8")
    return latest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted-dir", required=True, type=Path)
    parser.add_argument("--signature", required=True, type=Path)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--previous-version", required=True)
    args = parser.parse_args()
    prepare(args.accepted_dir, args.signature, args.public_key, args.output,
            args.source_sha, args.version, args.previous_version)


if __name__ == "__main__":
    main()
