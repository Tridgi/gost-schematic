# CHAT 3 / R5 adversarial identity regression — independent QA

Base `ui/visual-cad-mvp` at `01e24d8992c257da2aaf09a7733ce65df935f79f`.
Owned evidence: `ui/editor/src/authoring/session-domain.test.mjs`.

Reproduction (CI Linux, Node 22):
```bash
cd ui/editor
npm ci --no-audit --no-fund
node --test src/authoring/session-domain.test.mjs
```

Negative cases:
1. Delete the first synthetic Net (unroute then remove both connected parts) while Net N2 survives; add a new pair of parts and connect. New Net must not reuse N2.
2. Import an otherwise valid synthetic ProjectV2 with distinct Net IDs but duplicate human-visible Net names. Reject with `DUPLICATE_NET_NAME`.
3. Inject a duplicate physical pin number into an *unused* part definition. Reject with `DUPLICATE_PHYSICAL_PIN` before any placement.

All cases keep physical `PinRef=(component_id,physical_pin_number)` and source topology intact. Frozen E695 23/15/62/16 plus two non-electrical b graphics remain untouched. Red tests are intended to first document the vulnerable base, followed by a minimal atomic validation/generator fix and a full green rerun. No shared integration branch or old branches are modified.
