# Cycle 11 — actual checked-out owner API compatibility gate (YGO2)

Date 2026-11-15. Existing Draft PR #113; frozen source `e695c415fdced164b0e0c39c5249d030795a0aa6`. No merge, no main/integration changes.

## Exact source-owner inputs

| Independent owner | Frozen HEAD at gate authoring | Real API under test |
| --- | --- | --- |
| NET #114 | `3b0f29cf253e4649179afa879aa1281d982df53b` | `engines.multiterminal_router._source_ink_obstacles`, actual transformed stroked primitive AABB, real touching lead and physical PinRef identity |
| IC #97 | `9242fa83606a881b8ff277ff051c7b46a5b63a22` | `examples.tl494_cycle9_circuit_integration.build_frozen_photo_23`; exact original 23 components/15 Nets/62 PinRef and all 16 DA1 pins tested against 13 YGO source footprints, without relocating or changing the source topology |
| PAINT #93 | `dea3b4564fa32ef3ff040f1ffdd9aa47ab480d2d` | `rendering.svg.render_symbol_svg` via real `examples.review_tl494_ugo_source_cycle9._actual_root`, plus importable routed_native_sheet API |

The workflow uses a detached **temporary Git worktree at each exact owner commit** and copies ONLY the YGO source-profile modules and gallery method into that disposable checkout. It never commits or pushes to an owner branch. Python imports the real owner repository package, not the older base version. Both Python 3.12 and 3.13 run.

## Numerical acceptance / exclusions

* NET compares 13 original source shapes in eight D4 transforms = 104 cases. Every real printer stroke is individually matched against current NET owner `_SourceInk`, including the VT1 DRAFT photo-specific source dot; outer wire-stroke expansion is 150 micrometres at 0.30mm. Bounds may vary only up to **2 micrometres** because an existing `Line` AABB uses one-micrometre integer end inclusivity. A larger mismatch is a hard FAIL. Real pin leads must map to identical `PinRef`, endpoint and stroke width; no fabricated additional contact accepted. This is a **source UGO ink contract check**, not proof that global router connects 15/15.
* PAINT generates actual source-symbol SVG DOM through the **currently pinned owner** implementation for every source reference in all eight D4 transforms. Clean must contain zero diagnostic squares; debug must contain exactly the number of real physical terminals with exact true local pin endpoints. VT1 dotted photo-style source marker must remain separate from its three electrical pins. The full new-routed renderer's API is imported, but a full routing/sheet print is not generated or certified by this owner gate.
* Shared YGO manifest now pins **ordered terminal numbers** in addition to role names and graphic labels. Set-equivalent swapped pin-number assignments are rejected, especially VD1 A/K, VT1 G/D/S, R5 wiper and polarity-preserving capacitor identities. Neither owner can treat a reordered number set as equivalent to the original frozen electrical topology.

* IC reads the exact owner-frozen photo fixture, verifies the source SHA, 23/15/62 and 16 actual DA1 contacts, then binds all 13 source UGO at the owner's *non-printable placeholder* positions using explicit allow_relayout. This tests PartDefinition/PinRef cooperation only. It cannot claim a new A3 placement, fully routed sheet or print pass.

**No GOST APPROVED assertions:** 36 DRAFT symbols, 0 APPROVED; source-figure 1:1 user/photo calibration and original detailed manufacturer pinouts remain BLOCKED.

**Full user TL494 acceptance remains BLOCKED until** NET completes all 15 source networks (62 real memberships), RECON/PAINT renders a real new 23-component print sheet with 0 disallowed DRC errors and independent QA on pinned exact owner heads. A successful workflow here is only contract compatibility for glyph ink and PinRefs, not a substitute for 15-Net route.
