"""MASTER export CLI regression: real physical SVG/PNG, fail-closed font policy."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ui" / "integration"))
from export_preview import export_local

SOURCE = ROOT / "ui" / "fixtures" / "tl494-source-e695-v2.gscad.json"


class PreviewExportTests(unittest.TestCase):
    def test_requires_explicit_unverified_font_acknowledgment(self):
        with tempfile.TemporaryDirectory() as base:
            output = Path(base) / "output"
            with self.assertRaisesRegex(ValueError, "FONT_NOT_OUTLINED"):
                export_local(SOURCE, output)
            self.assertFalse(output.exists())

    def test_stale_sha_no_files(self):
        with tempfile.TemporaryDirectory() as base:
            output = Path(base) / "output"
            with self.assertRaisesRegex(ValueError, "SOURCE_SHA_CONFLICT"):
                export_local(SOURCE, output, expected_sha="0" * 64,
                             preview_font=True)
            self.assertFalse(output.exists())

    def test_real_frozen_e695_preview_is_png300_not_screenshot(self):
        with tempfile.TemporaryDirectory() as base:
            output = Path(base) / "output"
            manifest = export_local(SOURCE, output, preview_font=True)
            self.assertEqual(manifest["source_origin"],
                             "e695c415fdced164b0e0c39c5249d030795a0aa6")
            self.assertEqual(manifest["pixel_dimensions"], [4961, 3508])
            self.assertEqual(manifest["sheet_um"], [420000, 297000])
            self.assertIn("FONT_RENDER_UNVERIFIED", manifest["warnings"])
            svg = (output / manifest["svg_file"]).read_bytes()
            self.assertIn(b"gscad-project-v2", svg)
            self.assertEqual(svg.count(b'data-kind="source_b_continuation"'), 2)
            self.assertIn(b'data-source-net-count="15"', svg)
            with Image.open(io.BytesIO((output / manifest["png_file"]).read_bytes())) as image:
                self.assertEqual(image.size, (4961, 3508))
                self.assertAlmostEqual(image.info["dpi"][0], 300, delta=0.02)
            self.assertEqual(
                json.loads((output / "sheet-1.unverified-font-preview.manifest.json")
                           .read_text(encoding="utf-8")), manifest
            )


if __name__ == "__main__":
    unittest.main()
