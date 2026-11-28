"""Review coverage detects gaps without inventing connections or certification."""
from gost_schematic.agent_project.catalog import CatalogResolver
from gost_schematic.core.geometry import Box
from scripts.audit_routing_protection import audit_symbol, covered, generate


def test_union_of_adjacent_protection_boxes_covers_ink():
    ink = Box(0, 0, 100, 100)
    assert covered(ink, (Box(0, 0, 50, 100), Box(50, 0, 100, 100)))
    assert not covered(ink, (Box(0, 0, 49, 100), Box(50, 0, 100, 100)))
    assert not covered(ink, (Box(0, 0, 100, 49), Box(0, 50, 100, 100)))
    assert not covered(ink, ())


def test_protection_audit_is_complete_and_deterministic():
    catalog = CatalogResolver()
    report = generate()
    assert report == generate()
    assert report["total"] == len(catalog.symbols)
    assert [e["id"] for e in report["entries"]] == sorted(catalog.symbols)
    assert report["with_blue_zone"] == sum(bool(s.routing_keepouts)
                                          for s in catalog.symbols.values())
    for identifier in ("resistor.photo", "transductor.parallel_single_phase",
                       "magnetic_amplifier.four_work_three_control"):
        row = audit_symbol(catalog.symbols[identifier])
        assert row["has_blue_zone"]
        assert not row["blocked_cardinal_escapes"]
        assert not [item for item in row["uncovered_functional_bounds"]
                    if not item["conductive"]]
