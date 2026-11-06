@echo off
rem =========================================================================
rem StatCraft Live Testing Sandbox Launcher
rem Instantly launches the StatCraft Live Sandbox Hub with zero build lag.
rem =========================================================================
setlocal

if exist "%~dp0launch_modern.py" (
    set "REPO_ROOT=%~dp0"
    set "BUILD_DEPS=%~dp0..\statcraft-build-deps"
) else (
    set "REPO_ROOT=%~dp0work\statcraft"
    set "BUILD_DEPS=%~dp0work\statcraft-build-deps"
)

set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PYTHON_EXE%" (
    for %%P in (python.exe) do set "PYTHON_EXE=%%~$PATH:P"
)
if not exist "%PYTHON_EXE%" (
    where py >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%I"
    )
)

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found. Please install Python or set PATH.
    pause
    exit /b 1
)

if exist "%BUILD_DEPS%" (
    set "PYTHONPATH=%BUILD_DEPS%;%REPO_ROOT%;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%REPO_ROOT%;%PYTHONPATH%"
)

cd /d "%REPO_ROOT%"
start "" "%PYTHON_EXE%" -m statcraft.sandbox_hub
