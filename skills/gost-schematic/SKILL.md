---
name: gost-schematic
description: Inspect real GOST Schematic Engine SVG-derived images and authoritative electrical diagnostics through the read-only MCP server.
---

# GOST Schematic Engine — Visual inspection workflow

Use this Skill when reviewing circuit layout, refdes, physical pins, conductor
intersections or potential shorts. The MCP service is **read-only** in Issue #65.
There is no move/add/connect tool yet. Never claim it changed a schematic.

## First inspect, then reason

1. Invoke `schematic_list_views(project_ref="six-part")` to get the current
   `project_revision`, candidate views and source `geometry_sha256`.
2. Invoke `schematic_render_overview(project_ref="six-part", mode="clean")`.
   Inspect the returned **ImageContent image/png**, not a text path or a
   generated illustration. Inspect the JSON metadata alongside the picture.
3. If a symbol, text or wire is unclear, invoke one of:
   - `schematic_inspect_component(project_ref="six-part", reference="C3", target_dpi=500)`;
   - `schematic_inspect_region(project_ref="six-part", selector={"pin":{"component":"C3","number":"1"}})`;
   - `schematic_inspect_region(project_ref="six-part", selector={"net":"TOP"})`;
   - `schematic_inspect_region(project_ref="six-part", selector={"bbox_mm":[65,35,75,45]}, padding_mm=4, target_dpi=500)`.
   Each operation re-rasterizes **the original SVG**, retaining millimetre geometry.
   Do not enlarge low-resolution overview PNG pixels.
4. Invoke `schematic_inspect_connection` with two declared physical contact
   dictionaries, for example R1.2 and C3.1. Read the returned declared net and
   the independent ExternalWireGraph diagnostics.
5. Invoke `schematic_get_diagnostics(project_ref="six-part", check="all")`.
   Treat `Circuit` and `ExternalWireGraph` as authoritative; do not deduce
   net membership from a crossing or drawn black dot.
6. Compare `project_revision`, `geometry_sha256`, `bbox_mm`, `pixels`,
   `effective_dpi`, `catalog_sha256` and warning status in results. A preview
   is evidence of render geometry, **not ГОСТ / ЕСКД approval**.

## Validation discipline

- Crossings of distinct conductors may be unconnected unless a junction is
  explicitly authored. Do not connect T/X intersections based on appearances.
- Check physical pins using `PartDefinition` and the component transform,
  especially C3 PLUS pin 1 on TOP and MINUS pin 2 on RIGHT.
- The live six-part specimen has C3 at `(100000,80000)` µm and **16** wire
  segments. Historical C3 at 75 mm / 18-wire examples must remain archival.
- Available modes: `clean` and `diagnostic`. Diagnostic mode shows
  protective boxes, contact dots and semantic net labels for human review.
- If an image is blank, clipped, font-substituted or returns an error, stop,
  disclose the limitation and request a higher-resolution vector re-render.
- Experimental catalog DRAFT status cannot be promoted by this Skill or MCP.
- Reject requests to execute Python, read arbitrary project paths, draw invented
  electrical networks or write to an unapproved workspace.

## Agent iteration contract (future P1; **not implemented**)

When the coordinator approves Issue #64's command service, a future agent can:
snapshot with expected revision → propose *typed* add/move/connect commands →
transactionally validate Circuit and ExternalWireGraph → commit a new revision →
request overview, crop and diagnostics → inspect and repeat. A rejected revision
or geometry conflict must never silently alter wiring. The current MCP tools
only perform the **render / inspect / validate** half of this cycle.

## Known limitations

The only shipped provider is the fixed `six-part` specimen and its named
negative cases from the repository's review examples. Launch in an editable
source checkout. No persistent .gseproj, arbitrary schematics, mutation
commands, sheet-form normative approval, label checker or automatic placement
are available. Font provenance explicitly warns that specimen refdes are
sans-serif, not proven OpenGost Type A. See
`docs/ai-integration/mcp-vision.md`.
