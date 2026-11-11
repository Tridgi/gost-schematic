# ADR-0001: One package, immutable domain objects

Status: accepted for the experimental foundation.

Use a modular monolith with directional imports, NOT one Python class per symbol.
Catalog assets describe fixed symbols; specialized generators will build parameterized
shapes such as IC bodies. Physical parts, graphic views and electrical nets have
different identities and version histories.

Advantages: independent regression tests, small base runtime, swappable rendering
and routing implementations, no duplication across hundreds of ICs.

Tradeoff: stronger boundary contracts and explicit mapping validation are required.
