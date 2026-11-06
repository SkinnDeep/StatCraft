# Modern StatCraft Consolidation & R Code Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate StatCraft into a unified, high-performance modern Minitab workstation (Option C). Retire the fragmented tri-engine mode switcher (Minitab/JMP/R) and elevate the pure Base R translation into a 1-click reproducible R script export and audit viewer across all analysis results.

**Architecture:** StatCraft adopts a single cohesive desktop interface centered on the proven Six Sigma workflow (Worksheet -> Stat/Graph Dialogs -> Output Navigator & ReportPad). Each analysis result embeds a sleek StatCraft Analysis Bar providing 1-click "Edit Dialog", "Copy R Script", "View R Code", "Add to ReportPad", and native interactive profilers. All pure Base R generators (`statcraft/connect_r.py`) are preserved and exposed as first-class reproducible science tools.

**Tech Stack:** Python 3.11+, PySide6, Pure Base R code generation (zero external CRAN dependencies), pytest.

**Spec:** Strategic Option C approved by user: Focus on modern, robust Minitab alternative with seamless R code export on every output.

## Global Constraints

- Zero UI mode fragmentation: Eliminate `btn_mode_minitab`, `btn_mode_jmp`, `btn_mode_r` from the main window.
- 100% Pure Base R code export on all analysis results (zero external dependencies).
- Single-click clipboard copy (`QApplication.clipboard().setText(r_script)`) and `.R` file export.
- Full backward compatibility with `.mpx`, `.mwx`, `.jmp`, `.statcraft` files.
- 100% pass rate across the full 2,189+ test suite.

## Review Focus

- Result entries without an active R generator falling back gracefully to a descriptive Base R template without crashing.
- Clipboard copy working reliably on Windows without external dependencies.
- "Edit Procedure Dialog" correctly re-opening the exact dialog and restoring previous parameters.
- View R Script dialog supporting dark and light themes with clean copy-to-clipboard button.
- Saving/opening projects and ReportPad exports functioning without regression.

---

### Task 1: Streamline Main Window Navigation & Retire Mode Switcher

**Files:**
- Modify: `statcraft/modern_app.py`
- Modify: `statcraft/connect_hub.py`
- Test: `tests/test_statcraft_unified_ui.py`

**Interfaces:**
- Removes: `btn_mode_minitab`, `btn_mode_jmp`, `btn_mode_r` from toolbar.
- Sets: Permanent default UI mode to native StatCraft (Minitab standard workflow).
- Keeps: `set_ui_mode` as compatibility shim if called programmatically, but eliminates mode toggle UI.

- [ ] **Step 1: Write failing test in `tests/test_statcraft_unified_ui.py`**
  Verify main window has unified toolbar without mode switcher buttons, default navigation is native StatCraft, and menus follow standard Minitab hierarchy (File, Edit, Data, Calc, Stat, Graph, Editor, Tools, Window, Help).

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_statcraft_unified_ui.py -v`
  Expected: FAIL

- [ ] **Step 3: Refactor toolbar and mode switching in `statcraft/modern_app.py`**
  Remove mode switch button group from main window toolbar. Streamline window initialization to open directly into native StatCraft workspace.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_statcraft_unified_ui.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  `git commit -m "refactor(ui): unify StatCraft interface and retire mode switcher buttons"`

---

### Task 2: Build Sleek Analysis Action Bar with 1-Click R Code Export

**Files:**
- Modify: `statcraft/connect_hub.py`
- Modify: `statcraft/modern_app.py`
- Test: `tests/test_r_code_export_bar.py`

**Interfaces:**
- Replaces: Cluttered tri-engine `ConnectBridgeWidget` banner.
- Implements: `StatCraftAnalysisBar` with buttons:
  - `📊 Edit Dialog...`
  - `📋 Copy R Script`
  - `👁️ View R Code`
  - `💾 Export .R`
  - `📑 Add to ReportPad`
  - `📈 Interactive Profiler` (conditional on model type)
- Implements: `ViewRCodeDialog` (clean modal code viewer with syntax highlighting and Copy button).

- [ ] **Step 1: Write failing test in `tests/test_r_code_export_bar.py`**
  Verify `StatCraftAnalysisBar` renders on analysis results, `copy_r_script()` copies pure Base R code to system clipboard, and `show_r_code_dialog()` displays the code dialog.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_r_code_export_bar.py -v`
  Expected: FAIL

- [ ] **Step 3: Implement `StatCraftAnalysisBar` and `ViewRCodeDialog`**
  In `statcraft/connect_hub.py`: Create `StatCraftAnalysisBar` and `ViewRCodeDialog`.
  In `statcraft/modern_app.py`: Embed `StatCraftAnalysisBar` at the top of every analysis result view in `show_result()`. Add `copy_analysis_r_script(entry)` and `view_analysis_r_code(entry)` methods.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_r_code_export_bar.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  `git commit -m "feat(r-export): add 1-click R script copy, view, and file export toolbar to analysis results"`

---

### Task 3: Universal Fallback R Generator for All Remaining Analyses

**Files:**
- Modify: `statcraft/connect_r.py`
- Modify: `statcraft/connect.py`
- Test: `tests/test_universal_r_fallback.py`

**Interfaces:**
- Produces: `generate_generic_r_script(entry, worksheet) -> str`
- Ensures: Every single analysis in history—even legacy or niche tests without a dedicated custom generator—generates a clean, valid, executable Base R script loading `df` and executing standard diagnostics.

- [ ] **Step 1: Write failing test in `tests/test_universal_r_fallback.py`**
  Verify that arbitrary/unconnected analysis entries generate a valid Base R script with worksheet loading and summary statistics.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_universal_r_fallback.py -v`
  Expected: FAIL

- [ ] **Step 3: Implement `generate_generic_r_script`**
  In `statcraft/connect_r.py`: Add robust generic Base R fallback that inspects recipe parameters and formats clean R code.
  In `statcraft/connect.py`: Wire fallback into `create_connected_analysis_from_entry` so no result ever has an empty or null R script.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_universal_r_fallback.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  `git commit -m "feat(r-export): add universal Base R fallback script generator for all analyses"`

---

### Task 4: Polish Minitab-Standard Sample Data & Assistant Workflows

**Files:**
- Modify: `statcraft/modern_app.py`
- Test: `tests/test_modern_minitab_workflows.py`

**Interfaces:**
- Enhances: `File -> Open Sample Data` menu with clean Six Sigma benchmarks.
- Verifies: Full workflow from sample dataset -> Dialog execution -> Result inspection -> 1-click R copy -> ReportPad compilation.

- [ ] **Step 1: Write test in `tests/test_modern_minitab_workflows.py`**
  Test complete end-to-end user workflow: load sample data, open dialog, run analysis, copy R script, add to ReportPad.

- [ ] **Step 2: Polish sample data menu and ReportPad integration**
  Ensure menu entries under `File -> Open Sample Data` are clean, descriptive, and launch without friction.

- [ ] **Step 3: Run test to verify it passes**
  Run: `pytest tests/test_modern_minitab_workflows.py -v`
  Expected: PASS

- [ ] **Step 4: Commit**
  `git commit -m "feat(workflow): polish standard sample datasets and ReportPad export workflow"`

---

### Task 5: Full Regression Pass, Subagent Review, and Production Compilation

**Files:**
- Entire repository

- [ ] **Step 1: Run complete 2,189+ test suite**
  Verify 100% pass rate.

- [ ] **Step 2: Dispatch Code Reviewer subagent**
  Audit consolidation changes against Option C requirements.

- [ ] **Step 3: Recompile production executables**
  Build `StatCraft.exe` and `StatCraft-Setup.exe`. Verify sizes and execution.

- [ ] **Step 4: Commit and push to origin/main**
