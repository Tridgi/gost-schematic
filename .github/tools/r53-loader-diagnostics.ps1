# Diagnostic-only; does not launch or alter the application or change test outcome.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or !$env:RUNNER_TEMP) { throw 'R53_CI_ONLY' }
$out = Join-Path $env:RUNNER_TEMP 'gscad-r53-loader-diagnostics'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$target = 'ui/desktop/src-tauri/target/debug'
$lock = 'ui/desktop/src-tauri/Cargo.lock'
if (Test-Path -LiteralPath $lock) {
    Copy-Item -LiteralPath $lock -Destination $out
    $digest = (Get-FileHash -LiteralPath $lock -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host ('R53_FAILED_CARGO_LOCK_SHA256=' + $digest)
}
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture |
    Format-List | Out-String | Set-Content (Join-Path $out 'os.txt')
$system = Join-Path $env:SystemRoot 'System32'
$names = @('kernel32.dll','KernelBase.dll','ntdll.dll','user32.dll','ucrtbase.dll','vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','bcrypt.dll','crypt32.dll','winhttp.dll','dwmapi.dll','shcore.dll','combase.dll')
foreach ($name in $names) {
    $file = Join-Path $system $name
    if (Test-Path -LiteralPath $file) {
        $item = Get-Item -LiteralPath $file
        "$name $($item.VersionInfo.FileVersion) $((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash)" |
            Add-Content (Join-Path $out 'system-dlls.txt')
    }
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or !$vs) { throw 'R53_VSWHERE_FAILED' }
$dumpbin = Get-ChildItem (Join-Path $vs 'VC/Tools/MSVC') -Filter dumpbin.exe -Recurse -File |
    Where-Object { $_.FullName -match 'Hostx64[\\/]x64[\\/]dumpbin\.exe$' } |
    Select-Object -First 1
if (!$dumpbin) { throw 'R53_DUMPBIN_MISSING' }
$tests = @(Get-ChildItem -LiteralPath $target -Filter 'gost_cad_desktop_lib-*.exe' -Recurse -File)
if ($tests.Count -eq 0) { throw 'R53_TEST_EXE_NOT_FOUND' }
$i = 0
foreach ($test in $tests) {
    $i++
    Write-Host ('R53_DIAGNOSTIC_TEST_EXE=' + $test.FullName)
    $prefix = Join-Path $out ('test-' + $i)
    $test.FullName | Set-Content ($prefix + '-path.txt')
    & $dumpbin.FullName /imports $test.FullName | Set-Content ($prefix + '-imports.txt')
    if ($LASTEXITCODE -ne 0) { throw 'R53_DUMPBIN_IMPORTS_FAILED' }
    & $dumpbin.FullName /dependents $test.FullName | Set-Content ($prefix + '-dependents.txt')
    if ($LASTEXITCODE -ne 0) { throw 'R53_DUMPBIN_DEPENDENTS_FAILED' }
}
# Export tables enable comparison against missing entry points without shipping DLLs.
foreach ($name in $names) {
    $file = Join-Path $system $name
    if (Test-Path -LiteralPath $file) {
        & $dumpbin.FullName /exports $file | Set-Content (Join-Path $out ($name + '-exports.txt'))
    }
}
Write-Host 'R53_LOADER_DIAGNOSTIC_EVIDENCE_COLLECTED'
