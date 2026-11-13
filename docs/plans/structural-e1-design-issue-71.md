# Plan: YGO2 structural block graphics, Issue #71

Base `integration/stage0-12` at `45d4451eb06e7e469aa4e3c26e728ac8a5bdf3c5`, work branch `parallel/catalog-structural-e1-design`.

**Scope:** a separate standalone contract-only design dossier, JSON profile, deterministic 6-block SVG reference specimen, scenario tests and a GitHub Issue #70 cross-team proposal. Functional structural blocks are **not** 22nd electrical symbols and never carry a physical `PartDefinition`, `PinRef`, electrical topology or electrical net.

**Order:** source-backed requirements, proposed coordinates/port spacing/keepouts, example fixture, executable negative tests, branch CI for Python 3.12/3.13 + Ruff + 21 DRAFT audit + wheel, Draft PR and evidence report. Do not edit `model/*`, `core/*`, `rendering/*`, `catalog/symbols/*`, `catalog/parts/*`, existing tests, CI, or integration branch.

**Known risks:** 2.701/2.702 govern the diagram differently from electrical principle УГО; a line break arrow is not necessarily a process arrow; axis-aligned box checking overestimates diagonal strokes; unmeasured fallback font is not ГОСТ Type A proof; port size/pitch is project policy. All proposed schema keys are pending ELEKTRIK #70 approval; no common API signatures are frozen.

**Acceptance:** eight or more independent positive/negative scenarios, deterministic SVG and port geometry under 8 transforms, separate semantic graph, and no changes to existing 21 DRAFT/0-hard-errors wheel payload. Coordinator alone merges.

## Follow-up PR #78 after coordinator's 7/18/9 request

Add real PR80 model overlay in an independent CI job (not committed to this branch), switch all visual PortRef geometry to the model resolver, prepare 7/18/9 SVG and 4200px PNG, independently parse the SVG path commands, measure OpenGost text hitboxes, and report real model SHA and hashes to QA Issue #83. Follow ELEKTRIK's agreed **signed final absolute Fraction ROUND_HALF_UP** quantization plan; do not add a conflicting local E1 resolver. Compact and spacious styles are explicitly distinct EDITORIAL view profiles, not a GOST-specified 5/6 mm port-spacing standard. Do not modify common Circuit/PartDefinition/rendering APIs. Re-run both generic Python CI matrix and real PR80 integration matrix after the ELEKTRIK fix. Draft PR #78 stays open; coordinator alone may merge.
