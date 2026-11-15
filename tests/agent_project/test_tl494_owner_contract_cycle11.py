"""Real IC97 frozen 23/15/62 fixture + typed RECON115 display bridge.

The committed source fixture must remain the EXACT immutable Git blob from
the independent IC PR. No tests use synthetic photo topology for acceptance.
"""
import json
from pathlib import Path

import pytest

from gost_schematic.agent_project import owner_source_contract as own
from gost_schematic.agent_project.catalog import CatalogResolver, ProjectError
from gost_schematic.agent_project.design_assistant import (
    TL494_FROZEN_SOURCE_SHA,
    TL494_REQUIRED_PARTS,
)

SOURCE = Path(__file__).parents[1] / "fixtures" / "ai_tl494_ic97_pinned_source.json"


def _fixture():
    raw = SOURCE.read_bytes()
    assert own._git_blob_sha1(raw) == own.IC_FROZEN_FIXTURE_BLOB_SHA1
    return raw


def _modified(src, *, update):
    data = json.loads(src)
    update(data)
    return (json.dumps(data, sort_keys=True, ensure_ascii=False)
            .encode("utf-8"))


def _validate_negative_modified(raw, monkeypatch):
    # Only within this adverse unit test, reach the semantic validation after
    # bypassing the immutable blob guard; production still pins the REAL blob.
    monkeypatch.setattr(own, "IC_FROZEN_FIXTURE_BLOB_SHA1", own._git_blob_sha1(raw))
    return own.verify_frozen_owner_fixture(raw, CatalogResolver())


def test_actual_frozen_23_15_62_16_and_nominals_source_git_identity():
    source = own.verify_frozen_owner_fixture(_fixture(), CatalogResolver())
    assert source["status"] == "SOURCE_TYPED_MEMBERSHIP_LOCKED_PRINT_BLOCKED"
    assert source["source_commit"] == TL494_FROZEN_SOURCE_SHA
    assert source["source_fixture_git_blob_sha1"] == (
        "a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65"
    )
    assert len(source["source_typed_manifest_sha256"]) == 64
    assert source["component_count"] == 23
    assert source["net_count"] == 15
    assert source["source_physical_pinref_memberships"] == 62
    assert source["da1_all_16_physical_pins"]
    assert not source["source_circuit_approved"]
    assert not source["source_photo_pixel_verified"]
    assert not source["print_ready"]
    assert source["source_nominals_preserved_as_literals"]
    assert source["non_installed_parts"] == {
        "DA1": "reference.tl494cn",
        "X1": "reference.connector.x1", "X2": "reference.connector.x2",
    }
    original = json.loads(_fixture())
    for ref in original["components"]:
        assert next(x for x in source["source_components"]
                    if x["reference"] == ref["ref"])["nominal_si"] == ref["nominal_si"]
    for name, members in original["nets"].items():
        assert source["source_nets"][name] == members
    for ref, expected_part in TL494_REQUIRED_PARTS.items():
        assert next(c["part_id"] for c in source["source_components"]
                    if c["reference"] == ref) == expected_part
    assert source == own.verify_frozen_owner_fixture(_fixture(), CatalogResolver())


def test_recon_renames_preserve_original_15_nets_and_never_merge():
    source = own.verify_frozen_owner_fixture(_fixture(), CatalogResolver())
    owner = own.verify_pinned_owner_headers(
        b'TI_DEVICE_ID = "ti.tl494cn.pdip16"\n',
        (
            f'SOURCE_SHA = "{TL494_FROZEN_SOURCE_SHA}"\n'
            'NET_RENAMES = {\n'
            '    "a_INPUT_PLUS": "INPUT_POS",\n'
            '    "b_NEGATIVE_OUTPUT": "OUTPUT_NEG",\n'
            '    "TRANSFER": "ENERGY_TRANSFER",\n'
            '}\n'
        ).encode(),
    )
    assert owner["source_part_id"] == "reference.tl494cn"
    assert owner["manufacturer_part_id"] == "ti.tl494cn.pdip16"
    assert owner["reversible"]
    assert own.verify_owner_reversible_display(
        source, owner,
    )["reversible_to_original_physical_15_net_memberships"]


@pytest.mark.parametrize(("ic_py", "recon_py", "code"), [
    (b'TI_DEVICE_ID = "reference.tl494cn"\n', b'', "OWNER_TI_PART_ID_DRIFT"),
    (b'TI_DEVICE_ID = __import__("os").system("echo bad")\n',
     b'', "OWNER_LITERAL_NOT_STATIC"),
    (b'TI_DEVICE_ID = "ti.tl494cn.pdip16"\n',
     b'NET_RENAMES = {}\n', "OWNER_CONTRACT_MISSING_OR_AMBIGUOUS"),
])
def test_part_bridge_mismatch_or_injection_fails_without_execution(ic_py, recon_py, code):
    with pytest.raises(ProjectError, match=code):
        own.verify_pinned_owner_headers(ic_py, recon_py)


def test_changed_fixture_content_denied_by_git_blob_lock():
    raw = _modified(_fixture(), update=lambda o: o["nets"].pop("FEEDBACK"))
    with pytest.raises(ProjectError, match="SOURCE_FIXTURE_BLOB_SHA_MISMATCH"):
        own.verify_frozen_owner_fixture(raw, CatalogResolver())


@pytest.mark.parametrize(("change", "code"), [
    (lambda x: x["nets"].pop("FEEDBACK"), "SOURCE_NET_INVENTORY_INCOMPLETE"),
    (lambda x: x["components"].pop(), "SOURCE_COMPONENT_INVENTORY_INCOMPLETE"),
    (lambda x: x["nets"]["COMMON"].append("DA1.3"),
     "SOURCE_PINREF_DUPLICATED_ACROSS_NETS"),
    (lambda x: x["nets"]["a_INPUT_PLUS"].append("DA1.99"),
     "SOURCE_DA1_PIN_INVALID"),
    (lambda x: x["nets"].update({"PE": x["nets"].pop("COMMON")}),
     "SOURCE_INVENTED_PROTECTIVE_EARTH"),
    (lambda x: x["nets"]["b_NEGATIVE_OUTPUT"].pop(),
     "SOURCE_PIN_INVENTORY_INCOMPLETE"),
    (lambda x: next(c for c in x["components"] if c["ref"] == "R5").update(
        part_id="resistor.fixed"
    ), "SOURCE_UGO_VARIANT_MISMATCH"),
    (lambda x: next(c for c in x["components"] if c["ref"] == "X1").update(
        part_id="reference.connector.x2"
    ), "SOURCE_EXTERNAL_PART_ID_DRIFT"),
])
def test_strict_original_physical_semantics_negative(change, code, monkeypatch):
    altered = _modified(_fixture(), update=change)
    with pytest.raises(ProjectError, match=code):
        _validate_negative_modified(altered, monkeypatch)


def test_header_source_names_cannot_merge_protective_or_foreign_nets():
    source = own.verify_frozen_owner_fixture(_fixture(), CatalogResolver())
    good = {
        "source_part_id": own.SOURCE_DEVICE_ALIAS,
        "manufacturer_part_id": own.IC_MANUFACTURER_DEVICE_ID,
        "recon_display_renames": {"TRANSFER": "COMMON"},
    }
    with pytest.raises(ProjectError, match="OWNER_NET_RENAME_COLLISION"):
        own.verify_owner_reversible_display(source, good)


def test_only_source_verified_parts_can_be_selected_not_fake_connector_ugo():
    actual = own.verify_frozen_owner_fixture(_fixture(), CatalogResolver())
    assert set(actual["installed_part_locks"]) == {
        c["reference"] for c in actual["source_components"]
        if c["reference"] not in ("DA1", "X1", "X2")
    }
    assert actual["non_installed_parts"]["DA1"] == "reference.tl494cn"
    assert "ti.tl494cn.pdip16" not in CatalogResolver().parts
