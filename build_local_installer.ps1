<#
.SYNOPSIS
    Builds the standalone StatCraft-Setup.exe installer locally for testing.
.DESCRIPTION
    Compiles installer_main.py using PyInstaller into outputs/StatCraft-Setup.exe.
    Does NOT publish to GitHub releases, allowing safe local testing of the compiled binary.
.PARAMETER Launch
    Automatically launch the compiled installer executable after building.
.PARAMETER Full
    Also compile the main StatCraft.exe binary into outputs/ so the installer can test local offline installation.
.EXAMPLE
    .\build_local_installer.ps1 -Launch
    .\build_local_installer.ps1 -Full -Launch
#>
[CmdletBinding()]
param (
    [switch]$Launch,
    [switch]$Full,
    [string]$OutputDir
)

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot

# Locate Python
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe -or $pythonExe -like "*WindowsApps*") {
    $runtimePython = "C:/Users/funny/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
    if (Test-Path $runtimePython) {
        $pythonExe = $runtimePython
    } else {
        $envPython = Join-Path $repoRoot "..\statcraft-build-env\Scripts\python.exe"
        if (Test-Path $envPython) {
            $pythonExe = $envPython
        }
    }
}

if (-not $pythonExe) {
    Write-Error "Python executable not found. Please ensure Python is in your PATH."
    exit 1
}

$deps = Join-Path $repoRoot "..\statcraft-build-deps"
if (Test-Path $deps) {
    $env:PYTHONPATH = "$deps;$repoRoot"
} else {
    $env:PYTHONPATH = "$repoRoot"
}

$targetOutputs = if ($OutputDir) { $OutputDir } else {
    $candidates = @(
        (Join-Path $repoRoot "outputs"),
        (Join-Path (Split-Path $repoRoot) "outputs"),
        (Join-Path (Split-Path (Split-Path $repoRoot)) "outputs")
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($found) { $found } else { Join-Path $repoRoot "outputs" }
}

if (-not (Test-Path $targetOutputs)) {
    New-Item -ItemType Directory -Path $targetOutputs -Force | Out-Null
}

$distSetup = Join-Path $repoRoot "dist\setup"
$workSetup = Join-Path $repoRoot "build\setup"

if ($Full) {
    Write-Host "`n=== Compiling StatCraft Main Application ===" -ForegroundColor Cyan
    $distApp = Join-Path $repoRoot "dist\app"
    $workApp = Join-Path $repoRoot "build\app"
    & $pythonExe -m PyInstaller --noconfirm --distpath $distApp --workpath $workApp (Join-Path $repoRoot "StatCraft.spec")
    
    $appExe = Join-Path $distApp "StatCraft.exe"
    if (Test-Path $appExe) {
        Copy-Item -Path $appExe -Destination (Join-Path $targetOutputs "StatCraft.exe") -Force
        Write-Host "  [OK] Main app compiled to: $(Join-Path $targetOutputs 'StatCraft.exe')" -ForegroundColor Green
    }
}

Write-Host "`n=== Compiling StatCraft Windows Setup Installer ===" -ForegroundColor Cyan
& $pythonExe -m PyInstaller --noconfirm --distpath $distSetup --workpath $workSetup (Join-Path $repoRoot "installer.spec")

$setupExe = Join-Path $distSetup "StatCraft-Setup.exe"
if (-not (Test-Path $setupExe)) {
    Write-Error "PyInstaller build failed: $setupExe not created."
    exit 1
}

$finalSetup = Join-Path $targetOutputs "StatCraft-Setup.exe"
Copy-Item -Path $setupExe -Destination $finalSetup -Force
Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "  SUCCESS! Test installer built at:" -ForegroundColor Green
Write-Host "  $finalSetup" -ForegroundColor Yellow
Write-Host "========================================================`n" -ForegroundColor Green

if ($Launch) {
    Write-Host "--> Launching $finalSetup for immediate testing..." -ForegroundColor Cyan
    Start-Process -FilePath $finalSetup
}
