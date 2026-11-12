# Minitab 22 UX Parity & First-Timer Polish — Round 1 Design Spec

**Date:** 2026-11-11  
**Target Version:** `v118.0.0` (Round 1 of iterative Minitab parity & UX polish before release)  
**Evidence Sources:** Reverse-engineered Minitab 22 artifacts (`Dialogs.data`, `mss-graphs.data`, `mss-graph-editing.data`, `Resources\1033\MtbResources.dll`) + StatCraft audit across `statcraft/`.

---

## 1. Goals & Scope

Eliminate the highest-friction daily workflow, dark-mode, clipboard/export, worksheet navigation, and dialog replayability bugs discovered after `v117.0.0`:

1. **Dark-Mode & Minitab Dialog Replay Consistency**
2. **High-DPI Clipboard, Rich HTML Table Copy, and Complete SVG Export**
3. **Full-Sheet Selection Summary, `Ctrl+Arrow` Block Navigation, Column Context Menu & Undo Selection Retention**
4. **StatCraft Connect Recipe Dispatch & Shortcut Cleanup**

*(Round 2 will follow immediately after Round 1 tests pass: Output Report `Ctrl+F` search + Navigator filter, 2D interactive zoom/pan + legend toggle, mouse drag-fill handle, and result-table precision toggle.)*

---

## 2. Detailed Component Design

### Component 1: Dialog Theme, Persistence & Pre-Selection Consistency

- **Shared Dialog Theme Helper (`statcraft/dialog_theme.py`):**
  - Expose `is_dark_active(widget=None) -> bool`, `dialog_stylesheet(dark: bool) -> str`, `gallery_button_stylesheet(dark: bool) -> str`, and `subtle_label_style(dark: bool) -> str` so custom `QDialog` subclasses match `ProcedureDialog` without duplicating 100-line QSS strings.
- **Dark-Mode Fixes:**
  - `ScatterDialog` (`statcraft/variable_dialogs.py`): use theme-aware QSS (`dialog_stylesheet`), fix hint label color in dark mode.
  - Gallery choosers (`ScatterTypeDialog` in `variable_dialogs.py`, `BoxplotTypeDialog` in `boxplot_dialogs.py`, `DotplotTypeDialog` in `dotplot_dialogs.py`, `HistogramTypeDialog` in `histogram_dialogs.py`, `CategoricalTypeDialog` in `categorical_points_dialogs.py`): use `gallery_button_stylesheet(dark)` and theme-appropriate thumbnail backdrop/axes when dark mode is active.
  - `GraphObjectDialog` (`statcraft/graph_object_dialog.py`): apply `dialog_stylesheet(is_dark_active(self))` and theme-aware error label color (`#f87171` dark / `#a00000` light).
  - `GraphFrame._apply_theme_styles` (`statcraft/graph_frame.py`): style `footnote_label` consistently alongside `title_label` and `subtitle_label`.
  - `VariabilityChartDialog` (`statcraft/variability_dialog.py`), `CheckForUpdatesDialog` (`statcraft/updater_dialog.py` light-mode branch when not dark), `GraphBuilderDialog.show_error` (`statcraft/graph_builder_dialog.py`), and subdialog muted headers (`paired_t_dialogs.py`, `two_sample_t_dialogs.py`, `rare_event_control_dialogs.py`).
- **`ScatterDialog` & `GraphBuilderDialog` Parity:**
  - `ScatterDialog`: add `var_filter` (`QLineEdit` with `setClearButtonEnabled(True)`), `Reset` button + `F3` shortcut (`reset_dialog()`), and `save_dialog_state`/`load_dialog_state` persistence keyed per mode (`f"ScatterDialog:{mode}"`).
  - `GraphBuilderDialog`: save/restore state via `save_dialog_state` / `load_dialog_state` when `parameters is None`, plus `Reset` button (`clear_mappings()` + reset options) and `F3` shortcut.
- **`Edit Last Dialog (Ctrl+E)` Fixes (`statcraft/modern_app.py`):**
  - When `graph("scatter")` accepts `ScatterTypeDialog`, update `self._last_dialog_action` to reopen `ScatterDialog` directly in `chooser.mode` (skipping the type chooser on `Ctrl+E`). Also store `_last_scatter_mode` to default-select it next time `ScatterTypeDialog` opens.
  - Set `record_last=False` on non-procedure utility actions (`find_dialog`, `replace_dialog`, `goto_dialog`, `worksheet_description_dialog`, `check_for_updates_dialog`) so they do not overwrite the last Stat/Graph/Calc procedure.
- **Column Pre-Selection & Clear Error Messages (`statcraft/variable_dialogs.py`):**
  - `ProcedureDialog.__init__`: if no saved state populated the first eligible selector (matching `column.kind in spec['kinds']`) and `parent` has `_selected_columns`, pre-populate from those selected columns cleanly (single or multi depending on `multiple`/`maximum`).
  - `resolve_variables`: when a token references an existing column whose `kind` does not match `kinds`, raise a clear message naming the column, its actual type, and expected type(s), e.g. `"Column C1 ('Name') is text, but this field requires numeric columns."`

### Component 2: Output Clipboard Fidelity & Vector SVG Export

- **Complete Vector SVG Export (`statcraft/svg_html_export.py`):**
  - When `export_widget_to_svg_bytes(widget)` receives a `GraphFrame`, preserve visible `title_label`, `subtitle_label`, and `footnote_label` alongside `widget.chart` by laying out header/chart/footer cleanly inside one `QSvgGenerator` vector paint pass instead of unwrapping `widget.chart` alone.
- **High-DPI Graph Clipboard Copy (`statcraft/graph_frame.py`, `statcraft/modern_app.py`):**
  - Update `GraphFrame.capture(self, scale: float = 2.0)` to render at `scale` device pixel ratio (`QPixmap` sized `(w * scale, h * scale)` with `setDevicePixelRatio(scale)` and `render(&painter)`), keeping existing zero-arg `capture()` callers working with crisp `2x` output.
- **Rich HTML + TSV Table Copy (`statcraft/modern_app.py`):**
  - Add helper `set_table_clipboard(headers, rows, delim="\t")` that constructs a `QMimeData` payload containing both plain-text (`TSV`/`CSV`) and clean styled `text/html` (`<table><thead>...<tbody>...`) and places it on `QApplication.clipboard()`. Wire this into `_result_table` context copy, `copy_output_table_tsv`, and `_copy_generic_table_tsv`.

### Component 3: Worksheet Grid, Block Navigation & Status Bar Ergonomics

- **Full-Sheet + Non-Numeric Status Summary (`statcraft/modern_app.py`):**
  - Update `_update_selection_summary()`:
    - When `self._selected_columns` is non-empty, iterate the underlying `worksheet.columns[c].values` across **all rows** (not capped at `PAGE_SIZE = 100`).
    - When `self._selected_rows` is non-empty, iterate underlying worksheet rows across all columns.
    - Track both `nonempty_count` (all non-`None`, non-empty cells including text/dates) and numeric `vals`.
    - For numeric `len(vals) >= 2`: display `Count` (all non-empty if larger, or numeric count), `Sum`, `Mean`, `StDev`, `Min`, `Max`.
    - For single numeric: `Count: 1 | Value: ...`.
    - For non-numeric selections (`nonempty_count >= 1`, `len(vals) == 0`): display `Count: {nonempty_count}` (plus single value preview if `nonempty_count == 1`).
- **`Ctrl+Arrow` Data Block Edge Navigation (`statcraft/modern_worksheet.py`, `statcraft/modern_app.py`):**
  - Support `Ctrl+Up`, `Ctrl+Down`, `Ctrl+Left`, `Ctrl+Right` navigation across contiguous non-empty blocks in the underlying `worksheet` (using a callback or helper method on the window/worksheet model):
    - Preserve `Ctrl+Up` at global row `0` moving focus to `column_names`.
    - Move to the edge of the current contiguous non-empty block, or jump across blanks to the next non-empty cell (or worksheet boundary `[0, max_populated_row]` / `[0, num_cols-1]`), flipping `self.page` if crossing a pagination boundary.
- **Worksheet Context Menu & `Ctrl+1` Shortcut (`statcraft/modern_app.py`):**
  - Add `"Rename Column…"` to `build_worksheet_context_menu` when in column mode or single-column context.
  - Dynamically label `"Clear Column(s)"` / `"Delete Column(s)"` when `col_mode` is active, and `"Clear Row(s)"` / `"Delete Row(s)"` when `row_mode` is active.
  - Bind real `Ctrl+1` shortcut to `self.format_column_action` -> `format_column_dialog`.
- **Undo / Redo Selection Retention (`statcraft/modern_app.py`):**
  - Capture active `(row, col)` and `_selected_columns` / `_selected_rows` before `undo()` / `redo()` refresh and restore valid coordinates/column selection afterward.

### Component 4: Connect Dispatch & Shortcut Cleanup

- **Repair `connect_open_dialog` (`statcraft/modern_app.py`):**
  - Fix `action == "fit_y_by_x"` -> `self.fit_y_by_x_dialog()`.
  - Dispatch `fitted_line_plot`, `scatter_plot`/`scatter`, `histogram`, `boxplot`, `dotplot`, `best_subsets`, `stepwise_regression`, `poisson_regression`, `pls_regression`, `nonlinear_regression`, `fit_binary_logistic`/`binary_logistic`/`nominal_logistic`/`ordinal_logistic`, `graph_builder`, `capability_sixpack`, `equal_variances`, `one_variance`, `two_variances`, `one_proportion`, `two_proportions`, `two_sample_t` -> `two_sample_t_dialog`, `one_sample_t` -> `one_sample_t_dialog`, `paired_t` -> `paired_t_dialog`.
- **Connect Feedback:**
  - When Connect menu actions require `self.selected_entry` and none is selected, show a clear status message (`"Select an analysis output in Navigator first."`) instead of silent no-op.
- **Shortcut Cleanup:**
  - Remove duplicate inline `\tCtrl+Alt+R` / `\tCtrl+Alt+S` text on `_action(...)` items where `shortcut` is also passed.
  - Bind `Ctrl+M` to toggle/focus the Session Command Line (`toggle_command_line`).

---

## 3. Verification Criteria

- Unit & offscreen Qt tests (TDD) covering every component:
  - `test_dialog_theme_and_replay.py`: dark/light theme stylesheets for `ScatterDialog`, `ScatterTypeDialog`, `BoxplotTypeDialog`, `GraphObjectDialog`, `GraphFrame` footnote, `CheckForUpdatesDialog`, `VariabilityChartDialog`; `ScatterDialog` filter, Reset/F3, and saved state; `Edit Last Dialog` skipping `ScatterTypeDialog`; `ProcedureDialog` column pre-selection & clear text-column error message.
  - `test_export_and_clipboard_fidelity.py`: `GraphFrame` SVG export includes title, subtitle, and footnote text; `GraphFrame.capture(scale=2.0)` produces HiDPI pixmap; HTML + TSV clipboard `QMimeData` on table copy.
  - `test_worksheet_ergonomics_round1.py`: status bar selection summary across >100 paginated rows + text columns; `Ctrl+Arrow` block-edge navigation across gaps & pages; context menu `Rename Column…` and `Clear/Delete Column(s)` labels; `Ctrl+1` action; undo selection retention.
  - `test_connect_dispatch_and_shortcuts.py`: `connect_open_dialog` routes `fit_y_by_x`, `fitted_line_plot`, `scatter_plot`, `best_subsets`, etc.; no-selection status bar feedback; no duplicate `\t` shortcuts in `_action` calls; `Ctrl+M` bound.
- Full `unittest discover` suite runs cleanly.
