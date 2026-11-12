# First-Timer Bugs, Rendering Defects & Minitab Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate high-visibility first-timer bugs (chart chord-fill rendering artifacts, dead dialog controls, dark mode blindness, silent Graph Options failures, Excel/date clipboard paste failures, `Ctrl+C` table hijacking, missing undo, non-persisting dialogs) and close critical Minitab-parity gaps (`Fit Regression Model` categorical/interaction support, `Display Descriptive Statistics` By/Graphs/Stats, `Calculator` UI + text formulas, `Xbar`/`R`/`S` single-chart modes, `Normality Test` RJ/KS, `.mtw`/`.mpj` user guidance).

**Architecture:** Extract shared helpers (`chart_theme.py` for Dark Mode across all 60+ chart painters, `paste` value/date parsing in `app.py`, shared dialog state persistence in `variable_dialogs.py`, `glm`/design-matrix helpers for regression) rather than duplicating per-module logic. Every bugfix is paired with targeted headless Qt/unit tests under `tests/`.

**Tech Stack:** Python 3.12, PySide6 (`QPainter`, `QWidget`, `QDialog`), NumPy, SciPy, `unittest` (`STATCRAFT_TESTING=1`, `QT_QPA_PLATFORM=offscreen`).

**Verification Command Convention:**
```powershell
Set-Location "c:\Users\funny\Documents\Codex\2026-10-12\us\work\statcraft"
$env:PYTHONPATH=".;tests;..\statcraft-build-deps"; $env:QT_QPA_PLATFORM="offscreen"; $env:STATCRAFT_TESTING="1"
```
Run with `C:\Users\funny\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`. Always end inline Qt scripts with `sys.stdout.flush(); os._exit(0)`.

---

### Task 1: Fix Remaining Open-Path `QPainter` Chord-Fill Rendering Bugs (6 Chart Modules)

**Files:**
- Modify: `statcraft/regression_residual_chart.py`
- Modify: `statcraft/sixpack_chart.py`
- Modify: `statcraft/control_chart_builder_chart.py`
- Modify: `statcraft/rare_event_control_chart.py`
- Modify: `statcraft/time_weighted_control_chart.py`
- Modify: `statcraft/multivariate_chart.py`
- Test: `tests/test_chart_no_chord_fill.py`

- [ ] **Step 1: Write failing pixel/painter tests asserting no filled chord polygons appear on open line series**
  Create `tests/test_chart_no_chord_fill.py` rendering:
  - `RegressionResidualChartWidget` (Order plot tab/mode with non-monotonic residual sequence where chord fill would paint solid `#93c5fd` above/below baseline)
  - `CapabilitySixpackWidget` (with >= 6 subgroups in Moving Range / Xbar / R panels)
  - `ControlChartBuilderWidget` (connected subgroup path)
  - `RareEventControlChartWidget` (G / T chart series path)
  - `TimeWeightedControlChartWidget` (CUSUM chart `cusum_plus` / `cusum_minus` paths)
  - `MultivariateChartWidget` (scree / score trajectory open path)
  Verify background pixels far from strokes/markers are canvas background, NOT stale brush fill (`#93c5fd`, `#dbeafe`, `#fcfdfd`, `BLUE_FILL`).

- [ ] **Step 2: Run test to verify failure**
  Run `python -m unittest tests.test_chart_no_chord_fill -v` and confirm chord-fill failures trigger.

- [ ] **Step 3: Reset `Qt.BrushStyle.NoBrush` before every open `drawPath(...)` call in all 6 modules**
  - `regression_residual_chart.py:295`: `p.setBrush(Qt.BrushStyle.NoBrush)` right before `p.drawPath(path)`.
  - `sixpack_chart.py:358,366`: `painter.setBrush(Qt.BrushStyle.NoBrush)` before `painter.drawPath(path_w)` and `painter.drawPath(path_o)`.
  - `control_chart_builder_chart.py:338`: `p.setBrush(Qt.BrushStyle.NoBrush)` before `p.drawPath(path)`.
  - `rare_event_control_chart.py:212`: `painter.setBrush(Qt.BrushStyle.NoBrush)` before `painter.drawPath(path_series)`.
  - `time_weighted_control_chart.py:249,258` (and check any earlier `drawPath`): `painter.setBrush(Qt.BrushStyle.NoBrush)` before CUSUM `path_cp` and `path_cm`.
  - `multivariate_chart.py:458` (and audit every `drawPath` in `multivariate_chart.py`): `painter.setBrush(Qt.BrushStyle.NoBrush)` before every open series path.

- [ ] **Step 4: Run tests to verify pass**
  Run `python -m unittest tests.test_chart_no_chord_fill -v`.

---

### Task 2: Wire Fitted Line Plot `Graphs…`/`Storage…` and `Fit Regression Model` `Results…` Display Controls

**Files:**
- Modify: `statcraft/modern_app.py` (around `6899-6918`, regression / fitted_line_plot tabs & results filtering)
- Modify: `statcraft/fitted_line_plot_dialog.py` (`_apply_storage` to implement `coefficients` storage)
- Modify: `statcraft/regression_dialog.py` (propagate `self.options["results"]` into `self.entry["result"]["options"]`)
- Modify: `statcraft/regression_residual_chart.py` (handle `residuals_type` (`regular`/`standardized`/`deleted`) cleanly)
- Modify: `statcraft/app.py` (`multiple_regression` options parameter & `format_entry` filtering when `results` toggles are False)
- Test: `tests/test_fitted_line_plot_and_regression_options.py`

- [ ] **Step 1: Write failing tests for Fitted Line Plot residual graphs/coefficients storage and Fit Regression Model `results` toggles**
  - Test `FittedLinePlotDialog` with `options['graphs'] = 'four'` and `'fits'`, `options['residuals_type'] = 'standardized'`, `options['storage']['coefficients'] = True` -> verify second tab `"Residual Plots"` exists in `result_tabs`, plots standardized residuals, and stores `COEF1` column in worksheet.
  - Test `FittedLinePlotDialog` with `options['graphs'] = 'none'` -> verify no `"Residual Plots"` tab is added.
  - Test `FitRegressionModelDialog` with `options['results'] = {'equation': False, 'summary': False, 'anova': True, 'unusual': False}` -> verify Report & Text export honor those checkboxes.

- [ ] **Step 2: Run test to verify it fails**
  `python -m unittest tests.test_fitted_line_plot_and_regression_options -v`

- [ ] **Step 3: Implement wiring cleanly**
  - `fitted_line_plot_dialog.py:_apply_storage`: add `coefficients` storage branch writing `res.get("coefficients", [])` (parameter estimates in order) to non-conflicting `COEF1` column (`Column(base_name, "number", vals)`).
  - `regression_residual_chart.py`: read `residuals_type = opts.get("residuals_type", "regular")` and select `residuals` / `std_residuals` / `del_residuals` when present, plus `fitted` or `fits` (`FittedLinePlot` uses `fits` while `multiple_regression` uses `fitted`!).
  - `modern_app.py:show_result`: after adding primary `FittedLinePlotChartWidget` tab (`"Graph"`), when `result.get("options", {}).get("graphs", "four") != "none"`, build a companion `RegressionResidualChartWidget(entry)` inside a second `GraphFrame` tab titled `"Residual Plots"`! (Reuse a clean `_add_graph_tab(chart_widget, entry, tab_title)` helper extracted from the existing boilerplate in `show_result`.)
  - `regression_dialog.py` & `app.py:multiple_regression` & `modern_app.py:show_result`: pass `options=self.options` into `entry["result"]["options"]`; filter out `"Regression Equation"`, `"Model Summary"`, `"Analysis of Variance"`, or `"Fits and Diagnostics for Unusual Observations"` sections in both `format_entry()` and `show_result()` when disabled in `options["results"]`.

- [ ] **Step 4: Run tests to verify pass**
  `python -m unittest tests.test_fitted_line_plot_and_regression_options tests.test_fitted_line_plot -v`

---

### Task 3: Subgroup Control Chart Modes (`Xbar…`/`R…`/`S…`), Simple Regression `(Y, X)` Order, `Edit Last Dialog`, and `_commit_editor()`

**Files:**
- Modify: `statcraft/modern_app.py` (`xbar_r_dialog`, `xbar_s_dialog`, new `xbar_dialog`, `r_chart_dialog`, `s_chart_dialog`, menu wiring with `record_last=True`, `inference_dialog("linear_regression")` labels & argument order, audit custom dialogs for `_commit_editor()` + `self._last_dialog_action`)
- Modify: `statcraft/subgroup_control_dialogs.py` (`BaseSubgroupChartDialog`, `_save_dialog_state`)
- Modify: `statcraft/subgroup_control.py` (`fit_from_worksheet` accepting `'xbar'`, `'r'`, `'s'`, `'xbar_r'`, `'xbar_s'`)
- Modify: `statcraft/subgroup_control_chart.py` (`prepare` rendering single-panel `'xbar'`, `'r'`, or `'s'` when requested instead of always rendering two panels)
- Modify: `statcraft/app.py` (`subgroup_control_chart` title naming & `inference` `linear_regression` signature note)
- Test: `tests/test_subgroup_modes_and_dialog_wiring.py`

- [ ] **Step 1: Write failing tests for:**
  - `chart_type in ('xbar', 'r', 's', 'xbar_r', 'xbar_s')` producing distinct single-panel vs dual-panel `panels` in `subgroup_control_chart.py` and distinct titles (`"Xbar Chart"`, `"R Chart"`, `"S Chart"`).
  - Triggering `Xbar…`, `R…`, `S…`, `Fitted Line Plot…`, `Fit Regression Model…`, `Calculator…`, `Display Descriptive Statistics…` sets `window._last_dialog_action` cleanly so `Ctrl+E` / `edit_last_dialog()` re-opens that exact dialog.
  - Opening any dialog while a table cell editor has uncommitted text commits the edit into `presenter.worksheet` before the dialog validates.
  - `Simple regression…` (`inference_dialog('linear_regression')`) treats first selection as `Y` (response) and second as `X` (predictor).

- [ ] **Step 2: Run test to verify failure**
  `python -m unittest tests.test_subgroup_modes_and_dialog_wiring -v`

- [ ] **Step 3: Implement fixes**
  - In `subgroup_control.py` & `subgroup_control_chart.py`: allow `chart_type in ('xbar_r', 'xbar_s', 'xbar', 'r', 's')`; `'xbar'` uses range-based `A2` estimation (Minitab default for Xbar Chart) and appends only Xbar panel; `'r'` appends only R panel; `'s'` appends only S panel; set proper chart titles in `app.py`.
  - In `modern_app.py`: connect `Xbar…`, `R…`, `S…` actions to dedicated methods (or parameterized callbacks) with `record_last=True` so `Ctrl+E` works; audit Minitab dialog menu items + `_open_*` handlers so every analysis/graph dialog calls `self._commit_editor()` and assigns `self._last_dialog_action`.
  - In `modern_app.py:inference_dialog`: update prompt/note for `linear_regression` to two single selectors or clear order `"First selected column is Y (response); second is X (predictor)"` and swap `[p["indices"][1], p["indices"][0]]` when calling `inference.linear_regression(x, y)`.

- [ ] **Step 4: Run test to verify pass**
  `python -m unittest tests.test_subgroup_modes_and_dialog_wiring -v`

---

### Task 4: Systemic Dark Mode Support Across All Charts & `GraphOptionsPane`

**Files:**
- Create: `statcraft/chart_theme.py`
- Modify: `statcraft/graph_options_pane.py`
- Modify: `statcraft/modern_app.py` (`set_dark_mode` refreshes `graph_options_pane` & active chart/report widgets; `resultCard` dark styling; equation box dark styling if inline)
- Modify: `statcraft/modern_charts.py` and specialized chart widgets (`*_chart.py`, `*_plot*.py`, `sixpack_chart.py`, `capability_chart.py`, `fitted_line_plot_chart.py`, `regression_residual_chart.py`, `imr_chart.py`, `time_series_chart.py`, `subgroup_control_chart.py`, `multivariate_chart.py`, `control_chart_builder_chart.py`, `rare_event_control_chart.py`, `time_weighted_control_chart.py`, `run_chart_plot.py`, `graphical_summary_chart.py`, etc.)
- Test: `tests/test_dark_mode_charts.py`

- [ ] **Step 1: Design & test `chart_theme.py`**
  Rather than brittle regex hacks, design `statcraft/chart_theme.py` with:
  - `is_dark_mode(widget=None) -> bool` checking ancestor window `_dark_mode`, `QSettings` fallback / `QApplication.palette().window().color().lightness() < 128`.
  - `ChartTheme` dataclass providing standard tokens: `bg`, `plot_bg`, `card_bg`, `ink`, `muted`, `grid`, `border`, `accent_blue`, `accent_red`, `accent_green`, `band_fill`, `callout_bg`, `callout_border`.
  - `theme_color(color, is_dark)` that maps light-mode hardcoded chart neutrals (`#ffffff`/`white`/`#fcfdfd`/`#f8fafc` -> dark card/plot `#18181b`/`#1f1f23`, `#000000`/`#111827`/`#1e293b`/`#202020`/`#232a30`/`#263440`/`#1a2b38`/`#333333` -> `#f4f4f5`, muted grays -> `#a1a1aa`, light grid borders -> `#2e2e36`) cleanly via a `ThemedQPainter` or per-chart `chart_theme(self)` helper, preserving vivid colored series!
  - Let's think carefully: `ChartWidget` and specialized chart widgets either adopt `chart_theme(self)` explicitly OR wrap `painter` / inspect `theme = get_chart_theme(self)`. Better yet: update `modern_charts.py` + the core specialized chart files cleanly with `get_chart_theme(self)` AND provide a safety `apply_dark_theme_to_chart_widget` helper or `ThemedQPainter` proxy where needed, plus update `GraphOptionsPane.set_dark_mode(is_dark)`. Actually, auditing all 61 chart `paintEvent`s via script to verify ZERO light-background blinding rectangles remain when `_dark_mode=True` in an automated test (`test_dark_mode_charts.py`) is 100% deterministic! Let's render ALL chart widgets we have constructors for under `_dark_mode=True` and assert the rendered image's corner/background luminance is dark (`< 80`) rather than bright white (`> 240`)!

- [ ] **Step 2: Write failing Dark Mode test (`tests/test_dark_mode_charts.py`)**
  Instantiate window with `set_dark_mode(True)` and verify `GraphOptionsPane`, `ChartWidget`, `FittedLinePlotChartWidget`, `RegressionResidualChartWidget`, `CapabilityPlotWidget`, `IMRChartWidget`, `TimeSeriesChartWidget`, `SubgroupControl`, `RunChartWidget`, `GraphicalSummaryChartWidget`, and at least 20+ other chart widgets render dark backgrounds and light text without white canvas blast.

- [ ] **Step 3: Implement `statcraft/chart_theme.py`, `GraphOptionsPane.set_dark_mode`, `modern_app.set_dark_mode` refresh, and wire theme across chart painters**
  - Ensure `modern_app.set_dark_mode()` updates `graph_options_pane.set_dark_mode(is_dark)` and calls `.update()` / refreshes active result tabs/charts!
  - Apply `get_chart_theme(self)` cleanly across chart modules (`modern_charts.py` + specialized `*_chart*.py` modules). Check if any chart uses `fillRect(..., Qt.GlobalColor.white)` / `QColor("#ffffff")` and replace via `theme.bg` / `theme.plot_bg` / `theme.ink` / `theme.border` / `theme.grid` / `theme.muted` / `theme.card_bg`.

- [ ] **Step 4: Run `tests/test_dark_mode_charts.py` to verify all tested charts pass in both Light Mode and Dark Mode**

---

### Task 5: Make `GraphOptionsPane` Live-Editable on Key Specialized Charts & Gate Unsupported Options Cleanly

**Files:**
- Modify: `statcraft/chart_theme.py` or new small helper in `statcraft/graph_options_helper.py`
- Modify: `statcraft/fitted_line_plot_chart.py`, `statcraft/regression_residual_chart.py`, `statcraft/imr_chart.py`, `statcraft/time_series_chart.py`, `statcraft/subgroup_control_chart.py`
- Modify: `statcraft/graph_options_pane.py` & `statcraft/modern_app.py` (`_setup_graph_frame`)
- Test: `tests/test_graph_options_specialized.py`

- [ ] **Step 1: Write failing test verifying Graph Options changes (`x_label`, `y_label`, `x_min`/`x_max`, `y_min`/`y_max`, `grid_enabled`, `x_ref_line`, `y_ref_line`) actually change output/state on `FittedLinePlotChartWidget` & `IMRChartWidget`, and unsupported sections hide/show capability notice on custom composite widgets (`CapabilitySixpackWidget`, etc.) instead of silent no-ops.**

- [ ] **Step 2: Run test to verify failure**
  `python -m unittest tests.test_graph_options_specialized -v`

- [ ] **Step 3: Implement shared annotation application helper & wire into specialized charts**
  - Create small helper `graph_annotation_overrides(chart, default_x='', default_y='', default_x_range=None, default_y_range=None)` reading `annotation_axes`, `annotation_limits`, `annotation_grid`, `annotation_x_ref`, `annotation_y_ref`, `annotation_positions` + shared `draw_reference_lines(...)`.
  - Wire into `FittedLinePlotChartWidget`, `RegressionResidualChartWidget`, `IMRChartWidget`, `TimeSeriesChartWidget`, and `subgroup_control_chart.py`.
  - Add attribute `supports_axis_options = True/False` on chart widgets (default `True` for `ChartWidget`/`ExpandedChartWidget` and wired charts above, `False` for complex fixed multi-panel dashboards like `CapabilitySixpackWidget`, `CapabilityPlotWidget`, `MultivariateChartWidget`, `NativeOutputChart`) so `GraphOptionsPane.load_entry()` hides X/Y axis scale & ref-line groups (keeping Title/Subtitle/Footnote which work on every `GraphFrame`!) instead of showing silent non-functional inputs.

- [ ] **Step 4: Run test to verify pass**
  `python -m unittest tests.test_graph_options_specialized -v`

---

### Task 6: Clipboard Paste/Copy, Variable Multi-Select Deduplication, Undo Coverage, Duplicate Column Disambiguation, `=Formula` Cell Guidance & Dialog State Persistence

**Files:**
- Modify: `statcraft/app.py` (`paste`, `copy_block`, `set_cell`, `@undoable` on `reorder_worksheets`, `create_definitive_screening_design`, `create_optimal_design`, `subset_worksheet`, `subset_worksheet_by_condition`)
- Modify: `statcraft/modern_app.py` (`copy_cells`, `cut_cells`, `on_cell_changed` `=expr` prompt/feedback, duplicate column warning on rename/paste)
- Modify: `statcraft/variable_dialogs.py` (`ProcedureDialog` multi-select deduping, `_resolve_unique_column` duplicate-name handling, shared `DialogStateMixin` / helpers for saving/restoring custom dialog state)
- Modify: standalone dialogs (`regression_dialog.py`, `fitted_line_plot_dialog.py`, `subgroup_control_dialogs.py`, `normality_dialog.py`, etc.) to persist & restore last inputs for active worksheet
- Test: `tests/test_clipboard_undo_selection.py`

- [ ] **Step 1: Write failing tests for all items in Task 6**
  - `paste` with ragged TSV (`"1\t2\n3\t4\t5\n6"`), formatted numbers (`"$1,234.50"`, `"45.2%"`, `"1,200"`), ISO/US dates (`"2026-01-15"`, `"01/15/2026"` -> column kind `"date"`), headers above text/date columns (`"Dept\tJoined\nOps\t2026-01-15\nQA\t2026-01-16"`), single column & blank interior rows.
  - `copy_cells` when focus is in an output Report `QTableWidget` or `QPlainTextEdit` copies selected text/cells rather than PNG graph image; non-contiguous table selection copies cleanly without throwing `ValueError`.
  - `ProcedureDialog` double-clicking the same variable twice in a multi-select field does not duplicate it (`C1`, not `C1 C1`).
  - `undo()` / `redo()` works for `reorder_worksheets`, `create_definitive_screening_design`, `create_optimal_design`, and `subset_worksheet`.
  - Duplicate column names trigger clear feedback / disambiguation (`C3` ref resolution works unambiguously) instead of silent wrong-column analysis.
  - Entering `=C1*2` directly into a spreadsheet cell detects formula-like syntax and informs/offers Calc > Assign Formula rather than confusing first-timers silently.
  - Re-opening `FittedLinePlotDialog` / `FitRegressionModelDialog` / `XbarRChartDialog` restores previous selections on the same worksheet.

- [ ] **Step 2: Run test to verify failures**
  `python -m unittest tests.test_clipboard_undo_selection -v`

- [ ] **Step 3: Implement all fixes cleanly**
  - Extract `_parse_pasted_scalar(raw)` and `_infer_pasted_column_kind(raw_values)` in `app.py` supporting formatted numbers (`$`, commas, `%`), dates (`model.parse_date`), and smart header detection across numeric/date/text columns. Pad ragged paste rows to `max_width` with `""`.
  - Update `modern_app.py:copy_cells` to inspect `QApplication.focusWidget()` inside `self.result_tabs` (`QTableWidget`, `QPlainTextEdit`, `QTextEdit`, selectable `QLabel`) BEFORE falling back to `copy_output_graph()`, and handle multi-range worksheet selections via bounding-box or union serialization instead of raising `ValueError`.
  - In `variable_dialogs.py`: deduplicate tokens when appending to multi-select line edits; handle duplicate column names explicitly when resolving bare names if ambiguous (prefer exact `C#` token or raise clear disambiguation error referencing `C1`/`C2`, and ensure `variable_selector` lists show `C1  Name`).
  - Add `@undoable` to `reorder_worksheets`, `create_definitive_screening_design`, `create_optimal_design`, `subset_worksheet`, `subset_worksheet_by_condition`.
  - Add gentle non-blocking status bar / info toast when a user types `=EXPR` into a non-text cell (explaining Minitab uses `Calc > Calculator` or `Data > Assign Formula…` and evaluating or offering one-click formula assignment cleanly — even better, prompt if they want to assign it or show clear status hint!). Wait: let's avoid modal popups inside random cell edits during automated tests unless appropriate; showing a clear status bar tip (and offering an optional quick-action or `Edit` prompt when typing `=`) or evaluating safely? Wait: a status bar message `"Tip: StatCraft uses Calc > Calculator… for column formulas (cell stored as text '=...')"` is 100% non-blocking in tests AND immediately educates first-time Excel users! Plus add `set_cell` hint check in `modern_app.py`.
  - Ensure standalone dialogs call `_load_dialog_state()` / `_save_dialog_state()` cleanly using `variable_dialogs._DIALOG_STATE`.

- [ ] **Step 4: Run tests to verify pass**
  `python -m unittest tests.test_clipboard_undo_selection -v`

---

### Task 7: Minitab Parity Upgrades & `.MTW`/`.MPJ` Open Clarity

**Files:**
- Modify: `statcraft/app.py` (`multiple_regression`, `describe_columns`, `assign_formula`, `normality`, `load`)
- Modify: `statcraft/regression.py` & `statcraft/regression_dialog.py` (categorical factors, Model subdialog interactions `A*B` & quadratic `X*X`, VIF/ANOVA/coefficients)
- Create/Modify: `statcraft/descriptive_dialog.py` & `statcraft/modern_app.py` (`Display Descriptive Statistics…` dialog with `Variables`, `By variables`, `Statistics…`, `Graphs…`; render grouped stats + charts in `show_result`)
- Create/Modify: `statcraft/calculator_dialog.py`, `statcraft/formulas.py`, `statcraft/modern_app.py` (rich `Calc > Calculator` picker UI with Variables, Functions, Keypad, `"Assign as a formula"`; allow text/boolean column results from `formulas.recalculate` / `assign_formula`)
- Modify: `statcraft/normality.py`, new or updated `statcraft/normality_dialog.py` & `statcraft/modern_app.py` (`Anderson-Darling`, `Ryan-Joiner`, `Kolmogorov-Smirnov`, percentile lines / title options)
- Modify: `statcraft/updater.py`, `statcraft/modern_app.py`, `statcraft/app.py` (accurate `.MTW`/`.MPJ` vs `.MWX`/`.MPX` messaging & file filter honesty; clear instructions on opening unsupported legacy binary `.mtw`/`.mpj` files)
- Test: `tests/test_minitab_parity_upgrades.py`

- [ ] **Step 1: Write failing tests for all 5 Minitab-parity upgrades**
  - `Fit Regression Model` with categorical factor + interaction + quadratic term (`Y ~ Temp + Catalyst + Temp*Temp + Temp*Catalyst`), producing ANOVA, coefficients with factor levels, equation, R-sq, and optional 4-in-1 residual plots.
  - `Display Descriptive Statistics` with `By variables`, custom `Statistics…` selection (`SEMean`, `Trimmed Mean`, `Variance`, `IQR`, `Skewness`, `Kurtosis`, etc.), and `Graphs…` (`Histogram`, `Histogram w/ normal curve`, `Individual value plot`, `Boxplot`).
  - `Calculator` dialog double-click variable/function insertion, keypad insertion, `"Assign as a formula"` creating formula metadata, AND `assign_formula` + `recalculate` working with `IF(C1 > 5, 'High', 'Low')` without crashing (`kind='text'`).
  - `Normality Test` running all 3 methods (`anderson_darling`, `ryan_joiner`, `kolmogorov_smirnov`) with valid p-values and plots.
  - Attempting to load `sample.mtw` / `sample.mpj` raises `UnsupportedFormatError` with clear guidance explaining legacy binary `.mtw`/`.mpj` vs supported `.mwx`/`.mpx`/`.xlsx`/`.csv`, and `about()` copy accurately lists `.MPX/.MWX` instead of false `.MTW`.

- [ ] **Step 2: Run test to verify failures**
  `python -m unittest tests.test_minitab_parity_upgrades -v`

- [ ] **Step 3: Implement upgrades cleanly, reusing existing engines**
  - **Regression (`regression_dialog.py` + `app.py:multiple_regression`):** Leverage existing `glm.fit` / polynomial basis expansion when categorical predictors or higher-order/interaction terms are present, keeping backward-compatible plain `multiple_regression(response, predictors)` signature intact for existing callers/tests while adding optional `categorical_indices=None, terms=None, options=None`.
  - **Display Descriptive Statistics (`descriptive_dialog.py` + `analyses.py` / `app.py:describe_columns`):** Support `by_indices`, selectable stats checkboxes (computing any missing ones like `variance`, `iqr`, `trimmed_mean`, `skewness`, `kurtosis`, `cv`), grouped tables, and optional companion graph entry (`Histogram`, `Individual Value Plot`, `Boxplot`) via existing chart pipelines!
  - **Calculator + Text Formulas (`calculator_dialog.py`, `formulas.py`, `app.py:assign_formula`):** Detect non-numeric output values (`isinstance(v, str)`) in `recalculate()` and `assign_formula()` -> set `column.kind = 'text'` and coerce non-`None` values via `str(v)`, while numeric-only results stay `kind = 'number'` normalized via `normalize_numeric`. Build clean `CalculatorDialog` with live variable/constant lists, function category/list, numeric/operator keypad, expression preview, and `"Assign as a formula"` checkbox.
  - **Normality Test (`normality.py`, `normality_dialog.py`, `modern_app.py`):** Implement `ryan_joiner` (Blom normal score correlation + Ryan-Joiner critical/p approximation) and `kolmogorov_smirnov` (Lilliefors normal KS test via SciPy/calibrated approximation), plus `NormalityTestDialog` with method radio buttons (`Anderson-Darling`, `Ryan-Joiner`, `Kolmogorov-Smirnov`), percentile lines option, and custom title.
  - **Legacy `.MTW`/`.MPJ` Honest Messaging (`app.py:load`, `modern_app.py`, `updater.py`):** Update `app.py:load` to give a specific helpful message for `.mtw`/`.mpj` (`"Legacy binary Minitab .mtw/.mpj files use a proprietary closed binary format. In Minitab, save/export as .mwx (worksheet), .mpx (project), .xlsx, or .csv to open in StatCraft."`), fix `about()` in `modern_app.py` to say `.MPX/.MWX` instead of `.MTW`, and audit `updater.py` legacy `.mtw` file association comments/entries so `.mwx`/`.mpx`/`.statcraft` are registered accurately without broken `.mtw` promise.

- [ ] **Step 4: Run test & full test suite verification**
  `python -m unittest tests.test_minitab_parity_upgrades -v`
  Then run the full `tests/` suite to verify zero regressions!
