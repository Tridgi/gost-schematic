# PAINT Cycle10 — typed external owner-route rendering (DRAFT)

Coordinator MAIN 3: https://github.com/Tridgi/gost-schematic/pull/93#issuecomment-6885032328

## API and source authority

The new src/gost_schematic/rendering/routed_native_sheet.py exports
render_routed_native_sheet(Circuit, ExternalWireGraph, PartDefinition mapping,
SymbolDefinition mapping, TextStyle, TextMeasurer,
physical_ic_renderings_clean={DA1: IcRendered},
physical_ic_renderings_diagnostic={DA1: IcRendered},
route_preview=GlobalRoutePreview, expected_component_count=23,
expected_net_count=15, expected_net_pinrefs=62, physical_page_box=Box(...)).
It returns RoutedSheetRender(clean_svg, diagnostic_svg, graph_sha256,
machine-readable manifest, printable_candidate).

Both SVG files are created from a NEW typed Circuit + NEW externally routed
ExternalWireGraph, never by modifying an existing exported SVG or by copying
the historical 91-wire image. Independent engine checks all 16 DA1 physical
PinRef endpoints and Net assignments, 23 actual symbols, all 15 untouched
Circuit.Net and 62 physical members. Clean and debug physical IC renderings
must use identical source contact identities; green diagnostic tip squares
are final foreground ink and absent from clean.

Every graph conductor name must come from the existing Circuit.Net inventory.
A physical junction dot must meet at least two truly incident conductor
segments on exactly one original electrical Net. Forged foreign Net, fake
same-wire junction, distinct-Net X join, missing member, NC-forged target,
different contact Point, or missing owner DRC must fail closed.

The PAINT independent after-route checks inspect actual measured Type A
glyph-run boundaries against actual wire strokes and native UGO primitives,
plus exact 3 mm distinct-Net parallel conductor clearances, and call
NET114 independent geometric DRC including component ink and measured text.
The source-authoritative wire connectivity checker is always applied.
A partial 8/15, 9/15, or 14/15 route is always BLOCKED, no matter how
few errors exist in its already-accepted partial conductor graph.

An optional physical A3 Box(0,0,420000,297000) changes the viewport to
420x297mm only when all actual symbol, source text, IC glyph, wire stroke
and junction bounds fit without clipping or scaling. Source b continuation
indicators may be printed in original world coordinates if an authoritative
source-owned project was supplied. Compact relocation without that owner's
explicit b mapping is BLOCKED; no fake a label, conductor, or PE.

## Real example and negative-test evidence

- examples/render_tl494_new_router_cycle10.py: original 23/15/16/62 source
  with genuine NEW NET114 attempted graph; exact owner Net and PinRefs,
  eight new-graph full-sheet D4 poses and true SVG output.
- examples/render_tl494_compact_new_router_cycle10.py: genuine RECON115
  compact A3 component placement and 39 font-metric labels, real NET114
  A3 graph attempt; painter renders source-owned DA1 itself, only the
  true 16-lead stroke model is used as an independent route keepout.
- scripts/verify_tl494_compact_cycle10.py: actual clean PNG300 DPI is
  monochrome; debug raster 16 true green pin-tip RGB samples and correct
  physical layout dimension; no photo bitmap parity claimed.
- tests/test_routed_native_sheet_cycle10.py: real 2-Net arbitrary-graph
  fixture distinct from old 91-wire fixed source, hostile wrong Net,
  15-vs-2 wrong topology, foreign X, fake dot on a single conductor,
  wrong owner preview, missing physical IC, 1-um PinRef point forgery
  in both clean and diagnostic snapshots.

Exact pinned immutable source:
e695c415fdced164b0e0c39c5249d030795a0aa6

Owner SHA snapshots staged read-only in C10 dual Python 3.12/3.13 workflow:
- IC97 809616e6ab58b80b6386c664405cdb8ef6a99196
- NET114 2c4596e3e2897c5a34618169e4cfa5c3b8c38b43
- RECON115 10f22cea8d5908605b52853113b0c75bf91eec75
- YGO113 779dc0eabbd2d8f2f1ef9289cb683fcab1414bf1

All the above are DRAFT source-locked artifacts, NOT a release
approval. The old 91-wire source is the known-bad 9-error/32-warning
negative benchmark. The newer route has uncompleted Net trees and must
remain blocked. Owner green CI is not independent QA99 acceptance.
Formal E3 sheet format, source photo parity, 15/15 complete electrically
correct new route, and original normative UGO provenance are pending.

Changes confined to existing Draft PR #93, no main/integration changes,
no self-merge.
