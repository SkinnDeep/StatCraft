# StatCraft End-User & First-Timer Bug Hunt — Round 2 (`v116.6.0`)

> **For agentic workers:** Executed under `superpowers:systematic-debugging`, `superpowers:writing-plans`, `superpowers:test-driven-development`, and `superpowers:verification-before-completion`. All 15 verified Round 2 bugs must first fail in `tests/test_phase11_end_user_round2.py` (RED), be fixed cleanly at their root causes (GREEN), and pass all targeted Phase 1–11 + regression suites before release.

**Goal:** Eliminate 15 additional end-user crashes, silent calculation/sorting bugs, dark-mode illegibility, dialog selector failures, and corrupt export bugs, shipping `v116.6.0`.

**Tech Stack:** Python 3.12, PySide6 (`QT_QPA_PLATFORM=offscreen`), `unittest`.

---

## 15 Verified Round 2 Bugs & Fixes

1. **`FitYByXDialog` Crashes on Creation (`AttributeError: 'list' object has no attribute 'get'`)** — [`statcraft/fit_y_by_x_dialog.py`](../../../statcraft/fit_y_by_x_dialog.py#L35-L58)
   - Fix: Read `QLineEdit` selector controls from `self.controls["y_index"]` / `self.controls["x_index"]`, resolve via `resolve_variables`, and update a real badge `QLabel` instead of non-existent `self.selectors.get(...)` / `self.note_label`.

2. **`replay_saved_workflow_dialog` Crashes with `UnboundLocalError`** — [`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L8190-L8197)
   - Fix: Remove redundant local `QMessageBox` import inside `replay_saved_workflow_dialog`.

3. **`ProcedureDialog` Ignores `"multi"`, `"min_count"`, `"max_count"`, & `"optional": True` — Breaking JMP Distribution, Control Chart Builder, Process Screening, and ALT Dialogs** — [`statcraft/variable_dialogs.py`](../../../statcraft/variable_dialogs.py#L430-L465), [`jmp_distribution_dialog.py`](../../../statcraft/jmp_distribution_dialog.py#L34), [`control_chart_builder_dialog.py`](../../../statcraft/control_chart_builder_dialog.py#L38), [`process_screening_dialog.py`](../../../statcraft/process_screening_dialog.py#L34)
   - Fix: Support `'multi'` / `'min_count'` / `'max_count'` aliases and `'optional': True` uniformly in `ProcedureDialog.transfer()` and `ProcedureDialog.values()` (returning `None` for blank optional single selectors), and fix falsy zero checks (`if not cols:` -> `if cols == []:`).

4. **`SplitWorksheetDialog` Discards Split Sheets & Freezes Open; Repeat Subset/Stack/Split Crash on Duplicate Sheet Names** — [`statcraft/data_prep_dialogs.py`](../../../statcraft/data_prep_dialogs.py#L134-L144), [`statcraft/data_prep.py`](../../../statcraft/data_prep.py#L146-L196), [`statcraft/app.py`](../../../statcraft/app.py#L6351-L6365)
   - Fix: Pass `'New worksheet'`, call `self.accept()`, set `self.error.setVisible(True)` in `SplitWorksheetDialog.validate`; extract `_disambiguate_worksheet_name` so `store_prepared` and `subset_worksheet_by_condition` never fail on existing sheet names, casing differences (`"Batch"` vs `"batch"`), or whitespace.

5. **`save_graph_as` Overwrites `.svg` Files with Plaintext Reports** — [`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L8986-L8999), [`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L9416-L9423)
   - Fix: Have `copy_active_chart_svg` return `True` when SVG copy succeeds (`False` otherwise) and export vector SVG cleanly inside `save_graph_as`.

6. **JMP Panel Context Menu `"Rename Column..."` Crashes with `TypeError`** — [`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L3592-L3596)
   - Fix: Allow `ModernWindow.rename_column(self, col_index=None)` to accept an optional column index cleanly.

7. **Clipboard Paste Crashes on Middle Blank Rows AND Date Cells Reject `"10/12/2026"`** — [`statcraft/app.py`](../../../statcraft/app.py#L406-L424), [`statcraft/app.py`](../../../statcraft/app.py#L502-L515)
   - Fix: Expand empty middle `[]` rows in clipboard TSV blocks to `[""] * width` rather than throwing a rectangular width error; reuse `data_prep._parse_datetime_cell` fallback date patterns inside `Presenter.parse_cell`.

8. **Multi-Column Sort Ejects Rows with Secondary Missing Values & `rank_column` Misaligns Sparse `C<k>` Targets** — [`statcraft/app.py`](../../../statcraft/app.py#L6975-L7055)
   - Fix: Perform stable per-key sort passes from least-significant to primary sort key (`sort_columns`), keeping secondary missing values grouped inside their primary key; expand sparse `C<k>` columns sequentially via `_assign_or_append_column` in `rank_column`.

9. **`TwoVariancesSummaryChart` Crashes on One-Sided Infinite CI Limits** — [`statcraft/two_variances_charts.py`](../../../statcraft/two_variances_charts.py#L90-L150)
   - Fix: Filter non-finite bounds cleanly when computing `min_v`/`max_v` axis limits and clamp infinite upper bounds at `right` with visual indicator instead of passing `math.inf`/`math.nan` into `int(tx)`.

10. **`connect_r.generate_r_subgroup_spc_script` Crashes on `disp_lcl=[None, ...]` AND R Vector Strings Leave Double Quotes Unescaped** — [`statcraft/connect_r.py`](../../../statcraft/connect_r.py#L1563-L1586), [`statcraft/connect_r.py`](../../../statcraft/connect_r.py#L1801-L1808), [`statcraft/connect_r.py`](../../../statcraft/connect_r.py#L1912-L1918)
    - Fix: Handle `None` elements inside `_scalar` list/tuple inputs safely, and escape `\` and `"` inside R character vector formatting helper `_r_quote`.

11. **`run_normal_capability` Silently Inflates $C_p$/$C_{pk}$ When `moving_range_len > 2`** — [`statcraft/capability_engine.py`](../../../statcraft/capability_engine.py#L370-L389)
    - Fix: Compute actual sliding `span`-observation moving ranges (`max(win) - min(win)`) matching `d2(span)` / `d4(span)`.

12. **Pre-Flight Data Doctor: Unaligned Missing-Row Collinearity, Skipped Numeric Sentinels in Autofix, & False `"Healthy"` UI Exit** — [`statcraft/data_doctor.py`](../../../statcraft/data_doctor.py#L131-L212), [`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L9333-L9355)
    - Fix: Compute pairwise complete-case row correlations `(x_r, y_r)` in `audit_worksheet`, clear `SENTINEL_VALUES` from numeric columns in `autofix_worksheet_issues`, and inspect `report.issues` (any warning OR autofixable issue) before declaring healthy in `run_data_doctor_dialog`.

13. **Dark Mode Output Tables Unreadable (White-on-White), `copy_output_table_tsv` Ignores Target Entry, & Subclass Dialog Validation Errors Invisible** — [`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L6179-L6198), [`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L8723-L8735), [`statcraft/logistic_dialogs.py`](../../../statcraft/logistic_dialogs.py#L200), [`statcraft/data_prep_dialogs.py`](../../../statcraft/data_prep_dialogs.py#L52), [`statcraft/prediction_dialogs.py`](../../../statcraft/prediction_dialogs.py#L56), [`statcraft/similar_graph_dialog.py`](../../../statcraft/similar_graph_dialog.py#L158)
    - Fix: Apply dark-mode palette inside `_result_table`; call `self.show_result(target)` in `copy_output_table_tsv` when `target is not self.selected_entry`; add `self.error.setVisible(True)` in overridden dialog `validate()` handlers.

14. **`assign_formula_dialog` Refuses Clearing Existing Formulas** — [`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L2997-L3004)
    - Fix: When `"Expression:"` is submitted blank for a calculated column, remove the formula cleanly via `self.presenter.remove_formulas([target_idx])`.

15. **`RPlotViewerWidget.save_current_plot` Writes Raw PNG Bytes into `.pdf` & `.jpg` Exports** — [`statcraft/r_workbench_widget.py`](../../../statcraft/r_workbench_widget.py#L499-L505)
    - Fix: Render `.jpg`/`.jpeg` via `QImage.save(..., "JPEG")` and `.pdf` via `QPrinter(QPrinter.OutputFormat.PdfFormat)` + `QPainter`.

---

## Execution Steps

- **Step 1 (RED):** Write `tests/test_phase11_end_user_round2.py` with 15 tests reproducing every bug above, run `unittest`, and confirm 15/15 failures on unpatched code.
- **Step 2 (GREEN):** Implement all 15 root-cause fixes cleanly and verify 15/15 tests pass.
- **Step 3 (Release):** Bump `116.5.0` -> `116.6.0`, run all Phase 1–11 + regression test suites, commit, tag `v116.6.0`, and push to `origin`.
