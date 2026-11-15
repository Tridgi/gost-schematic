# Cycle 16 — TL494CN physical router-port trust contract (PR #97)

**Release status:** source-accurate DRAFT geometric **INPUT** for NET/RECON/PAINT/QA,
**not** an externally routed sheet, an ESKD approval, or authorization to merge.

## 1. Source authority and exact reproducible interface

Owner module: `src/gost_schematic/electrical/ic_router_ports.py`.

```python
from gost_schematic.electrical.ic_router_ports import (
    export_tl494_router_ports,
)

# source_signed is a genuine IcCircuitBinding, verified with the immutable
# frozen fixture and true manufacturer IcLibraryRecord, not any ELK JSON.
router_ports = export_tl494_router_ports(
    source_signed,
    producer_shas={
        "IC97": "<real 40-hex Git commit SHA>",
        "RECON115": "<real 40-hex Git commit SHA>",
        "PAINT93": "<real 40-hex Git commit SHA>",
        "YGO113": "<real 40-hex Git commit SHA>",
    },
)
router_ports.verify_against(source_signed)
print(router_ports.to_json())
```

This exporter rejects any mismatch in the full **23 original reference+PartID**
inventory, the exact **15 literal original electrical Net names and every
ordered PinRef tuple (62 total)**, missing/extra DA1 physical terminals, a
forged Texas Instruments pin name/electrical type, or an invalid current
manufacturer `IcCircuitBinding`. Frozen source commit:
`e695c415fdced164b0e0c39c5249d030795a0aa6`.
Only DA1's original `reference.tl494cn` maps to
`ti.tl494cn.pdip16`; `b-X2` and `b-R5` are **two graphical, non-electrical
stubs**, never additional `Net`, `PinRef` or junctions.

Each `IcRouterPort` carries its true `DA1.n`, unchanged original Net,
TI full physical pin name and manufacturer description/role, TI electrical
type, **absolute integer-micrometre contact tip**, **outward unit normal**,
local coordinate relative to this specific native **DRAFT router symbol ink
AABB**, and a narrowly scoped **own-PinRef-only** 1800×800µm escape
rectangle. The 1800/400µm shape is a search/port reservation convenience,
**not** a reduction of the project's separate 3/2/1mm conductor/ink/text
clearances, and grants **no foreign-Net crossing permission**. Complete
Type A/text glyph ink/real SVG are owned by YGO/PAINT; this per-IC symbol
box must not be mistaken for all 73 RECON Type A text guards.

Source fingerprint fields `source_netlist_sha256`,
`source_binding_sha256`, `manufacturer_record_sha256` and the four actual
producer Git SHAs are **audit provenance only, not bearer authentication**.
Every importer MUST recompute/verify them against an actual owner checked-out
`IcCircuitBinding`, and run full typed Circuit and native ink DRC.
Arbitrary outsider-supplied JSON/metadata, even with copied SHA strings,
cannot serve as source authentication.

## 2. External placement/visibility graph safety

An external ELK `org.eclipse.elk.portConstraints=FIXED_POS` fixes the port
**relative to the moved node**, not its original absolute point. The
actual independent 23-node/62-port experiment in
[Cycle16 scouting](https://github.com/Tridgi/gost-schematic/issues/107#issuecomment-6897218435)
moved 23 nodes and 62 absolute world tips, output 493.805×529.159mm.
Importing those visually consistent points as true source wires would
corrupt the physical contract.

Use the **typed** candidate gate, for example:

```python
router_ports.verify_external_layout(
    source_signed,
    proposed_origin_um=router_ports.part_origin_um,
    proposed_rotation_deg=router_ports.rotation_deg,
    proposed_mirror_x=router_ports.mirror_x,
    proposed_ports=router_ports.ports,
)
```

It accepts only exactly the 16 original manufacturer PinRefs with their
actual 16 full names, TI functions, electrical types, original source Net,
integer absolute tip, outward normal, local ink offset and own-only escape
box. It fails closed on: extra/missing/duplicate/fake physical pin, 1µm
tip drift, local port shift, reverse-D4 normal, forged Net/NC/pin role,
changed footprint/part placement or absolute node transform, tampered
producer or source record, or stale geometry consent.

An `IcGeometryConsent` object **alone does not authorize any external
relocation**. The present production `IcCircuitBinding.revise()` requires
the same physical placement; if RECON actually moves the IC component,
it must first deliver a new source-validated physically positioned
`IcCircuitBinding` with source-fingerprint-bound geometry/reroute
authorization and all connected wires independently reconstructed. Until
a proper owner-reviewed current-place rebind exists, this exact-C16
import gate **BLOCKS even an ELK `FIXED_POS` layout that moves the entire
node by 1µm**. It does not make a false claim of accepting a relocated IC.

Neither this gate nor ELK may add electrically conductive intermediate
waypoints, auto-junctions, SVG T/X corners, simulated NC, or new b-stub
conductors. Routing topology remains solely the existing Circuit and
NET's independently DRC-audited `ExternalWireGraph`.

## 3. Exact source integration and CI command

The real, SHA-pinned RECON #115 + PAINT #93 + YGO #113 integration
workflow `.github/workflows/ic-recon115-live-cycle11.yml` assembles
actual owner Git checkout trees, then executes:

```sh
ruff check scripts/verify_ic_recon115_live_bridge.py \
  examples/tl494_cycle9_circuit_integration.py src/gost_schematic/electrical/
pytest -q -ra scripts/verify_ic_recon115_live_bridge.py
python -m scripts.verify_ic_recon115_live_bridge \
  --font-file "$IC_TYPE_A_FONT_PATH" \
  --output-dir output/ic-recon115-cycle11
sha256sum output/ic-recon115-cycle11/*.json
```

The output includes `DA1-tl494-router-ports.json` as a standalone
machine-readable import contract, the same data embedded in
`source-physical-witness.json`, two real source physical clean/diagnostic
SVGs (0 vs 16 verified editor contact targets), Type A source fingerprint,
exact two real non-electrical continuation *strokes*, and the original
`bridge-manifest.json`. Python 3.12 CI also rasterizes SVG to real PNG
300 DPI and computes `SHA256SUMS.txt`. In the workflow a second,
independent shell check requires exactly the actual `GITHUB_SHA` and
pinned RECON/PAINT/YGO checkout hashes and all 23/15/62/16 numbers.
The original wire graph in this physical-only witness is intentionally
**empty**. The output must state `full_15_net_route_verified=false`
and `printable_candidate=false`.

Standalone owner checks:

```sh
ruff check .
pytest -q tests/test_ic_router_ports_cycle16.py
pytest -q tests/test_ic_circuit_adapter_cycle9.py
```

**A successful port contract is not 15/15 routing**. The actual current
A3 route remains ~9/15 in other owners' independently pinned experiments,
and the original 91-wire/37-junction 9-ERROR/32-WARNING historical
fixture remains the immutable negative control.

## 4. Deliverables to owner teams

- **NET #114**: `port.tip_um`, `normal`, `net_name`,
  `own_only_escape_box_um`, `native_draft_ink_box_um`. Use real YGO full
  23-part strokes+Type A guards and full segment clearance instead of
  these narrow port boxes as complete route obstacles.
- **RECON #115**: original D4 transform and exact 16 absolute port
  positions; an ELK candidate may only propose an **untrusted** legal
  positional change. Validate source provenance and rebind before
  NET routes.
- **PAINT #93**: original `DA1.n` IDs and TI input/output roles, 0 green
  contacts in clean / exactly 16 in diagnostics; never make this surrogate
  ink the final printed Type A SVG.
- **QA #99**: strict parse of source hashes, full 23/15/62 source,
  16 role-correct ports, reject a 1µm ELK shift/false inward normal,
  mismatched caller-supplied manufacturer `PartDefinition`,
  and preserve a failed print release for partial graphs.

Upstream algorithm concepts used as research, not copied code:
libavoid visibility/nudging (LGPL-2.1+), ELK layer/ports (EPL-2.0),
Freerouting group rip-up (GPL-3.0) and X6 Manhattan (MIT). This exact
Python implementation is independently authored on our existing MIT PR.
