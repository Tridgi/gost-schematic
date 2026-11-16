# Windows-only packaging: requires Python 3.12 venv and rustc MSVC.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
# A developer may select a different Python *inside this checked-out repository*.
# This variable is a BUILD-ONLY option, never a frontend/IPC process path.
$py = Join-Path $root '.venv/Scripts/python.exe'
if ($env:GSCAD_SIDECAR_PYTHON) {
  $candidate = (Resolve-Path $env:GSCAD_SIDECAR_PYTHON -ErrorAction Stop).Path
  $prefix = [IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
  if (-not $candidate.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
      [IO.Path]::GetFileName($candidate) -ne 'python.exe') {
    throw 'Build-only Python interpreter must be a repository-local venv python.exe'
  }
  $py = $candidate
}
if (-not (Test-Path $py)) { throw 'Run py -3.12 -m venv .venv from repository root first' }
& $py -m pip install -e "$($root)[dev]"
if ($LASTEXITCODE -ne 0) { throw 'Install of Python engine failed' }
# Import the ONE authoritative #122 v2 model, rather than shipping a second schema.
& $py -m pip install 'pyinstaller>=6,<7' 'jsonschema==4.26.0' 'CairoSVG==2.8.2' 'Pillow>=10,<13'
if ($LASTEXITCODE -ne 0) { throw 'Install of PyInstaller/jsonschema failed' }
# CairoSVG is a Python wrapper around a NATIVE Cairo DLL, which plain pip
# wheels do not install on Windows. Bundle the reviewed MINGW64 Cairo binary
# and its transitive dependencies, instead of relying on the target PC's PATH.
# Only fixed local build-runtime prefixes are searched; never from frontend IPC.
$cairoCandidates = @(
  'C:\msys64\mingw64\bin',
  'D:\MSYS2\mingw64\bin'
)
# GitHub's msys2/setup-msys2 action installs under RUNNER_TEMP/msys64
# rather than C:/msys64. This is still a fixed build-host directory.
if ($env:RUNNER_TEMP) {
  $cairoCandidates += (Join-Path $env:RUNNER_TEMP 'msys64\mingw64\bin')
}
$cairoDir = $cairoCandidates | Where-Object {
  Test-Path (Join-Path $_ 'libcairo-2.dll')
} | Select-Object -First 1
if (-not $cairoDir) { throw 'CAIRO_DLL_NOT_INSTALLED_FOR_WINDOWS_PNG_EXPORT' }
$env:PATH = $cairoDir + ';' + $env:PATH
$env:CAIROCFFI_DLL_DIRECTORIES = $cairoDir
& $py -c 'import cairocffi; print("CAIRO_NATIVE_VERSION=" + cairocffi.cairo_version_string())'
if ($LASTEXITCODE -ne 0) { throw 'CAIRO_NATIVE_LOAD_FAILED' }
$schemaPath = Join-Path $root 'ui/contracts/project-v2.schema.json'
$modelPath = Join-Path $root 'ui/editor/src/model/contract.py'
$wireAdapterPath = Join-Path $root 'ui/integration/project_wire_bridge.py'
$engineAdapterPath = Join-Path $root 'ui/editor/src/model/engine_adapter.py'
if (-not (Test-Path $schemaPath) -or -not (Test-Path $modelPath) -or -not (Test-Path $wireAdapterPath)) {
  throw 'Install reviewed #122 model and MASTER #125 wire adapter before packaging'
}
$pyiArgs = @(
  '--clean', '--noconfirm', '--onefile',
  '--collect-all', 'gost_schematic', '--collect-all', 'jsonschema',
  '--collect-all', 'cairosvg', '--collect-all', 'PIL',
  '--add-binary', "$(Join-Path $cairoDir 'libcairo-2.dll');.",
  '--paths', $root,
  '--hidden-import', 'ui.bridge.export.project_v2',
  '--hidden-import', 'ui.bridge.export.canonical',
  '--add-data', "$(Join-Path $root 'ui/bridge/export');ui/bridge/export",
  '--add-data', "$modelPath;ui/editor/src/model",
  '--add-data', "$schemaPath;ui/contracts",
  '--add-data', "$wireAdapterPath;ui/integration",
  '--name', 'engine-bridge',
  '--distpath', (Join-Path $PSScriptRoot 'dist'),
  '--workpath', (Join-Path $PSScriptRoot '.pyi')
)
if (Test-Path $engineAdapterPath) {
  $pyiArgs += @('--add-data', "$engineAdapterPath;ui/editor/src/model")
} else {
  Write-Warning 'PR #134 E3 adapter not integrated: engine_projection returns ENGINE_ADAPTER_UNAVAILABLE'
}
$pyiArgs += (Join-Path $root 'ui/bridge/transport/worker.py')
& $py -m PyInstaller @pyiArgs
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$hostTriple = (& rustc -vV | Select-String '^host: (.+)$').Matches.Groups[1].Value
if (-not $hostTriple) { throw 'rustc host target unavailable' }
$binaryDir = Join-Path $PSScriptRoot 'src-tauri/binaries'
New-Item -ItemType Directory -Force $binaryDir | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'dist/engine-bridge.exe') (Join-Path $binaryDir "engine-bridge-$hostTriple.exe")
Get-FileHash (Join-Path $binaryDir "engine-bridge-$hostTriple.exe") -Algorithm SHA256
