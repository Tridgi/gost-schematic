"""Validated, reproducible demo input for the R2 browser preview.

No browser is allowed to validate or import untrusted physical source Nets.
The authoritative Python validator generates the matching CHAT7 wire snapshot.
"""
import json
from pathlib import Path

from project_wire_bridge import model, to_snapshot

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures"
TARGET = ROOT / "editor" / "public" / "fixtures"
TARGET.mkdir(parents=True, exist_ok=True)

for name in ("tl494-source-e695-v2.gscad.json", "toy-v2.gscad.json"):
    document = model.strict_loads((SOURCE / name).read_bytes())
    model.validate(document)
    snapshot = to_snapshot(document)
    (TARGET / name).write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (TARGET / name.replace(".gscad.json", ".wiring.json")).write_text(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(name, model.digest(document), snapshot["source_topology_hash"])
