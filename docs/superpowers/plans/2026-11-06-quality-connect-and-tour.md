# Industrial Quality Connect & Tri-Engine Tour Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete StatCraft Connect's production readiness with universal tri-engine support for industrial quality tools (Gage R&R MSA, Subgroup Xbar-R/S SPC), a 1-click Connect demo tour loader, high-DPI display layout safety, and subagent-verified production builds.

**Architecture:** Connect contracts (`ConnectedAnalysis`) standardise procedure metadata across Minitab, JMP, and R. For each quality tool, pure Base R generators produce standalone executable scripts with standard multi-panel graphics and variance tables. JMP navigators launch corresponding interactive platforms. A 1-click demo tour pre-populates multi-sheet benchmark data with active Connect links.

**Tech Stack:** Python 3.11+, PySide6, Pure Base R (zero tidyverse / zero CRAN dependencies), pytest.

**Spec:** Brainstormed tri-engine universal bridge specification (Approach 3 approved).

## Global Constraints

- 100% Pure Base R code generation (strictly zero external packages; no `ggplot2`, `dplyr`, `SixSigma`, or `qcc`).
- Double-quoted column indexing in generated R (`df[["Col"]]`).
- Zero unresizable modal traps (`setSizeGripEnabled(True)` after `super().__init__`).
- Backward compatibility with native `.mpx`, `.mwx`, `.jmp`, `.statcraft` files.
- 100% pass rate across all existing 2,178 tests.

## Review Focus

- Gage R&R with single appraiser (operator) or single part without crashing variance component calculation.
- Subgroup SPC with uneven subgroup sizes or missing values in subgroup column.
- Sample dataset loading into multi-sheet workbook without clobbering existing user sheets without prompt.
- R code string escaping for column names with spaces, special characters, or numbers.
- High-DPI menubar rendering on 125% and 150% Windows display scaling.

---

### Task 1: Gage R&R (Crossed MSA) Connect Integration

**Files:**
- Modify: `statcraft/connect.py`
- Modify: `statcraft/connect_r.py`
- Modify: `statcraft/connect_hub.py`
- Modify: `statcraft/modern_app.py`
- Test: `tests/test_connect_gage_rr.py`

**Interfaces:**
- Consumes: `Worksheet`, `ConnectedAnalysis`, `generate_r_script`
- Produces: `create_connected_gage_rr(worksheet, part_col, appraiser_col, response_col, result=None, spec_tolerance=None) -> ConnectedAnalysis`, `generate_r_gage_rr(...) -> str`

- [ ] **Step 1: Write failing test in `tests/test_connect_gage_rr.py`**
  Verify factory generates valid contract, pure Base R script with `aov()` and variance components, and ConnectBridgeWidget labels button as `📈 JMP Variability Gauge`.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_connect_gage_rr.py -v`
  Expected: FAIL (missing `create_connected_gage_rr` or `generate_r_gage_rr`)

- [ ] **Step 3: Implement Gage R&R Connect factory and R generator**
  In `statcraft/connect.py`: add `create_connected_gage_rr` and map action `gage_rr` / `gage_rr_crossed` in `create_connected_analysis_from_entry`.
  In `statcraft/connect_r.py`: add `generate_r_gage_rr` generating Base R ANOVA table, variance components calculation, and Gage evaluation table.
  In `statcraft/connect_hub.py`: add `conn_obj.analysis_type in ("gage_rr", "gage_rr_crossed") -> "📈 JMP Variability Gauge"`.
  In `statcraft/modern_app.py`: dispatch to `self.gage_rr()` in `connect_open_dialog`.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_connect_gage_rr.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  `git commit -m "feat(connect): add universal Gage R&R crossed MSA bridge"`

---

### Task 2: Subgroup SPC (Xbar-R / Xbar-S) Connect Integration

**Files:**
- Modify: `statcraft/connect.py`
- Modify: `statcraft/connect_r.py`
- Modify: `statcraft/connect_hub.py`
- Modify: `statcraft/modern_app.py`
- Test: `tests/test_connect_subgroup_spc.py`

**Interfaces:**
- Consumes: `Worksheet`, `ConnectedAnalysis`
- Produces: `create_connected_subgroup_spc(worksheet, data_col, subgroup_col_or_size, chart_type="xbar_r", result=None) -> ConnectedAnalysis`, `generate_r_subgroup_spc(...) -> str`

- [ ] **Step 1: Write failing test in `tests/test_connect_subgroup_spc.py`**
  Verify factory generates valid contract for Xbar-R and Xbar-S charts with subgroup sizes, generates pure Base R 2-panel chart, and routes JMP button to `📈 JMP Control Chart Builder`.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_connect_subgroup_spc.py -v`
  Expected: FAIL

- [ ] **Step 3: Implement Subgroup SPC Connect factory and R generator**
  In `statcraft/connect.py`: add `create_connected_subgroup_spc` and map actions `xbar_r`, `xbar_s`, `subgroup_control` in `create_connected_analysis_from_entry`.
  In `statcraft/connect_r.py`: add `generate_r_subgroup_spc` using Base R vector aggregation (`split()`, `sapply()`), mean/range calculations, control limits with standard $A_2, D_3, D_4$ / $A_3, B_3, B_4$ tables, and 2-panel `par(mfrow=c(2,1))` plotting.
  In `statcraft/connect_hub.py`: route `xbar_r`, `xbar_s` to `📈 JMP Control Chart Builder`.
  In `statcraft/modern_app.py`: dispatch to `self.xbar_r()` / `self.xbar_s()` in `connect_open_dialog`.

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_connect_subgroup_spc.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  `git commit -m "feat(connect): add universal Subgroup SPC (Xbar-R / Xbar-S) bridge"`

---

### Task 3: 1-Click Connect Demo Tour Loader

**Files:**
- Modify: `statcraft/modern_app.py`
- Test: `tests/test_connect_tour.py`

**Interfaces:**
- Produces: `ModernWindow.load_connect_sample_project()`
- Consumes: `Presenter.add_worksheet`, `Presenter.history`

- [ ] **Step 1: Write failing test in `tests/test_connect_tour.py`**
  Verify `load_connect_sample_project()` creates 3 worksheets with industrial benchmark data (`DOE_Battery`, `GageRR_Gasket`, `SPC_PistonRings`) and sets up active Connect recipes.

- [ ] **Step 2: Run test to verify failure**
  Run: `pytest tests/test_connect_tour.py -v`
  Expected: FAIL (`AttributeError: 'ModernWindow' object has no attribute 'load_connect_sample_project'`)

- [ ] **Step 3: Implement `load_connect_sample_project` and menu entry**
  In `statcraft/modern_app.py`:
  - Add `load_connect_sample_project(self)` method to populate standard sample sheets with known benchmarks.
  - Add menu item in Help menu (`Help -> StatCraft Connect Tour (Sample Project)`) and File menu (`File -> Open Sample Data`).

- [ ] **Step 4: Run test to verify it passes**
  Run: `pytest tests/test_connect_tour.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  `git commit -m "feat(connect): add 1-click Connect demo tour and sample project loader"`

---

### Task 4: High-DPI Display Safety & Layout Audit

**Files:**
- Modify: `statcraft/modern_app.py`
- Test: `tests/test_display_responsiveness.py`

**Interfaces:**
- Verifies: Minimum window size ($1024 \times 700$), toolbar overflow handling, menu responsiveness.

- [ ] **Step 1: Write test in `tests/test_display_responsiveness.py`**
  Test window resize down to minimum size, verify all child widgets remain accessible and no layout constraints are violated.

- [ ] **Step 2: Implement responsive toolbar and layout tweaks if needed**
  Ensure main toolbars and connect HUD don't clip at $1024 \times 700$.

- [ ] **Step 3: Run test to verify it passes**
  Run: `pytest tests/test_display_responsiveness.py -v`
  Expected: PASS

- [ ] **Step 4: Commit**
  `git commit -m "fix(ui): polish high-DPI and constrained display responsiveness"`

---

### Task 5: Full Regression, Subagent Code Review, and Production Compilation

**Files:**
- Whole repository

- [ ] **Step 1: Run full regression test suite (2,180+ tests)**
  Command: `pytest -q`
  Expected: 100% PASS

- [ ] **Step 2: Dispatch Code Reviewer subagent**
  Audit new code against strict constraints: pure Base R, double-quoted indexing, zero unresizable dialogs. Fix any findings.

- [ ] **Step 3: Compile production executables**
  Build `StatCraft.exe` and `StatCraft-Setup.exe`. Verify executable sizes and checksums.

- [ ] **Step 4: Commit and push**
  `git push origin main`
