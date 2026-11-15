# Windows-only packaging: requires Python 3.12 venv and rustc MSVC.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$py = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path $py)) { throw 'Run py -3.12 -m venv .venv from repository root first' }
& $py -m pip install -e "$($root)[dev]"
if ($LASTEXITCODE -ne 0) { throw 'Install of Python engine failed' }
& $py -m pip install 'pyinstaller>=6,<7'
if ($LASTEXITCODE -ne 0) { throw 'Install of PyInstaller failed' }
& $py -m PyInstaller --clean --noconfirm --onefile --collect-all gost_schematic --name engine-bridge --distpath (Join-Path $PSScriptRoot 'dist') --workpath (Join-Path $PSScriptRoot '.pyi') (Join-Path $root 'ui/bridge/transport/worker.py')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$hostTriple = (& rustc -vV | Select-String '^host: (.+)$').Matches.Groups[1].Value
if (-not $hostTriple) { throw 'rustc host target unavailable' }
$binaryDir = Join-Path $PSScriptRoot 'src-tauri/binaries'
New-Item -ItemType Directory -Force $binaryDir | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'dist/engine-bridge.exe') (Join-Path $binaryDir "engine-bridge-$hostTriple.exe")
Get-FileHash (Join-Path $binaryDir "engine-bridge-$hostTriple.exe") -Algorithm SHA256
