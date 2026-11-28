# Test-only loader experiment. Never modify production executables or skip a test.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or !$env:RUNNER_TEMP) { throw 'R53_CI_ONLY' }
$project = (Resolve-Path 'ui/desktop/src-tauri').Path
$out = Join-Path $env:RUNNER_TEMP 'gscad-r53-loader-diagnostics'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$lines = @(cargo test --manifest-path (Join-Path $project 'Cargo.toml') --no-run --message-format=json)
if ($LASTEXITCODE -ne 0) { throw 'R53_TEST_COMPILE_FAILED' }
$tests = @($lines | ForEach-Object { try { $_ | ConvertFrom-Json } catch {} } |
    Where-Object { $_.reason -eq 'compiler-artifact' -and $_.profile.test -eq $true -and $_.target.name -eq 'gost_cad_desktop_lib' -and $_.executable })
if ($tests.Count -ne 1) { throw ('R53_TEST_EXECUTABLE_COUNT_' + $tests.Count) }
$exe = (Resolve-Path -LiteralPath $tests[0].executable).Path
$debug = (Resolve-Path (Join-Path $project 'target/debug')).Path + [IO.Path]::DirectorySeparatorChar
if (!$exe.StartsWith($debug,[StringComparison]::OrdinalIgnoreCase) -or
    [IO.Path]::GetFileName($exe) -notmatch '^gost_cad_desktop_lib-[a-f0-9]+\.exe$') { throw 'R53_UNEXPECTED_TEST_EXECUTABLE' }
# Only enumerate tests; no installation, signature tests, or other test code runs here.
& $exe --list | Set-Content (Join-Path $out 'before-list.txt')
$before = $LASTEXITCODE
Write-Host ('R53_BEFORE_MANIFEST_TEST_LIST_EXIT=' + $before)
if ($before -eq 0) { return }
if ($before -ne -1073741511 -and $before -ne 3221225785) { throw ('R53_UNEXPECTED_LOADER_EXIT_' + $before) }

$kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin'
$mt = Get-ChildItem -LiteralPath $kits -Filter mt.exe -File -Recurse |
    Where-Object { $_.Directory.Name -eq 'x64' } |
    Sort-Object FullName -Descending | Select-Object -First 1
if (!$mt) { throw 'R53_MT_NOT_FOUND' }
$existing = Join-Path $out 'original-test.manifest'
$resource = '-inputresource:' + $exe + ';#1'
& $mt.FullName -nologo $resource ('-out:' + $existing)
$extract = $LASTEXITCODE
Write-Host ('R53_MANIFEST_EXTRACT_EXIT=' + $extract)
$hasExisting = $extract -eq 0 -and (Test-Path -LiteralPath $existing)
if ($hasExisting -and (Get-Content -LiteralPath $existing -Raw) -match 'Microsoft.Windows.Common-Controls') {
    throw 'R53_COMMON_CONTROLS_ALREADY_PRESENT_DIAGNOSE_OTHER_IMPORT'
}
$dependency = Join-Path $out 'common-controls-v6.manifest'
@'
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <dependency>
    <dependentAssembly>
      <assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls" version="6.0.0.0" processorArchitecture="*" publicKeyToken="6595b64144ccf1df" language="*" />
    </dependentAssembly>
  </dependency>
</assembly>
'@ | Set-Content -LiteralPath $dependency -Encoding utf8
$beforeHash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
$args = @('-nologo','-manifest')
if ($hasExisting) { $args += $existing }
$args += $dependency
$args += ('-outputresource:' + $exe + ';#1')
& $mt.FullName @args
if ($LASTEXITCODE -ne 0) { throw 'R53_TEST_MANIFEST_EMBED_FAILED' }
$afterHash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
if ($beforeHash -eq $afterHash) { throw 'R53_TEST_MANIFEST_NOT_CHANGED' }
& $mt.FullName -nologo $resource ('-out:' + (Join-Path $out 'updated-test.manifest'))
if ($LASTEXITCODE -ne 0) { throw 'R53_TEST_MANIFEST_VERIFY_FAILED' }
& $exe --list | Tee-Object -FilePath (Join-Path $out 'after-list.txt')
if ($LASTEXITCODE -ne 0) { throw ('R53_TEST_LOADER_STILL_FAILS_' + $LASTEXITCODE) }
Write-Host 'R53_COMMON_CONTROLS_MANIFEST_LOADER_EXPERIMENT_PASS'
# The workflow still executes full cargo test and the explicitly required real
# signature test with their original assertions; this experiment alone is not PASS.
