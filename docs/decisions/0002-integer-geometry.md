# ADR-0002: Exact integer micrometre geometry

Status: accepted for the experimental foundation.

Catalog dimensions are human-readable millimetres; internally everything is
integral micrometres. Conversion rejects fractional micrometres rather than silently
rounding. Orthogonal transformations operate on integers.

The rendering engine converts to exact decimal millimetres only at export.
This avoids cumulative floating-point drift in pin coordinates and unit tests.

Future changes in physical unit resolution need a deliberate file schema migration.
