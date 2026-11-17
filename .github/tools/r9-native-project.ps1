# R9 real native file I/O acceptance. ONLY Windows GitHub runner, disposable temp install/files.
param([Parameter(Mandatory=$true)][string]$ArtifactRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'R9_CI_ONLY' }
if (!$env:RUNNER_TEMP -or !(Test-Path -LiteralPath $env:RUNNER_TEMP)) { throw 'R9_RUNNER_TEMP_REQUIRED' }
$prefix = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'
$artifact = [IO.Path]::GetFullPath($ArtifactRoot)
if (!$artifact.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'R9_ARTIFACT_OUTSIDE_RUNNER_TEMP' }
$setups = @(Get-ChildItem -LiteralPath $artifact -File -Recurse -Filter '*setup.exe')
if ($setups.Count -ne 1) { throw ('R9_NSIS_SETUP_COUNT_' + $setups.Count) }
$root = Join-Path $env:RUNNER_TEMP ('gscad-r9-' + [guid]::NewGuid().ToString('N'))
$installDir = Join-Path $root 'Установка CAD R9'
$projectDir = Join-Path $root 'Проекты R9 с пробелами'
$project = Join-Path $projectDir 'Электросхема R9.gscad.json'
$copy = Join-Path $projectDir 'Копия проекта R9.gscad.json'
$svg = Join-Path $projectDir 'Схема R9.svg'
$png = Join-Path $projectDir 'Схема R9.png'
$uninstaller = Join-Path $installDir 'uninstall.exe'
$app = $null
$installed = $false
$env:GSCAD_R6_TRACE_WINDOW = '1'
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = '--remote-debugging-port=19443'
$env:WEBVIEW2_USER_DATA_FOLDER = Join-Path $root 'webview-profile'
try {
    New-Item -ItemType Directory -Path $root,$projectDir -Force | Out-Null
    if (Test-Path -LiteralPath $installDir) { throw 'R9_INSTALL_TARGET_EXISTS' }
    Write-Host 'R9_FROZEN_BINARY_SOURCE_SHA=d00c4324b1e31db73fdb577f120c6518bb5ad335'
    $setup = Start-Process -FilePath $setups[0].FullName -ArgumentList @('/S',('/D=' + $installDir)) -PassThru -Wait
    try { if ($setup.ExitCode -ne 0) { throw ('R9_NSIS_INSTALL_EXIT_' + $setup.ExitCode) } }
    finally { $setup.Dispose() }
    $exe = Join-Path $installDir 'gost-cad-desktop.exe'
    if (!(Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'R9_REAL_INSTALLED_EXE_MISSING' }
    $installed = $true
    Write-Host 'R9_REAL_NSIS_INSTALLED_PASS'
    $sidecars = @(Get-ChildItem -LiteralPath $installDir -Recurse -File -Filter 'engine-bridge*.exe')
    if ($sidecars.Count -ne 1) { throw ('R9_INSTALLED_SIDECAR_COUNT_' + $sidecars.Count) }
    $env:GSCAD_R9_SIDECAR_EXE = $sidecars[0].FullName
    # Independent real packed-process check: same operation Rust uses on Save,
    # but without Tauri or the system file picker.
    $fixture = Get-Content -LiteralPath 'ui/fixtures/tl494-source-e695-v2.gscad.json' -Raw -Encoding utf8
    $directRequest = [ordered]@{
        v = 1
        id = 'r9_direct_parse'
        op = 'parse_document_blob'
        args = @{ blob = $fixture }
    } | ConvertTo-Json -Compress -Depth 5
    $directOutput = @($directRequest | & $env:GSCAD_R9_SIDECAR_EXE)
    if ($LASTEXITCODE -ne 0) { throw ('R9_PACKAGED_DIRECT_PARSE_EXIT_' + $LASTEXITCODE) }
    if ($directOutput.Count -ne 1) { throw ('R9_PACKAGED_DIRECT_PARSE_LINES_' + $directOutput.Count) }
    $directReply = $directOutput[0] | ConvertFrom-Json
    if ($directReply.ok -ne $true -or $directReply.id -ne 'r9_direct_parse') {
        throw ('R9_PACKAGED_DIRECT_PARSE_REJECTED_' + $directReply.error.code)
    }
    Write-Host 'R9_PACKAGED_DIRECT_PARSE_SOURCE_PASS'
    foreach ($phase in @('create','reopen')) {
        $app = Start-Process -FilePath $exe -WorkingDirectory $installDir -PassThru
        Write-Host ("R9_NATIVE_LAUNCH phase=$phase pid=" + $app.Id)
        & node .github/tools/r9-native-project.mjs $phase $app.Id 19443 $project $copy $svg $png
        if ($LASTEXITCODE -ne 0) { throw ('R9_NATIVE_PHASE_FAILED_' + $phase) }
        $app.Refresh()
        if (!$app.HasExited) {
            if (!$app.CloseMainWindow()) { throw ('R9_WINDOW_CLOSE_REJECTED_' + $phase) }
            if (!$app.WaitForExit(30000)) { throw ('R9_WINDOW_CLOSE_TIMEOUT_' + $phase) }
        }
        Write-Host ('R9_CLEAN_NATIVE_CLOSE_PASS phase=' + $phase)
        $app.Dispose()
        $app = $null
        Start-Sleep -Seconds 2
    }
    foreach ($file in @($project,$copy,$svg,$png)) {
        if (!(Test-Path -LiteralPath $file -PathType Leaf)) {
            throw ('R9_EXPECTED_DISK_FILE_MISSING_' + [IO.Path]::GetFileName($file))
        }
    }
    Write-Host 'R9_REAL_NATIVE_PROJECT_ROUNDTRIP_AND_EXPORT_PASS'
} finally {
    if ($app) {
        try {
            $app.Refresh()
            if (!$app.HasExited) { $app.Kill(); $app.WaitForExit(10000) | Out-Null }
        } catch { Write-Warning ('R9 CI-only process cleanup: ' + $_.Exception.Message) }
        $app.Dispose()
    }
    if ($installed -and (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
        try {
            $un = Start-Process -FilePath $uninstaller -ArgumentList @('/S') -Wait -PassThru
            try { if ($un.ExitCode -ne 0) { Write-Warning ('R9 uninstall exit code ' + $un.ExitCode) } }
            finally { $un.Dispose() }
        } catch { Write-Warning ('R9 CI-only NSIS cleanup: ' + $_.Exception.Message) }
    }
    Remove-Item Env:GSCAD_R9_SIDECAR_EXE -ErrorAction SilentlyContinue
    Remove-Item Env:GSCAD_R6_TRACE_WINDOW -ErrorAction SilentlyContinue
    Remove-Item Env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS -ErrorAction SilentlyContinue
    Remove-Item Env:WEBVIEW2_USER_DATA_FOLDER -ErrorAction SilentlyContinue
    if ($root.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
