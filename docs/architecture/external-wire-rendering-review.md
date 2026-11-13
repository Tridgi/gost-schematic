# Rendering cycle 4: catalog expansion and explicit wire junctions

**Issue:** https://github.com/Tridgi/gost-schematic/issues/33
**Baseline:** `caf7db7ad22d9cd22202664471da5ff3a49a754c` (integration/stage0-12). No public model or electrical contract changes; everything remains DRAFT.

## P0: No fixed 19-item ceiling

The gallery continues discovering every installed UGO and checks live catalog audit parity. The visual tests now require **at least** the accepted baseline 19 (a floor, not an exact count), and every baseline symbol ID as a *subset*. Any missing accepted ID yields a unified diff of expected vs actual IDs. New catalog IDs require no manual list edit. Temporary copies of the existing catalog with one and two additional valid versioned symbol/part JSON pairs verify 20 and 21 elements, clean and diagnostic SVG, manifest, pin coordinates, deterministic source vectors, unique refdes, and zero unexpected collisions. Tests never commit simulated UGO or change core/catalog/part sources.

## P1: Internal SVG external-wire adapter

`src/gost_schematic/rendering/external_wire_sheet.py` defines `build_external_wire_obstacles(graph)` and `render_external_wire_sheet(circuit, graph, symbols_by_part, style, measurer, ...)`. The adapter is **private**; it does not modify `gost_schematic.api`, electrical validation, public SVG APIs, Circuit or ExternalWireGraph.

1. Each real `ExternalWireGraph.segments` item becomes one `WireObstacle`, preserving ordered exact integer-micrometre endpoints and net names.
2. The standard `layout_sheet(..., wires=wires)` places text while avoiding the real wires; a failed required text placement produces an error in strict mode. `render_sheet_svg` draws original UGO primitives, wire segments, upright text, and optional geometry-review overlays.
3. A separate SVG group `data-layer=explicit-junctions` receives one circle per **author-specified** `graph.junctions` point. An orphan mark outside all segments is rejected rather than silently clipped. No contact is inferred from arbitrary T touches, X crossings or parsed SVG.
4. Each rendered wire line is checked against its authored endpoints before export. The frozen result includes the SVG, the computed SheetLayout and wire obstacles. The adapter never changes net membership, physical pins, values, or the source graph.

The electrical team's example #29 and its golden fixtures remain untouched. A new example imports its six real components, 18 authored segments and three explicit junctions, validates their external connectivity, then calls the rendering adapter directly.

## Example and review artifact

Install external licensed OpenGost Type A and use:

```bash
python -m pip install -e '.[dev]'
python scripts/install_opengost_type_a.py --directory "$HOME/.local/share/fonts"
FONT_FILE="$(find "$HOME/.local/share/fonts" -type f -iname '*TypeA*.ttf' | head -1)"
python -m examples.review_external_wire_sheet --font-file "$FONT_FILE" --font-family 'OpenGost Type A' --output-dir output/external-wire-review
```

The example emits `authored-wire-clean.svg`, `authored-wire-diagnostic.svg` and `authored-wire-manifest.json`. CI additionally rasterizes both SVGs into PNG and uploads `draft-external-wire-sheet-review` separately from the catalog artifact.

## Checks and limitations

Regression tests cover exact endpoints including 1 µm edits, 18-wire count/order, unchanged Circuit and physical IDs, explicitly marked T, unmarked X, explicitly marked (electrically invalid) X, missing T mark, all junction points present, deterministic output, measured text avoidance/negative collision, and diagnostic SVG layers.

The adapter is a drawing utility, not a topology inference engine, router, simulator or ГОСТ/ЕСКД certification. External wire validation still owns net semantics and may reject an authored marked X crossing. Text glyphs are measured using the installed font but are **not embedded** in SVG; other viewers may substitute glyphs despite CI Fontconfig consistency. Normative comparison and manual approval remain required.
