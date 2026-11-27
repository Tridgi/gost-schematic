"""Offline release-preparation checks. Mock verification is not crypto acceptance."""
import base64
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from r41_prepare_update import prepare, sha256, validate_acceptance, verify_signature


class PrepareUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.accepted = self.root / "accepted"
        self.accepted.mkdir()
        self.installer = self.accepted / "GOST CAD_0.2.0_x64-setup.exe"
        self.installer.write_bytes(b"synthetic test installer, never publish")
        self.manifest = {
            "schema": 1, "source_sha": "a" * 40, "app_version": "0.2.0",
            "target": "windows-x86_64", "native_acceptance": "PASS",
            "full_tl494": "PASS", "installer": self.installer.name,
            "sha256": sha256(self.installer), "size_bytes": self.installer.stat().st_size,
        }
        self.signature = self.root / "update.sig"
        self.signature.write_text("test-only")
        self.key = self.root / "public.key"
        self.key.write_text("test-only")
        self.output = self.root / "out"

    def run_prepare(self):
        (self.accepted / "manifest.json").write_text(json.dumps(self.manifest))
        return prepare(self.accepted, self.signature, self.key, self.output,
                       "a" * 40, "0.2.0", "0.1.0")

    def test_exact_bytes_and_fixed_release_url(self):
        with patch("r41_prepare_update.verify_signature") as verify:
            result = self.run_prepare()
            self.assertEqual(verify.call_count, 2)
        asset = self.output / "schematik-0.2.0-x64-setup.exe"
        self.assertEqual(sha256(asset), self.manifest["sha256"])
        self.assertEqual(result["platforms"]["windows-x86_64"]["url"],
                         "https://github.com/Tridgi/gost-schematic/releases/download/v0.2.0/" + asset.name)
        self.assertEqual(json.loads((self.output / "latest.json").read_text()), result)

    def test_reject_manifest_mismatch_and_downgrade(self):
        for field, value in [("source_sha", "b"*40), ("app_version", "0.3.0"),
                             ("native_acceptance", "FAIL"), ("full_tl494", "FAIL"),
                             ("target", "windows-aarch64"), ("installer", "../x-setup.exe")]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_acceptance({**self.manifest, field: value},
                                    "a"*40, "0.2.0", "0.1.0")
        with self.assertRaises(ValueError):
            validate_acceptance(self.manifest, "a"*40, "0.2.0", "0.2.0")

    def test_tampered_bytes_rejected_before_signature(self):
        self.installer.write_bytes(b"changed")
        with patch("r41_prepare_update.verify_signature") as verify:
            with self.assertRaises(ValueError):
                self.run_prepare()
            verify.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_invalid_signature_never_creates_feed(self):
        with (
            patch("r41_prepare_update.verify_signature", side_effect=ValueError("invalid signature")),
            self.assertRaises(ValueError),
        ):
            self.run_prepare()
        self.assertFalse(self.output.exists())

    def test_signed_version_required_after_verifier_success(self):
        key = base64.b64encode(b"untrusted comment: test\nkey").decode()
        for comment in ["timestamp:1", "timestamp:1\tversion:0.1.0", "version:0.2.0\tversion:0.2.0"]:
            sig = base64.b64encode(
                ("untrusted comment: test\nsig\ntrusted comment: " + comment + "\nproof").encode()
            ).decode()
            with patch("r41_prepare_update.subprocess.run") as verifier:
                with self.assertRaises(ValueError):
                    verify_signature(self.installer, sig, key, "0.2.0")
                verifier.assert_called_once()

    def test_no_overwrite_existing_output(self):
        self.output.mkdir()
        with patch("r41_prepare_update.verify_signature"), self.assertRaises(FileExistsError):
            self.run_prepare()
        self.assertFalse((self.output / "latest.json").exists())


@unittest.skipUnless(shutil.which("minisign"), "requires real minisign executable")
class RealSignatureTests(unittest.TestCase):
    def test_ephemeral_key_rejects_tamper_wrong_key_and_wrong_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "payload.exe"
            data.write_bytes(b"synthetic test payload, not executable")
            pub = root / "test.pub"
            secret = root / "test.key"
            sig = root / "test.sig"
            other_pub = root / "other.pub"
            other_secret = root / "other.key"
            for p, k in [(pub, secret), (other_pub, other_secret)]:
                subprocess.run(
                    ["minisign", "-G", "-W", "-p", str(p), "-s", str(k)],
                    check=True, capture_output=True, timeout=30,
                )
            subprocess.run(
                ["minisign", "-S", "-s", str(secret), "-m", str(data),
                 "-x", str(sig), "-t", "timestamp:1\tversion:0.2.0"],
                check=True, capture_output=True, timeout=30,
            )
            signature = base64.b64encode(sig.read_bytes()).decode()
            public_key = base64.b64encode(pub.read_bytes()).decode()
            verify_signature(data, signature, public_key, "0.2.0")
            with self.assertRaises(ValueError):
                verify_signature(data, signature, public_key, "0.3.0")
            wrong_key = base64.b64encode(other_pub.read_bytes()).decode()
            with self.assertRaises(subprocess.CalledProcessError):
                verify_signature(data, signature, wrong_key, "0.2.0")
            data.write_bytes(b"tampered test payload")
            with self.assertRaises(subprocess.CalledProcessError):
                verify_signature(data, signature, public_key, "0.2.0")


if __name__ == "__main__":
    unittest.main()
