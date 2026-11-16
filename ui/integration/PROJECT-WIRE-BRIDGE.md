# MASTER — ProjectFileV2 ↔ Manual Wire Engine integration (R1/R2)

First verified adapter boundary between #122's canonical ProjectFileV2 and
#123's compiled TypeScript ManualWireEngine. Source Net and manufacturer
PinRef identities are immutable. A Python adapter calls the **original**
#122 validator, source inventory SHA, project digest, route completeness gate
and atomic file serializer; a real Node test uses the **actual** CHAT7
WireEngine, not a copy of its algorithm. The E695 test retains all 23
components / 15 literal Nets / 62 PinRef memberships / 16 signed DA1 pins /
2 NON-electrical b graphics. A single authored route cannot make 15/15 valid.

Run in repository root:

    python -m pip install -r ui/editor/src/model/requirements-dev.txt
    python -m unittest discover -s ui/integration -p 'test_project_wire_bridge.py' -v
    cd ui/editor/src/wires
    npm install --no-audit --no-fund --ignore-scripts --no-save typescript@5.8.3
    npm run typecheck && npm run build
    cd ../../../..
    node --test ui/integration/project-wire-bridge.test.mjs

Developer CLI:

    python ui/integration/project_wire_bridge.py digest --project ui/fixtures/tl494-source-e695-v2.gscad.json
    python ui/integration/project_wire_bridge.py snapshot --project ui/fixtures/tl494-source-e695-v2.gscad.json --out wire-state.json
    python ui/integration/project_wire_bridge.py apply --project SOURCE.gscad.json --snapshot edited-wire-state.json --expected-sha PROJECT_DIGEST --out OUTPUT.gscad.json

Limits / downstream blockers:
- Single sheet, one graphic placement per physical component. Multi-unit and
  multisheet conversion explicitly fail closed rather than inventing PinRefs.
- CHAT7's runtime requires free_id equal to wireId:start|end, stricter than
  CHAT6's globally unique free ID schema. Other valid free IDs are refused,
  not silently rewritten. Requires #123/#122 compatibility decision.
- Only wires/junctions/splices are committed. Pose/part/source changes cannot
  sneak through this adapter; a future typed joint pose+wire reroute API must
  be reviewed by #122/#123.
- expected_project_sha256 is a snapshot precondition. It does not make the
  filesystem writer a concurrency-safe compare-and-swap across processes.
  #118 desktop IPC must provide generation journal, OS file lock and native
  destination permissions before production.
- This is **not** a browser UI, React shell or canonical SVG/PNG/Tauri release.
  #124 SVG/PNG renderer and fonts remain separate downstream gates.
- Authoritative frozen original source is Git commit
  e695c415fdced164b0e0c39c5249d030795a0aa6.
