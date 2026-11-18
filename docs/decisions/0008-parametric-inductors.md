# ADR-0008 — Parametric winding family, never per-variant hard-coded paths

Status: experimental, pending user visual approval.

Decision: implement semicircular winding as an immutable engineering
primitive rather than approximating it with 3–10 lines. A magnetic core
is a separately styled stroke or broken stroke, never a generic resistor
body line. The core material, adjustment flag and physical tap/slider
positions belong to a typed versioned configuration.

The symbol factory outputs `SymbolDefinition` and `PartDefinition`
from the *same* `InductorSpec`, which prevents pin graphics from drifting
away from their physical part mappings. A rotation or mirror must change
only the view coordinates and arc orientation.

Styles and display glyphs are **draft** pending comparison with KOMPAS
and the current edition/changes of ГОСТ 2.723-68. Do not infer GOST
compliance from test success.

Rejected alternatives:
- Duplicating full SVG or fully expanded JSON for every coil design;
- Raster screenshots as the source of truth;
- Fixed coil count independent of the template;
- Treating sliding contacts as decoration without physical netlist pins;
- Inferring a `Cu` label without reserving its text hitbox;
- Assuming all coupled magnetic components are single two-pin inductors.

Future: validate electrical transformer/coupling topology separately,
provide dot/start-of-winding semantics and separate normative coverage.
