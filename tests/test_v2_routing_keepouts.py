"""Persist exact protection boxes and reject routes through transformed artwork."""
import copy
import json
from pathlib import Path

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from ui.editor.src.model.contract import ContractError, digest, validate
from ui.integration.transistor_catalog import project_v2_profile

FIXTURE = Path(__file__).resolve().parents[1] / "ui/fixtures/toy-v2.gscad.json"
PROFILE = "transistor.bjt_npn.layout_hh.case"


def sample(angle=0, mirror=False):
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    project = doc["project"]
    profile = project_v2_profile(CatalogResolver(), PROFILE)
    project["part_definitions"].append(profile["part_definition"])
    project["symbol_definitions"].append(profile["symbol_definition"])
    project["components"].append({
        "id": "protected-device", "source_refdes": "VT1", "refdes": "VT1",
        "part_id": PROFILE, "value": "",
    })
    sheet = project["sheets"][0]
    inst = {
        "id": "protected-instance", "component_id": "protected-device",
        "symbol_id": profile["symbol_definition"]["id"], "origin_um": [130000, 100000],
        "rotation_deg": angle, "mirror_x": mirror, "layer_id": "layer-electric",
    }
    sheet["instances"].append(inst)
    project["provenance"]["expected_counts"]["components"] += 1
    return doc, inst, profile


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_protection_roundtrip_and_wire_collision(angle, mirror):
    doc, inst, profile = sample(angle, mirror)
    validate(doc)
    before = digest(doc)
    restored = json.loads(json.dumps(doc))
    validate(restored)
    assert digest(restored) == before
    assert profile["symbol_definition"]["routing_keepouts_um"] == (
        profile["protection"]["routing_keepouts_um"]
    )
    # Existing horizontal route runs x=20..80 mm at y=30 mm.
    # Place the protected transistor across it, away from route endpoints.
    inst["origin_um"] = [40000, 30000]
    with pytest.raises(ContractError, match="WIRE_KEEPOUT_COLLISION"):
        validate(doc)
    assert digest(restored) == before


@pytest.mark.parametrize("zone,code", (
    ([0, 0, 0, 1000], "INVALID_KEEPOUT"),
    ([1000, 0, -1000, 1000], "INVALID_KEEPOUT"),
    ([-13000, -1000, -11000, 1000], "PIN_IN_KEEPOUT"),
))
def test_malformed_or_pin_blocking_zone_rejected(zone, code):
    doc, _, _ = sample()
    doc["project"]["symbol_definitions"][-1]["routing_keepouts_um"] = [zone]
    with pytest.raises(ContractError, match=code):
        validate(doc)


def test_closed_boundary_and_project_clearance_are_enforced():
    doc, inst, profile = sample()
    # Case radius 5 mm + half stroke + 200 um box padding.
    y0 = min(box[1] for box in profile["symbol_definition"]["routing_keepouts_um"])
    inst["origin_um"] = [30000, 30000 - y0 + 550]
    # Use top edge exactly at y=30 mm, including the margin.
    with pytest.raises(ContractError, match="WIRE_KEEPOUT_COLLISION"):
        validate(doc)
    safe = copy.deepcopy(doc)
    safe["project"]["sheets"][0]["instances"][-1]["origin_um"][1] += 1
    validate(safe)
