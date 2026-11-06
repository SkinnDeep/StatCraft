# StatCraft Major Release (v111.0.0) & Live Sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release StatCraft v111.0.0 and provide an instant, 1-click desktop Sandbox Hub with live source sync and visual in-app sandbox marking so changes can be tested without builds or downloads.

**Architecture:** A lightweight desktop control panel (`StatCraftSandboxHub` / `StatCraft-Sandbox.bat`) launches the live Python codebase directly using the project's runtime with `--sandbox`. StatCraft renders a high-contrast sandbox banner and title badge, using an isolated scratch directory so edits are tested in real time with zero compilation overhead.

**Tech Stack:** Python 3.12, PySide6 (Qt6), Git CLI, Windows Batch.

**Spec:** [docs/superpowers/specs/2026-11-06-statcraft-live-sandbox-design.md](file:///c:/Users/funny/Documents/Codex/2026-10-12/us/work/statcraft/docs/superpowers/specs/2026-11-06-statcraft-live-sandbox-design.md)

## Global Constraints
- Target version: `111.0.0`
- Zero external build dependencies required for live sandbox execution.
- Production `.mpx` and project files must not be corrupted (isolated sandbox profile).
- Clean fallback if git is unavailable or repo is detached.

## Review Focus
- Running sandbox when no active git repo is found: graceful fallback to `v111.0.0-dev (local source)`.
- Re-launching sandbox while another instance is open: handles processes safely without locking files.
- High-DPI and dark mode rendering of sandbox banner in `ModernWindow`.
- Batch script path handling with spaces in directory names.

---

### Task 1: Major Version Bump to v111.0.0

**Files:**
- Modify: `statcraft/__init__.py:1`
- Modify: `statcraft/updater.py:27`
- Modify: `app_version.txt:20-25`
- Modify: `README.md:1-10`
- Modify: `docs/index.html:20-60`
- Test: `tests/test_version_bump.py`

**Interfaces:**
- Produces: `statcraft.__version__ == "111.0.0"` and `statcraft.updater.STATCRAFT_VERSION == "111.0.0"`

- [ ] **Step 1: Write failing test in `tests/test_version_bump.py`**
```python
import unittest
import statcraft
from statcraft import updater

class TestVersionBump(unittest.TestCase):
    def test_version_111(self):
        self.assertEqual(statcraft.__version__, "111.0.0")
        self.assertEqual(updater.STATCRAFT_VERSION, "111.0.0")
```

- [ ] **Step 2: Run test to verify failure**
Run: `python -m unittest tests/test_version_bump.py`
Expected: FAIL (`110.0.0 != 111.0.0`)

- [ ] **Step 3: Update version strings to 111.0.0**
Update `statcraft/__init__.py`, `statcraft/updater.py`, `app_version.txt`, `README.md`, and `docs/index.html`.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_version_bump.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add statcraft/__init__.py statcraft/updater.py app_version.txt README.md docs/index.html tests/test_version_bump.py
git commit -m "chore(release): bump major version to v111.0.0"
```

---

### Task 2: In-App Sandbox Mode Support (`--sandbox`)

**Files:**
- Modify: `launch_modern.py`
- Modify: `statcraft/modern_app.py`
- Test: `tests/test_sandbox_mode.py`

**Interfaces:**
- Consumes: `--sandbox` flag in `sys.argv`
- Produces: `ModernWindow.sandbox_mode: bool`, window title prefix `[🧪 LIVE SANDBOX · v111.0.0-dev]`, and `ModernWindow.sandbox_banner` widget

- [ ] **Step 1: Write failing test in `tests/test_sandbox_mode.py`**
```python
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.modern_app import ModernWindow
from statcraft.model import Project

class TestSandboxMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_sandbox_ui_elements(self):
        win = ModernWindow(Project(), sandbox_mode=True)
        self.assertTrue(win.sandbox_mode)
        self.assertIn("LIVE SANDBOX", win.windowTitle())
        self.assertIsNotNone(getattr(win, "sandbox_banner", None))
        self.assertTrue(win.sandbox_banner.isVisible())
        win.closeEvent = lambda e: e.accept()
        win.close()
```

- [ ] **Step 2: Run test to verify failure**
Run: `python -m unittest tests/test_sandbox_mode.py`
Expected: FAIL (`unexpected keyword argument 'sandbox_mode'`)

- [ ] **Step 3: Implement `--sandbox` support in `launch_modern.py` and `ModernWindow`**
- In `launch_modern.py`, parse `--sandbox` from `sys.argv` and pass `sandbox_mode=True` to `ModernWindow`.
- In `statcraft/modern_app.py`:
  - Accept `sandbox_mode: bool = False` in `ModernWindow.__init__`.
  - When `True`, prefix window title with `[🧪 LIVE SANDBOX · v111.0.0-dev] `.
  - Create and prepend a stylized amber banner `self.sandbox_banner` above the toolbar:
    `🧪 LIVE SANDBOX · v111.0.0-dev · Live Local Source · Changes apply instantly on restart`
  - Include a quick `📋 Copy Diagnostics` button and an `ℹ️ Help` button on the banner.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_sandbox_mode.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add launch_modern.py statcraft/modern_app.py tests/test_sandbox_mode.py
git commit -m "feat(sandbox): add --sandbox mode with prominent live UI ribbon and title badge"
```

---

### Task 3: StatCraft Sandbox Hub Launcher UI & Desktop Script

**Files:**
- Create: `statcraft/sandbox_hub.py`
- Create: `c:\Users\funny\Documents\Codex\2026-10-12\us\StatCraft-Sandbox.bat`
- Test: `tests/test_sandbox_hub.py`

**Interfaces:**
- Produces: `StatCraftSandboxHub` dialog window and standalone `.bat` launcher

- [ ] **Step 1: Write failing test in `tests/test_sandbox_hub.py`**
```python
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.sandbox_hub import StatCraftSandboxHub, get_git_status_info

class TestSandboxHub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_git_info_retrieval(self):
        info = get_git_status_info()
        self.assertIn("branch", info)
        self.assertIn("commit", info)

    def test_sandbox_hub_widget(self):
        hub = StatCraftSandboxHub()
        self.assertIsNotNone(hub.btn_launch)
        self.assertIn("Launch Live Sandbox", hub.btn_launch.text())
        hub.close()
```

- [ ] **Step 2: Run test to verify failure**
Run: `python -m unittest tests/test_sandbox_hub.py`
Expected: FAIL (`ModuleNotFoundError: No module named 'statcraft.sandbox_hub'`)

- [ ] **Step 3: Implement `statcraft/sandbox_hub.py` and `StatCraft-Sandbox.bat`**
- `statcraft/sandbox_hub.py`:
  - `get_git_status_info()`: queries git branch, SHA (7 chars), and message via `subprocess`.
  - `StatCraftSandboxHub(QDialog)`:
    - Sleek modern window: `🧪 StatCraft Live Testing Sandbox`
    - Displays: Current Version (`v111.0.0-dev`), Git Branch, Git Commit, Python Runtime.
    - Prominent `🚀 Launch Live Sandbox` button (spawns `python launch_modern.py --sandbox` as detached process so Hub can stay open or close).
    - `📋 Copy Diagnostics & Status` button (copies version, git hash, python env to clipboard).
    - `📂 Open Source Code Directory` & `🧪 Open Sandbox Scratch Folder`.
- `StatCraft-Sandbox.bat`:
  - Simple 1-click batch file located at repo/workspace root.
  - Automatically sets `PYTHONPATH` with `statcraft-build-deps` and runs `python -m statcraft.sandbox_hub`.

- [ ] **Step 4: Run test to verify it passes**
Run: `python -m unittest tests/test_sandbox_hub.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add statcraft/sandbox_hub.py tests/test_sandbox_hub.py StatCraft-Sandbox.bat
git commit -m "feat(sandbox): create StatCraft Sandbox Hub GUI launcher and 1-click batch script"
```

---

### Task 4: Regression Pass, Code Review Subagent, and Verification

**Files:**
- Whole repository

- [ ] **Step 1: Run complete test suite**
Run: `python -m unittest discover tests -p "test_*.py"`
Expected: All tests PASS

- [ ] **Step 2: Dispatch Code Reviewer subagent**
Verify changes against spec and ensure zero breaking changes.

- [ ] **Step 3: Address any subagent findings**

- [ ] **Step 4: Commit and push to origin/main**
```bash
git push origin main
```
