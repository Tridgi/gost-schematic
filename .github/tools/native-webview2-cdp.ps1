# Experimental R8 real GUI test; execute ONLY inside an isolated GitHub Windows Runner.
param([Parameter(Mandatory=$true)][string]$ArtifactRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:GITHUB_ACTIONS -ne 'true') { throw 'CI_ONLY_TEST' }
if (!$env:RUNNER_TEMP -or !(Test-Path -LiteralPath $env:RUNNER_TEMP)) { throw 'RUNNER_TEMP_REQUIRED' }
$safePrefix = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'
$artifact = [IO.Path]::GetFullPath($ArtifactRoot)
if (!$artifact.StartsWith($safePrefix,[StringComparison]::OrdinalIgnoreCase)) {
    throw 'FROZEN_ARTIFACT_MUST_BE_RUNNER_TEMP'
}
$setupFiles = @(Get-ChildItem -LiteralPath $artifact -File -Recurse -Filter '*setup.exe')
if ($setupFiles.Count -ne 1) { throw ('FROZEN_INSTALLER_COUNT_' + $setupFiles.Count) }
$root = Join-Path $env:RUNNER_TEMP ('gscad-r8-cdp-' + [guid]::NewGuid().ToString('N'))
$installDir = Join-Path $root 'Установка CAD R8 с пробелами'
$uninstaller = Join-Path $installDir 'uninstall.exe'
$app = $null
$installWasCreated = $false
$traceFile = $null
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    if (Test-Path -LiteralPath $installDir) { throw 'R8_INSTALL_DIR_PREEXISTS' }
    Write-Host ('R8_FROZEN_ARTIFACT_SHA=d00c4324b1e31db73fdb577f120c6518bb5ad335')
    $installer = Start-Process -FilePath $setupFiles[0].FullName -ArgumentList @('/S',('/D=' + $installDir)) -Wait -PassThru
    try { if ($installer.ExitCode -ne 0) { throw ('R8_INSTALL_EXIT_' + $installer.ExitCode) } }
    finally { $installer.Dispose() }
    $appExe = Join-Path $installDir 'gost-cad-desktop.exe'
    if (!(Test-Path -LiteralPath $appExe -PathType Leaf)) { throw 'R8_CUSTOM_UNICODE_INSTALL_MISSING' }
    $installWasCreated = $true
    $env:GSCAD_R6_TRACE_WINDOW = '1'
    $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = '--remote-debugging-port=19443'
    $env:WEBVIEW2_USER_DATA_FOLDER = Join-Path $root 'webview-profile'
    $app = Start-Process -FilePath $appExe -WorkingDirectory $installDir -PassThru
    $traceFile = Join-Path ([IO.Path]::GetTempPath()) ('gscad-r6-window-' + $app.Id + '.log')
    Write-Host ('R8_GUI_PID=' + $app.Id)
    & node .github/tools/native-webview2-cdp.mjs $app.Id 19443
    if ($LASTEXITCODE -ne 0) { throw 'R8_CDP_E2E_FAILED' }
    if (!$app.WaitForExit(30000)) { throw 'R8_APP_NOT_EXITED_AFTER_CONFIRM' }
    Write-Host 'R8_REAL_WEBVIEW2_GUI_EXIT_PASS'
    if (!(Test-Path -LiteralPath $traceFile -PathType Leaf)) { throw 'R8_NATIVE_TRACE_MISSING' }
    $trace = Get-Content -LiteralPath $traceFile
    $trace | ForEach-Object { Write-Host ('R8_NATIVE_EVENT ' + $_) }
    foreach ($required in @('stage=guard_confirm_cancel', 'stage=guard_prevent_default',
                            'stage=guard_confirm_accept', 'event=Destroyed')) {
        if (!($trace | Where-Object { $_.Contains($required) })) { throw ('R8_TRACE_MISSING_' + $required) }
    }
    Write-Host 'R8_REAL_WEBVIEW2_DIRTY_CLOSE_CANCEL_CONFIRM_PASS'
} finally {
    if ($app) {
        try { $app.Refresh(); if (!$app.HasExited) { $app.Kill(); $app.WaitForExit(10000) | Out-Null } }
        catch { Write-Warning ('R8 isolated cleanup: ' + $_.Exception.Message) }
        $app.Dispose()
    }
    if ($installWasCreated -and (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
        try {
            $u = Start-Process -FilePath $uninstaller -ArgumentList @('/S') -Wait -PassThru
            try { if ($u.ExitCode -ne 0) { Write-Warning ('R8 cleanup uninstaller exit: ' + $u.ExitCode) } }
            finally { $u.Dispose() }
        } catch { Write-Warning ('R8 cleanup uninstall: ' + $_.Exception.Message) }
    }
    if ($traceFile -and (Test-Path -LiteralPath $traceFile)) {
        Remove-Item -LiteralPath $traceFile -Force -ErrorAction SilentlyContinue
    }
    Remove-Item Env:GSCAD_R6_TRACE_WINDOW -ErrorAction SilentlyContinue
    Remove-Item Env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS -ErrorAction SilentlyContinue
    Remove-Item Env:WEBVIEW2_USER_DATA_FOLDER -ErrorAction SilentlyContinue
    if ($root.StartsWith($safePrefix,[StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
