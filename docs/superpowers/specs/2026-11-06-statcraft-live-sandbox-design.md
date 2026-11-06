# Design Document: StatCraft Major Release (v111.0.0) & Live Testing Sandbox

## 1. Intent & Purpose
Enable the user to test rapid mini-iterations of StatCraft directly from live source edits without having to wait for binary compilation, search through the crowded `outputs/` folder, or download releases from GitHub. Provide a simple, clearly marked Sandbox UI and bump the project to its next major release: `v111.0.0`.

---

## 2. Goals & Non-Goals

### Goals
- **Bump Major Version**: Upgrade from `110.0.0` to `111.0.0` across all metadata, updater, documentation, and version headers.
- **Instant Live Execution**: Launch the app directly against working directory source files (`work/statcraft`) using the configured Python runtime (`codex-primary-runtime`). Edits take effect on the next launch with zero build or wait time.
- **Dedicated Sandbox Control Panel**: Provide a simple, sleek 1-click desktop launcher GUI (`StatCraft Sandbox Hub`) that displays git commit status, active version, and a 1-click "🚀 Launch Live Sandbox" button.
- **Prominent In-App Marking**: Running in `--sandbox` mode adds an unmistakable top ribbon (`🧪 LIVE SANDBOX · v111.0.0-dev · Live Source Sync`) and window title badge, preventing confusion with production releases.
- **Isolated Scratch Profile**: The sandbox uses an isolated user data / project cache (`.sandbox_cache/`) so testing never corrupts actual project files.

### Non-Goals
- Replacing PyInstaller production builds (production compilation remains available via `build_local_installer.ps1`).
- Building a complex web server or external cloud testing harness (everything is fast, local, and private).

---

## 3. Approaches Considered

1. **Dedicated Desktop Sandbox Launcher (Chosen)**:
   - A lightweight control panel UI (`launch_sandbox_ui.py`) and Windows `.bat` launcher (`StatCraft-Sandbox.bat`).
   - Displays git commit status, provides a 1-click launch button into live source mode, and launches StatCraft with a prominent yellow/amber "🧪 LIVE SANDBOX" banner.
   - *Trade-off*: Requires a tiny helper UI script, but delivers the cleanest, most accessible user experience without file confusion.

2. **Terminal Batch Script Only**:
   - A command-line `.bat` script that simply invokes Python.
   - *Trade-off*: Lacks visual polish, version status, and clear feedback buttons.

3. **In-App Menu Toggle**:
   - Starting the compiled app and toggling into sandbox mode.
   - *Trade-off*: Fails the requirement of not needing to recompile or download new executables to test source edits.

---

## 4. Detailed Specification

### A. Version Bump (`v111.0.0`)
- `statcraft/__init__.py`: `__version__ = "111.0.0"`
- `statcraft/updater.py`: `STATCRAFT_VERSION = "111.0.0"`
- `app_version.txt`: `111.0.0.0`
- `README.md` & `docs/index.html`: Updated release badges and download links for `v111.0.0`.

### B. Sandbox App Flag (`--sandbox`)
- In `statcraft/modern_app.py`:
  - When `--sandbox` is passed via CLI, the main window window title is prefixed with `[🧪 LIVE SANDBOX · v111.0.0-dev]`.
  - An unmistakable high-contrast banner is docked at the very top of the window:
    `🧪 LIVE SANDBOX MODE — Running directly from local source files. Edits apply immediately upon app restart.`
  - Isolates temporary recovery files to a `.sandbox_workspace/` directory.

### C. StatCraft Sandbox Hub (`launch_sandbox_ui.py` & `StatCraft-Sandbox.bat`)
- Located at workspace root `c:\Users\funny\Documents\Codex\2026-10-12\us\StatCraft-Sandbox.bat` for instant access.
- Lightweight Qt control panel:
  - **Status Box**: Current git branch, latest commit hash and commit message, Python runtime path, and `v111.0.0-dev` badge.
  - **Primary Action**: `🚀 Launch Live Sandbox` (spawns `python launch_modern.py --sandbox` cleanly in the background).
  - **Quick Action**: `📋 Copy System & Git Diagnostics` (for easy pasting of feedback).
  - **Quick Action**: `📂 Open Source Folder` & `🧪 Open Sandbox Scratch Directory`.

---

## 5. Verification Plan
- Unit tests in `tests/test_sandbox_mode.py` verifying `--sandbox` flag handling, title prefixing, and banner initialization.
- Regression check running the test suite to ensure zero regressions.
- Live launch test of `StatCraft-Sandbox.bat` verifying the control panel opens, reports git state, and launches the live application.
