# Minitab 22 UX Parity & First-Timer Polish — Round 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve dark-mode inconsistencies across custom dialogs/chrome, add Minitab-standard `Reset`/`F3`, `var_filter`, `Ctrl+E` replay & column pre-selection, upgrade graph copy/SVG/table clipboard fidelity, fix worksheet status summary/`Ctrl+Arrow`/context-menu/`undo` selection retention, and repair Connect recipe dispatch & menu shortcuts.

**Architecture:** Extract shared theme-aware QSS helpers into `statcraft/dialog_theme.py` so custom dialogs stay DRY and follow `is_dark_active`. Upgrade `GraphFrame` and `svg_html_export` to render full titled compositions at high DPI / vector SVG, and attach dual `text/html` + `text/plain` `QMimeData` for Office-ready table copying. Wire worksheet-backed selection aggregation, block-edge movement, and Connect dispatch directly in `modern_worksheet.py` and `modern_app.py`.

**Tech Stack:** Python 3.12, PySide6 (`QtWidgets`, `QtGui`, `QtSvg`), `unittest` (offscreen Qt).

**Spec:** `docs/superpowers/specs/2026-11-11-minitab-ux-parity-round1-design.md`

## Global Constraints
- Preserve existing public signatures (new parameters like `scale=2.0` must have backwards-compatible defaults).
- Never mutate `statcraft_owned=False` project restrictions cleanly.
- All code and tests run cleanly under `QT_QPA_PLATFORM=offscreen` and `STATCRAFT_TESTING=1`.

## Review Focus
- Dark mode active AND light mode active: verify no hardcoded white/dark-slate backgrounds invert legibility in either theme.
- Paginated worksheets (>100 rows) and non-numeric (text/date) columns: verify selection summaries and `Ctrl+Arrow` jumps inspect underlying `presenter.worksheet` values rather than only page 0 items.
- Multi-paragraph or empty `GraphFrame` title/subtitle/footnote during SVG export and 2x HiDPI capture.
- Canceling `ScatterTypeDialog` or running `Find`/`Replace`/`Go To` must not leave `Ctrl+E` broken or clobbering the previous procedure.
- Copying an empty or single-cell result table must still produce valid TSV and HTML without crashing.

---

### Task 1: Shared Dialog Theme Helper & Dark-Mode Parity Across Dialogs and Graph Chrome

**Files:**
- Create: `statcraft/dialog_theme.py`
- Modify: `statcraft/variable_dialogs.py` (`ScatterDialog`, `ScatterTypeDialog`, `_is_dark_active`)
- Modify: `statcraft/boxplot_dialogs.py:14-41` (`box_icon`, `BoxplotTypeDialog`)
- Modify: `statcraft/dotplot_dialogs.py:15-41` (`dot_icon`, `DotplotTypeDialog`)
- Modify: `statcraft/histogram_dialogs.py:23-81` (`histogram_icon`, `HistogramTypeDialog`)
- Modify: `statcraft/categorical_points_dialogs.py:15-41` (`point_icon`, `CategoricalTypeDialog`)
- Modify: `statcraft/graph_object_dialog.py:22-65` (`GraphObjectDialog`)
- Modify: `statcraft/graph_frame.py:82-105` (`_apply_theme_styles`)
- Modify: `statcraft/variability_dialog.py:45-60` (`VariabilityChartDialog`)
- Modify: `statcraft/updater_dialog.py:78-175` (`CheckForUpdatesDialog`)
- Modify: `statcraft/graph_builder_dialog.py:124, 215-220` (`show_error`)
- Modify: `statcraft/paired_t_dialogs.py:28-30`, `statcraft/two_sample_t_dialogs.py:28-30`, `statcraft/rare_event_control_dialogs.py:70-75`
- Test: `tests/test_dialog_theme_and_replay.py`

**Interfaces:**
- Produces: `statcraft/dialog_theme.py`:
  - `is_dark_active(widget=None) -> bool`
  - `dialog_stylesheet(dark: bool) -> str`
  - `gallery_button_stylesheet(dark: bool) -> str`
  - `subtle_label_style(dark: bool, bold: bool = False) -> str`
  - `error_label_style(dark: bool) -> str`

- [ ] **Step 1: Write failing dark/light theme parity tests in `tests/test_dialog_theme_and_replay.py`**
  - Verify `_is_dark_active` / `is_dark_active` behavior with mock dark & light parent windows (`_dark_mode = True/False`).
  - Instantiate `ScatterDialog`, `ScatterTypeDialog`, `BoxplotTypeDialog`, `DotplotTypeDialog`, `HistogramTypeDialog`, `CategoricalTypeDialog`, `GraphObjectDialog`, `GraphFrame`, `VariabilityChartDialog`, `CheckForUpdatesDialog` under dark and light parents and assert theme colors (`#18181b`/`#1f1f23` dark backgrounds vs `#ffffff`/`#f8fafc` light, `#f4f4f5` vs `#0f172a` ink, `footnote_label` styled dark/light, `CheckForUpdatesDialog` has light stylesheet when `not dark`).
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Create `statcraft/dialog_theme.py` and wire into `ScatterDialog`, `ScatterTypeDialog`, gallery dialogs, `GraphObjectDialog`, `GraphFrame`, `VariabilityChartDialog`, `CheckForUpdatesDialog`, `GraphBuilderDialog`, and muted subdialog labels**
- [ ] **Step 4: Run test to verify it passes**

---

### Task 2: `ScatterDialog` & `GraphBuilderDialog` Minitab Features, `Ctrl+E` Replay, Pre-Selection & Clear Validation

**Files:**
- Modify: `statcraft/variable_dialogs.py` (`resolve_variables`, `ProcedureDialog`, `ScatterDialog`)
- Modify: `statcraft/graph_builder_dialog.py` (`GraphBuilderDialog`)
- Modify: `statcraft/modern_app.py:1199-1205, 1685, 6279-6317`
- Test: `tests/test_dialog_theme_and_replay.py`

**Interfaces:**
- Produces:
  - `ScatterDialog`: `self.var_filter`, `reset_dialog()`, `keyPressEvent` (`F3` -> `reset_dialog()`), `load_dialog_state` / `save_dialog_state` keyed `f"ScatterDialog:{mode}"`
  - `GraphBuilderDialog`: `reset_dialog()`, `F3` shortcut, `load_dialog_state` / `save_dialog_state` keyed `"GraphBuilderDialog"` when `parameters is None`
  - `MainWindow.graph("scatter")`: stores `self._last_scatter_mode` and sets `_last_dialog_action` to reopen `ScatterDialog` directly in the chosen mode (bypassing `ScatterTypeDialog` on `Ctrl+E`)
  - `ProcedureDialog`: pre-populates first eligible empty selector from `parent._selected_columns` when no saved state exists

- [ ] **Step 1: Add failing tests to `tests/test_dialog_theme_and_replay.py`**
  - `ScatterDialog`: filter narrows `available`, `Reset` / `F3` clears roles & labels, state persists across reopen (`role_pairs`, `group`, `order`, `labels`).
  - `GraphBuilderDialog`: `Reset` / `F3` clears mappings, state persists when `parameters=None`.
  - `MainWindow`: opening `Find` does not overwrite `_last_dialog_action`; `_last_dialog_action` after choosing a scatter mode opens `ScatterDialog` directly without re-launching `ScatterTypeDialog`.
  - `ProcedureDialog` pre-populates when `parent._selected_columns = {0}` and field is empty without saved state; `resolve_variables` on a text column with `kinds=('number',)` raises message mentioning the column name and `"numeric"`.
- [ ] **Step 2: Run tests to verify failure**
- [ ] **Step 3: Implement `ScatterDialog`, `GraphBuilderDialog`, `ProcedureDialog`, `resolve_variables`, and `modern_app.py` replay fixes**
- [ ] **Step 4: Run tests to verify pass**

---

### Task 3: High-DPI Graph Capture, Full `GraphFrame` Vector SVG Export & Rich HTML+TSV Table Copy

**Files:**
- Modify: `statcraft/graph_frame.py:145-158` (`capture`)
- Modify: `statcraft/svg_html_export.py:22-75` (`export_widget_to_svg_bytes`)
- Modify: `statcraft/modern_app.py:2824-2863, 6416-6425, 9058-9135` (`set_table_clipboard` helper + `copy_output_graph`, `_result_table`, `copy_output_table_tsv`, `copy_cells`)
- Test: `tests/test_export_and_clipboard_fidelity.py`

**Interfaces:**
- Produces:
  - `GraphFrame.capture(self, scale: float = 2.0) -> QPixmap`
  - `export_widget_to_svg_bytes(widget: QWidget) -> bytes` (renders `GraphFrame` title, subtitle, chart, and footnote into unified SVG)
  - `set_table_clipboard(headers, rows, delim="\t")` helper on `MainWindow` / module writing `text/plain` + `text/html` `QMimeData`

- [ ] **Step 1: Write failing tests in `tests/test_export_and_clipboard_fidelity.py`**
  - Verify `GraphFrame.capture()` returns pixmap with `devicePixelRatio() >= 2.0` and logical size matching widget size.
  - Verify `export_widget_to_svg_bytes(frame)` output bytes contain `<svg` AND the visible Title, Subtitle, and Footnote strings when set on `GraphFrame`.
  - Verify copying a result table puts BOTH `mime.hasText()` (TSV) and `mime.hasHtml()` (`<table` + `<th` + `<td`) on `QApplication.clipboard().mimeData()`.
- [ ] **Step 2: Run tests to verify failure**
- [ ] **Step 3: Implement `GraphFrame.capture(scale=2.0)`, `export_widget_to_svg_bytes(GraphFrame)`, and `QMimeData` HTML+TSV table copy**
- [ ] **Step 4: Run tests to verify pass**

---

### Task 4: Worksheet Status Summary, `Ctrl+Arrow` Block Navigation, Context Menu & Undo Selection Retention

**Files:**
- Modify: `statcraft/modern_worksheet.py` (`WorksheetTable` / `movement` supporting `Ctrl+Arrow` block-edge callback)
- Modify: `statcraft/modern_app.py` (`_update_selection_summary`, `build_worksheet_context_menu`, `format_column_action` `Ctrl+1`, `undo`/`redo`, `Ctrl+Arrow` handler on table)
- Test: `tests/test_worksheet_ergonomics_round1.py`

- [ ] **Step 1: Write failing tests in `tests/test_worksheet_ergonomics_round1.py`**
  - Worksheet with 250 rows in column `C1` (numbers `1..250`) and text column `C2` (`["A", "B", "C"]`): selecting `C1` (`select_worksheet_column(0)`) updates `status_selection_summary` with `Count: 250`; selecting `C2` shows `Count: 3`.
  - `Ctrl+Down` from row 0 in a populated block `[0..4, 7..9]` jumps to row 4, then row 7, then row 9 (and works across >100 rows / pages); `Ctrl+Right`/`Ctrl+Left` jumps across column data blocks; `Ctrl+Up` from row 0 still moves focus to `column_names`.
  - `build_worksheet_context_menu` in `col_mode` includes `"Rename Column…"` and labels `"Clear Column(s)"` / `"Delete Column(s)"`. `self.format_column_action.shortcut().toString()` equals `"Ctrl+1"`.
  - Selecting column `0` (`_selected_columns = {0}`) or cell `(2, 1)`, applying `undo()` restores selection state after refresh.
- [ ] **Step 2: Run tests to verify failure**
- [ ] **Step 3: Implement `_update_selection_summary`, `_ctrl_arrow_navigate`, `build_worksheet_context_menu` improvements + `Ctrl+1`, and `undo`/`redo` selection preservation**
- [ ] **Step 4: Run tests to verify pass**

---

### Task 5: Connect Recipe Dispatch Fixes & Menu Shortcut Cleanup

**Files:**
- Modify: `statcraft/modern_app.py:1191-1193, 1595, 1626, 7675-7684, 7976-8020` (`connect_open_dialog`, Connect menu hints, shortcuts)
- Test: `tests/test_connect_dispatch_and_shortcuts.py`

- [ ] **Step 1: Write failing tests in `tests/test_connect_dispatch_and_shortcuts.py`**
  - Mock/monkeypatch dialog launchers on `MainWindow` and verify `connect_open_dialog` routes `"fit_y_by_x"` -> `fit_y_by_x_dialog`, `"fitted_line_plot"` -> `fitted_line_plot_dialog`, `"scatter_plot"` -> Scatter flow, `"best_subsets"` -> `best_subsets_dialog`, `"stepwise_regression"` -> `stepwise_regression_dialog`, `"two_sample_t"` -> `two_sample_t_dialog`.
  - Clicking Connect menu action with `selected_entry=None` updates status bar with helpful guidance instead of silent no-op.
  - No `QAction` in `menuBar()` mixes `\t` shortcut text when `shortcut` is set; `Ctrl+M` triggers `toggle_command_line` (no ambiguous collision).
- [ ] **Step 2: Run tests to verify failure**
- [ ] **Step 3: Implement `connect_open_dialog` dispatch, Connect empty-selection feedback, `\t` label cleanup, and `Ctrl+M` binding**
- [ ] **Step 4: Run tests to verify pass, then run full `unittest discover` suite**
