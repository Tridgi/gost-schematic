"""Prevent Windows core.autocrlf from corrupting Git-blob pinned evidence.

Never normalize or silently correct immutable source bytes at runtime.
The committed .gitattributes must preserve the exact signed Git blobs.
"""
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN_BLOBS = {
    "src/gost_schematic/agent_project/data/tl494_ic97_frozen_source.json":
        "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65",
    "tests/fixtures/ai_tl494_ic97_pinned_source.json":
        "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65",
    "tests/fixtures/qa_e1_pr80/gost_schematic/structural/__init__.txt":
        "733a2eb2c36ae9eab3f11fa3ee0cb539845f9a3e",
    "tests/fixtures/qa_pr39_1a137562_orthogonal.txt":
        "0b338b938cdd7c66a05c5cf68f02c8e6509589dc",
}


def test_signed_original_and_archived_qa_fixtures_preserve_exact_git_blob_bytes():
    for path, pinned_sha1 in FROZEN_BLOBS.items():
        raw = (ROOT / path).read_bytes()
        blob = b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw
        assert hashlib.sha1(blob).hexdigest() == pinned_sha1, path
        attr = subprocess.run(
            ["git", "-C", str(ROOT), "check-attr", "text", "--", path],
            capture_output=True, text=True, check=True,
        )
        assert attr.stdout.strip().endswith(": text: unset"), (path, attr.stdout)
