"""Independent, offline frozen source loader for exact Draft PR #39 SHA.

No git, network or production changes during pytest. The frozen blobs were
retrieved from GitHub at the exact reviewed commit and are verified before
execution, so author changes cannot silently change these results.
"""
import sys
from functools import lru_cache
from hashlib import sha1
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

HEAD = "1a1375623c0f098cac14f7843c44d75982a4d749"
ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    (
        "gost_schematic.engines.routing.two_pin_orthogonal",
        "tests/fixtures/qa_pr39_1a137562_orthogonal.py",
        "0b338b938cdd7c66a05c5cf68f02c8e6509589dc",
    ),
    (
        "gost_schematic.engines.routing.two_pin_sheet",
        "tests/fixtures/qa_pr39_1a137562_sheet.py",
        "1af14ada6e1e37c8c94d8c27b100bdba14a41a4d",
    ),
)


@lru_cache(maxsize=1)
def load_frozen_pr39():
    """Return (low_level, typed_sheet) imported from verified frozen source."""
    loaded = []
    for module_name, relative_path, expected_blob in MODULES:
        path = ROOT / relative_path
        raw = path.read_bytes()
        actual = sha1(
            b"blob " + str(len(raw)).encode() + bytes((0,)) + raw
        ).hexdigest()
        if actual != expected_blob:
            raise AssertionError(
                f"PR39 frozen source mismatch: {relative_path}: {actual}"
            )
        spec = spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load frozen PR39 source: {relative_path}")
        module = module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        loaded.append(module)
    return tuple(loaded)
