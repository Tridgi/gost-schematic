# Issue #89 / Cycle 8 — XP/XS physical connectors (DRAFT)

Base integration/stage0-12 at 1cdd11a3e72e467573d5d660db923b201be21df9. Normative source: [ГОСТ 2.755-87, tables 5/6](https://eelib.narod.ru/eskd/GOST_2.755-87.pdf), figures visually inspected on PDF pp. 9–10 (one-based).

| ID | Physical variant | Pins | Exact source |
|---|---|---:|---|
| connector.plug_contact | XP shank | 1 | table 5 pos.1(1) |
| connector.socket_contact | XS receptacle | 1 | table 5 pos.1(1) |
| connector.plug_4 | XP four-contact group | 4 | table 6 pos.3 |
| connector.socket_4 | XS four-contact group | 4 | table 6 pos.4 |

All four have separate SymbolDefinition and PartDefinition passports. Each physical contact has distinct PhysicalPin, GraphicPin and usable PinRef; groups have four electrically independent conductor islands. Numbers 1–4 identify *abstract* catalog terminals, not manufacturer pinouts. Nothing implies automatic mating, crossing or common-nets: real Circuit.Net is always explicitly authored. Do not substitute Issue #90 graphical continuation for a physical connector. Group profiles use repeated contacts from the standard; they do not claim numbered-block variant or a true package footprint.

## Diagnostic target contract

Module: gost_schematic.engines.connection_targets; function connection_targets(instance, part, symbol). Validates IDs and physical/graphic contact inventory, produces typed DiagnosticConnectionTarget with real PinRef, number, physical name, transformed Point and Side for all eight D4 orientations. Supports every old static discrete component as well. PAINT can draw a green editor-only square at this Point. No green graphics enter clean SymbolDefinition.graphics or clean PDF/SVG; example debug square 1.3 mm exists ONLY in diagnostic render.

## Review, tests, and release gates

examples.review_connectors_cycle8 generates 2 overview and 8 individual clean/diagnostic metric SVG (10 in total); GitHub workflow rasterizes 10 PNG at true 300 DPI with rsvg-convert and examples.verify_connectors_cycle8 checks hashes, mm-to-pixel scale, vector content, nonblank pixels and real physical marker coordinates. tests/test_connector_cycle8.py exercises D4, independent nets, false bridge, phantom pin, double net ownership, target roles, keepout spacing, source status and full catalog 40 DRAFT / 0 APPROVED. Packaging script verifies four additional JSON pairs in wheel.

Source 1:1 independent calibrated overlay, product/package/revision pin assignment, full physical mating semantics, sheet-level typography and independent ESKD/QA sign-off are BLOCKED. All contact dimensions, 0.3 mm stroke, 8 mm row pitch, keepout and text positions are EDITORIAL only. No merge, no main edits, no APPROVED conversion.
