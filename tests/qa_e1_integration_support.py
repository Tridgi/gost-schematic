"""Independent E1 QA: execute byte-identical frozen real PR80/PR78 sources.

Source SHAs are Git *blob* identities, not made-up test doubles. No package
source or owner PR is edited or merged into the integration branch. A test-only
package search path is installed temporarily for PR80's real source, while
PR78's real standalone file is loaded independently. No Git/network in pytest.
"""

from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
from hashlib import sha1
from importlib import import_module, util
import json
from pathlib import Path
import sys

import gost_schematic


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
MODEL_ROOT = FIXTURES / "qa_e1_pr80"
GRAPHIC_ROOT = FIXTURES / "qa_e1_pr78"
SOURCE_COMMITS = {
    "model": "9c7f62510baafb12685acb67c5034ebfbb8a6b8b",
    "graphics": "c49b7632cac33eafd77b29cc746a37978838f3e4",
    "base": "e79a12003144a1981bdec829573784215ecaf6d7",
}
PINNED_BLOBS = {
    "qa_e1_pr80/gost_schematic/structural/__init__.py":
        "733a2eb2c36ae9eab3f11fa3ee0cb539845f9a3e",
    "qa_e1_pr80/gost_schematic/structural/model.py":
        "c1a6239f4475a8e2c1bcd428168a32726dc53b03",
    "qa_e1_pr80/gost_schematic/structural/serialization.py":
        "8f9a7492b99b9f98a8bc0a21edc6269d575202dc",
    "qa_e1_pr80/gost_schematic/structural/validation.py":
        "70ee1f368f0dcaa9b3617bcad8a2c9d48c595162",
    "qa_e1_pr80/review_structural_e1.py":
        "bc3f3e042714082b4a2794cdc367ae060498c3c9",
    "qa_e1_pr80/structural-e1.json":
        "fbcbf1a6bf5b2303b004b21ffdb1f90e1d2e636f",
    "qa_e1_pr78/review_structural_e1_design.py":
        "85fcf7bc5aff7057f5c489d3f5b697d10c36f119",
    "qa_e1_pr78/blocks.json":
        "cd1ecc6b6c2219b0615dc00b8952ea5588ee77be",
    "qa_e1_pr78/structural-e1-graphic-profile-v1.json":
        "7ec3b786b1a84d21656413a38bfe56bbf91bfd53",
}


def blob_hash(data: bytes) -> str:
    return sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def verify_exact_source_files() -> None:
    for path, expected_sha in PINNED_BLOBS.items():
        file = FIXTURES / path
        assert file.is_file(), f"Missing actual upstream source {file}"
        actual = blob_hash(file.read_bytes())
        assert actual == expected_sha, (
            f"Upstream PR code drift for {path}: {actual} != {expected_sha}"
        )


def _load_standalone(name: str, path: Path):
    spec = util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def real_sources():
    """Load upstream source code, keep model import identities unmodified."""
    verify_exact_source_files()
    search_path = str(MODEL_ROOT / "gost_schematic")
    package_path = gost_schematic.__path__
    assert "gost_schematic.structural" not in sys.modules, (
        "This QA must not accidentally execute an installed model instead of PR80"
    )
    package_path.append(search_path)
    try:
        model = import_module("gost_schematic.structural")
        model_specimen = _load_standalone(
            "_qa_real_pr80_7block", MODEL_ROOT / "review_structural_e1.py"
        )
        graphics = _load_standalone(
            "_qa_real_pr78_svg", GRAPHIC_ROOT / "review_structural_e1_design.py"
        )
        yield model, model_specimen, graphics
    finally:
        package_path.remove(search_path)
        for name in ("_qa_real_pr80_7block", "_qa_real_pr78_svg"):
            sys.modules.pop(name, None)
        for name in tuple(sys.modules):
            if name == "gost_schematic.structural" or name.startswith(
                "gost_schematic.structural."
            ):
                del sys.modules[name]
        # Re-imports from production after test teardown remain unmodified.


def graphic_source():
    return json.loads((GRAPHIC_ROOT / "blocks.json").read_text(encoding="utf-8"))


def previous_32():
    return json.loads(
        (FIXTURES / "qa_structural_e1_negative_vectors.json").read_text(
            encoding="utf-8"
        )
    )["cases"]


def _set_at_pointer(obj, pointer, operation, value):
    parts = pointer.strip("/").split("/")
    target = obj
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    key = parts[-1]
    if operation == "replace":
        if isinstance(target, list):
            target[int(key)] = value
        else:
            assert key in target
            target[key] = value
    elif operation == "add":
        if isinstance(target, list):
            assert key == "-"
            target.append(value)
        else:
            assert key not in target
            target[key] = value
    elif operation == "remove":
        if isinstance(target, list):
            target.pop(int(key))
        else:
            del target[key]
    else:
        raise AssertionError(f"Unknown historical QA operation {operation!r}")


def materialize_previous(case):
    parent = json.loads(
        (FIXTURES / "qa_structural_e1_negative_vectors.json").read_text(
            encoding="utf-8"
        )
    )
    graph = deepcopy(parent["base_diagram"])
    for mutation in case["mutations"]:
        _set_at_pointer(
            graph, mutation["path"], mutation["op"], mutation.get("value")
        )
    return graph


def _canonical_position(value):
    """Explicit, loss-documented adapter for the OLD noncanonical test corpus.

    Only original fixture's six-decimal pseudo-thirds are interpreted as exact
    thirds. This is *not* an upstream model or a safe general float converter.
    Invalid positions remain invalid and are passed to strict real decoder.
    """
    if value is None:
        return None
    if type(value) is float and value == 0.333333:
        return [1, 3]
    if type(value) is float and value == 0.666667:
        return [2, 3]
    if type(value) is float:
        fraction = Fraction(str(value))
        return [fraction.numerator, fraction.denominator]
    return value


def convert_previous_to_model_data(legacy):
    """Test-only translation of the old 32-case intent to actual PR80 JSON v1.

    Explicitly strips ONLY old view metadata; unknown mutations are retained
    and consequently rejected by the real strict parser. No E3 semantics.
    """
    result = {
        "schema_version": legacy["schema_version"],
        "diagram_type": "E1",
        "blocks": [],
        "ports": [],
        "links": [],
    }
    for block in legacy["blocks"]:
        known = {
            "id", "name", "x_um", "y_um", "width_um", "height_um", "ports"
        }
        item = {
            "id": block["id"],
            "name": block["name"].replace("\n", " "),
            "origin_um": [block["x_um"], block["y_um"]],
            "width_um": block["width_um"],
            "height_um": block["height_um"],
        }
        item.update({k: v for k, v in block.items() if k not in known})
        result["blocks"].append(item)
        for port in block["ports"]:
            port_known = {"id", "side", "direction", "position"}
            record = {
                "block_id": block["id"],
                "id": port["id"],
                "side": str(port["side"]).lower(),
                "direction": str(port["direction"]).lower(),
                "position": _canonical_position(port["position"]),
            }
            record.update({k: v for k, v in port.items() if k not in port_known})
            result["ports"].append(record)
    for edge in legacy["links"]:
        record = {
            "id": edge["id"],
            "source": deepcopy(edge["source"]),
            "target": deepcopy(edge["target"]),
        }
        if edge.get("arrow") != "source_to_target":
            record["arrow"] = edge.get("arrow")
        record.update({
            k: v for k, v in edge.items()
            if k not in {"id", "source", "target", "arrow"}
        })
        result["links"].append(record)
    return result


DISPLAY_ONLY = frozenset({
    "TEXT_INK_OVERFLOW",
    "TEXT_OUTSIDE_BLOCK",
    "PORT_CLEARANCE_BLOCKED",
    "CROSSING_NO_IMPLICIT_JOIN",
    "CROSSING_FORCED_NET_JOIN",
    "ARROWHEAD_VISUAL_REVERSED",
    "MULTIPLE_LINKS_ON_ONE_PORT",
    "INVALID_TRANSFORM",
})
