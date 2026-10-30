$ErrorActionPreference = 'Stop'
$taskWorkspace = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskPython = 'C:/Users/funny/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$taskDeps = Join-Path $taskWorkspace 'work/statcraft-build-deps'
$taskGate = Get-Content -LiteralPath (Join-Path $taskWorkspace 'work/deliverable-gate.json') -Raw | ConvertFrom-Json
if (-not $taskGate.preview_authorized) { throw 'An incomplete preview executable has not been authorized.' }
$env:PYTHONPATH = $taskDeps + ';' + $PSScriptRoot
Push-Location $taskWorkspace
try {
    & $taskPython work/statcraft/verify_tests.py
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build cancelled.' }
    & $taskPython -m PyInstaller --onefile --windowed --name StatCraft --distpath work/statcraft-release-next --workpath work/statcraft-freeze --specpath work/statcraft --paths $PSScriptRoot --icon (Join-Path $PSScriptRoot 'StatCraft.ico') --add-data ($PSScriptRoot + '/notices;notices') --add-data ($PSScriptRoot + '/StatCraft.ico;.') --exclude-module pandas --exclude-module matplotlib --exclude-module IPython --exclude-module pytest work/statcraft/launch_statcraft.py
    if ($LASTEXITCODE -ne 0) { throw 'Executable packaging failed.' }
    $taskExe = Join-Path $taskWorkspace 'work/statcraft-release-next/StatCraft.exe'
    $taskSmoke = Join-Path $taskWorkspace 'work/packaged-smoke-v2.json'
    $taskProcess = Start-Process -FilePath $taskExe -ArgumentList @('--self-test', $taskSmoke) -WindowStyle Hidden -PassThru -Wait
    if ($taskProcess.ExitCode -ne 0) { throw 'Packaged smoke test failed.' }
    $taskResult = Get-Content -LiteralPath $taskSmoke -Raw | ConvertFrom-Json
    if (-not $taskResult.frozen -or $taskResult.tk_widgets -ne 'passed' -or $taskResult.project_roundtrip -ne 'passed') { throw 'Packaged verification was incomplete.' }
    Copy-Item -LiteralPath $taskExe -Destination (Join-Path $taskWorkspace 'outputs/StatCraft.exe')
    Write-Output 'Verified preview executable copied to outputs/StatCraft.exe'
} finally { Pop-Location }
