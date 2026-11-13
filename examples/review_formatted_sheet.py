"""SVG review: default clean schematic, opt-in A4/A3 paper and title content.

No frame/title is drawn unless --mode a4|a3|all is selected.
No title field value is fabricated. --title-headings draws fixed form captions
only, using calibrated OpenGost Type A physical capital-letter height.
"""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from examples.review_c3_placement_proposal import generate_c3_comparison
from examples.review_end_to_end_circuit import authored_specimen, definitions
from gost_schematic.engines.annotation.metrics import PillowTextMeasurer
from gost_schematic.rendering.external_wire_sheet import render_external_wire_sheet
from gost_schematic.rendering.formatted_sheet import PageProfile, compose_formatted_sheet
from gost_schematic.standards.type_a_font import inspect_type_a_font
from gost_schematic.validation.external_wire_checks import validate_external_wires

_SVG = "{http://www.w3.org/2000/svg}"


def _closeup_title(svg: str) -> str:
    """Deliberate review-only title crop at 1:1, not clipping a schematic."""
    source = ET.fromstring(svg)
    title = source.find(f".//{_SVG}g[@data-layer='title-block']")
    if title is None:
        raise ValueError("No title-block for the explicit review close-up")
    root = ET.Element(_SVG + "svg", {
        "width": "189mm", "height": "64mm", "viewBox": "18 235 189 64",
        "data-approval-status": "DRAFT", "data-view": "title-1-to-1",
    })
    ET.SubElement(root, _SVG + "title").text = (
        "DRAFT form 1 with auxiliary lower sheet-margin fields: 1:1 metric review"
    )
    root.append(title)
    return ET.tostring(root, encoding="unicode") + "\n"


def parse_title_fields(raw_fields: list[str]) -> dict[str, str]:
    """Explicit values only, never generated or silently overwritten."""
    parsed: dict[str, str] = {}
    for entry in raw_fields:
        key, separator, value = entry.partition("=")
        if not separator or not key.strip():
            raise ValueError("--title-field requires KEY=VALUE")
        key = key.strip()
        if key in parsed:
            raise ValueError(f"Duplicate --title-field: {key}")
        parsed[key] = value
    return parsed


def generate(
    output_dir: Path,
    font_file: Path,
    *,
    font_family: str = "OpenGost Type A",
    mode: str = "clean",
    title_headings: bool = False,
    title_values: dict[str, str] | None = None,
    compare_c3: bool = False,
) -> dict[str, object]:
    if mode not in {"clean", "a4", "a3", "all"}:
        raise ValueError("Mode must be clean, a4, a3 or all")
    if title_headings and mode == "clean":
        raise ValueError("Title headings require explicit A4/A3 mode")
    if title_values and mode == "clean":
        raise ValueError("Explicit title values require --mode a4|a3|all")
    circuit, graph = authored_specimen()
    parts, symbols = definitions()
    issues = validate_external_wires(circuit, graph, parts, symbols)
    if issues:
        raise ValueError("Refusing invalid authored wiring: " + ", ".join(
            f"{issue.code}:{issue.subject}" for issue in issues
        ))
    style = inspect_type_a_font(font_file, family=font_family, h_um=3500).style
    caption_style = inspect_type_a_font(
        font_file, family=font_family, h_um=2500,
    ).style if (title_headings or title_values) else None
    by_part = {
        part_id: symbols[part.symbol_id] for part_id, part in parts.items()
    }
    measurer = PillowTextMeasurer()
    original_clean = render_external_wire_sheet(
        circuit, graph, by_part, style, measurer,
    )
    original_diag = render_external_wire_sheet(
        circuit, graph, by_part, style, measurer, diagnostic=True,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    sheets: list[dict[str, object]] = []

    # Always provide the unframed, physical 1:1 schematic in requested export.
    if mode in {"clean", "all"}:
        for name, svg in (
            ("schematic-clean.svg", original_clean.svg),
            ("schematic-diagnostic.svg", original_diag.svg),
        ):
            (output_dir / name).write_text(svg, encoding="utf-8")
            files.append(name)

    profiles = {
        "a4-portrait": PageProfile("A4", "portrait"),
        "a3-landscape": PageProfile("A3", "landscape"),
        "a3-portrait": PageProfile("A3", "portrait"),
    }
    selected = (
        list(profiles) if mode == "all"
        else ["a4-portrait"] if mode == "a4"
        else ["a3-landscape", "a3-portrait"] if mode == "a3"
        else []
    )
    for name in selected:
        profile = profiles[name]
        clean = compose_formatted_sheet(original_clean, profile)
        diagnostic = compose_formatted_sheet(
            original_diag, profile, diagnostic=True, offset_um=clean.offset_um,
        )
        filenames = [f"{name}-clean.svg", f"{name}-diagnostic.svg"]
        (output_dir / filenames[0]).write_text(clean.svg, encoding="utf-8")
        (output_dir / filenames[1]).write_text(diagnostic.svg, encoding="utf-8")
        files.extend(filenames)
        sheets.append({
            "format": profile.format,
            "orientation": profile.orientation,
            "mode": profile.mode,
            "dimensions_um": list(profile.dimensions_um),
            "frame_um": [
                profile.frame_um.min_x, profile.frame_um.min_y,
                profile.frame_um.max_x, profile.frame_um.max_y,
            ],
            "form_1_um": [
                profile.title_um.min_x, profile.title_um.min_y,
                profile.title_um.max_x, profile.title_um.max_y,
            ],
            "content_viewport_um": [
                clean.placed_viewport_um.min_x,
                clean.placed_viewport_um.min_y,
                clean.placed_viewport_um.max_x,
                clean.placed_viewport_um.max_y,
            ],
            "offset_um": list(clean.offset_um), "files": filenames,
        })

    if title_headings and "a4-portrait" in selected:
        # Captions are defined by B.1; no fictitious signatories, identifiers
        # or approvals. Fill remains an independent opt-in API operation.
        captioned = compose_formatted_sheet(
            original_clean, profiles["a4-portrait"], title_captions=True,
            title_text_style=caption_style, title_measurer=measurer,
        )
        example = "a4-portrait-captioned.svg"
        close = "form-one-title-closeup.svg"
        (output_dir / example).write_text(captioned.svg, encoding="utf-8")
        (output_dir / close).write_text(
            _closeup_title(captioned.svg), encoding="utf-8",
        )
        files.extend((example, close))

    if title_values:
        # A document number, drawing name, author and signatory must come
        # explicitly from the caller; no sample requisites are invented.
        for name in selected:
            filled = compose_formatted_sheet(
                original_clean, profiles[name], title_values=title_values,
                title_text_style=caption_style, title_measurer=measurer,
                title_captions=title_headings,
            )
            filename = f"{name}-explicit-fields.svg"
            (output_dir / filename).write_text(filled.svg, encoding="utf-8")
            files.append(filename)

    if compare_c3:
        generate_c3_comparison(output_dir, style)
        files.extend(
            f"c3-{case}-{view}.svg"
            for case in ("archived-issue35", "current")
            for view in ("clean", "diagnostic")
        )
        files.append("c3-comparison.json")

    c3 = next(component for component in circuit.components if component.reference == "C3")
    c3_symbol = by_part[c3.part_id]
    report: dict[str, object] = {
        "schema_version": 2,
        "default_export_mode": "clean",
        "selected_mode": mode,
        "status": "DRAFT_VISUAL_REVIEW_ONLY",
        "not_gost_approved": True,
        "standard_reference": "GOST R 2.104-2023 annex B.1; Issue #35",
        "font": {
            "family": style.font_family,
            "sha256": style.font_sha256,
            "source": "external; not embedded; substitution is possible",
            "schematic_cap_height_um": 3500,
            "title_caption_cap_height_um": 2500 if title_headings else None,
        },
        "components": [component.reference for component in circuit.components],
        "component_part_ids": [component.part_id for component in circuit.components],
        "c3_current": {
            "symbol_id": c3_symbol.identifier, "revision": c3_symbol.revision,
            "status": c3_symbol.status.value,
            "origin_um": [c3.origin.x, c3.origin.y],
            "pins_um": {
                k: [v.x, v.y] for k, v in c3.pin_positions(c3_symbol).items()
            },
        },
        "net_names": [net.name for net in circuit.nets],
        "wires": len(graph.segments),
        "junctions": [[point.x, point.y] for point in graph.junctions],
        "sheets": sheets,
        "artifacts": files,
        "restrictions": (
            "No rendered sheet is a certified document. Form-1 fields remain "
            "blank by default. Captions use measured OpenGost Type A h=2.5 mm; "
            "manual comparison to B.1 and requisites still required. "
            "C3 archival Issue35 comparison never alters the current PR62 fixture."
        ),
    }
    (output_dir / "formatted-sheet-manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-file", type=Path, required=True)
    parser.add_argument("--font-family", default="OpenGost Type A")
    parser.add_argument("--mode", choices=("clean", "a4", "a3", "all"), default="clean")
    parser.add_argument("--title-headings", action="store_true")
    parser.add_argument(
        "--title-field", action="append", default=[], metavar="KEY=VALUE",
        help="Explicit form-one cell text, e.g. designation=...; never fabricated",
    )
    parser.add_argument("--compare-c3", action="store_true")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output/formatted-sheet-review"),
    )
    args = parser.parse_args(argv)
    report = generate(
        args.output_dir, args.font_file, font_family=args.font_family,
        mode=args.mode, title_headings=args.title_headings,
        title_values=parse_title_fields(args.title_field),
        compare_c3=args.compare_c3,
    )
    print(
        f"DRAFT review: default clean SVG, selected {args.mode}, "
        f"{len(report['sheets'])} optional page profiles, "
        f"{len(report['components'])} real UGO, {report['wires']} wires, "
        f"{len(report['junctions'])} authored junctions; not ГОСТ-approved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
