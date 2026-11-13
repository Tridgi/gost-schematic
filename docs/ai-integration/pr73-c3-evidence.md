# PR #73 follow-up: C3 is the real electrolytic symbol

Read-only evidence obtained from source, live `Circuit`/catalog, exact
SVG viewport and real PNG. This checks the coordinator's concern about
a misleading earlier thumbnail. **Do not substitute generic images from
an image search** in reports: only link the authenticated renderer files.

## Source-of-truth comparison

| Property | Actual live data |
| --- | --- |
| Six-part revision | `03c624ec68760a31b5b7f48d1cfcfffe1fb3e293fb616f2b03127cdd2ed1ddf9` |
| C3 `ComponentInstance.part_id` | `capacitor.electrolytic` |
| physical `PartDefinition` symbol ID | `capacitor.electrolytic` |
| real `SymbolDefinition` | revision **1**, DRAFT, 12 `Line` primitives |
| contrast: ordinary `capacitor.polarized` | 6 `Line` primitives, different body and pins |
| origin | **(100000,80000) µm** = (100,80) mm |
| C3.1 | `PLUS`, positive, **(91000,80000) µm** = (91,80) mm, declared TOP |
| C3.2 | `MINUS`, negative, **(109000,80000) µm** = (109,80) mm, declared RIGHT |
| specimen | 6 components, **16** authored segments, 5 nets, 3 explicit junctions |
| crop `selector` | `{"reference":"C3"}`, direct SVG `viewBox` |
| crop `bbox_mm` | **[87.999,64.5,112.001,87.5]** |
| crop image | **472×453 PNG**, target 500 DPI |
| canonical SVG source SHA | `e90f3e4da6cd1ea8e9f9fa03d191dc79ca5df228e8152b489c1d0d4c388ba9da` |
| canonical crop SVG SHA | `f7c67cbf02741260fb7c423285d68cf2cefe2efc9f4e8ce30566fa91a5f2dab7` |
| PNG SHA256 | `a0f1b46f7d098d17704d2483aedff0af987ee93ad68e49f8f65becbfa4ee2828` |

These hashes describe the fixed baseline proof files; each committed
regeneration may alter JSON metadata but must keep the component source
identity and map exact physical coordinates.

## Why the symbol is **not** the ordinary polarized capacitor

The electrolytic `capacitor.electrolytic` defines two contour-shaped
electrodes (each four closed strokes) and two leads with a pair of
strokes forming the positive sign. In original viewBox coordinates:

- Left input line: (91,80)→(97.75,80) mm.
- Right output line: (102.25,80)→(109,80) mm.
- First contour: x=97.75..99.25, y=76..84 mm.
- Second contour: x=100.75..102.25, y=76..84 mm.
- Plus sign at x≈96.5, y≈75.5 mm.

The simple `capacitor.polarized` instead has two single vertical
plates, does **not** draw these closed contours, has ±8 mm lead ends
and just six strokes. `tests/agent_api/test_c3_provenance.py`
compares **all 12 rendered line coordinates** to the original,
transformed `SymbolDefinition.graphics`, and asserts both physical
`PinRef` positions, polarities and viewport bounds. This test does
not infer symbol ID from pixels.

## Review original artifacts

- [Authentic C3 PNG](../assets/ai-mcp/c3-at-80mm.png)
- [Exact vector SVG](../assets/ai-mcp/c3-at-80mm.svg)
- [Source metadata JSON](../assets/ai-mcp/c3-at-80mm.json)
- [Full six-part PNG](../assets/ai-mcp/six-part-overview.png)
- [Independent model diagnostics](../assets/ai-mcp/diagnostics.json)

This is *geometry identity*, not normative approval of the DRAFT UGO
or OpenGost Type A compliance. Refdes remains an explicitly disclosed
sans-serif specimen label; label checker is not implemented.
