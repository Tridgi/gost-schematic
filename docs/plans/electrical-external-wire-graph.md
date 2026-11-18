# Electrical workstream: external wire graph and conservative ERC prototype

**Issue:** [#12](https://github.com/Tridgi/gost-schematic/issues/12)  
**Baseline:** `67c66da9950fe36d5955b86a6c1ce93217ca4edc` on `integration/stage0-12`  
**Source branch:** `parallel/electrical`  
**Status:** experimental independent validation; normative approval and routing are out of scope.

## Architectural boundary

The immutable `Circuit.nets` contains physical `PinRef` memberships. It does
not describe drawn wire geometry. `ConductorTopology` remains the independent
**inside-a-symbol** authored ink graph; the external sheet graph must never
join component terminals through the interior of a resistor, capacitor or coil.

New internal-only module: `gost_schematic.validation.external_wire_checks`:

- `WireSegment(start: Point, end: Point, net_name: str)`: exact straight
  external sheet conductor, with an *expected* semantic net label.
- `ExternalWireGraph(segments: tuple[WireSegment, ...], junctions: tuple[Point, ...] = ())`:
  immutable authored geometric facts, not a serialized standard schema.
- `validate_external_wires(circuit, graph, parts, symbols) -> tuple[Diagnostic, ...]`:
  independent inspection; no mutation and no addition to `gost_schematic.api`.

The validator obtains physical connection positions through
`ComponentInstance.pin_positions(symbol)`, resolved by the physical
`PartDefinition.symbol_id`. Pin numbers, not visible labels, identify
terminals. Existing `validate_circuit` is still responsible for general
electrical structural checks and (when requested) polarity ERC.

## Exact contact rules

1. Shared *endpoints* of two external segments are connected.
2. Collinear segments overlapping over strictly positive length are
   physically joined (including partial, nested and reversed segments),
   irrespective of their declared net labels. Different labels yield a short.
3. At other intersections, an explicit `junction` on every participating
   segment is required: an unmarked X crossing or endpoint-to-interior
   T touching point does **not** create a connection.
4. A physical pin attaches at a segment endpoint or an explicit junction
   lying on the segment. A naked crossing at its coordinate cannot attach it
   by proximity. Identical free pin coordinates do not alone connect pins.
5. All coordinates use integer micrometres. No epsilon, snapping, SVG pixel
   intersection, line-width collision, inferred electrical behavior or
   graph mutations are allowed.

Example: two coincidently crossing *unmarked* wires can pass different nets
without a `WIRE_NET_SHORT`; adding the corresponding junction makes their
conductive islands join and exposes a short if the net names differ.

## Validation and negative cases

- Compare connected conductor islands against `Circuit.nets`, detect a
  wire island mixing labels/pin memberships (`WIRE_NET_SHORT`).
- Check every multi-member logical net has one connected conductor island;
  report unwired pins and missing joins (`WIRE_PIN_UNWIRED`,
  `WIRE_NET_DISCONNECTED`).
- Detect physical pin ↔ segment net conflicts, pin touches at unmarked
  interiors, missing net names, unknown pins/parts/symbols, unrelated wired
  pins, unanchored conductor islands, free ends and bogus junctions.
- Preserve physical pin identity under orthogonal rotation and mirroring.
- Regression fixtures test positive and negative X crossings, marked and
  unmarked T branches, valid/shorting overlap, 1 µm gaps, dangling/orphan
  branches, diagonal crossings and rotated/mirrored terminals.

## Complexity and explicit limits

The prototype intentionally uses an `O(S² + S·P + S·J)` exact pairwise
algorithm for `S` wire segments, `P` physical pins and `J` explicit
junctions. It is **not** suitable for large routing canvases without a
spatial index. Segment coordinates and junctions are manually authored;
there is no persistence/JSON schema, command-line switch, public API,
auto-placement, autorouter or reverse generation of `Circuit.nets`.

Only straight external segments are supported. Exact stroke-width/clearance
DRC, layered crossings, jumpers, electrical equivalence through passive
components, multi-sheet labels/ports, net ties, buses, intentional
no-connects, diagonal junction at non-integer coordinates, arc conductors,
and thermal/electrical simulation are **not** implemented.

A missing mark on an actual intended electrical T-junction is treated as a
missing connection, not silently repaired. This conservative convention
requires explicit upstream authoring; it is not presented as full
ГОСТ 2.721/2.702 conformity. All 18 existing catalog UGO remain DRAFT.

## Delivery gate

Run `ruff check .`, `pytest -q`, catalog audit, wheel verification and
GitHub Actions on Python 3.12/3.13. Review the isolated Draft PR into
`integration/stage0-12`; no merge by this workstream.
