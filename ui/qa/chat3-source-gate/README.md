# CHAT 3 — cross-review of MASTER source-gate (R1)

Target: `ui/integration/source-gate.mjs` **Git blob SHA**
`dc6275481be7f2717e6e8223cfc7acca85d1aa5d` at UI HEAD
`9d2d8c1c683efba29338addc86631f8a6b68a6e6`.

This directory is **tests + suggested patch only**, NOT a change to #125-owned
production source. The independent reviewer reproduced the bugs against an
exact local copy of that file, verified by `git hash-object` matching the
GitHub blob SHA. Original upstream 15 tests source matched Git blob
`c8c9891479d549e846ed5d0c4d2d1331d4b6058a`.

## Negative reproducible tests

From repository root on Node.js 22+:

```sh
node --test ui/qa/chat3-source-gate/source-gate-adversarial.test.mjs
```

**Expected before owner fix:** 0 PASS / 2 FAIL, each `Missing expected exception`:

1. `JUNCTION_CROSSES_FOREIGN_NET`: an explicit same-Net junction with two
   attached arms on one horizontal Net crosses the *interior* of a separate
   vertical foreign-Net wire, but structural gate accepts it. Contradicts
   `ui/contracts/manual-wire-v2.md` "zero foreign Net strokes".
2. `PIN_NET_MISMATCH`: `key = component_id + ':' + physical_pin_number`
   is not injective. Component `a:b` pin `c` and component `a` pin `b:c`
   both map to `a:b:c`; an undeclared physical PinRef is falsely accepted
   as a declared Net member when optional `pinWorld` is absent.

The regression test is deliberately red until the production owner #125
reviews and applies a fix. It must not be misreported as successful CI.

## Independently validated suggested patch

`./suggested-fix.patch` is **not applied** to any shared branch. It:

- uses `JSON.stringify([component_id, physical_pin_number])` for injective
  typed tuple keys and changes frozen DA1 check to compare explicit ID fields;
- checks each explicit Junction point against all foreign-Net H/V strokes
  in the same sheet, rejecting an unauthorized foreign-Net overlap.

On a **local copy** of exact source-gate, applying the proposed fix yields
**17/17 PASS** (original 15 + 2 adversarial) on Node 22.16.0 Linux. This is
not proof that MASTER's live branch or CI contains the fix. O(J×segments)
reference validation is correct for small fixtures; owner can optimize with
spatial indexing at scale. This is a structural gate, not a full ERC checker.

**Ownership:** #125 alone approves/edits `ui/integration` and its CI. CHAT3
owns only tests and sends this finding to #119 and #125. No merge without
user authorization.