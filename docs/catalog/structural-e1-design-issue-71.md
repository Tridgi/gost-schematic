# Structural electrical diagrams Э1 — standalone graphics design dossier (Issue #71)

**Status: DRAFT proposal, NOT an approved ГОСТ implementation.** Owner YGO2. ELEKTRIK owns the **separate** semantic graph Issue #70. The two contracts must be reviewed together before public API work. The proposal is strictly outside `catalog/symbols`, `catalog/parts`, `PartDefinition`, `Circuit`, `PinRef` and electrical `ConductorTopology`.

## Normative matrix — each requirement isolated from project choices

| Source/paragraph | Normatively supported rule | Not proven / editorial choice |
|---|---|---|
| ГОСТ 2.701-2008, classifications + §5.3.1 | Electrical structural diagram is **Э1**; schematics are not required to be drawn to physical scale. | Neither a universal 40×20 nor a 60×30 mm block is prescribed. |
| ГОСТ 2.702-2011 §§5.1.1–5.1.2 | Show main functional parts and the key relationships; rectangles **or** applicable UGO may represent functional parts. | This library prototypes rectangles only, not electrical physical symbols. |
| ГОСТ 2.702-2011 §5.1.3 | Process-direction arrows on interrelationships are **recommended**, and the sequence of interaction should be legible. | Arrowhead length=3.5 mm, half width=1.5 mm and target placement are design assumptions. An in-sheet process arrow is not an electrical junction. |
| ГОСТ 2.702-2011 §5.1.4 | Every functional part drawn as a rectangle must be named; name/type/document identifier **recommended inside**. | `title_lines`, top-left code, center alignment and wrap rules are editorial. §5.1.5 permits numbered blocks with a table in crowded diagrams; not implemented. |
| ГОСТ 2.701-2008 §5.3.4 | At least **1.0 mm** between neighboring UGO strokes; **3.0 mm** between parallel relationship lines; **2.0 mm** between separate UGO. | Port pitch ≥6 mm, corner inset ≥5 mm and text inset ≥3 mm are *stricter project choices*, not ГОСТ dimensions. |
| ГОСТ 2.701-2008 §§5.3.5–5.3.6 | Contour class can matter: independent-schematic device uses a solid contour; a functional group/device without independent schematic can require a dash-dot contour. | `outline` is deliberately explicit rather than derived from display name. It needs normative contextual review per concrete device. |
| ГОСТ 2.701-2008 §5.5.1 | Relationship lines thickness **0.2–1.0 mm**, recommended **0.3–0.4 mm**. | Preview chooses 0.35 mm for both stroke and relation link. |
| ГОСТ 2.701-2008 §§5.5.2–5.5.4 | Relationships generally use horizontal and vertical segments; sheet-break endings have special rules and cannot be conflated with ordinary flow arrows. | Preview forbids diagonal links and page breaks. Routing is explicit, not inferred from border contact. |
| ГОСТ 2.304-81 | Text styling requires a separately verified actual font profile. | Example uses `OpenGost Type A, sans-serif` as *viewer font request*; it does not embed or measure a licensed face and cannot prove typographic compliance. |

**Official source cards:** https://protect.gost.ru/gost/details/87f1f382-a055-48b7-ae80-f359ff5e1f4e and https://protect.gost.ru/gost/details/d9c1c334-2a90-45cb-ac00-c31da92d706b . Clause interpretations are based on published standard texts; normative line/arrow/paper distinctions require independent ESKD review before approved status.

## Functional block passport / geometry

- Unique stable `id`, semantic `name`, and explicit `title_lines` whose space-joined content must equal `name`; `code` is an optional *view-only* document-facing identifier, not an electrical position marker.
- Rectangle is local `width_um × height_um` around `center_um`; its size can be freely selected **if** text, declared ports, inter-block limits and applicable contour constraints pass. No silent auto-stretch that changes authored size.
- `rotation ∈ {0,90,180,270}`, `mirror_x` and `scale > 0` transform the **body and port coordinates**, never the stable port IDs/functional roles. Text is regenerated horizontally after transform. The one production anchor authority is ELEKTRIK's `resolve_port_positions()`. Model positions stay exact `Fraction`; the final **absolute document** `Point` is rounded once using signed `ROUND_HALF_UP` (half away from zero). SVG never rounds a model anchor. View-only rotation/mirroring/scale are applied afterward and explicitly tracked in manifest.
- Outline is an independent explicit choice: `functional`, `device_with_schematic` or `group_without_schematic`. Avoid guessing whether a particular block is a device with its own schematic.
- Preview demonstrates a nested **text content keepout** (3 mm editorial inset) and code zone above a centered multiline title. A candidate is rejected if text dimensions do not fit; real Type A ink measurement is necessary later. In a production system keep distinct (1) exact glyph ink, (2) text hitbox with clearance, (3) outer block stroke, (4) port approach corridor, (5) arrow tip/stroke clearances, (6) external line keepout. AABB alone is conservative, not final pixel intersection.
- Default title flow: split into `title_lines`, center each line at block `center_um.x`; line centers are symmetric about `center_um.y` at editorial leading 5 mm. Code lies in top inset, must not intersect title. Every transform must **remeasure** this upright text rather than rotate glyphs.

## Declarative side ports and process arrows

`BlockPort` contains `id`, `side` from LEFT/RIGHT/TOP/BOTTOM, `relative_position` as a Decimal string, `direction` from input/output/bidirectional. Local mapping:

| Side | Local coordinates (center origin, width w, height h, `0<t<1`) | Outward normal |
|---|---|---|
| LEFT | `(-w/2, h(t-1/2))` | (-1,0) |
| RIGHT | `(+w/2, h(t-1/2))` | (+1,0) |
| TOP | `(w(t-1/2), -h/2)` | (0,-1) |
| BOTTOM | `(w(t-1/2), +h/2)` | (0,+1) |

For **one** port per side, `t=0.5` is an editorial preference only. For **N** on the same side, proposal: `t_i=(i+1)/(N+1)`, i=0..N−1. This remains an exact `Fraction` through the model; only its **absolute** end coordinate is quantized once in ELEKTRIK. The legacy spacious view checks 6/5 mm editorial gaps, whereas the real PR80 compact view uses different measured clearances (see below). A fractional position must be *explicitly recorded* and immutable; do not infer ports where a line touches a border. Multiple ports of a side with nonuniform spacing are rejected by this proposal's default visual policy; ELEKTRIK can propose another named layout policy explicitly.

`FunctionalLink` binds two `{block_id,port_id}` endpoints: **source → target is always the semantic process direction** in ELEKTRIK RFC E1-001. The standalone **visual-only** `arrow_at=target` draws the recommended arrow, and `none` omits it; reverse/source/both arrow styles remain BLOCKED pending an independent graphics contract, rather than silently reversing the typed link. Port directions are checked against arrow semantics. Route waypoints are explicit orthogonal sheet coordinates. No arrow, link crossing or touched border creates a `PinRef`, a node, a conductor, or electrical continuity. The first/last segment must exit/enter the declared outward normal without crossing the block interior; do not silently change endpoint attachment under routing.

**Important:** an arrow symbol at a document/sheet break has special §5.5 requirements. This design does **not** model sheet transitions; never re-label its process arrow as a verified sheet-break arrow.

## Separation from Issue #70

The JSON files in this PR are **standalone design fixtures**, not a locked production model. The new PR80 bridge uses the genuine typed model at runtime from an ephemeral CI worktree; the production model is not copied into PR #78. Mapping proposed to ELEKTRIK:

| Visual proposal | ELEKTRIK typed graph notion | Ownership |
|---|---|---|
| `blocks[*].id/name/title_lines/code` | `FunctionalBlock.id/name`, view-only `title_lines/code` | ELEKTRIK owns semantic name; YGO enforces exact split mapping, never embeds line breaks or code into the graph |
| `center_um/size_um/rotation/mirror_x/scale` | model `origin:Point, width_um,height_um`; view-only rotation/mirror/scale | For untransformed geometry, model origin=visual center−size/2; odd-µm half-origins fail closed; transforms are an independent view |
| `ports[*].id/side/relative_position/direction` | separate typed `BlockPort(block_id,id,side,direction,position:Fraction)` | Visual decimal strings convert exactly to rational `[numerator,denominator]`; no float; model owns IDs/roles, YGO view owns clearances |
| `links[*].source/target/arrow_at/via_um` | typed `FunctionalLink(id,source,target)`, view-only `arrow_at/via_um` | Source→target remains semantic direction; route waypoints and arrow markers are not part of the model |
| `diagram_type=E1` | `StructuralDiagram` | Typed separate structural domain; never `Circuit` |

Issue #70 RFC E1-001: https://github.com/Tridgi/gost-schematic/issues/70#issuecomment-6862724943 ; coordinator conditional **GO for isolated prototype only**, not a public schema or merge: https://github.com/Tridgi/gost-schematic/issues/70#issuecomment-6862999265 . The `semantic_projection()` adapter exports experimental `{schema_version,blocks,ports,links}` with separate typed ports and `[numerator,denominator]` rational positions. Because the current proposed ELEKTRIK graph contains no pose transform, projection **fails closed** on rotated, mirrored or scaled views rather than quietly misplacing typed side ports. Pose/view translation needs a future approved RFC. **BLOCKED for stable/public schema and renderer integration** pending subsequent ELEKTRIK/ESKD review.

## Reference preview and evidence

`python examples/review_structural_e1_design.py --fixture examples/fixtures/structural_e1/blocks.json --output-dir output/structural-e1` generates **clean/diagnostic vector SVG**, a geometric manifest and `semantic-projection.json` (draft Issue #70 field mapping, no runtime model import). Six functional blocks, seven semantic links, 3 parallel B2→B3 tracks, one bottom/top flow, two right→left flows, explicit ports, inside multiline names and optional codes. Everything is DRAFT. This is *not* a production renderer and intentionally uses only Python stdlib; it cannot represent a physically validated net.

The default sample has no crossed links. A separate negative fixture/test verifies ambiguous border contact does not create a port. For invalid geometry the reference renderer fails closed rather than painting a misleading valid sheet. The new seven-block reference preview now measures OpenGost Type A ink from the actual external font and rejects title hitbox overflow. Independent normative font-outline/contour review, non-orthogonal diagram routing policies, page breaks and cycle policy remain **deferred**.

## Positive / negative acceptance scenarios

| ID | Scenario | Required outcome |
|---|---|---|
| E1-P01 | 6 independently named blocks, 7 links, multi-line name and optional code | Deterministic clean/diagnostic SVG; 21 electrical DRAFT remain unchanged |
| E1-P02 | 3 uniformly spaced right ports + 3 aligned left ports | Preserved exact port IDs, 9 mm pitch for sample, deterministic attachment |
| E1-P03 | Orthogonal transformation `0/90/180/270` × mirror | Eight distinct correct poses; IDs and directions unchanged; title stays upright |
| E1-P04 | Scaled block with valid multiple ports and title | Positive size/placement revalidation, no change of semantics |
| E1-N01 | Missing/double block or port ID | Hard failure; never infer endpoint |
| E1-N02 | Corner port / nonuniform / parallel port pitch <6 mm | Hard failure, no fallback fake physical pin |
| E1-N03 | Wrong arrow flow (output used as target, input as source), dangling or self-link | Hard failure |
| E1-N04 | Diagonal/zero segment, inward initial segment, block interception, parallel links <3 mm | Hard failure |
| E1-N05 | Title/code exceeds text region; transformed small side does not fit | Hard failure, no silent text shrink or content truncation |
| E1-N06 | Add `PartDefinition`, `PinRef`, `nets`, electrical `part_id` | Hard failure; no electric circuit coercion |
| E1-N07 | Invalid scale/rotation, float relative position / NaN / duplicate link | Hard failure and deterministic diagnostics |
| E1-N08 | Geometric crossing of two functional links | No inferred net/junction; graph remains declared-only |

**Not acceptance:** visual comparison to original ГОСТ does not prove 1:1 calibration or verified text heights; samples use editorial dimensions. All future bridges into shared rendering/graph APIs require separate RFC and coordinator consent.


## Issue #71 follow-up: actual ELEKTRIK PR #80 compatibility, QA Issue #83

**New deliverable:** `examples/review_structural_e1_model.py`, backed by the exact real `gost_schematic.structural` types from ELEKTRIK PR #80 (not a fake class, and never a new electrical UGO). The independent CI `.github/workflows/e1-pr80-graphics-review.yml` fetches the true owner branch **into a temporary runner only**, records its commit SHA and verifies a byte-exact copy of the owner's canonical 7/18/9 fixture. The branch/PR code remains strictly separated.

### Common source of truth and quantization (ONE contract)

The initial difference was material: PR #78 rounded intermediate local offsets while PR #80 previously rejected `E1_PORT_OFF_GRID`. ELEKTRIK's corrective plan in [Issue #70](https://github.com/Tridgi/gost-schematic/issues/70#issuecomment-6864537202) specifies signed absolute `ROUND_HALF_UP`, and YGO2 [accepted](https://github.com/Tridgi/gost-schematic/issues/70#issuecomment-6864809378). This is now implemented in PR #80 at `82d400d2472a0a546dafcbf18f70d581642ca284`, verified by the real-model cross-PR workflow; the earlier model SHA `9c7f625...` instead rejected fractional-µm ports.

- **Typed positions:** `BlockPort.position: Fraction | None`, JSON `[numerator,denominator]` or `null`. Auto side positions `(i+1)/(N+1)`; exact fraction until final document point.
- **Final integer model anchor:** given absolute rational `n/d` (`d>0`), use `sign(n) * ((2*abs(n)+d)//(2*d))` **once**, after addition of rectangle `origin`; not bankers' rounding, and not prior rounding of relative offset. Negative `-10000.5` → `-10001`.
- **Consumer rule:** SVG/PNG generator **must use only** `resolve_port_positions(diagram): dict[PortRef, Point]` and never calculate parallel side-port anchors. The same resolved point is used for diagnostic marker, path start/end, scene manifest and post-raster audit. Coincident anchors after quantization must produce `E1_PORT_COLLISION` in the real model.
- **Example:** 20 000 µm side + 2 automatic ports → final offsets `6667/13333` µm; 12 000 µm side → exact `4000/8000` µm. The legacy standalone reference preview now mirrors signed *absolute* rounding for illustration; **only** real-model SVG gate proves production equivalence.
- **Transform:** rotation/mirroring and view scale operate on the resolved model Point and its rectangle, retain original `PortRef`, and record `model_um` vs `svg_um` in the manifest. Without view pose they must match 1:1. These graphics transforms are not silently added to `FunctionalBlock`; no production pose schema has been approved.

### Explicit compatibility matrix

| Concern | ELEKTRIK PR #80 (semantic authority) | YGO2 PR #78 (view authority) | Proof / caveat |
|---|---|---|---|
| Functional entity | `FunctionalBlock(id,name,origin,width_um,height_um)` | `BlockView(title_lines,code,rotation,mirror,scale,outline)` | `"".join(title_lines)==block.name` checked; no E3 part |
| Side port | `BlockPort(block_id,id,side,direction,position)` | `PortRef → model Point`, corner/spacing reservations | No fake pin; identity remains stable across rotations |
| Quantization | Final absolute Fraction → signed half-away `Point` (implemented in PR80 `82d400d...`) | `resolve_port_positions` only, no extra SVG snap | 20k/N2, negative half ties, odd dimensions, post-round collisions |
| Direction | `FunctionalLink(source,target)` | One process arrow at **target**, not a conductive net | Nine one-to-one `data-link-id` and `data-source-ref`/ `data-target-ref` |
| Routing | PR80 straight *inspection chord* detects geometry but is NOT a router | Explicit visible path with possible orthogonal waypoints, endpoints always model anchors | L9 loops below the 7-block row using two explicit orthogonal waypoints; no inferred X junction |
| Names | Flat semantic `name` | Centered 1–2-line separate fragments, optional code | Actual Type A glyph ink measured with FreeType/Pillow |
| Visual transform | No pose field in typed model | Eight 90°/mirror combinations, exact PortRef identities | Body+link endpoints transformed in one view operation; manifest records both |
| Model JSON | `diagram_type:E1`, strict canonical `blocks/ports/links` | Uses byte-for-byte PR80 fixture; old semantic projection now includes `diagram_type` | `structural_to_json(structural_from_json(raw)) == raw` |
| Electrical data | No `Circuit`, `PinRef`, `Net` or `PartDefinition` | No physical side pins, no painted nodes, no E3 UGO registration | 21 DRAFT electrical UGO unaffected |

### Two explicitly EDITORIAL layout profiles

The previous **spacious 6-block design preview** uses 5 mm corner / 6 mm side-port pitch / 3 mm title inset. These are **NOT ГОСТ-prescribed** constraints. That profile could not render the **previous** PR80 12 mm-high layout with two ports at 4/8 mm, but the **current** PR80 7/18/9 fixture has 30/36 mm-high B1–B7 rectangles and 3-port sides at 9/18/27 mm. Both profiles remain explicitly editorial.

The optional **compact real-model 7-block review view** uses 2 mm corner inset, a ≥3.35 mm side-port center-to-center pitch at 0.35 mm line thickness (≥3 mm clear gap for parallel connection strokes), 1.2 mm inner text inset and 2.5 mm capital glyphs calibrated against an actual installed external OpenGost Type A file. This is an *editorial fit profile* requiring independent ESKD approval; the general physical separation rules do not mandate a particular count or fractional position of ports. The E1 bridge checks measured text hitboxes within the block and does not silently shrink a failing name.

### Shared end-to-end demonstration / artifact provenance

`examples/fixtures/structural_e1/pr80-shared-7b-18p-9l.json` is the **exact canonical** 7 FunctionalBlock / 18 BlockPort / 9 FunctionalLink fixture from ELEKTRIK PR #80 at `82d400d2472a0a546dafcbf18f70d581642ca284` (source blob SHA `fc41ee29b42c84bf5cb967981cf9eab614641083`). The seven blocks are B1 «ДАТЧИК СИГНАЛА», B2 «ОБРАБОТКА СИГНАЛА», B3 «МОДУЛЬ СВЯЗИ», B4 «СИСТЕМА ИНДИКАЦИИ», B5 «УПРАВЛЯЮЩИЙ БЛОК», B6 «ИСПОЛНИТЕЛЬНЫЙ УЗЕЛ», B7 «ОБРАТНАЯ СВЯЗЬ». B2.RIGHT and B3.LEFT each expose 3 ports at 9 mm axis pitch. All 18 stable `PortRef` identities are preserved.

`python -m examples.review_structural_e1_model --model-json examples/fixtures/structural_e1/pr80-shared-7b-18p-9l.json --font-file /path/to/licensed-OpenGost-Type-A.ttf --output-dir output/e1-real-model` generates:

- `e1-seven-clean.svg` — true vector rectangles, centered multiline names, nine actual linked paths with process arrow tips at corresponding target PortRefs;
- `e1-seven-diagnostic.svg` — same geometry plus all 18 **real** port marker coordinates and actual measured text hitboxes;
- `structural-e1.json` — unmodified canonical semantic graph;
- `manifest.json` — per-link PortRef identities and every real SVG path point in integer µm, model/view points, measured font SHA256, view box;
- 4200-pixel `e1-seven-clean-4200px.png` and `e1-seven-diagnostic-4200px.png` produced by the real-font rsvg rasterizer in the independent workflow; `SHA256SUMS` and `PR80_SOURCE_SHA.txt` ensure repeatable provenance.

The post-export verifier in `examples/verify_structural_e1_model_render.py` independently parses the **actual SVG `d` commands**, multiplies visible millimetres by 1000 using exact `Fraction`, compares every first/last coordinate to real model `resolve_port_positions`, validates every named link and arrow, checks the PNG is high resolution and nonblank and publishes SHA-256 hashes. This validates **displayed paths**, not merely image metadata.

**Current real-model verification:** [Cross-PR CI #43508726989](https://github.com/Tridgi/gost-schematic/actions/runs/43508726989) **SUCCESS** Python 3.12/3.13 with actual PR80 `82d400d2472a0a546dafcbf18f70d581642ca284`, **63 dedicated tests passed per interpreter**, authentic B1–B7 7/18/9, real OpenGost Type A font SHA `f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`, actual SVG `d` path verification and PNGs 4200px. Archive `draft-e1-pr80-graphics-seven-blocks`, artifact ID `14076528103`. SHA-256: clean SVG `9f6753f7853c095144e99162ebbb84f131be06181c5b28a0a2b6fdfcbacdb23a`, clean PNG `2acd61a9a40c7658d3b212c8b10e987b0607a99dcc70d005a5bc8c7cdf28a117`, diagnostic SVG `650694d73a5f25f937b88422c453aa81aa433184726a5f22a005a815610b75ac`, diagnostic PNG `30ace25a957352bf3d87114401b49176c26865146a80353dea38dc30ad5d7ba7`. The explicit L9 feedback route runs below all rectangles at y=154000 µm, and viewBox includes every route waypoint, preventing crop.

**QA Issue #83:** https://github.com/Tridgi/gost-schematic/issues/83 . The independent QA owner will execute the wider 32-vector adversarial set and review real SVG/PNG; the YGO result does **not** certify GOST 2.304 glyph outlines or other normative geometry. No merge.
