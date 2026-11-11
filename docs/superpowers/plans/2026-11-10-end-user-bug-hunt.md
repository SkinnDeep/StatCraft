# StatCraft End-User & First-Timer Bug Hunt Plan (`v116.5.0`)

> **For agentic workers:** Executed under `superpowers:systematic-debugging`, `superpowers:writing-plans`, `superpowers:test-driven-development`, and `superpowers:verification-before-completion`. All 15 verified first-timer/end-user bugs must first fail in `tests/test_phase10_end_user_bugs.py` (RED), be fixed cleanly at their root causes (GREEN), and pass all targeted Phase 1–10 + regression suites before release.

**Goal:** Eliminate 15 high-impact first-timer and everyday end-user crashes, data loss traps, import/clipboard failures, R/HTML/SVG export errors, and formula/dialog pitfalls, shipping release `v116.5.0`.

**Tech Stack:** Python 3.12, PySide6 (`QT_QPA_PLATFORM=offscreen`), `unittest`.

---

## 15 Verified End-User & First-Timer Bugs

1. **One-Way ANOVA Crashes on OK (`AttributeError: set_entry`)** — [`ModernWindow.oneway_anova_dialog`](../../../statcraft/modern_app.py#L3798-L3807)
   - Fix: Call `self.show_result(dlg.entry)` instead of non-existent `self.set_entry(dlg.entry)`.

2. **Navigator `F2` Worksheet Rename Crashes (`AttributeError: rename_sheet`)** — [`_nav_key_press`](../../../statcraft/modern_app.py#L785-L802)
   - Fix: Call `self.rename_worksheet()` instead of non-existent `self.rename_sheet()`.

3. **Graph Context Menu `"Descriptive Statistics on Selection…"` Crashes (`AttributeError: display_descriptive_dialog`)** — [`ModernWindow._descriptive_stats_on_selection`](../../../statcraft/modern_app.py#L8027-L8031)
   - Fix: Call `self.describe()` instead of non-existent `self.display_descriptive_dialog()`.

4. **Best Subsets Regression & Data Recode Crash on OK (`AttributeError: _update_all`)** — [`ModernWindow.best_subsets_dialog`](../../../statcraft/modern_app.py#L7341-L7342), [`ModernWindow.recode_dialog`](../../../statcraft/modern_app.py#L7602-L7603)
   - Fix: Call `self.refresh(); self.show_result(entry)` instead of non-existent `self._update_all()`.

5. **`File > Export Worksheet with vroom / readxl (.R)…` Crashes (`ImportError`)** — [`ModernWindow.export_worksheet_vroom`](../../../statcraft/modern_app.py#L9185-L9198)
   - Fix: Import and call `generate_vroom_data_import_code` from `.connect_r` instead of `generate_vroom_load_code`.

6. **"View R Code Dialog…" on Graph Header & Entry Menu Crashes (`ModuleNotFoundError`)** — [`ModernWindow.view_entry_r_code`](../../../statcraft/modern_app.py#L9239-L9260)
   - Fix: Replace missing `.r_viewer.RScriptViewerDialog` with an inline read-only monospace `QDialog` featuring copy-to-clipboard and close buttons (also extracting `entry.get("title")` when `entry` is a dict).

7. **Date Columns Crash ALL R Code Translation/Export (`ImportError: serial_to_date_string`)** — [`generate_dataframe_r_code`](../../../statcraft/r_universal_translator.py#L22-L42)
   - Fix: Import `display_date` from `.model` and format date cells with `display_date(v)`.

8. **Excel `cp1252` CSV Files (`°`, `±`, `µ`) & Trailing Blank-Line CSVs Crash Import** — [`load_csv`](../../../statcraft/io.py#L151-L158), [`parse_delimited`](../../../statcraft/io.py#L112-L149)
   - Fix: Decode files using fallback chain `("utf-8-sig", "cp1252", "latin-1")` (wrapping undecodable binary files cleanly as `FormatError`) and strip trailing completely empty rows (`[]`) before rectangular width validation.

9. **Clipboard Paste Crashes on Trailing Newlines AND Eats Leading `*` / `""` Missing Values as Headers** — [`Presenter.paste`](../../../statcraft/app.py#L498-L542)
   - Fix: Strip trailing empty `[]` rows after `csv.reader`, and exclude missing sentinels `("", "*", "NA", "N/A", "nan", "NaN")` from Smart Header candidates so leading missing rows are never mistaken for column headers.

10. **Copying Selected Column(s) Silently Truncates Beyond 300 Rows (`PAGE_SIZE`)** — [`ModernWindow.copy_with_column_names`](../../../statcraft/modern_app.py#L2741-L2762), [`ModernWindow.copy_cells`](../../../statcraft/modern_app.py#L2763-L2783)
    - Fix: Extract helper `_copy_selected_columns_text(include_headers=False)` so any non-empty `self._selected_columns` selection copies all `worksheet.row_count` rows across selected columns instead of falling back to the 300-row visible table `_range()`.

11. **`Open Recent` & Welcome `"Sample Data"` Bypass Unsaved-Changes Prompt (`_confirm_leave`), and `Open Recent` Crashes on Moved/Deleted Files** — [`ModernWindow._update_recent_menu`](../../../statcraft/modern_app.py#L3297-L3318), [`ModernWindow.load_connect_sample`](../../../statcraft/modern_app.py#L7708-L7718)
    - Fix: Gate both via `self._confirm_leave()`, and wrap Recent opens in `self._call(lambda: self.load_path(path))` via `_open_recent_file(path)`.

12. **Autofill Inserts `None` Gaps When Extending Downward Into Empty Cells** — [`ModernWindow.autofill_dialog`](../../../statcraft/modern_app.py#L3429-L3451)
    - Fix: Extract seed length from leading non-empty entries across `first_r..last_r` regardless of whether `last_r >= len(col.values)`, computing exact fill count `sel_len - sample_len`.

13. **SVG Export Outputs Blank `viewBox="0 0 0 0"` Offscreen AND `ChartWidget` Leaks `KeyError` During Session HTML/MD Export** — [`export_widget_to_svg_bytes`](../../../statcraft/svg_html_export.py#L22-L44), [`ChartWidget.paintEvent`](../../../statcraft/modern_charts.py#L940-L959), [`ModernWindow.export_session_markdown_dialog`](../../../statcraft/modern_app.py#L5288-L5303)
    - Fix: Set `generator.setViewBox(QRect(0, 0, w_size.width(), w_size.height()))`, catch `KeyError` in `ChartWidget.paintEvent`, and wrap session Markdown export I/O in `_call`/error handling.

14. **`wafer_plot` Crashes with `IndexError` on `< 3` Columns & Generic Connected Analyses Falsely Flagged `"repair_needed"`** — [`expanded_graphs.compute`](../../../statcraft/expanded_graphs.py#L115-L123), [`check_analysis_freshness`](../../../statcraft/connect.py#L581-L622)
    - Fix: Add `'wafer_plot': 3` to `minimum` and `exact` maps in `expanded_graphs.py`; handle `response_col_id == "generic"` cleanly in `check_analysis_freshness` via whole-worksheet fingerprint comparison.

15. **Live Formula & Calculator Pitfalls + `ProcedureDialog` Search Filter Desync** — [`formulas.py`](../../../statcraft/formulas.py#L8-L73), [`calculator.py`](../../../statcraft/calculator.py#L27-L59), [`Presenter.calculate`](../../../statcraft/app.py#L780-L815), [`Presenter.assign_formula`](../../../statcraft/app.py#L7046-L7060), [`ProcedureDialog.activate`](../../../statcraft/variable_dialogs.py#L412-L422)
    - Fix:
      - Support case-insensitive `c1`/`k1` references in `calculator.evaluate`, `calculator.column_references`, and `formulas.remap_references` (`re.IGNORECASE`).
      - Allow `assign_formula` and `formulas.recalculate` / `calculation_order` to use `evaluate_advanced` + `[Column Name]` bracketed column refs cleanly without breaking existing `evaluate()` contracts.
      - Overwrite an existing column when `Presenter.calculate(..., destination)` names an existing column instead of creating duplicate columns.
      - Re-apply `self._filter_available_variables(self.var_filter.text())` inside `ProcedureDialog.activate`.

---

## Execution Steps

- **Step 1 (RED):** Write `tests/test_phase10_end_user_bugs.py` with 15 tests reproducing all 15 bugs, run `unittest`, and confirm all 15 fail on unpatched code.
- **Step 2 (GREEN):** Fix all 15 root causes cleanly with zero duplicated logic and preserve existing contracts/docstrings, then re-run `tests/test_phase10_end_user_bugs.py` until 15/15 pass.
- **Step 3 (Version Bump):** Update version `116.4.0` -> `116.5.0` across all 7 version metadata files + Phase 5 & Phase 6 test version checks.
- **Step 4 (Verification):** Run all Phases 1–10 suites plus `test_calculator`, `test_run_comparator`, `test_data_doctor`, `test_connect_advanced`, `test_connect`, `test_app_contract`, `test_formula_updates`, `test_io`, `test_missing_sentinels`, `test_mpx_*`, `test_session_commands_and_batch`.
- **Step 5 (Release):** Commit, tag `v116.5.0`, and push `main` + tag to `origin`.
