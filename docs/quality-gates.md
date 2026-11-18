# Quality gates and review boundaries

## Before editing

Write a scoped plan in `docs/plans/`, identify the parent PR and expected
behaviour and explicitly list what remains outside the step.

## During editing

- Changes live on a stacked draft PR and must not be merged or labelled
  `approved` automatically.
- Structural checks are separate from normative ГОСТ conformity.
- Every new UGO needs a physical-pin map, dimensions, a reported source
  standard, measured annotation zones and an automated negative regression.
- Every discovered defect needs an explanatory commit and test.
- Use one source of truth for geometry and an immutable instance model.

## CI for stage 0.11

```bash
python -m pip install -e ".[dev]"
ruff check .
python -m pytest -q
python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
```

CI validates Python 3.12 and 3.13 and uploads a dated-run artifact named
`draft-catalog-integrity-audit`. The JSON audit reports each versioned UGO,
the SHA-256 of its JSON source, physical-part linkage, contact definitions,
stroked bounds and validation diagnostic codes.

**Interpretation:** zero hard errors means no *known checked structural*
contradiction, not ГОСТ compliance or electrically functional wiring. An
`UNAPPROVED_SYMBOL` warning is expected for every pending UGO.
Do not remove this warning merely to make a green dashboard.

## Human sign-off required

For each element: inspect the clean and diagnostic SVG next to its KOMPAS/GOST
original, approve exact geometry and fonts, then record an explicit decision
referencing that fixture. Do not make up missing images, compliance certificates,
part numbers or physical dimensions.

## Stage chain

The latest review stack is PR #8 → #7 → #6 → #5 → #4 → #3 → #2.
Each PR targets its predecessor, not `main` directly. Update
`docs/project-log.md` with actual CI IDs, test counts and known limits.
