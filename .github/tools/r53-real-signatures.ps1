# Test-only official Tauri signer fixtures. Never use release credentials.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:GITHUB_ACTIONS -ne 'true' -or !$env:RUNNER_TEMP) { throw 'R53_CI_ONLY' }
foreach ($name in @('TAURI_SIGNING_PRIVATE_KEY','TAURI_SIGNING_PRIVATE_KEY_PATH','TAURI_SIGNING_PRIVATE_KEY_PASSWORD','TAURI_PRIVATE_KEY','TAURI_PRIVATE_KEY_PATH','TAURI_PRIVATE_KEY_PASSWORD')) {
    if ([Environment]::GetEnvironmentVariable($name)) { throw 'R53_RELEASE_SIGNING_ENV_FORBIDDEN' }
}
$root = Join-Path $env:RUNNER_TEMP ('gscad-r53-signatures-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $key = Join-Path $root 'trusted.key'
    $other = Join-Path $root 'other.key'
    # --ci generates a fresh empty-password key, writes only to the isolated path.
    npx --yes @tauri-apps/cli@2.12.6 signer generate --ci --write-keys $key
    if ($LASTEXITCODE -ne 0) { throw 'R53_SIGNER_GENERATE_FAILED' }
    npx --yes @tauri-apps/cli@2.12.6 signer generate --ci --write-keys $other
    if ($LASTEXITCODE -ne 0) { throw 'R53_SECOND_SIGNER_GENERATE_FAILED' }
    $bytes = [Text.Encoding]::UTF8.GetBytes("GSCAD R53 non-executable signature fixture`n")
    foreach ($file in @('versioned.bin','old.bin','unversioned.bin')) {
        [IO.File]::WriteAllBytes((Join-Path $root $file), $bytes)
    }
    # The signer defaults to empty password without interactive stdin in CI.
    $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = ''
    npx --yes @tauri-apps/cli@2.12.6 signer sign --private-key-path $key --app-version 0.2.0 (Join-Path $root 'versioned.bin')
    if ($LASTEXITCODE -ne 0) { throw 'R53_SIGN_NEW_FAILED' }
    npx --yes @tauri-apps/cli@2.12.6 signer sign --private-key-path $key --app-version 0.1.0 (Join-Path $root 'old.bin')
    if ($LASTEXITCODE -ne 0) { throw 'R53_SIGN_OLD_FAILED' }
    npx --yes @tauri-apps/cli@2.12.6 signer sign --private-key-path $key (Join-Path $root 'unversioned.bin')
    if ($LASTEXITCODE -ne 0) { throw 'R53_SIGN_UNVERSIONED_FAILED' }
    Remove-Item -LiteralPath $key,$other -Force
    Remove-Item Env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD -ErrorAction SilentlyContinue
    $env:GSCAD_R53_FIXTURES = $root
    cargo test --manifest-path ui/desktop/src-tauri/Cargo.toml r53_real_signed_update_verification -- --ignored --nocapture | Tee-Object -Variable result
    if ($LASTEXITCODE -ne 0) { throw 'R53_NATIVE_SIGNATURE_VERIFICATION_FAILED' }
    $lines = @($result | ForEach-Object { $_.ToString().Trim() })
    if ($lines -notcontains 'R53_OFFICIAL_TAURI_SIGNATURE_VERIFICATION_PASS' -or
        !($lines | Where-Object { $_ -match '^test result: ok\. 1 passed; 0 failed;' })) {
        throw 'R53_REQUIRED_TEST_NOT_EXECUTED'
    }
    Write-Host 'R53_DISPOSABLE_SIGNATURE_FIXTURES_ACCEPTED'
} finally {
    Remove-Item Env:GSCAD_R53_FIXTURES -ErrorAction SilentlyContinue
    Remove-Item Env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $root -Recurse -Force
}
