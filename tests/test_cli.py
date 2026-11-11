from gost_schematic.cli import main


def test_cli_renders_draft_symbol_to_svg(resistor_path, tmp_path):
    output = tmp_path / "review.svg"
    result = main(["render-symbol", str(resistor_path), "--output",
                   str(output), "--review-overlay"])
    assert result == 0
    assert output.is_file()
    assert "stroke-dasharray" in output.read_text(encoding="utf-8")
