# PR #73 — Codex CLI MCP Vision smoke, Windows 11

**Date:** 2026-11-13. **CLI:** @openai/codex 0.169.0, authenticated via ChatGPT.
**Checkout:** C:\Users\User\Documents\gost-schematic-ai-mcp (verified on the device).
The test did not modify the user's permanent Codex config.toml.

## Actual model-driven results

- Codex CLI ran with --ignore-user-config --ephemeral --sandbox read-only, and only this MCP server configured through temporary -c overrides.
- A first attempt demonstrated that unannotated MCP tools were denied by CLI approval rules. All six tools are now explicitly marked readOnlyHint=true, destructiveHint=false, idempotentHint=true and openWorldHint=false. No dangerous sandbox-bypass flag was used.
- Codex completed an agent turn with **15 MCP tool calls**: view discovery, diagnostics, overview, component crops, and net/connection inspection.
- Actual model tool results contained **12 native ImageContent image/png blocks**, all valid PNG magic. Codex made multiple FOLLOW-UP component-zoom calls after receiving the overview, including C3 and physical connection tools.
- **14 calls completed and one connection query failed**; the rejected query is retained in the report, not hidden.
- All metadata bearing a revision agreed on SHA 03c624ec68760a31b5b7f48d1cfcfffe1fb3e293fb616f2b03127cdd2ed1ddf9.
- Codex's engineering answer identified six DRAFT UGO warnings, noted possible diagnostic label overlap, and did not declare ГОСТ/ESKD conformity.

[Sanitized real Codex CLI tool-call evidence](../assets/ai-mcp/codex-cli-smoke-summary.json).
The raw JSONL with Base64 PNGs stays only in the ignored local workspace
artifacts/ai-mcp/codex-cli-smoke.jsonl.

## Reproduction on this actual checkout

Use the normal Windows 11 terminal after Codex CLI is installed and authenticated.

1. Open PowerShell in C:\Users\User\Documents\gost-schematic-ai-mcp.
2. Install project dependencies with: uv pip install --python .venv\Scripts\python.exe -e ".[dev,mcp]"
3. If needed install Codex CLI: npm.cmd install -g @openai/codex
4. Check authentication: codex login status
5. Run: .\scripts\verify_codex_cli_mcp.ps1 -Codex "codex.cmd"
6. Summarize: .\.venv\Scripts\python.exe scripts\summarize_codex_mcp_smoke.py artifacts\ai-mcp\codex-cli-smoke.jsonl

The script pins the real absolute worktree path, uses one MCP server,
and pipes EOF to Codex exec. The EOF is essential in a remote interactive
terminal; otherwise CLI waits indefinitely for additional standard input.
A real Codex run may choose a different number of follow-up views.

For persistent Codex use, add the verified TOML block from
[Windows connection guide](mcp-vision.md) to
C:\Users\User\.codex\config.toml and verify with codex mcp list.

## C3 provenance and limitations

[C3 source-level evidence](pr73-c3-evidence.md) proves that this
is the real capacitor.electrolytic with 12 catalog strokes, not a
generic polarized two-plate substitute. Its physical PLUS pin 1 and MINUS
pin 2, bbox and a separate 500-DPI SVG crop are regression-tested.
The Codex model requested its own image at a different DPI but the
same snapshot revision.

The project remains a read-only fixed six-part specimen: no arbitrary
SchematicProject, move/connect/save MCP operations, automatic ГОСТ
approval or proven OpenGost Type A refdes. The label checker is unimplemented.
ProjectService editing is a separate Issue #74 design task.
