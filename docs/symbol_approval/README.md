# User-controlled symbol approval protocol

All symbols start with `status: draft`. This includes the initial fixed resistor.
A valid schema and successful automated tests do **not** prove ГОСТ conformity.

For each UGO family, record:

1. Source evidence from KOMPAS or other legitimate reference (image and, where
   available, dimensions or exported vectors).
2. Applicable normative reference, clauses and explicitly verified dimensions.
3. Pin mapping and numbering; body, visual, text and collision geometry.
4. Inspectable rendered SVG with review overlay; variations and 0/90/180/270 rotations.
5. Automated structural tests, manually checked dimensions and visual comparisons.
6. Explicit user review and approval with revision and date before promoting the
   fixture to `approved`.

No approval is inferred from a screenshot. A screenshot is a visual reference, not
accurate dimensional proof. Proprietary source fonts or KOMPAS library files must
not be redistributed without permission.

Current review queue:
- `resistor.fixed`, revision 1 — **DRAFT / not user-approved**.
