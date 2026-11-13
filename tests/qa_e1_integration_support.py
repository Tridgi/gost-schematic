"""Independent E1 QA: execute byte-identical frozen real PR80/PR78 sources.

Source SHAs are Git *blob* identities, not made-up test doubles. No package
source or owner PR is edited or merged into the integration branch. A test-only
package search path is installed temporarily for PR80's real source, while
PR78's real standalone file is loaded independently. No Git/network in pytest.
"""

import json
import sys
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
from hashlib import sha1
from importlib import import_module, util
from pathlib import Path

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
    "qa_e1_pr80/gost_schematic/structural/__init__.txt":
        "733a2eb2c36ae9eab3f11fa3ee0cb539845f9a3e",
    "qa_e1_pr80/gost_schematic/structural/model.txt":
        "c1a6239f4475a8e2c1bcd428168a32726dc53b03",
    "qa_e1_pr80/gost_schematic/structural/serialization.txt":
        "8f9a7492b99b9f98a8bc0a21edc6269d575202dc",
    "qa_e1_pr80/gost_schematic/structural/validation.txt":
        "70ee1f368f0dcaa9b3617bcad8a2c9d48c595162",
    "qa_e1_pr80/review_structural_e1.txt":
        "bc3f3e042714082b4a2794cdc367ae060498c3c9",
    "qa_e1_pr80/structural-e1.json":
        "fbcbf1a6bf5b2303b004b21ffdb1f90e1d2e636f",
    "qa_e1_pr78/review_structural_e1_design.txt":
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
    """Materialize exactly verified upstream bytes into ephemeral Python files.

    Ruff can inspect authored QA code without reformatting upstream copies.
    Neither Git fetch nor pip-installed owner implementation is needed.
    """
    verify_exact_source_files()
    assert "gost_schematic.structural" not in sys.modules, (
        "This QA must not accidentally execute an installed model instead of PR80"
    )
    with tempfile.TemporaryDirectory(prefix="qa-e1-upstream-") as sandbox:
        root = Path(sandbox)
        package = root / "gost_schematic" / "structural"
        package.mkdir(parents=True)
        for name in ("__init__", "model", "serialization", "validation"):
            (package / f"{name}.py").write_bytes(
                (MODEL_ROOT / "gost_schematic" / "structural" / f"{name}.txt"
                 ).read_bytes()
            )
        example = root / "review_structural_e1.py"
        example.write_bytes((MODEL_ROOT / "review_structural_e1.txt").read_bytes())
        graphic = root / "review_structural_e1_design.py"
        graphic.write_bytes(
            (GRAPHIC_ROOT / "review_structural_e1_design.txt").read_bytes()
        )
        search_path = str(root / "gost_schematic")
        package_path = gost_schematic.__path__
        package_path.append(search_path)
        try:
            model = import_module("gost_schematic.structural")
            model_specimen = _load_standalone("_qa_real_pr80_7block", example)
            graphics = _load_standalone("_qa_real_pr78_svg", graphic)
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


# Two *separate* concurrent owner updates after the initial snapshot:
# PR80 9c7f.. -> 82d400..; PR78 c49b.. -> b7fa..
CURRENT_SHAS = {
    "model": "82d400d2472a0a546dafcbf18f70d581642ca284",
    "graphics": "b7fa2138e84d5279ef0b894cb4ca56b32732b11b",
}
CURRENT_BLOBS = {
    "qa_e1_current80/__init__.txt":
        "c651d580daf68193554199fbcbfc75107d3a210c",
    "qa_e1_current80/validation.txt":
        "a73dfd1f454031e65142dc91e01f87748b842001",
    "qa_e1_current80/review_structural_e1.txt":
        "40a7c8362d67aa65b9941a0c01934d78ac8f6f5d",
    "qa_e1_current80/verify_structural_e1_ygo2.txt":
        "3667f86a56ea68813df9b13b71417bae8a15bf42",
    "qa_e1_current80/ygo2-seven-view.json":
        "9ddb28d6d0aa42e2d29544020c97b88c6f8650fd",
    "qa_e1_current78/review_structural_e1_design.txt":
        "a4355f76daa5a586f4058bd9f4df26c4acc6634b",
    "qa_e1_current78/review_structural_e1_model.txt":
        "a4c8f7d563fd883c7affede1d0dd067ed258d141",
    "qa_e1_current78/verify_structural_e1_model_render.txt":
        "0802828c688e929dc3ac4f850ff42ab686c85d7e",
}


def current_shared_visual_seed():
    return json.loads(
        (FIXTURES / "qa_e1_current80/ygo2-seven-view.json").read_text(
            encoding="utf-8"
        )
    )


@contextmanager
def real_current_sources():
    """Run genuine latest owner code: PR80 82d400 + PR78 b7fa in isolation.

    Files use the exact original Git blob content. The common model __init__,
    model and serialization modules did NOT change after old 9c7f, so they
    remain identical source blobs; validation and example changed and are
    loaded from the current separately hashed snapshots.
    """
    verify_exact_source_files()
    for path, sha in CURRENT_BLOBS.items():
        assert blob_hash((FIXTURES / path).read_bytes()) == sha, path
    assert "gost_schematic.structural" not in sys.modules
    with tempfile.TemporaryDirectory(prefix="qa-e1-current-") as directory:
        work = Path(directory)
        pack = work / "gost_schematic" / "structural"
        pack.mkdir(parents=True)
        for part in ("model", "serialization"):
            (pack / (part + ".py")).write_bytes(
                (MODEL_ROOT / "gost_schematic" / "structural"
                 / (part + ".txt")).read_bytes()
            )
        (pack / "__init__.py").write_bytes(
            (FIXTURES / "qa_e1_current80/__init__.txt").read_bytes()
        )
        (pack / "validation.py").write_bytes(
            (FIXTURES / "qa_e1_current80/validation.txt").read_bytes()
        )
        sources = {
            "_qa_current80_example":
                "qa_e1_current80/review_structural_e1.txt",
            "_qa_current78_design":
                "qa_e1_current78/review_structural_e1_design.txt",
            "_qa_current78_model_svg":
                "qa_e1_current78/review_structural_e1_model.txt",
            "_qa_current80_verify_legacy":
                "qa_e1_current80/verify_structural_e1_ygo2.txt",
        }
        module_paths = {}
        for name, relative in sources.items():
            target = work / (name + ".py")
            target.write_bytes((FIXTURES / relative).read_bytes())
            module_paths[name] = target
        package_path = gost_schematic.__path__
        package_path.append(str(work / "gost_schematic"))
        try:
            model = import_module("gost_schematic.structural")
            demo = _load_standalone(
                "_qa_current80_example", module_paths["_qa_current80_example"]
            )
            legacy = _load_standalone(
                "_qa_current78_design", module_paths["_qa_current78_design"]
            )
            svg = _load_standalone(
                "_qa_current78_model_svg", module_paths["_qa_current78_model_svg"]
            )
            yield model, demo, legacy, svg
        finally:
            package_path.remove(str(work / "gost_schematic"))
            for name in sources:
                sys.modules.pop(name, None)
            for name in tuple(sys.modules):
                if name == "gost_schematic.structural" or name.startswith(
                    "gost_schematic.structural."
                ):
                    del sys.modules[name]
