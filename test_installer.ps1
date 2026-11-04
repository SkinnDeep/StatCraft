<#
.SYNOPSIS
    Instantly launch and test the StatCraft Setup & Uninstaller Wizard.
.DESCRIPTION
    Runs installer_main.py directly with PySide6 and full dependency pathing,
    allowing instantaneous (0-second wait) testing of the installer UI,
    license acceptance, disk space calculation, tasks, shortcuts, and navigation.
.EXAMPLE
    .\test_installer.ps1
    .\test_installer.ps1 -Uninstall
    .\test_installer.ps1 -Silent -Dir "C:\Temp\TestInstall"
#>
[CmdletBinding()]
param (
    [switch]$Uninstall,
    [switch]$Silent,
    [string]$Dir,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

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
    Write-Error "Python executable not found."
    exit 1
}

$deps = Join-Path $repoRoot "..\statcraft-build-deps"
if (Test-Path $deps) {
    $env:PYTHONPATH = "$deps;$repoRoot"
} else {
    $env:PYTHONPATH = "$repoRoot"
}

$installerScript = Join-Path $repoRoot "installer_main.py"
$cmdArgs = @($installerScript)

if ($Uninstall) { $cmdArgs += "--uninstall" }
if ($Silent) { $cmdArgs += "--silent" }
if ($Dir) { $cmdArgs += "--dir", $Dir }
if ($ExtraArgs) { $cmdArgs += $ExtraArgs }

Write-Host "--> Launching StatCraft Setup Wizard in test mode..." -ForegroundColor Cyan
& $pythonExe $cmdArgs
