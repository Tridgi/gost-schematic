# RFC NET-C7-001 — typed named E3 net continuation

Status: DRAFT EXPERIMENTAL, no normative approval. Issue #90; ESKD #91; QA #92.
Design request: https://github.com/Tridgi/gost-schematic/issues/90#issuecomment-6866828267

## Electrical truth and graphical continuity are separate

NetIdentity(id,net_name,members) binds one stable semantic ID to the exact frozen PinRef membership of one existing Circuit.Net. The original Circuit is ALWAYS supplied; rendering cannot infer or mutate physical connectivity by matching labels, positions or ink intersections.
ContinuationSheet(id,number) declares unique page IDs/numbers. NetContinuationEndpoint(id,net_id,sheet_id,sheet_number,address,target_address,anchor,label,direction) stores a nonphysical view marker and explicit reciprocal remote address. ContinuationPair(id,source_id,target_id,scope) only pairs two markers of the SAME existing Net ID; scope is sheet_local or global. Direction is SOURCE/TARGET/BIDIRECTIONAL visual meaning, not digital logic electrical type.
ContinuationStub(id,endpoint_id,pin,start,end) represents one short, real, orthogonal conductor ending EXACTLY at the marker Point; the beginning is an actual physical PinRef already contained in the bound Circuit.Net. Optional exact physical pin anchor map catches even 1µm mismatch. There is NO invisible line across pages.

Fail-closed diagnostics: duplicate sheet/page/endpoint/net/pair/stub, missing or ambiguous actual Net, physically duplicated PinRef, wrong members, unknown target, reused marker, missing reciprocal address, direction/scope mismatch, false cross-net join, wrong local physical PinRef, 1µm stub off endpoint, unpaired marker, and ambiguous same/global-scope printed labels. A marker masquerading as XP/XS is rejected. Genuine plug/socket is a different physical PartDefinition with PinRef, not a continuation marker.

Strict deterministic DRAFT_E3_NET_CONTINUATIONS JSON v1 requires the REAL existing Circuit on import, rejects float/NaN, unknown keys, duplicate JSON keys, invalid graphs and cannot fabricate a net. Eight D4 transforms alter only visible marker/stub coordinates, preserving stable IDs and exact Net members.

## DRAFT two-sheet CTRL proof

examples/review_net_continuations_cycle7.py::specimen() has synthetic DD1.5 and VT1.G physical PinRefs in one existing Circuit.Net('CTRL'), with S1 marker 1/D4 targeting 2/B7 and S2 marker 2/B7 targeting 1/D4. Exactly two short independent H/V visible wire stubs, no automatic PartDefinition or SVG conductor across sheets. Two deterministic A4 SVG images and optional 300 DPI PNG are review-only; actual OpenGost Type A glyph ink, overflow, GOST symbol geometry and accurate sheet-address mark remain BLOCKED pending PAINT/ESKD. The font family in the SVG is a request, not verified measured face.

Commands: python -m examples.review_net_continuations_cycle7 --output-dir output/netrefs-cycle7 --png
          pytest -q tests/test_netrefs_cycle7.py
          ruff check .
          python scripts/audit_symbol_catalog.py --output output/catalog-integrity-audit.json
          python -m pip wheel . --no-deps --wheel-dir dist
          python scripts/verify_wheel_payload.py dist

Independent branch parallel/electrical-netrefs-cycle7: NO import of incomplete IC #87, NO edits to Circuit/PinRef/ExternalWireGraph/E1/public API/main. Issue #90 normative source pointers: ГОСТ 2.721-74 table 6 pos 8, ГОСТ 2.709-89 §§5.13–5.14. DO NOT MERGE.
