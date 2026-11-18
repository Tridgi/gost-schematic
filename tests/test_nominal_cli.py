"""CLI integration for typed nominals, visibility and exact format switching."""

from xml.etree import ElementTree as ET

from gost_schematic.cli import main
from gost_schematic.core.geometry import Box
from gost_schematic.model.annotations import MeasuredText


class Metrics:
    def measure(self, text, style):
        return MeasuredText(Box(0, -1600, len(text) * 500, 1), len(text) * 500)


def _render(resistor_path, tmp_path, monkeypatch, *options):
    monkeypatch.setattr("gost_schematic.cli.PillowTextMeasurer", Metrics)
    output = tmp_path / ("-".join(str(part).replace("/", "_") for part in options) + ".svg")
    status = main([
        "render-annotated-symbol", str(resistor_path),
        "--font-file", "/fake/font.ttf", "--font-family", "Demo",
        "--output", str(output), *options,
    ])
    return status, output


def _labels(path):
    namespace = "{http://www.w3.org/2000/svg}"
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    return [element.text for element in root.findall(f".//{namespace}text")]


def test_cli_compact_by_default_and_full_units(resistor_path, tmp_path, monkeypatch):
    status, output = _render(
        resistor_path, tmp_path, monkeypatch,
        "--nominal", "2300", "--unit", "ohm",
    )
    assert status == 0
    assert _labels(output) == ["R1", "2,3к"]
    status, full = _render(
        resistor_path, tmp_path, monkeypatch,
        "--nominal", "2300", "--unit", "ohm",
        "--nominal-mode", "full_units",
    )
    assert status == 0
    assert _labels(full) == ["R1", "2,3 кОм"]


def test_cli_hides_nominal_but_keeps_reference(resistor_path, tmp_path, monkeypatch):
    status, output = _render(
        resistor_path, tmp_path, monkeypatch,
        "--nominal", "2300", "--unit", "ohm", "--hide-nominal",
    )
    assert status == 0
    assert _labels(output) == ["R1"]


def test_cli_accepts_capacitance_with_si_units(resistor_path, tmp_path, monkeypatch):
    # Resistor geometry is only a layout fixture; the formatter sees the unit.
    status, output = _render(
        resistor_path, tmp_path, monkeypatch,
        "--nominal", "100", "--unit", "nF",
    )
    assert status == 0
    assert _labels(output) == ["R1", "0,1мк"]


def test_cli_rejects_unitless_nominal_and_conflicting_literal(
    resistor_path, tmp_path, monkeypatch,
):
    status, output = _render(
        resistor_path, tmp_path, monkeypatch, "--nominal", "10",
    )
    assert status == 1
    assert not output.exists()
    status, output = _render(
        resistor_path, tmp_path, monkeypatch, "--nominal", "10",
        "--unit", "ohm", "--value", "fake",
    )
    assert status == 1
    assert not output.exists()


def test_cli_undefined_compact_value_fallback_and_strict_error(
    resistor_path, tmp_path, monkeypatch, capsys,
):
    status, output = _render(
        resistor_path, tmp_path, monkeypatch,
        "--nominal", "999.5", "--unit", "ohm",
    )
    assert status == 0
    assert _labels(output)[-1] == "999,5 Ом"
    assert "NOMINAL_COMPACT_UNSUPPORTED" in capsys.readouterr().out
    status, output = _render(
        resistor_path, tmp_path, monkeypatch,
        "--nominal", "999.5", "--unit", "ohm", "--strict-compact",
    )
    assert status == 1
    assert not output.exists()
