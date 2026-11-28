"""Wheel verification cannot silently omit or alter expanding catalog data."""
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.verify_wheel_payload import verify_wheel

ROOT = Path(__file__).resolve().parents[1] / "src" / "gost_schematic"


def test_wheel_matches_all_current_catalog_json(tmp_path):
    wheel = tmp_path / "fixture.whl"
    data = {
        p.relative_to(ROOT).as_posix(): p.read_bytes()
        for folder in ("catalog", "standards")
        for p in (ROOT / folder).rglob("*.json")
    }
    target = "catalog/transformers/transformer.air_core.json"
    assert target in data
    for mode in ("correct", "missing", "modified"):
        with ZipFile(wheel, "w") as archive:
            for name, content in data.items():
                if name == target and mode == "missing":
                    continue
                if name == target and mode == "modified":
                    content += b" "
                archive.writestr("gost_schematic/" + name, content)
        if mode == "correct":
            report = verify_wheel(wheel)
            assert report["winding_profiles"] >= 21
            assert report["transformer_profiles"] >= 5
        else:
            with pytest.raises(ValueError, match="Wheel catalog mismatch|Wheel data differs"):
                verify_wheel(wheel)
