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
- `rotation ∈ {0,90,180,270}`, `mirror_x` and `scale > 0` transform the **body and port coordinates**, never the stable port IDs/functional roles. Text is regenerated horizontally after transform. Fractional results round **half up** to integer µm (project determinism, not GOST prescription).
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

For **one** port per side, `t=0.5` is an editorial preference only. For **N** on the same side, proposal: `t_i=(i+1)/(N+1)`, i=0..N−1, rounded to nearest integer µm; actual resulting pitch and corner distances still must pass 6/5 mm editorial checks. A fractional position must be *explicitly recorded* and immutable; do not infer ports where a line touches a border. Multiple ports of a side with nonuniform spacing are rejected by this proposal's default visual policy; ELEKTRIK can propose another named layout policy explicitly.

`FunctionalLink` binds two `{block_id,port_id}` endpoints: **source → target is always the semantic process direction** in ELEKTRIK RFC E1-001. The standalone **visual-only** `arrow_at=target` draws the recommended arrow, and `none` omits it; reverse/source/both arrow styles remain BLOCKED pending an independent graphics contract, rather than silently reversing the typed link. Port directions are checked against arrow semantics. Route waypoints are explicit orthogonal sheet coordinates. No arrow, link crossing or touched border creates a `PinRef`, a node, a conductor, or electrical continuity. The first/last segment must exit/enter the declared outward normal without crossing the block interior; do not silently change endpoint attachment under routing.

**Important:** an arrow symbol at a document/sheet break has special §5.5 requirements. This design does **not** model sheet transitions; never re-label its process arrow as a verified sheet-break arrow.

## Separation from Issue #70

The JSON files in this PR are **standalone design fixtures**, not a locked production model. Mapping proposed to ELEKTRIK:

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

The default sample has no crossed links. A separate negative fixture/test verifies ambiguous border contact does not create a port. For invalid geometry the reference renderer fails closed rather than painting a misleading valid sheet. Additional manually measured OpenGost, independent human typography/contour review, text collision with neighboring blocks/arrows, special line crossing policies, page breaks and cycle policy are **deferred**.

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
