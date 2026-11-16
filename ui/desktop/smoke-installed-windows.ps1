# R5 Windows CI install smoke. All disk writes are isolated to a new RUNNER_TEMP GUID.
# This is a real installed-process check, not interactive CAD or ESKD approval.
param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP) -or !(Test-Path $env:RUNNER_TEMP)) { throw 'CI_RUNNER_TEMP_REQUIRED' }
$setup = (Resolve-Path -LiteralPath $Installer).Path
$root = Join-Path $env:RUNNER_TEMP ('gscad-r5-' + [guid]::NewGuid().ToString('N'))
$installedDir = Join-Path $root 'Проверка CAD с пробелами'
$launched = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()
$uninstaller = $null
$installed = $false
function Run-Bounded([string]$File,[string[]]$Args,[int]$TimeoutMs) {
    $p = Start-Process -FilePath $File -ArgumentList $Args -PassThru -WindowStyle Hidden
    try {
        if (!$p.WaitForExit($TimeoutMs)) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            throw ('TIMEOUT: ' + [IO.Path]::GetFileName($File))
        }
        if ($p.ExitCode -ne 0) { throw ('EXIT_' + $p.ExitCode + ': ' + [IO.Path]::GetFileName($File)) }
    } finally { $p.Dispose() }
}
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    Write-Host ('NSIS_UNICODE_INSTALL_DIR: ' + $installedDir)
    # NSIS /D must be last, and Unicode/space paths exercise wide-character Win32 APIs.
    Run-Bounded -File $setup -Args @('/S',('/D=' + $installedDir)) -TimeoutMs 120000
    $appExe = Join-Path $installedDir 'gost-cad-desktop.exe'
    $sidecarExe = Join-Path $installedDir 'engine-bridge-x86_64-pc-windows-msvc.exe'
    if (!(Test-Path -LiteralPath $appExe -PathType Leaf)) { throw 'INSTALLED_APP_MISSING' }
    if (!(Test-Path -LiteralPath $sidecarExe -PathType Leaf)) { throw 'INSTALLED_SIDECAR_MISSING' }
    $installed = $true
    $line = '{"v":1,"id":"installed_hello","op":"hello","args":{}}'
    $output = @($line | & $sidecarExe)
    if ($LASTEXITCODE -ne 0 -or $output.Count -ne 1) { throw 'INSTALLED_SIDECAR_HELLO_FAILED' }
    $reply = $output[0] | ConvertFrom-Json
    if ($reply.v -ne 1 -or $reply.id -ne 'installed_hello' -or $reply.ok -ne $true) {
        throw 'INSTALLED_SIDECAR_PROTOCOL_INVALID'
    }
    Write-Host 'INSTALLED_PYTHON_HELLO_PASS'
    for ($i=1; $i -le 2; $i++) {
        $app = Start-Process -FilePath $appExe -WorkingDirectory $installedDir -PassThru
        $launched.Add($app)
        $found = $false
        for ($attempt=0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Milliseconds 500
            $app.Refresh()
            if ($app.HasExited) { throw ("APP_EXITED_EARLY_$i exit=" + $app.ExitCode) }
            if ($app.MainWindowHandle -ne [IntPtr]::Zero) { $found = $true; break }
        }
        if (!$found) { throw ("APP_WINDOW_NOT_FOUND_$i") }
        if (!$app.CloseMainWindow()) { throw ("APP_WINDOW_CLOSE_REJECTED_$i") }
        if (!$app.WaitForExit(15000)) { throw ("APP_CLOSE_TIMEOUT_$i") }
        Write-Host ("INSTALLED_APP_LAUNCH_CLOSE_PASS_$i")
    }
    Start-Sleep -Seconds 2
    $orphans = @(Get-CimInstance Win32_Process -Filter "Name = 'engine-bridge-x86_64-pc-windows-msvc.exe'" |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($installedDir,[StringComparison]::OrdinalIgnoreCase) })
    if ($orphans.Count -ne 0) { throw 'ORPHAN_INSTALLED_SIDECAR' }
    Write-Host 'NO_INSTALLED_SIDECAR_ORPHANS_PASS'
    $uninstaller = Join-Path $installedDir 'uninstall.exe'
    if (!(Test-Path -LiteralPath $uninstaller -PathType Leaf)) { throw 'NSIS_UNINSTALLER_MISSING' }
    Run-Bounded -File $uninstaller -Args @('/S') -TimeoutMs 120000
    if (Test-Path -LiteralPath $appExe -PathType Leaf) { throw 'NSIS_UNINSTALL_LEFT_EXE' }
    $installed = $false
    Write-Host 'NSIS_INSTALL_UNINSTALL_PASS'
} finally {
    foreach ($app in $launched) {
        try {
            $app.Refresh()
            if (!$app.HasExited) { $app.Kill() }
            $app.Dispose()
        } catch { Write-Warning ('cleanup: ' + $_.Exception.Message) }
    }
    if ($installed -and $uninstaller -and (Test-Path -LiteralPath $uninstaller)) {
        try { Run-Bounded -File $uninstaller -Args @('/S') -TimeoutMs 30000 }
        catch { Write-Warning ('cleanup uninstall: ' + $_.Exception.Message) }
    }
    if ((Test-Path -LiteralPath $root) -and
        $root.StartsWith($env:RUNNER_TEMP,[StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
