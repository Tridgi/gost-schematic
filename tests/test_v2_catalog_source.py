"""Source-pinned CAD definitions must match generated geometry and physical pins."""
import copy
import json
from pathlib import Path

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from ui.editor.src.model.contract import ContractError, digest, validate
from ui.integration.transistor_catalog import project_v2_profile

FIX = Path(__file__).resolve().parents[1] / "ui/fixtures/toy-v2.gscad.json"


def locked_document():
    doc = json.loads(FIX.read_text(encoding="utf-8"))
    p = project_v2_profile(CatalogResolver(), "transistor.bjt_npn.layout_hh.case")
    s = p["symbol_definition"]
    s["catalog_source"] = {k: p["source_lock"][k] for k in ("part_sha256", "symbol_sha256")}
    doc["project"]["symbol_definitions"].append(s)
    doc["project"]["part_definitions"].append(p["part_definition"])
    return doc


def test_locked_source_roundtrip():
    doc = locked_document()
    validate(doc)
    restored = json.loads(json.dumps(doc))
    validate(restored)
    assert digest(doc) == digest(restored)


@pytest.mark.parametrize("field", ("hash", "geometry", "pins", "keepout", "part"))
def test_tampered_locked_source_rejected(field):
    doc = copy.deepcopy(locked_document())
    s = doc["project"]["symbol_definitions"][-1]
    if field == "hash":
        s["catalog_source"]["symbol_sha256"] = "0" * 64
    elif field == "geometry":
        s["graphics"][0]["points_um"][0][0] -= 1
    elif field == "pins":
        s["pins"][0]["at_um"][0] -= 1
    elif field == "keepout":
        s["routing_keepouts_um"][0][0] -= 1
    else:
        doc["project"]["part_definitions"][-1]["physical_pins"][0]["name"] = "WRONG"
    with pytest.raises(ContractError, match="CATALOG_SOURCE_MISMATCH"):
        validate(doc)
