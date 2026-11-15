"""QA router loader: prefer integrated production, else immutable local PR39 snapshot.

No git executable, Git network access, subprocess or production patch required.
The snapshot is an explicit historical oracle for the still-unmerged PR #39,
not a replacement for testing the future integrated router.
"""

import sys
from functools import lru_cache
from hashlib import sha1
from importlib import import_module
from importlib.util import find_spec, module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

ROUTER_COMMIT = "4e86e2e0e10d05c591ed004c4d6096de21520007"
ROUTER_BLOB = "50b9102191fbe7f5876b14bd9ef10dcbbb1fe600"
ROUTER_PATH = "src/gost_schematic/engines/routing/two_pin_orthogonal.py"
ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "tests/fixtures/qa_router_pr39_snapshot.py"
ROUTER_MODULE = "gost_schematic.engines.routing.two_pin_orthogonal"


@lru_cache(maxsize=1)
def load_pr39_router() -> ModuleType:
    """Use production after merge, otherwise exactly the checked-in PR39 source."""
    if find_spec(ROUTER_MODULE) is not None:
        return import_module(ROUTER_MODULE)
    raw = SNAPSHOT.read_bytes()
    expected = ROUTER_BLOB
    actual = sha1(b"blob " + str(len(raw)).encode() + bytes((0,)) + raw).hexdigest()
    if actual != expected:
        raise AssertionError(
            f"QA snapshot Git blob mismatch: {actual} != {expected}"
        )
    module_name = "gost_schematic.engines.routing._qa_pr39_snapshot"
    spec = spec_from_file_location(module_name, SNAPSHOT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Missing QA router snapshot import specification")
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
