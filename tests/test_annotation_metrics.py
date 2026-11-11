"""The true font measurement adapter propagates actual face metrics."""

from gost_schematic.core.geometry import Box
from gost_schematic.engines.annotation import metrics
from gost_schematic.model.annotations import TextStyle


def test_pillow_adapter_converts_font_bbox_into_physical_units(monkeypatch):
    class FakeFont:
        def getbbox(self, text, anchor):
            assert anchor == "ls"
            assert text == "R123"
            return (-2, -400, 600, 80)

        def getlength(self, text):
            return 620

    monkeypatch.setattr(metrics, "_load_font", lambda path: FakeFont())
    style = TextStyle("/fake/gost.ttf", "GOST Type B", 5120, 300)
    measured = metrics.PillowTextMeasurer().measure("R123", style)
    assert measured.ink_box == Box(-20, -4000, 6000, 800)
    assert measured.advance_um == 6200
