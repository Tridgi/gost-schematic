"""Independent frozen-source loader; never replace installed production modules.

Exact historical PR39 blob provenance is preserved; private module namespaces
make it possible to test the integrated router and archived router in one run.
No git, network or production edits during pytest.
"""

import sys
from functools import lru_cache
from hashlib import sha1
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

HEAD = "1a1375623c0f098cac14f7843c44d75982a4d749"
ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_LOW = "gost_schematic.engines.routing.two_pin_orthogonal"
MODULES = (
    (
        "gost_schematic.engines.routing._qa_pinned_1a137562_orthogonal",
        "tests/fixtures/qa_pr39_1a137562_orthogonal.txt",
        "0b338b938cdd7c66a05c5cf68f02c8e6509589dc",
    ),
    (
        "gost_schematic.engines.routing._qa_pinned_1a137562_sheet",
        "tests/fixtures/qa_pr39_1a137562_sheet.txt",
        "1af14ada6e1e37c8c94d8c27b100bdba14a41a4d",
    ),
)


@lru_cache(maxsize=1)
def load_frozen_pr39():
    """Import both immutable QA snapshots without permanently shadowing src/."""
    prior = sys.modules.get(PRODUCTION_LOW)
    low = None
    loaded = []
    try:
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
            # The frozen sheet's 'from ...two_pin_orthogonal import' must
            # capture the pinned low-level code, not any changed installed code.
            if low is not None:
                sys.modules[PRODUCTION_LOW] = low
            spec = spec_from_loader(
                module_name, SourceFileLoader(module_name, str(path))
            )
            if spec is None or spec.loader is None:
                raise RuntimeError(
                    f"Cannot load frozen PR39 source: {relative_path}"
                )
            module = module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            loaded.append(module)
            if low is None:
                low = module
    finally:
        if prior is None:
            sys.modules.pop(PRODUCTION_LOW, None)
        else:
            sys.modules[PRODUCTION_LOW] = prior
    return tuple(loaded)
