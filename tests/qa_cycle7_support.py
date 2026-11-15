"""Independent Cycle-7 source provenance and real-loader adapters.

The .txt source is byte-identical to PAINT's owner file, not a mock renderer.
Part/symbol .json blobs are exact YGO2 owner data; actual repository's
production parse_symbol/parse_part/renderers/validators execute them.
No git/network access during pytest; no owner production file is modified.
"""

import json
import sys
from hashlib import sha1
from importlib import util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = Path(__file__).resolve().parent / "fixtures"
OWNER_SHA = {
    "paint_commit": "f8f9dc4c1fd8266b807dea9d6f268d971bec8d7a",
    "ygo_commit": "ddb7881c52055fe44120a36015a469a847c70c16",
    "base_integration": "578e018f2b0be37b37fa4c8e52692cc1c5f941c5",
}
BLOBS = {
    "qa_cycle7_ic_owner88/ic_rectangular.txt":
        "a2077cd21bcd5f497ac3304bf7f9d0d76d6b32bd",
    "qa_cycle7_ygo89/symbols/variable.json":
        "3f0d4c2f2a8ff0a85cf33f80e25862cf168d43db",
    "qa_cycle7_ygo89/parts/variable.json":
        "f7f8dc1e2c76e870733c9f087c2f6d5dc8dffbc9",
    "qa_cycle7_ygo89/symbols/trimmer.json":
        "acd23f7f5902f41ec888619165b0cfd92db7fd59",
    "qa_cycle7_ygo89/parts/trimmer.json":
        "93859282dddaa77f11d35202a644d8f159919ab1",
    "qa_cycle7_ygo89/symbols/fuse.json":
        "6af105eb850211b0f86e5fc7df59da28719d2e76",
    "qa_cycle7_ygo89/parts/fuse.json":
        "a0ec7cc01b22c26506ce581376c5d9925f8e9890",
}
IDS = {
    "variable": "resistor.variable",
    "trimmer": "resistor.trimmer",
    "fuse": "fuse.general",
}
EXPECTED_NUMBERS = {
    "variable": ("1", "2", "3"),
    "trimmer": ("1", "2", "3"),
    "fuse": ("1", "2"),
}
EXPECTED_NAMES = {
    "variable": ("A", "B", "W"),
    "trimmer": ("A", "B", "W"),
    "fuse": ("A", "B"),
}


def _git_blob(value: bytes) -> str:
    return sha1(b"blob " + str(len(value)).encode() + b"\0" + value).hexdigest()


def ensure_verified():
    for path, digest in BLOBS.items():
        raw = (SNAPSHOTS / path).read_bytes()
        assert _git_blob(raw) == digest, (
            f"Noncanonical owner production snapshot {path}"
        )


def owner_symbol_part(key: str):
    from gost_schematic.catalog.loader import parse_symbol
    from gost_schematic.catalog.part_loader import parse_part

    ensure_verified()
    raw = SNAPSHOTS / "qa_cycle7_ygo89"
    symbol = parse_symbol(json.loads(
        (raw / "symbols" / (key + ".json")).read_text(encoding="utf-8")
    ))
    part = parse_part(json.loads(
        (raw / "parts" / (key + ".json")).read_text(encoding="utf-8")
    ))
    return symbol, part


def owner_renderer():
    """Execute genuine PAINT bytes as a separate test-only Python module.

    Source .txt is never copied to an installed production source package.
    Real math, glyph measurement and SVG implementation are imported verbatim.
    """
    ensure_verified()
    name = "_qa_cycle7_real_paint_88"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    origin = SNAPSHOTS / "qa_cycle7_ic_owner88/ic_rectangular.txt"
    # SourceFileLoader accepts .txt as Python source without copying/modifying.
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader(name, str(origin))
    spec = util.spec_from_loader(name, loader)
    assert spec and spec.loader
    mod = util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod
