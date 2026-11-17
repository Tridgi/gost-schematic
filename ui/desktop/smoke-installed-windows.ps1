# R5 Windows CI install smoke. All temporary files are isolated to RUNNER_TEMP GUID.
# NSIS current-user install uses HKCU/LOCALAPPDATA; fail rather than touch pre-existing installations.
# Does not certify human GUI interaction or ESKD compliance.
param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP) -or !(Test-Path $env:RUNNER_TEMP)) { throw 'CI_RUNNER_TEMP_REQUIRED' }
$setup = (Resolve-Path -LiteralPath $Installer).Path
$root = Join-Path $env:RUNNER_TEMP ('gscad-r5-' + [guid]::NewGuid().ToString('N'))
$installedDir = Join-Path $env:LOCALAPPDATA 'GOST Schematic CAD - Desktop IPC Preview'
$unicodeDir = Join-Path $root 'Проверка CAD с пробелами'
$initialInstallDir = $installedDir
$launched = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()
$uninstaller = $null
$installed = $false
function Run-Bounded([string]$File,[string[]]$ArgumentTokens,[int]$TimeoutMs) {
    # Native NSIS stays visible to CI's interactive user; /S itself silences the UI.
    if (!$ArgumentTokens -or $ArgumentTokens.Count -eq 0) { throw 'EMPTY_PROCESS_ARGUMENTS' }
    Write-Host ('PROCESS_ARGUMENTS: ' + ($ArgumentTokens -join ' '))
    $p = Start-Process -FilePath $File -ArgumentList $ArgumentTokens -PassThru
    try {
        $elapsed = 0
        while (!$p.WaitForExit(10000)) {
            $elapsed += 10000
            $children = @(Get-CimInstance Win32_Process -Filter ('ParentProcessId = ' + $p.Id))
            $names = ($children | ForEach-Object { $_.Name + ':' + $_.ProcessId }) -join ','
            $p.Refresh()
            $mainWindow = $p.MainWindowTitle
            $cpu = $p.CPU
            Write-Host ('INSTALLER_WAIT_MS=' + $elapsed + ' parent=' + $p.Id +
                ' cpuSeconds=' + $cpu + ' title=' + $mainWindow +
                ' children=' + $names + ' targetExists=' + (Test-Path -LiteralPath $installedDir))
            if ($elapsed -ge $TimeoutMs) {
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
                throw ('TIMEOUT: ' + [IO.Path]::GetFileName($File))
            }
        }
        if ($p.ExitCode -ne 0) { throw ('EXIT_' + $p.ExitCode + ': ' + [IO.Path]::GetFileName($File)) }
    } finally { $p.Dispose() }
}
try {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    Write-Host ('NSIS_DEFAULT_USER_INSTALL_DIR: ' + $installedDir)
    if (Test-Path -LiteralPath $installedDir) { throw 'NSIS_DEFAULT_TARGET_PREEXISTS' }
    # First isolate whether NSIS /D with Cyrillic/spaces was the reason for the stall.
    # Default currentUser mode does not require elevation or custom path handling.
    Run-Bounded -File $setup -ArgumentTokens @('/S') -TimeoutMs 90000
    $registered = @(Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -eq 'GOST Schematic CAD - Desktop IPC Preview' -and $_.InstallLocation })
    if ($registered.Count -eq 1) {
        Write-Host ('NSIS_REGISTRY_INSTALL_LOCATION: ' + $registered[0].InstallLocation)
    }
    # A successful actual installation under the verified default per-user
    # directory is authoritative. The uninstall registry entry may contain
    # quoted, relative or provider-specific locations: never follow it if the
    # target files are already at the known safe default.
    if (!(Test-Path -LiteralPath (Join-Path $installedDir 'gost-cad-desktop.exe') -PathType Leaf)) {
        if ($registered.Count -ne 1) { throw 'NSIS_DEFAULT_APP_MISSING_NO_REGISTRY' }
        $candidate = [IO.Path]::GetFullPath(
            [Environment]::ExpandEnvironmentVariables([string]$registered[0].InstallLocation).Trim('"'))
        $safePrefix = [IO.Path]::GetFullPath($env:LOCALAPPDATA).TrimEnd('\') + '\'
        if (!$candidate.StartsWith($safePrefix,[StringComparison]::OrdinalIgnoreCase)) {
            throw 'NSIS_INSTALL_OUTSIDE_USER_APPDATA'
        }
        $installedDir = $candidate
    }
    if (!(Test-Path -LiteralPath $installedDir -PathType Container)) {
        throw 'NSIS_DEFAULT_INSTALL_DIRECTORY_MISSING'
    }
    $installed = $true
    Write-Host ('NSIS_ACTUAL_INSTALL_DIR: ' + $installedDir)
    $appExe = Join-Path $installedDir 'gost-cad-desktop.exe'
    if (!(Test-Path -LiteralPath $appExe -PathType Leaf)) { throw 'INSTALLED_APP_MISSING' }
    # Tauri may strip the platform triple from the copied sidecar filename.
    $sidecar = @(Get-ChildItem -LiteralPath $installedDir -File -Recurse -Filter 'engine-bridge*.exe')
    if ($sidecar.Count -ne 1) { throw ('INSTALLED_SIDECAR_COUNT_' + $sidecar.Count) }
    $sidecarExe = $sidecar[0].FullName
    # Test the installed layout after copying it into a Unicode + whitespace path.
    # This does NOT claim NSIS itself installed to that path.
    Copy-Item -LiteralPath $installedDir -Destination $unicodeDir -Recurse -Force
    $unicodeSidecars = @(Get-ChildItem -LiteralPath $unicodeDir -File -Recurse -Filter 'engine-bridge*.exe')
    if ($unicodeSidecars.Count -ne 1) { throw 'RELOCATED_UNICODE_SIDECAR_MISSING' }
    $sidecarExe = $unicodeSidecars[0].FullName
    Write-Host 'UNICODE_RELOCATED_BUNDLE_READY'
    $line = '{"v":1,"id":"installed_hello","op":"hello","args":{}}'
    $output = @($line | & $sidecarExe)
    if ($LASTEXITCODE -ne 0 -or $output.Count -ne 1) { throw 'INSTALLED_SIDECAR_HELLO_FAILED' }
    $reply = $output[0] | ConvertFrom-Json
    if ($reply.v -ne 1 -or $reply.id -ne 'installed_hello' -or $reply.ok -ne $true) {
        throw 'INSTALLED_SIDECAR_PROTOCOL_INVALID'
    }
    Write-Host 'INSTALLED_PYTHON_HELLO_PASS'
    # Repeated startup in the genuine installed location precedes relocation.
    # Failures then identify restart versus Unicode relocation distinctly.
    for ($i=1; $i -le 3; $i++) {
        $launchDir = if ($i -le 2) { $installedDir } else { $unicodeDir }
        Write-Host ("APP_LAUNCH_LOCATION_$i=" + $launchDir)
        $launchExe = Join-Path $launchDir 'gost-cad-desktop.exe'
        $app = Start-Process -FilePath $launchExe -WorkingDirectory $launchDir -PassThru
        $launched.Add($app)
        $found = $false
        for ($attempt=0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Milliseconds 500
            $app.Refresh()
            if ($app.HasExited) { throw ("APP_EXITED_EARLY_$i exit=" + $app.ExitCode) }
            if ($app.MainWindowHandle -ne [IntPtr]::Zero) { $found = $true; break }
        }
        if (!$found) { throw ("APP_WINDOW_NOT_FOUND_$i") }
        Write-Host ("APP_WINDOW_FOUND_$i handle=" + $app.MainWindowHandle +
            ' title=' + $app.MainWindowTitle)
        # The first native window can become visible before the React/Tauri
        # close-request event listener has finished registering. Exercise a
        # settled window, not a partial startup race.
        Start-Sleep -Seconds 3
        if (!$app.CloseMainWindow()) { throw ("APP_WINDOW_CLOSE_REJECTED_$i") }
        Write-Host ("APP_CLOSE_REQUEST_SENT_$i")
        if (!$app.WaitForExit(30000)) {
            $app.Refresh()
            $child = @(Get-CimInstance Win32_Process -Filter ('ParentProcessId = ' + $app.Id) |
                ForEach-Object { $_.Name + ':' + $_.ProcessId })
            Write-Host ("APP_CLOSE_TIMEOUT_DIAGNOSTIC_$i alive=" + (-not $app.HasExited) +
                ' handle=' + $app.MainWindowHandle +
                ' title=' + $app.MainWindowTitle + ' children=' + ($child -join ','))
            # Never force a PASS; the finally clause terminates the test process.
            throw ("APP_CLOSE_TIMEOUT_$i")
        }
        Write-Host ("INSTALLED_APP_LAUNCH_CLOSE_PASS_$i")
    }
    Start-Sleep -Seconds 2
    $orphans = @(Get-CimInstance Win32_Process |
        Where-Object { $_.Name -like 'engine-bridge*.exe' -and $_.ExecutablePath -and
            ($_.ExecutablePath.StartsWith($installedDir,[StringComparison]::OrdinalIgnoreCase) -or
            $_.ExecutablePath.StartsWith($unicodeDir,[StringComparison]::OrdinalIgnoreCase)) })
    if ($orphans.Count -ne 0) { throw 'ORPHAN_INSTALLED_SIDECAR' }
    Write-Host 'NO_INSTALLED_SIDECAR_ORPHANS_PASS'
    $uninstaller = Join-Path $installedDir 'uninstall.exe'
    if (!(Test-Path -LiteralPath $uninstaller -PathType Leaf)) { throw 'NSIS_UNINSTALLER_MISSING' }
    Run-Bounded -File $uninstaller -ArgumentTokens @('/S') -TimeoutMs 120000
    if (Test-Path -LiteralPath $appExe -PathType Leaf) { throw 'NSIS_UNINSTALL_LEFT_EXE' }
    $installed = $false
    Write-Host 'NSIS_INSTALL_UNINSTALL_PASS'
    # Separate test: exercise NSIS /D itself, NOT merely a relocated copy.
    # This installer invocation is permitted only inside the fresh RUNNER_TEMP GUID.
    $unicodeInstall = Join-Path $root 'NSIS Установка CAD с пробелами'
    if (Test-Path -LiteralPath $unicodeInstall) { throw 'UNICODE_NSIS_TARGET_PREEXISTS' }
    Write-Host ('NSIS_UNICODE_CUSTOM_TARGET: ' + $unicodeInstall)
    # /D=<path> is the final command-line token, as NSIS requires.
    Run-Bounded -File $setup -ArgumentTokens @('/S',('/D=' + $unicodeInstall)) -TimeoutMs 90000
    $unicodeExe = Join-Path $unicodeInstall 'gost-cad-desktop.exe'
    if (!(Test-Path -LiteralPath $unicodeExe -PathType Leaf)) {
        if (Test-Path -LiteralPath (Join-Path $initialInstallDir 'gost-cad-desktop.exe')) {
            $installedDir = $initialInstallDir
            $uninstaller = Join-Path $installedDir 'uninstall.exe'
            $installed = $true
        }
        throw 'NSIS_D_UNICODE_INSTALL_EXE_MISSING'
    }
    $installedDir = $unicodeInstall
    $uninstaller = Join-Path $unicodeInstall 'uninstall.exe'
    $installed = $true
    $installedSidecars = @(Get-ChildItem -LiteralPath $unicodeInstall -Recurse -File -Filter 'engine-bridge*.exe')
    if ($installedSidecars.Count -ne 1) { throw 'NSIS_D_UNICODE_SIDECAR_MISSING' }
    $unicodeSidecarPath = $installedSidecars[0].FullName
    $responseText = @($line | & $unicodeSidecarPath)
    if ($LASTEXITCODE -ne 0 -or $responseText.Count -ne 1) {
        throw 'NSIS_D_UNICODE_IPC_HELLO_FAILED'
    }
    $response = $responseText[0] | ConvertFrom-Json
    if ($response.ok -ne $true -or $response.id -ne 'installed_hello') {
        throw 'NSIS_D_UNICODE_IPC_INVALID'
    }
    Write-Host 'NSIS_D_UNICODE_AND_SPACES_HELLO_PASS'
    if (!(Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
        throw 'NSIS_D_UNICODE_UNINSTALLER_MISSING'
    }
    Run-Bounded -File $uninstaller -ArgumentTokens @('/S') -TimeoutMs 120000
    if (Test-Path -LiteralPath $unicodeExe -PathType Leaf) {
        throw 'NSIS_D_UNICODE_UNINSTALL_LEFT_EXE'
    }
    $installed = $false
    Write-Host 'NSIS_D_UNICODE_INSTALL_UNINSTALL_PASS'
} finally {
    foreach ($app in $launched) {
        try {
            $app.Refresh()
            if (!$app.HasExited) { $app.Kill() }
            $app.Dispose()
        } catch { Write-Warning ('cleanup: ' + $_.Exception.Message) }
    }
    if ($installed -and $uninstaller -and (Test-Path -LiteralPath $uninstaller)) {
        try { Run-Bounded -File $uninstaller -ArgumentTokens @('/S') -TimeoutMs 30000 }
        catch { Write-Warning ('cleanup uninstall: ' + $_.Exception.Message) }
    }
    if ((Test-Path -LiteralPath $root) -and
        $root.StartsWith($env:RUNNER_TEMP,[StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
