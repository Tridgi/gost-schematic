# MASTER R1 integration cross-review

This is a dependency-free Node 22 structural gate, NOT an authoritative gscad-project serializer, a real CAD editor, or frozen TL494 import. It supplements #122 (schema/physical model), #123 (wire state machine), #124 (export). Its test toy is SYNTHETIC. Only explicit pin/junction/splice/free IDs can represent contacts: coordinate coincidence alone does not join Nets. It rejects gscad-spike v1. Source SHA E695 is constant; the frozen gate checks counts but cannot independently prove vendor pinout, full ERC, DRC, fonts, or 15/15 routing.

Run from repository root: node --test ui/integration/source-gate.test.mjs

No npm install required. See docs/coordination/visual-cad-agent-loop.md and ui/contracts/manual-wire-v2.md. #122 JSON Schema, signed source fixture and #123 write-safe graph commands are still BLOCKED for shared integration until committed.