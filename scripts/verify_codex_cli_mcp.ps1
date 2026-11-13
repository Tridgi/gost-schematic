# Reproducible real Codex CLI -> MCP ImageContent -> second inspection smoke.
# Requires Codex CLI authenticated via 'codex login'; never copies auth/session files.
param(
    [string]$Codex = 'codex.cmd',
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (!(Test-Path $Python)) { throw "Missing venv Python at $Python; install .[dev,mcp]" }
$OutDir = Join-Path $ProjectRoot 'artifacts\ai-mcp'
New-Item -Path $OutDir -ItemType Directory -Force | Out-Null
$Log = Join-Path $OutDir 'codex-cli-smoke.jsonl'
$Answer = Join-Path $OutDir 'codex-cli-smoke-answer.md'
$Prompt = @'
Read-only engineering audit, using ONLY the gost_schematic_vision MCP tools, not terminal,
python, shell or file-reading tools. Call schematic_render_overview for project_ref=six-part,
mode=clean. Inspect the actual returned image and describe what C3 looks like, and
identify one area worth zooming. Then call schematic_inspect_component for reference=C3
at target_dpi=500 mode=diagnostic. Independently inspect the second image. Then call
schematic_get_diagnostics for project_ref=six-part check=all. Return a short report with
the exact MCP tool names called, visual observations from the images (not guessed from
names), whether specialized electrolytic C3 and two physical leads are visible, SHA
revision and bbox from metadata, and diagnostics codes. Do not modify any files.
If the MCP images are not visible to you as images, explicitly say so, without guessing.
'@
$Cfg = @(
    "mcp_servers.gost_schematic_vision.command='$Python'",
    "mcp_servers.gost_schematic_vision.args=['-m','gost_schematic.mcp_server']",
    "mcp_servers.gost_schematic_vision.cwd='$ProjectRoot'",
    "mcp_servers.gost_schematic_vision.env.GSE_MCP_WORKSPACE='$ProjectRoot'"
)
$CliArgs = @('exec','--ignore-user-config','--ephemeral','--sandbox','read-only',
             '-C',$ProjectRoot,'--json','--output-last-message',$Answer)
foreach ($entry in $Cfg) { $CliArgs += @('-c', $entry) }
$CliArgs += $Prompt
Write-Host "Running Codex CLI (read-only) on verified checkout: $ProjectRoot"
$ErrorActionPreference = 'Continue' # Codex writes harmless stdin notice on stderr
# Desktop Commander holds stdin open; pipe EOF explicitly, or Codex waits forever.
'' | & $Codex @CliArgs 2> (Join-Path $OutDir 'codex-cli-smoke.stderr') |
    Out-File -FilePath $Log -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "Codex CLI exited with $LASTEXITCODE; inspect stderr and JSONL." }
Write-Host "Codex JSONL: $Log"
Write-Host "Codex final: $Answer"
