# RFC #74 Annex B — components, trust boundaries and data flows

Status: architecture diagram, **not implementation**. Source of
method contracts: [v1 contract](agent-project-service-contract-v1.md).

## Component diagram

~~~mermaid
flowchart TB
  subgraph Clients["Untrusted clients (no direct storage)"]
    Codex["Codex CLI / IDE / ChatGPT"]
    Skill["Agent Skill: workflow advice only"]
    Codex --- Skill
  end
  subgraph Adapters["Transport boundary"]
    MCP["MCP stdio facade\nstrict schemas / auth scope"]
    CLI["Trusted local CLI adapter\nexplicit import workflow"]
  end
  subgraph Application["Application trust boundary"]
    Service["ProjectService\nsingle command/validation authority"]
    ACL["Capability + workspace\npolicy enforcement"]
    Draft["Typed command executor\ncopy-on-write draft + CAS"]
    Projectors["Typed ProjectKind adapter registry"]
    Validator["Independent domain validators\nversioned diagnostics"]
    Render["Revision-bound SVG/PNG presenter\nImageContent"]
  end
  subgraph Domains["Separate engineering domain models"]
    E3["E3 adapter\nCircuit / ExternalWireGraph\nPartDefinition / SymbolDefinition"]
    E1["E1 adapter (future)\nStructuralDiagram / FunctionalLink"]
    Flow["ALGORITHM adapter (Issue #82)\nFlowNode / ControlFlowEdge"]
  end
  subgraph Storage["Controlled persistence boundary"]
    Repo["ProjectRepository interface\nimmutable read / CAS commit"]
    Store["LocalProjectStore\nallowed project IDs only"]
    Head["HEAD: revision + generation"]
    Blobs["Immutable .gseproj revisions\ncontent-addressed blobs"]
    Audit["Idempotency + crash journal"]
    Artifacts["Views by project/revision/view hash"]
  end
  Codex --> MCP
  CLI --> Service
  MCP --> Service
  Service --> ACL
  Service --> Draft
  Draft --> Projectors
  Projectors --> E3
  Projectors -. "after distinct acceptance" .-> E1
  Projectors -. "after Issue #82" .-> Flow
  Draft --> Validator
  Validator --> E3
  Service --> Render
  Render --> E3
  Service --> Repo
  Repo --> Store
  Store --> Head
  Store --> Blobs
  Store --> Audit
  Render --> Artifacts
  Render --> MCP
~~~

**Invariant:** Codex and the MCP layer cannot write JSON, mutate
Circuit, add a junction, or invoke low-level routing independently.
Only ProjectService authorizes an application command; only the
ProjectRepository commits a validated immutable revision.

## Read-only P1.1: trusted import, cold reopen and visual proof

~~~mermaid
sequenceDiagram
  autonumber
  participant T as Trusted importer (fixed live specimen)
  participant S as ProjectService
  participant P as E3 projector
  participant C as Real Circuit + ExternalWireGraph
  participant V as Independent validators
  participant R as ProjectRepository / Store
  participant M as MCP Vision / Renderer
  participant A as Codex agent

  T->>S: import_fixed_source(fixed six-part, new project_id)
  S->>C: acquire authored Circuit, ExternalWireGraph, catalog
  C-->>S: 6 components, 5 nets, 16 segments, 3 junctions
  S->>P: serialize strictly typed E3 payload + catalog lock
  P-->>S: canonical v1 snapshot candidate
  S->>V: validate physical PinRefs, semantic nets, topology, provenance
  V-->>S: independent diagnostics
  alt cannot prove source/style/geometry
    S-->>T: IMPORT_PROVENANCE_BLOCKED; no HEAD created
  else valid import
    S->>R: put immutable blob + CAS empty HEAD to gen=1
    R-->>S: project_id, SHA, generation=1
    S-->>T: committed import receipt
  end

  Note over R: Restart service in a new process
  A->>M: schematic_open_project(project_id)
  M->>S: open exact project + revision
  S->>R: read HEAD then immutable revision blob
  R-->>S: canonical bytes and pinned lock
  S->>P: hydrate existing immutable Circuit + ExternalWireGraph
  P->>V: independently validate restored model
  V-->>S: diagnostics bearing exact revision SHA
  S-->>M: typed ProjectSnapshot + report
  A->>M: schematic_render_overview(exact revision)
  M->>S: get same immutable snapshot
  S-->>M: verified typed E3 model
  M-->>A: ImageContent image/png + TextContent SHA, bbox, SVG/PNG hashes
  A->>M: schematic_inspect_component(C3, exact revision)
  M-->>A: fresh vector-backed crop, same snapshot SHA
~~~

The fixed importer reads real instances *inside the approved source
provider*. The persisted schema is not just a netlist-shaped demo.
A new process must reconstruct the same immutable Circuit and
ExternalWireGraph, not re-import from Python to regenerate the project.

## Future write transaction (BLOCKED until separate approval)

~~~mermaid
sequenceDiagram
  autonumber
  participant A as MCP agent
  participant S as ProjectService
  participant R as ProjectRepository
  participant E as E3 typed executor
  participant Q as Validators
  participant P as SVG/PNG

  A->>S: apply_transaction(expected SHA + generation, idempotency key, commands)
  S->>R: get committed replay receipt / CAS HEAD
  alt exact idempotent replay
    R-->>A: same committed receipt, unchanged generation
  else fresh request
    R-->>S: immutable old snapshot
    S->>E: copy-on-write draft + typed commands
    E->>Q: final-state physical/net/geometry check
    alt invalid or branch routing unavailable
      Q-->>S: BLOCKED with independent diagnostics
      S-->>A: mutated=false; old SHA unchanged
    else valid with approved routing
      Q-->>S: PASS / WARN
      S->>R: stage immutable new snapshot, compare-and-swap HEAD
      alt stale head or disk failure
        R-->>S: REVISION_CONFLICT or PERSISTENCE_FAILURE
        S-->>A: mutated=false; no new published HEAD
      else successful commit
        R-->>S: after SHA + new generation
        S->>P: render old/new exact immutable revisions
        P-->>A: two ImageContent + typed model/geometry diff
      end
    end
  end
~~~

Only a *reviewed safe branch-aware adapter* may alter a connected
C3's TOP/RIGHT routing. The existing two-pin adapter rejects those
multi-member nets. An image crossing is not a conductive junction.

## Non-interchangeable diagram kinds

~~~mermaid
flowchart LR
    Envelope["ProjectEnvelope\nID + revision + policy + viewport"]
    A["E3 domain\nCircuit + ExternalWireGraph"]
    B["E1 domain\nStructuralDiagram + FunctionalLink"]
    C["ALGORITHM domain\nFlowNode + ControlFlowEdge"]
    Envelope -->|"project_kind=E3"| A
    Envelope -. "future independent adapter" .-> B
    Envelope -. "future Issue #82" .-> C
~~~

Shared snapshot storage and view metadata do not imply shared domain
commands or standard compliance. E3 electrical PinRef has no meaning
inside E1 or a software CFG.