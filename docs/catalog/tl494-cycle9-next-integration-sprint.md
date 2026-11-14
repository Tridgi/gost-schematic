# YGO 2 — MAIN 3 2026-11-15 source figure / A3 footprint integration sprint

**PR #113 (existing only).** Frozen original reference: `e695c415fdced164b0e0c39c5249d030795a0aa6`. This is an independently reviewable **read-only symbol geometry** and type-selection adapter, **not a full 15-Net router** or a claim of certified ГОСТ.

## What was already working before this sprint

The first 13 source positions were locked to real packaged `SymbolDefinition` and `PartDefinition`, 36 DRAFT/0 APPROVED. Their real standalone SVG/PNG300DPI, 8 D4 poses of 8 semiconductor source variants, case/arrow/pin tests and original source reference were already present. On old exact SHA `edc71a48035723d48a203ae2ea12588701f68ba8`, specialized 89/89 Python3.12/3.13 PASS. **No repeated catalog IDs or redundant figures introduced.**

## New machine contracts

`gost_schematic.catalog.source_profiles.select_tl494_symbol(reference, candidates)`: fail-closed EXACTLY one source-approved catalog ID, even if correct ID is present among multiple ambiguous offered alternatives. Unknown references, missing symbols, unsafe IDs and unknown manufacturer package mapping cannot be guessed. Failure is `SymbolProfileMismatch.code == "SYMBOL_PROFILE_MISMATCH"`. Source `bind_tl494_source` now invokes the same resolver.

`gost_schematic.catalog.source_footprints.source_footprint(binding)`: immutable typed `SourceFootprint`, fully derived from the **existing real package** and applied D4 transform, with original source pose or independently requested A3 origin. Includes exact physical `PinRef` inventory and role, full stroke-aware ink obstacles for **every** printed primitive, symbol/body keepout, visual bounds, every pin's one real conductive lead segment and its specific outward reserved escape corridor. A 3-pin source-dotted VT1 includes the same 250 µm **nonconductive** photo-specific junction dot in gallery ink and footprint; still only 3 G/D/S real contacts.

`footprint_record(source_footprint(binding))` exports schema v1, integer micrometre positions/boxes/strokes and original part+symbol SHA256 from `agent_project.catalog.value_digest`, plus separate final rendered-symbol SHA and a canonical footprint SHA. `verify_footprint_record` refuses a tampered body, pin, lead, D4 pose, source-lock or SHA. This is read-only and deterministic; neither a paper Net nor a route segment is inferred from ink. NET/PAINT should use **these exact physical bounds** rather than replacing them with a single approximately sized central rectangle.

**Important collision semantics:** `graphic_ink` is a conservative axis-aligned stroked obstacle, not pixel-perfect curve intersection. The pin escape permission applies **only** for the exact `PinRef`, contact coordinate and outward tangent, and does not allow a wire to cross its own symbol body/other leads. Applying overly broad own-symbol exemptions would conceal DA1.12` DRC_WIRE_SYMBOL_INK` and is prohibited. Annotation ink and routing wire-to-wire spacing are separate checks owned by PAINT/NET/QA.

**Output:** `TL494-UGO-cycle9-footprints.json` records 13 true source poses + 104 D4 (13×8) source-symbol footprints. Integrated `TL494-UGO-cycle9-figure-comparisons.json` is a machine-readable source-figure ledger with primary PDF edition/table/page anchors, review scope, and explicit measured-1:1 **BLOCKED**. Both files are packaged and included in the existing 92 SVG + 92 PNG 300DPI workflow artifact, with independently checked hashes and physical lead–endpoint relationships.

## Independent original figure checklist (not a false raster golden)

| Native ID | Printed source | Shape-level finding | Numeric certification |
|---|---|---|---|
| `diode.schottky` | ГОСТ 2.730-73 table 4/9, table 5/9 | Two asymmetric cathode hooks, actual local µm source coordinates, A/K + D4 90° | **BLOCKED** until calibrated source figure |
| `transistor.mosfet_n_enh` | ГОСТ 2.730-73 table 8/3б | Isolated gate, 3 real G/D/S, discontinuous enhancement channel, arrow; extra source dot is photo DRAFT, not a new pin | **BLOCKED** figure overlay / manufacturer datasheet |
| `capacitor.fixed`, `capacitor.polarized`, nonselected `capacitor.electrolytic` | ГОСТ 2.728-74 table 4/1 and note, table 4/2a | Thin plates (+ where source-specified) versus separate heavy-plate option, no implicit substitution | **BLOCKED** |
| `inductor.ferromagnetic` | ГОСТ 2.723-68 table 1/1+2a | Four true arcs and separate nonconductive core, no air-core substitution | **BLOCKED** |
| `resistor.variable` | ГОСТ 2.728-74 table 1/4 | Third physical sliding contact retained; arrow is not a direct common wire | **BLOCKED** |
| `fuse.general` | ГОСТ 2.727-68 table 3/2 | Two real pins; graphic inner line not an unconditional zero-Ohm `Net` | **BLOCKED** |

`src/gost_schematic/catalog/source_profiles/tl494_figure_comparisons_20261115.json` is intentionally **not a saved crop of an unlicensed original scan or a purported calibrated 1:1 image golden**. It records the explicit source graphic form and current vector invariants, not unsupported absolute metric GOST values. ESKD must separately supply signed first-party source imagery or a reproducible, documented measurement reference and approve each figure. No one in this branch may mark any symbol APPROVED.

## Positive, negative, integration QA

- Full 13 source real positions and 104 all-D4 typed stroke footprints, reproducible canonical hash, unique real PinRefs, exactly one conductor lead per physical port;
- fail-closed ambiguous candidates, missing figure, unsafe part/path, wrong ref, swapped diode/MOS physical numbers/roles, lead disconnected from pin, fake revision and stale SHA;
- wrong electrical Net and stolen or inward pin corridor rejected; no blanket self-ink waiver;
- actual SVG/PNG at 300 DPI, true display normal/diagnostic with no green/colored overlays in print, raster metadata plus SHA and all exported pin-lead obstacle provenance checked;
- source 23/15/91/16 remains frozen, no addition/removal of `Circuit.Net` or replacement of current router;
- Python 3.12 and 3.13, Ruff, packaging, 36 DRAFT audit; independent QA/ESKD required.

## Blockers and dependencies

**PASS (this owner's scope only)** if exact-head checks green. **BLOCKED** actual original photograph crop, independent normalized+calibrated ГОСТ↔SVG 1:1 overlay and ESKD figure acceptance; IRFZ44N/1N5822 vendor pin numbers; router 15/15 Net tree; full A3 layout DRC and user print. Current MAIN 3 checkpoint: NET #114 **8/15** only, old original 91-wire route known BAD; this owner will not falsely claim a clean printed TL494 sheet. Main/integration, #105 XP/XS, and frozen user reference unmodified; no merge.

## Explicit original-source versus new-A3 poses

`bind_tl494_source(..., allow_relayout=False)` now checks exact original reference branch **position AND D4**, as well as locked UGO ID and actual physical roles. It fails on a moved original symbol, including VD1. To build a distinct documented **new A3** placement, the consumer MUST opt in via `allow_relayout=True`; all physical `PinRef` numbers and symbolic pin roles are still source-locked and every new point/obstacle is recomputed from the actual moved `ComponentInstance`. This prevents copying obstacles from an old sheet or silently treating A3 re-layout as a byte-identical photo fixture. Boolean values are type checked; no generic "best fit" fallback.
