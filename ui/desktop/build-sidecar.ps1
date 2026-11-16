# Windows-only packaging: requires Python 3.12 venv and rustc MSVC.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$py = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path $py)) { throw 'Run py -3.12 -m venv .venv from repository root first' }
& $py -m pip install -e "$($root)[dev]"
if ($LASTEXITCODE -ne 0) { throw 'Install of Python engine failed' }
# Import the ONE authoritative #122 v2 model, rather than shipping a second schema.
& $py -m pip install 'pyinstaller>=6,<7' 'jsonschema==4.26.0'
if ($LASTEXITCODE -ne 0) { throw 'Install of PyInstaller/jsonschema failed' }
$schemaPath = Join-Path $root 'ui/contracts/project-v2.schema.json'
$modelPath = Join-Path $root 'ui/editor/src/model/contract.py'
if (-not (Test-Path $schemaPath) -or -not (Test-Path $modelPath)) {
  throw 'Install reviewed #122 ProjectFileV2 contract and schema before packaging'
}
& $py -m PyInstaller --clean --noconfirm --onefile --collect-all gost_schematic --collect-all jsonschema --add-data "$modelPath;ui/editor/src/model" --add-data "$schemaPath;ui/contracts" --name engine-bridge --distpath (Join-Path $PSScriptRoot 'dist') --workpath (Join-Path $PSScriptRoot '.pyi') (Join-Path $root 'ui/bridge/transport/worker.py')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$hostTriple = (& rustc -vV | Select-String '^host: (.+)$').Matches.Groups[1].Value
if (-not $hostTriple) { throw 'rustc host target unavailable' }
$binaryDir = Join-Path $PSScriptRoot 'src-tauri/binaries'
New-Item -ItemType Directory -Force $binaryDir | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'dist/engine-bridge.exe') (Join-Path $binaryDir "engine-bridge-$hostTriple.exe")
Get-FileHash (Join-Path $binaryDir "engine-bridge-$hostTriple.exe") -Algorithm SHA256
