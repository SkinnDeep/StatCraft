<#
.SYNOPSIS
    StatCraft 1-Click Automated Release Publisher.
.DESCRIPTION
    Builds the production executables with PyInstaller, signs them with Authenticode,
    and automatically uploads them to GitHub Releases without opening a web browser.
.EXAMPLE
    .\publish_release.ps1
    .\publish_release.ps1 -SkipBuild
    .\publish_release.ps1 -Version "106.0.0"
#>
[CmdletBinding()]
param (
    [string]$Version,
    [switch]$SkipBuild,
    [string]$Notes,
    [string]$Repo = "SkinnDeep/StatCraft"
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

$scriptPath = Join-Path $repoRoot "publish_release.py"
if (-not (Test-Path $scriptPath)) {
    $scriptPath = Join-Path $repoRoot "tools\dev\publish_release.py"
}
$argsList = @($scriptPath)
if ($Version) { $argsList += "--version", $Version }
if ($SkipBuild) { $argsList += "--skip-build" }
if ($Notes) { $argsList += "--notes", $Notes }
if ($Repo) { $argsList += "--repo", $Repo }

& $pythonExe $argsList
