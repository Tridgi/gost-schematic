# Stage 0.12 — normative traceability and internal graphic topology

**Planned:** 2026-11-12, before changes to models or algorithms.
**Parent:** draft PR #8, commit `4913dbd`. **Review:** separate draft PR #9, no merge into `main` and no promotion of draft UGO to approved.

## Source-of-truth strategy

1. **Audit document status against Rosstandart** and keep current vs future-effective standards distinguishable. Russian Federation application profile as of 2026-11-12; do not infer validity of a future accepted standard merely from its publication. All implementation assumptions carry document, clause/table, URL, interpretation and verification state.
2. **Dimension and shape audit** for resistor (`10 × 4 mm`) and fixed capacitor (`8 mm` plate, `1.5 mm` gap) against ГОСТ 2.728-74 table 6; carefully distinguish the generic polarized capacitor from the *electrolytic-specific* figure. ГОСТ 2.723-68 table 1/2 defines winding/core shapes but does not prescribe a universal semicircle count.
3. **Introduce an explicit graph-of-conducting-ink model** independent of `Circuit.nets`, actual electrical properties, rendering and obstacle geometry. Only authored line/arc primitives belong to the conductive layer. Crossing strokes MUST NOT auto-connect; an interior contact requires an authored junction. Distinct capacitor plates and the two resistor leads MUST NOT become a false short.
4. **Bind every baseline UGO** to a typed conductor topology. For inductors, confirm outer terminals and every tap/slider are attached to the winding via exact semicircular geometry. For capacitors, keep plates isolated. Report broken routes, pin isolation/mapping errors, missing junctions, isolated groups merged accidentally.
5. **Add test fixtures** including genuine breaks in coil paths, wrong/missing apex contact, unintended bridge between capacitor plates, unmarked crossing, quarter-turn/mirror invariant semantics. Export machine-readable structural and normative evidence in CI.
6. **Documentation and logs:** versioned, link-based normative registry; rule cards and applicability, not entire copyrighted standards; baseline comparison, implemented checks and explicit unresolved visual review for KOMPAS. Update `docs/project-log.md` with real CI results, PR link, and limitations.

## Acceptance gate

- Existing 18 catalog UGO have an explicit conductor-layer topology without errors.
- Component graphic internal routes are checked without ever claiming all pins on an element are shorted.
- New validator has negative and positive tests, including analytic arc and tap intersections.
- Machine-readable catalogue audit contains topology diagnostics, proof status and standardized requirements links.
- CI succeeds on Python 3.12/3.13, lint and example generation.
- All symbols remain DRAFT pending user visual approval; full wire autorouting, ERC, datasheets and end-to-end schematic completion are out of scope.

## Standards to examine

Core: ГОСТ 2.701-2008, 2.702-2011, 2.709-89, 2.710-81, 2.721-74,
2.723-68, 2.728-74, 2.747-68, 2.730-73, 2.743-91, 2.755-87.
Graphic/document rules: 2.301-68, 2.303-68, 2.304-81, ГОСТ Р
2.104-2023, 2.105-2019, 2.106-2019. Future-dated
ГОСТ Р 2.301-2026, 2.303-2026, 2.304-2026, 2.105-2026 (2027-10-01,
early application permitted); do not silently activate them.

Reference originals for visual verification:
- https://helpeng.ru/public/normdoc/eskd/gost_2.723-68.pdf
- https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf
- https://www.elec.ru/files/2019/03/25/gost_2.702-2011.pdf

Canonical document status: https://protect.gost.ru/gost/

## Completion record — 2026-11-12

**Technical scope: complete, human GOST approval: NOT COMPLETE.**

| Acceptance criterion | Result |
|---|---|
| All 18 UGO have explicit conductor graph | PASS, 18/18 draft |
| Topology catches false joining / disconnected arcs / missing tap nodes | PASS, positive/negative and rotated/mirrored tests |
| Machine-readable normative evidence with source URLs | PASS, `standards/requirements_2026_ru.json` + registry |
| Source-backed dimensional checks | PARTIAL BY DESIGN: 3 UGO have narrow verified dimension rules; 15 coils still need normative graphics signoff |
| Source-backed wire checks | PARTIAL BY DESIGN: width and exact parallel spacing; no whole-sheet proof |
| Python 3.12/3.13 pytest, Ruff, audit and wheel package | PASS: 364/364 per runtime, no errors in 18-symbol audit |
| All symbols DRAFT, no merge into main | PASS: PR #9 remains a draft, stacked over #8 |
| Logs and explicit limitations | PASS: project log, changelog, `standards/known-limitations.md` |

Full test run: [GitHub Actions #43289319096](https://github.com/Tridgi/gost-schematic/actions/runs/43289319096). The separate final documentation-only commit is subject to one additional CI check before freezing. **No next-stage development starts here.**
