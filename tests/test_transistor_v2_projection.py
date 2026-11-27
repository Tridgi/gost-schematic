"""Lossless V2 staging adapter: real schema, transformed export and source lock."""
import copy
import json
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Line
from gost_schematic.core.transforms import Transform
from ui.bridge.export.project_v2 import render_v2_source
from ui.editor.src.model.contract import digest, strict_loads, validate
from ui.integration.transistor_catalog import (
    ProjectionError,
    export_manifest,
    project_v2_profile,
    verify_profile,
)

FIXTURE = Path(__file__).resolve().parents[1] / "ui/fixtures/toy-v2.gscad.json"
SVG = "{http://www.w3.org/2000/svg}"
BJT = "transistor.bjt_npn.layout_hh.bare"


def test_manifest_partition_and_exact_line_projection():
    catalog = CatalogResolver()
    manifest = export_manifest(catalog)
    assert not manifest["placement_ready"]
    assert len(manifest["profiles"]) == 52
    assert len(manifest["blocked"]) == 60
    projected = {p["source_lock"]["part_id"] for p in manifest["profiles"]}
    blocked = {p["id"] for p in manifest["blocked"]}
    assert not projected.intersection(blocked)
    assert projected | blocked == set(catalog.transistor_layout_ids())
    assert {p["reason"] for p in manifest["blocked"]} == {"UNSUPPORTED_V2_PRIMITIVE"}
    assert json.dumps(manifest, sort_keys=True) == json.dumps(export_manifest(), sort_keys=True)
    for profile in manifest["profiles"]:
        verify_profile(catalog, profile)
        part, symbol = catalog.resolve(profile["source_lock"]["part_id"])
        assert not profile["placement_ready"]
        assert all(isinstance(g, Line) for g in symbol.graphics)
        assert profile["part_definition"]["physical_pins"] == [
            {"number": p.number, "name": p.name, "electrical_type": p.electrical_type.value}
            for p in part.pins
        ]
        for graphic, source in zip(profile["symbol_definition"]["graphics"],
                                   symbol.graphics, strict=True):
            assert graphic["points_um"] == [
                [source.start.x, source.start.y], [source.end.x, source.end.y],
            ]
        assert profile["protection"]["routing_keepouts_um"]
        assert profile["source_lock"] == catalog.lock(part.identifier)


@pytest.mark.parametrize("identifier,reason", (
    ("transistor.bjt_npn.layout_hh.case", "UNSUPPORTED_V2_PRIMITIVE"),
    ("transistor.mosfet_n_enh.body_diode.layout_vv.bare", "UNSUPPORTED_V2_PRIMITIVE"),
    ("transistor.bjt_npn", "UNKNOWN_TRANSISTOR_PROFILE"),
    ("transistor.unknown", "UNKNOWN_TRANSISTOR_PROFILE"),
))
def test_no_approximate_geometry_or_legacy_substitution(identifier, reason):
    with pytest.raises(ProjectionError, match=reason):
        project_v2_profile(CatalogResolver(), identifier)


@pytest.mark.parametrize("field", ("source_lock", "protection", "part_definition",
                                   "symbol_definition", "placement_ready"))
def test_tampered_staging_profile_rejected(field):
    catalog = CatalogResolver()
    profile = project_v2_profile(catalog, BJT)
    bad = copy.deepcopy(profile)
    bad[field] = None
    with pytest.raises(ProjectionError, match="PROFILE_SOURCE_MISMATCH"):
        verify_profile(catalog, bad)


def test_all_projected_profiles_real_v2_schema_and_stable_roundtrip():
    doc = strict_loads(FIXTURE.read_bytes())
    original_nets = copy.deepcopy(doc["project"]["nets"])
    manifest = export_manifest()
    for profile in manifest["profiles"]:
        doc["project"]["part_definitions"].append(profile["part_definition"])
        doc["project"]["symbol_definitions"].append(profile["symbol_definition"])
    validate(doc)
    reopened = strict_loads(json.dumps(doc, ensure_ascii=False))
    validate(reopened)
    assert digest(reopened) == digest(doc)
    assert reopened["project"]["nets"] == original_nets


@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("mirror", (False, True))
def test_real_v2_export_exact_transformed_line_geometry(angle, mirror):
    catalog = CatalogResolver()
    profile = project_v2_profile(catalog, BJT)
    _, symbol = catalog.resolve(BJT)
    doc = strict_loads(FIXTURE.read_bytes())
    project = doc["project"]
    project["part_definitions"].append(profile["part_definition"])
    project["symbol_definitions"].append(profile["symbol_definition"])
    project["components"].append({
        "id": "test-transistor", "source_refdes": "VT1", "refdes": "VT1",
        "part_id": BJT, "value": "",
    })
    sheet = project["sheets"][0]
    sheet["instances"].append({
        "id": "test-transistor-instance", "component_id": "test-transistor",
        "symbol_id": profile["symbol_definition"]["id"], "origin_um": [150000, 100000],
        "rotation_deg": angle, "mirror_x": mirror, "layer_id": "layer-electric",
    })
    project["provenance"]["expected_counts"]["components"] += 1
    validate(doc)
    root = ET.fromstring(render_v2_source(doc, sheet["id"], expected_project_sha256=digest(doc)))
    group = root.find(".//" + SVG + "g[@data-component-id='test-transistor']")
    assert group is not None
    assert json.loads(group.attrib["data-pinrefs"]) == [
        ["test-transistor", p.number] for p in symbol.pins
    ]
    transform = Transform(angle, mirror)
    for line, source in zip(group.findall(SVG + "line"), symbol.graphics, strict=True):
        a, b = transform.apply(source.start), transform.apply(source.end)
        assert tuple(int(Decimal(line.attrib[key]) * 1000)
                     for key in ("x1", "y1", "x2", "y2")) == (
            a.x + 150000, a.y + 100000, b.x + 150000, b.y + 100000,
        )
    assert root.attrib["data-source-net-count"] == "2"
    assert root.attrib["data-authored-wire-count"] == "2"
