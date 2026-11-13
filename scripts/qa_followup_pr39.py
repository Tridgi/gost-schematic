"""Load the EXACT, unchanged PR #39 router into a QA-only namespace.

The routing PR is deliberately unmerged. Avoid copying its production file,
altering its branch, or silently skipping pytest checks when it is unavailable.
We fetch one immutable Git commit once if shallow CI checkout lacks it.
"""

import subprocess
import sys
from functools import lru_cache
from hashlib import sha1
from pathlib import Path
from types import ModuleType

ROUTER_COMMIT = "4e86e2e0e10d05c591ed004c4d6096de21520007"
ROUTER_BLOB = "50b9102191fbe7f5876b14bd9ef10dcbbb1fe600"
ROUTER_PATH = "src/gost_schematic/engines/routing/two_pin_orthogonal.py"
ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=False, timeout=45,
    )


@lru_cache(maxsize=1)
def load_pr39_router() -> ModuleType:
    """Never substitute an unrelated local router or silently skip tests."""
    source = _git("show", f"{ROUTER_COMMIT}:{ROUTER_PATH}")
    if source.returncode:
        fetched = _git("fetch", "--no-tags", "--depth=1", "origin", ROUTER_COMMIT)
        if fetched.returncode:
            raise RuntimeError(
                "QA cannot fetch pinned PR #39 SHA; fail closed: "
                + fetched.stderr.decode("utf-8", errors="replace")[:500]
            )
        source = _git("show", f"{ROUTER_COMMIT}:{ROUTER_PATH}")
    if source.returncode:
        raise RuntimeError("Cannot retrieve pinned PR #39 router source")
    raw = source.stdout
    actual_blob = sha1(b"blob " + str(len(raw)).encode() + bytes((0,)) + raw).hexdigest()
    if actual_blob != ROUTER_BLOB:
        raise AssertionError(f"Router blob mismatch {actual_blob} != {ROUTER_BLOB}")
    module_name = "_qa_pr39_router_pinned_4e86e2"
    module = ModuleType(module_name)
    module.__file__ = f"git:{ROUTER_COMMIT}:{ROUTER_PATH}"
    module.__package__ = "gost_schematic.engines.routing"
    sys.modules[module_name] = module
    exec(compile(raw.decode("utf-8"), module.__file__, "exec"), module.__dict__)
    return module
