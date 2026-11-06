# StatCraft Connect & Universal UI Production-Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform StatCraft Connect from an isolated, pre-cooked sample into a seamless, universal tri-engine bridge that automatically translates any Minitab procedure into JMP interactive visual platforms and executable Base R scripts upon mode switching, while eliminating all dialog clipping bugs.

**Architecture:** 
1. `ModernWindow.set_ui_mode` is upgraded to perform active analysis routing: switching to JMP or R automatically resolves the active/selected analysis and renders the appropriate interactive visual platform or Base R script.
2. `statcraft.connect` and `statcraft.connect_r` are expanded to cover all standard Minitab procedures (2-Sample t, 1-Sample t, Paired t, Descriptives, Correlation, Capability) in addition to ANOVA, DOE, RSM, and Regression.
3. Every dialog across the codebase is guaranteed responsive minimums, dynamic size grips, and scroll-protected button layouts.

**Tech Stack:** Python 3.12, PySide6 (Qt 6.8+), Base R (zero external packages), SciPy/NumPy, PyInstaller.

**Spec:** User feedback from conversation history requiring:
1. Automatic translation of user Minitab analyses over to JMP visual platforms and R Workbench.
2. Production-ready UX replacing hard-coded store-model behavior.
3. Elimination of all UI cutoffs, hidden buttons, and unresizable popups.

---

## Global Constraints

- Pure Base R code generation (no tidyverse or external packages required).
- 100% backward compatibility with native formats (`.mpx`, `.mwx`, `.jmp`, `.statcraft`).
- All dialogs must support responsive `setMinimumSize()` and `setSizeGripEnabled(True)`.
- 100% test suite pass rate across all 2,168+ unit and integration tests.

---

## Review Focus

1. **Mode Switch with No Active Result:** Switching to JMP or R on a raw worksheet with no analysis must open the platform launcher or data viewer cleanly without errors.
2. **Missing Value Listwise Handling:** R scripts for t-tests, correlation, and capability must honor complete-case rows matched to StatCraft's row identities.
3. **High-DPI Dialog Display:** Secondary parameter popups on small 1366x768 or scaled displays must never hide OK/Cancel action buttons.
4. **Interactive Profiler Crosshair Sync:** Dragging factor crosshairs in JMP profiler must update candidate operating points in worksheet metadata in real time.
5. **ReportPad Office Export:** Appended connected reports must render cleanly in both dark/light mode and export valid Word (`.docx`) and PowerPoint (`.pptx`) documents.

---

### Task 1: Auto-Translation Engine on Mode Switch (`set_ui_mode`)

**Files:**
- Modify: `statcraft/modern_app.py:1546-1605`
- Test: `tests/test_connect_mode_switch.py`

- [ ] **Step 1: Write the failing test**
  Create `tests/test_connect_mode_switch.py` testing that switching mode to "jmp" when a regression or ANOVA result is selected opens the corresponding platform, and switching to "r" loads the translated Base R script into the workbench.
- [ ] **Step 2: Run test to confirm failure**
  Run test via `unittest` and verify that mode switching does not currently translate results.
- [ ] **Step 3: Implement active analysis translation in `set_ui_mode`**
  In `statcraft/modern_app.py:set_ui_mode`:
  - When switching to `"jmp"`: Call `self.connect_open_explorer(self.selected_entry)` if an entry is selected, or refresh the JMP table panel.
  - When switching to `"r"`: Sync active worksheet via `self.r_workbench.sync_active_worksheet_to_r()`, and if an entry is selected, generate and load its connected R script via `self.r_workbench.load_connected_analysis()`.
- [ ] **Step 4: Run test to confirm it passes**
  Verify `test_connect_mode_switch.py` passes.
- [ ] **Step 5: Commit**
  `git commit -m "Auto-translate active analysis to JMP and R on mode switch"`

---

### Task 2: Universal Connect Coverage for Standard Minitab Analyses

**Files:**
- Modify: `statcraft/connect.py:660-705`
- Modify: `statcraft/connect_r.py`
- Modify: `statcraft/connect_explorer.py`
- Test: `tests/test_connect_universal.py`

- [ ] **Step 1: Write the failing tests**
  Create test in `tests/test_connect_universal.py` verifying connected contract and Base R script generation for Two-Sample t, One-Sample t, Correlation, and Descriptive Statistics.
- [ ] **Step 2: Run test to confirm failure**
  Confirm `create_connected_analysis_from_entry` returns `None` for these actions.
- [ ] **Step 3: Implement connected factories and R generators**
  In `statcraft/connect.py` and `statcraft/connect_r.py`:
  - `create_connected_two_sample_t` and `generate_r_two_sample_t_script`
  - `create_connected_one_sample_t` and `generate_r_one_sample_t_script`
  - `create_connected_correlation` and `generate_r_correlation_script`
  - `create_connected_descriptives` and `generate_r_descriptives_script`
  - Route in `connect_explorer.py` to JMP Distribution / Multivariate platforms.
- [ ] **Step 4: Run test to confirm it passes**
  Run `tests/test_connect_universal.py`.
- [ ] **Step 5: Commit**
  `git commit -m "Add universal Connect and Base R translations for t-tests, correlation, and descriptives"`

---

### Task 3: Universal Dialog Safety & Responsive High-DPI Pass

**Files:**
- Modify: `statcraft/variable_dialogs.py`
- Modify: `statcraft/doe_dialogs.py`
- Modify: `statcraft/capability_dialogs.py`
- Modify: `statcraft/two_sample_t_dialogs.py`
- Modify: `statcraft/paired_t_dialogs.py`
- Modify: `statcraft/equal_variances_dialogs.py`
- Modify: `statcraft/optimizer_dialogs.py`
- Test: `tests/test_dialog_sizes_safety.py`

- [ ] **Step 1: Write the safety verification test**
  Create `tests/test_dialog_sizes_safety.py` inspecting all registered dialog classes for `setSizeGripEnabled(True)`, minimum dimensions, and ensuring no hardcoded unresizable window traps.
- [ ] **Step 2: Run test to locate offending dialogs**
  Identify any dialogs failing the responsive criteria.
- [ ] **Step 3: Fix dialog classes**
  Add size grips, appropriate minimum sizes ($\ge 640\times 420$ for primary procedure dialogs, $\ge 440\times 320$ for secondary options), and wrap densely packed parameter grids in `QScrollArea`.
- [ ] **Step 4: Run test to confirm all dialogs pass**
  Verify `test_dialog_sizes_safety.py` passes cleanly.
- [ ] **Step 5: Commit**
  `git commit -m "Ensure all dialogs have size grips, responsive minimums, and scroll-protected buttons"`

---

### Task 4: Interactive Connect HUD in Output Viewer

**Files:**
- Modify: `statcraft/modern_app.py`
- Test: `tests/test_connect_hud.py`

- [ ] **Step 1: Write the test**
  Create `tests/test_connect_hud.py` verifying that when a connected result is displayed in `modern_app.py`, an interactive Connect Bridge bar appears with quick 1-click action buttons (Minitab Dialog, JMP Platform, R Script, R Bootstrap, ReportPad).
- [ ] **Step 2: Run test to verify need**
- [ ] **Step 3: Implement Connect Bridge Banner in `modern_app.py`**
  Add a responsive banner atop the report tab displaying the active model provenance, engine badges, and one-click translation pills.
- [ ] **Step 4: Run test to confirm it passes**
- [ ] **Step 5: Commit**
  `git commit -m "Add interactive Connect Bridge banner to results view"`

---

### Task 5: Full Regression Testing & Binary Compilation

- [ ] **Step 1: Run complete test suite**
  Run all 2,168+ tests to guarantee 100% pass rate.
- [ ] **Step 2: Build local standalone executable and installer**
  Run `build_local_installer.ps1 -Full` to update `outputs/StatCraft.exe` and `outputs/StatCraft-Setup.exe`.
- [ ] **Step 3: Final verification**
  Confirm binary sizes and launch integrity.
