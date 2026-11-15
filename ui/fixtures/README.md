# CHAT 6 — verified native GSCAD v2 data proof

**Status:** R1 schema / source-authored fixture, not production GOST-approved geometry and not a fully-routed TL494. This folder is owned by #122, integrated only after #125 accepts Draft PR. Full 15/15 auto-routing is not claimed.

Canonical source: original `examples/tl494_full_native_model.py` at SHA `e695c415fdced164b0e0c39c5249d030795a0aa6`. Fixture `tl494-source-e695-v2.gscad.json` keeps **23 parts / 15 literal Nets / 62 physical memberships / 16 physical DA1 pins / 2 non-electrical b marks (`Graphic.kind='source_b_continuation'`, no Net/PinRef)** and deliberately **0 imported legacy wires**. Catalog graphics are explicitly DRAFT placeholders; do not use the fixture as normative print artwork.

## Local checks (repo root; Python >=3.12, Node >=20)

```powershell
python -m pip install -r ui/editor/src/model/requirements-dev.txt
$env:PYTHONPATH='ui/editor/src/model'
python -m pytest -q ui/editor/src/model/tests
python ui/fixtures/generate.py
node ui/editor/src/model/verify_hash.mjs ui/fixtures/tl494-source-e695-v2.gscad.json
tsc --noEmit --strict --target es2020 ui/editor/src/model/contract.ts
```

`ui/fixtures/generate.py` regenerates both `ui/contracts/project-v2.schema.json` and these fixtures deterministically. Review diffs before accepting. `project.gscad.json` v2 is distinct from the existing immutable Python `gse-project` v1; a dedicated, verified adapter is still required. Schema checks structural types; `ui/editor/src/model/contract.py` validates physical references, Manhattan segments, explicit junction vs hidden splice, uniquely isolated free terminal, wire-engine `needs_routing_review` flag, incomplete routes, E695 source lock, serialisation, migrations and CAS/in-memory undo.

Current product limitations: no actual TypeScript runtime integrated in the editor, Rust file is a **serde sketch not compiled**, no Windows Tauri packaging, native save journal/production DRC/E3 exporter requires #118/#124/#125.
