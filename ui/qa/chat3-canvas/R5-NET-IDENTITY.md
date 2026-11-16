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

## Actual CI evidence — 2026-11-16, GitHub ubuntu-24.04, Node 22

- **RED reproduction at `e853d0221445e4e75c242010bc3c80e9095851c7`:** real `react-mantine-preview` `npm test`, 34 PASS / **3 FAIL**. Failures were duplicate generated Net names, accepted duplicate imported Net names, and accepted duplicate unused physical pin numbers. Evidence: [run 43962014494](https://github.com/Tridgi/gost-schematic/actions/runs/43962014494).
- **Fix at `4b8adc360fbf896988f1484cf8c40d496eac779b`:** 37/37 frontend unit tests PASS, root Python CI PASS; no regressions in core model/export/wire/canvas jobs. Browser E2E failed on three separate newly added native-race cases, *not* on Net/physical-pin identity.
- **Extended fix at `2c26acecbebda3a7288c2202d350a8e0ebd86058`:** 38/38 frontend unit tests PASS (includes previously unplaced symbol duplicate or unknown physical PinRefs), `npm ci`, TypeScript and Vite build PASS; [root CI 43962642765](https://github.com/Tridgi/gost-schematic/actions/runs/43962642765) SUCCESS and 10 other Visual R1 jobs SUCCESS. `react-mantine-preview` had 18 Chromium PASS / 3 FAIL due ambiguous `getByText('Не сохранено')` in `e2e/native-file-races.spec.mjs` after shared integration changed; two legitimate status labels matched. [R1 run 43962642767](https://github.com/Tridgi/gost-schematic/actions/runs/43962642767). MASTER has already scoped that locator to `project-toolbar` at shared SHA `1bd88fcc8c49724804e09dc426b6f49e160baaf1`; that independent master edit was NOT made by CHAT3.
- Python strict `ui/editor/src/model/contract.py` already rejects duplicate original Net names, Part physical pin numbers and duplicate symbol physical pin numbers; this PR closes the previously weaker browser synthetic `AuthoringSession` gate before native IPC.

No Windows-native application interaction was performed by CHAT3; all observed results above are CI Linux tests. Pending checks should be identified by their exact commit SHA. Manual UI acceptance requires separate Windows testing.
