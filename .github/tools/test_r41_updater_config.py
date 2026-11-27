import base64
import unittest

from r41_updater_config import FEED, release_overlay


def encoded_key(raw):
    return base64.b64encode(b"untrusted comment: test fixture only\n" + base64.b64encode(raw)).decode()


class OverlayTests(unittest.TestCase):
    def test_strict_public_key_only_overlay(self):
        key = encoded_key(b"Ed" + b"k" * 40)
        overlay = release_overlay(key)
        plugin = overlay["plugins"]["updater"]
        self.assertEqual(plugin["pubkey"], key)
        self.assertEqual(plugin["endpoints"], [FEED])
        self.assertTrue(plugin["requireSignedVersion"])
        self.assertFalse(plugin["allowDowngrades"])
        self.assertFalse(plugin["dangerousInsecureTransportProtocol"])
        self.assertFalse(overlay["bundle"]["windows"]["allowDowngrades"])
        self.assertTrue(overlay["bundle"]["createUpdaterArtifacts"])
        self.assertNotIn("version", overlay)

    def test_invalid_key_rejected(self):
        for key in ["", "not-base64", encoded_key(b"Ed" + bytes(40)),
                    encoded_key(b"xx" + b"k" * 40), encoded_key(b"Ed" + b"k" * 39)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                release_overlay(key)


if __name__ == "__main__":
    unittest.main()
