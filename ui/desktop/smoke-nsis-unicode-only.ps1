# R6 independent NSIS /D-only Windows negative test.
# It does NOT substitute for GUI close/reopen acceptance.
param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if (!$env:RUNNER_TEMP -or !(Test-Path -LiteralPath $env:RUNNER_TEMP)) {
    throw 'CI_RUNNER_TEMP_REQUIRED'
}
$setup=(Resolve-Path -LiteralPath $Installer).Path
$root=Join-Path $env:RUNNER_TEMP ('gscad-r6-unicode-'+[guid]::NewGuid().ToString('N'))
$destination=Join-Path $root 'Тестовая установка CAD с пробелами'
$defaultDir=Join-Path $env:LOCALAPPDATA 'GOST Schematic CAD - Desktop IPC Preview'
$defaultExisted=Test-Path -LiteralPath $defaultDir
$installed=$false
$uninstaller=$null
function Run-Checked([string]$Program,[string[]]$Tokens,[int]$DeadlineMs){
    $p=Start-Process -FilePath $Program -ArgumentList $Tokens -PassThru
    try {
        if (!$p.WaitForExit($DeadlineMs)) {
            Write-Host ('NSIS_TIMEOUT_CHILDREN='+
                ((@(Get-CimInstance Win32_Process -Filter ('ParentProcessId = '+$p.Id)) |
                    ForEach-Object { $_.Name+':'+$_.ProcessId }) -join ','))
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            throw ('PROCESS_TIMEOUT: '+[IO.Path]::GetFileName($Program))
        }
        if($p.ExitCode -ne 0){throw ('PROCESS_EXIT_'+$p.ExitCode)}
    } finally {$p.Dispose()}
}
try {
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    if($defaultExisted){throw 'DEFAULT_INSTALL_PREEXISTS_ABORT'}
    if(Test-Path -LiteralPath $destination){throw 'UNICODE_DESTINATION_PREEXISTS'}
    Write-Host ('NSIS_D_UNICODE_DESTINATION='+$destination)
    Run-Checked $setup @('/S',('/D='+$destination)) 120000
    $app=Join-Path $destination 'gost-cad-desktop.exe'
    if(!(Test-Path -LiteralPath $app -PathType Leaf)){
        if(Test-Path -LiteralPath $defaultDir){
            $installed=$true
            $uninstaller=Join-Path $defaultDir 'uninstall.exe'
        }
        throw 'NSIS_D_UNICODE_APP_NOT_INSTALLED_AT_TARGET'
    }
    $installed=$true
    $uninstaller=Join-Path $destination 'uninstall.exe'
    $sidecars=@(Get-ChildItem -LiteralPath $destination -File -Recurse -Filter 'engine-bridge*.exe')
    if($sidecars.Count -ne 1){throw 'NSIS_D_UNICODE_SIDECAR_MISSING'}
    $inputLine='{"v":1,"id":"unicode_d","op":"hello","args":{}}'
    $sidecarExe=$sidecars[0].FullName
    $output=@($inputLine | & $sidecarExe)
    if($LASTEXITCODE -ne 0 -or $output.Count -ne 1){throw 'NSIS_D_UNICODE_IPC_FAILED'}
    $response=$output[0] | ConvertFrom-Json
    if($response.ok -ne $true -or $response.id -ne 'unicode_d'){throw 'NSIS_D_UNICODE_PROTOCOL_INVALID'}
    Write-Host 'NSIS_D_UNICODE_INSTALL_AND_IPC_PASS'
    if(!(Test-Path -LiteralPath $uninstaller -PathType Leaf)){throw 'NSIS_D_UNICODE_UNINSTALLER_MISSING'}
    Run-Checked $uninstaller @('/S') 120000
    # The NSIS parent can exit before its self-deleting child finishes removal.
    # Verify durable absence with a bounded poll; never treat lingering EXE as PASS.
    $elapsed=0
    while((Test-Path -LiteralPath $app -PathType Leaf) -and $elapsed -lt 30000){
        Start-Sleep -Milliseconds 500
        $elapsed+=500
    }
    Write-Host ('NSIS_D_UNICODE_REMOVAL_WAIT_MS='+$elapsed)
    if(Test-Path -LiteralPath $app -PathType Leaf){
        $remaining=Get-ChildItem -LiteralPath $destination -File -Recurse -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty FullName
        Write-Host ('NSIS_D_UNICODE_REMAINING_FILES=' + ($remaining -join ','))
        throw 'NSIS_D_UNICODE_UNINSTALL_LEFT_APP'
    }
    $installed=$false
    Write-Host 'NSIS_D_UNICODE_INSTALL_UNINSTALL_PASS'
} finally {
    if($installed -and $uninstaller -and (Test-Path -LiteralPath $uninstaller)){
        try {Run-Checked $uninstaller @('/S') 30000}
        catch {Write-Warning ('UNICODE_CLEANUP_UNINSTALL_FAILED: '+$_.Exception.Message)}
    }
    if(Test-Path -LiteralPath $root){
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
