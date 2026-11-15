# Cycle13 — future write gates for AI agents (design only)

**Current capability:** real native MCP catalog/read-only ProjectService. **No**
`schematic_create_*`, `schematic_connect_pins`, `schematic_route_*`,
`schematic_commit_transaction`, `schematic_undo` or mutable APIs registered.
The executable Cycle13 quickstart and unit tests **reject** write/tool
injection, unknown part selection, changed original R5 and R1,
incorrect Net, stale revision and invented references.

This is a narrowed interoperability acceptance checklist. The more
detailed P1.2 RFC remains the separate existing
[Draft PR #102](https://github.com/Tridgi/gost-schematic/pull/102).
Nothing here activates or supersedes that approval gate.

## Typed proposal (NOT currently a callable tool)

- Source evidence: immutable original SHA
  `e695c415fdced164b0e0c39c5249d030795a0aa6`; independent
  23 source component refs + part/nominal pairs, 15 exact original Net
  names and 62 complete physical members; vendor 16 pins and two
  **non-electrical** `b-X2`/`b-R5` markers.
- Trusted host identity: canonical project UUID, scoped authorization;
  no MCP-selected absolute path, arbitrary shell command, SVG patch,
  imported code, file write or user-claimed approval flag.
- Immutable prerequisites: catalogue `part_sha256` and
  `symbol_sha256`, actual PhysicalPin/PinRef ownership, project
  `expected_revision` SHA256 and `expected_generation` positive
  integer. All derived from the saved Circuit snapshot, not pixels.
- Proposed actions must explicitly say
  `AddComponent`, `MoveComponent`, `ConnectPins`, `RemoveWire`,
  `UndoTransaction`, with bounded operations/coordinates and source
  provenance, *after* a new reviewed API actually implements them.
  Never submit a free-form patch or invoke unknown operations.

## Hypothetical state machine (BLOCKED implementation)

1. `ReadSnapshot`: verify host allowlist and immutable exact revision,
   catalog locks and physically resolved contact labels.
2. `ValidateProposal`: bound size and rate; fail closed on
   unknown UGO, nonphysical pins, NC terminal, foreign Net,
   unexpected pin collision, output-output conflict, b-stub as
   electrical pin, sheet/keepout/routing violation, stale CAS.
   Validation MUST NOT allocate new Net or mutate HEAD.
3. `PreviewDiff`: provide deterministic typed before/after
   component references, pin ownership and affected Nets; do not
   modify E3 to show green UI snap. Record expected generation.
4. `CommitTransaction`: only trusted separately authorized
   implementation, exactly compare expected_revision+generation,
   idempotency UUID and immutable part SHA, lock project, apply
   all-or-nothing, validate ERC/DRC and generation, publish new
   content-addressed revision on success.
5. `Rollback`: if any validation, timeout, geometry, topology or
   persistence error occurs, restore original atomic state. Same
   idempotency receipt returns the same accepted result; stale retry
   is rejected, never converted to a second implicit edit.
6. `Undo`: a NEW independently validated transaction anchored at
   current expected revision; never an unsafe blind history rewind.

**Acceptance tests required before exposing any MCP writer:**
cross-project UUID, symlink/junction and path traversal, stale
revision/generation, repeated/foreign physical PinRef, unknown R5
symbol, changed original 15 Net membership, imported arbitrary part
ID, incompatible NC/power/BIDIRECTIONAL pairing, idempotent replay
and concurrent conflict, partial-write fault injection/rollback,
malformed JSON, wrong casing of source b aliases, permission denial,
bounded rate and image-to-net-invention attempts. Test both Python
3.12 and 3.13 and independently review full 15/15 printed graph
before a completed print status can be reported.

## Present executable safety evidence

The actual `examples.agent_tl494_cycle13_quickstart` executes eleven
real CLI refusal cases and the actual native
`mcp.ClientSession` catalog checks. The registry guard rejects
**any** MCP server tool not explicitly marked
`readOnlyHint=true`, `destructiveHint=false`,
`openWorldHint=false`, and even a falsely marked future
`create/move/connect/route/commit` name. The exact original source
and manufacturer owner blobs are pinned by the Cycle12 wheel
manifest. A successful CLI exit on this intentionally
`BLOCKED_PARTIAL` example does **not** authorize transaction writes,
prove 15/15 routing, run Codex LLM or clear full print DRC.
