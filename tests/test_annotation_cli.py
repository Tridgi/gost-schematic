"""End-to-end CLI entrypoint with deterministic external font metrics stub."""

from gost_schematic.cli import main
from gost_schematic.core.geometry import Box
from gost_schematic.model.annotations import MeasuredText


class Metrics:
    def measure(self, text, style):
        return MeasuredText(Box(0, -1600, len(text) * 500, 1), len(text) * 500)


def test_annotated_cli_creates_review_svg(resistor_path, tmp_path, monkeypatch):
    monkeypatch.setattr("gost_schematic.cli.PillowTextMeasurer", Metrics)
    output = tmp_path / "labels.svg"
    result = main([
        "render-annotated-symbol",
        str(resistor_path),
        "--ref", "R99",
        "--value", "100 kΩ",
        "--font-file", "/fake/font.ttf",
        "--font-family", "Demo Font",
        "--output", str(output),
        "--review-overlay",
    ])
    assert result == 0
    svg = output.read_text(encoding="utf-8")
    assert "R99" in svg
    assert "100 kΩ" in svg
    assert 'data-layer="geometry-review"' in svg



def test_cli_pin_connection_preview_uses_authorized_escape(resistor_path, tmp_path, monkeypatch):
    monkeypatch.setattr("gost_schematic.cli.PillowTextMeasurer", Metrics)
    output = tmp_path / "pin_connections.svg"
    result = main([
        "render-annotated-symbol",
        str(resistor_path),
        "--ref", "R1",
        "--value", "10 k",
        "--font-file", "/fake/font.ttf",
        "--font-family", "Demo Font",
        "--output", str(output),
        "--review-overlay",
        "--show-pin-connections",
    ])
    assert result == 0
    svg = output.read_text(encoding="utf-8")
    assert svg.count("<line ") == 4
    assert 'data-layer="geometry-review"' in svg
    assert "R1" in svg
