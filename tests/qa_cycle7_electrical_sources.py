"""Execute byte-identical ELEKTRIK #87/#90 experimental E3 code, never mocks.

Sources from independently pinned exact owner commits are materialized to a
temporary Python namespace package. Actual gost_schematic core remains the
installed production integration source. pytest does not perform git fetch.
"""
import json
import sys
import tempfile
from contextlib import contextmanager
from hashlib import sha1
from importlib import import_module, invalidate_caches, util
from pathlib import Path

import gost_schematic

ROOT = Path(__file__).resolve().parent / "fixtures"
SOURCE_COMMITS = {
    "ic": "0ea5bddbc0de658baefab2bdd8803576c41099ea",
    "net": "0738059d8d4c0f5b8854a73018501fb16543434b",
}
BLOBS = {
    "qa_cycle7_electric87/electrical/__init__.txt":
        "c7ded38056293f877748e50b3a997490c78b13cc",
    "qa_cycle7_electric87/electrical/contacts.txt":
        "4ab990f956e001d1ab87566d34f7f2176951226b",
    "qa_cycle7_electric87/electrical/ic.txt":
        "cd93b1f993a53d684d4830c2cee77126e96b06ce",
    "qa_cycle7_electric87/electrical/ic_serde.txt":
        "3fa52e136983ffefc7cd77ec16d53ec7eb480b6f",
    "qa_cycle7_electric87/review_ic_cycle7.txt":
        "5cf525745d809f818a8e218ea50415bafbb62463",
    "qa_cycle7_electric87/test_ic_digital14.json":
        "8ada75a9ac42b26b6d8253b12a40dbafff5f694b",
    "qa_cycle7_electric90/electrical/netrefs.txt":
        "a8c13dba69479e31ed02c91567b564f860b5d5f6",
    "qa_cycle7_electric90/electrical/netrefs_serde.txt":
        "e2499d98c31480ef0384238ab9c3e0c47283dad4",
    "qa_cycle7_electric90/review_net_continuations.txt":
        "21e76f0ab779cbc13eeeffdd1e0273fa38869e8f",
    "qa_cycle7_electric90/two-sheet-ctrl.json":
        "b33524fb0477714646544d97acd595374f7da08a",
}


def verified():
    for name, sha in BLOBS.items():
        data = (ROOT / name).read_bytes()
        assert sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data
        ).hexdigest() == sha, name


def _load(name, path):
    spec = util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def real_electrical_sources():
    verified()
    # Other tests in the merged integration can legitimately import the
    # installed electrical package before this exact-blob QA fixture. Save
    # their modules, run our byte-pinned originals under a fresh import,
    # and restore all prior objects without changing production code.
    namespace = "gost_schematic.electrical"
    existing = {
        name: module for name, module in sys.modules.items()
        if name == namespace or name.startswith(namespace + ".")
    }
    for name in existing:
        sys.modules.pop(name)
    parent_was_set = hasattr(gost_schematic, "electrical")
    original_parent = getattr(gost_schematic, "electrical", None)
    if parent_was_set:
        delattr(gost_schematic, "electrical")
    try:
        with tempfile.TemporaryDirectory(prefix="qa-cycle7-electric-") as tmp:
            root = Path(tmp)
            folder = root / "gost_schematic" / "electrical"
            folder.mkdir(parents=True)
            sources = {
                "__init__": "qa_cycle7_electric87/electrical/__init__.txt",
                "contacts": "qa_cycle7_electric87/electrical/contacts.txt",
                "ic": "qa_cycle7_electric87/electrical/ic.txt",
                "ic_serde": "qa_cycle7_electric87/electrical/ic_serde.txt",
                "netrefs": "qa_cycle7_electric90/electrical/netrefs.txt",
                "netrefs_serde": "qa_cycle7_electric90/electrical/netrefs_serde.txt",
            }
            for filename, source in sources.items():
                (folder / (filename + ".py")).write_bytes(
                    (ROOT / source).read_bytes()
                )
            examples = {
                "_qa_cycle7_ic_owner_demo":
                    "qa_cycle7_electric87/review_ic_cycle7.txt",
                "_qa_cycle7_net_owner_demo":
                    "qa_cycle7_electric90/review_net_continuations.txt",
            }
            guest = {}
            for name, source in examples.items():
                dst = root / (name + ".py")
                dst.write_bytes((ROOT / source).read_bytes())
                guest[name] = dst
            target = str(root / "gost_schematic")
            # Pinned fixtures, not coincidentally installed owner code,
            # are authoritative inside this temporary independent QA scope.
            gost_schematic.__path__.insert(0, target)
            invalidate_caches()
            try:
                ic = import_module("gost_schematic.electrical.ic")
                ic_serde = import_module("gost_schematic.electrical.ic_serde")
                net = import_module("gost_schematic.electrical.netrefs")
                net_serde = import_module("gost_schematic.electrical.netrefs_serde")
                demo_ic = _load("_qa_cycle7_ic_owner_demo", guest[
                    "_qa_cycle7_ic_owner_demo"
                ])
                demo_net = _load("_qa_cycle7_net_owner_demo", guest[
                    "_qa_cycle7_net_owner_demo"
                ])
                yield ic, ic_serde, demo_ic, net, net_serde, demo_net
            finally:
                gost_schematic.__path__.remove(target)
                invalidate_caches()
                for name in examples:
                    sys.modules.pop(name, None)
                for name in tuple(sys.modules):
                    if name == "gost_schematic.electrical" or name.startswith(
                        "gost_schematic.electrical."
                    ):
                        sys.modules.pop(name, None)

    finally:
        for name in tuple(sys.modules):
            if name == namespace or name.startswith(namespace + "."):
                sys.modules.pop(name, None)
        sys.modules.update(existing)
        if parent_was_set:
            gost_schematic.electrical = original_parent
        elif hasattr(gost_schematic, "electrical"):
            delattr(gost_schematic, "electrical")
        invalidate_caches()

def original_json(kind):
    name = {
        "ic": "qa_cycle7_electric87/test_ic_digital14.json",
        "net": "qa_cycle7_electric90/two-sheet-ctrl.json",
    }[kind]
    return json.loads((ROOT / name).read_text(encoding="utf-8"))
