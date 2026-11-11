# StatCraft Systematic Bug Hunt & Squash Plan (`v116.4.0`)

> **For agentic workers:** Executed under `superpowers:writing-plans`, `superpowers:test-driven-development`, and `superpowers:verification-before-completion`. Every bug below must first have a failing regression test in `tests/test_phase9_bug_hunt_squash.py` (RED), be fixed at its root cause (GREEN), and pass all targeted Phase 1–9 + regression suites before release.

**Goal:** Eliminate 10 verified edge-case, numerical, UI/session, chart, and calculator bugs discovered across StatCraft and ship release `v116.4.0`.

**Tech Stack:** Python 3, NumPy, SciPy, PySide6 (`QT_QPA_PLATFORM=offscreen`), `unittest`.

---

## Bug Inventory & Root-Cause Architecture

1. **REML Linear Mixed Model Singular Matrix Crash** ([`statcraft/mixed_reml.py`](../../../statcraft/mixed_reml.py#L128-L158))
   - **Root cause:** Collinear fixed predictors (e.g., `X2 = 2 * X1`) make `XtVinvX` singular. Inside `_reml_objective`, `cholesky(XtVinvX)` returns `1e18` penalty cleanly, but at lines 153–155 `np.linalg.inv(V)` and `np.linalg.inv(XtVinvX)` raise unhandled `np.linalg.LinAlgError`.
   - **Fix:** Inside `_reml_objective`, if `cholesky(XtVinvX)` fails on rank deficiency, regularize cleanly with tiny ridge (`1e-8 * scale * np.eye(p)`) or compute `slogdet` of regularized `XtVinvX` so L-BFGS-B still converges on variance components; at final solve (lines 153–156), compute `V_inv` and `cov_beta` via `np.linalg.inv` with `np.linalg.pinv` fallback on `LinAlgError`.

2. **`ModernWindow._call` Unhandled `LinAlgError`** ([`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L2006))
   - **Root cause:** `_call`'s exception handler catches `(ValueError, TypeError, IndexError, KeyError, ArithmeticError, OSError, ImportError)` but omits `np.linalg.LinAlgError`, allowing any linear-algebra failure to escape as an unhandled crash in the UI.
   - **Fix:** Add `np.linalg.LinAlgError` to the caught exception tuple in `_call`.

3. **Session Command `LET C<k> = expr` Crash on New Columns & Missing Undo** ([`statcraft/session_commands.py`](../../../statcraft/session_commands.py#L190-L198), [`statcraft/app.py`](../../../statcraft/app.py#L780-L802))
   - **Root cause:** `LET C5 = C1 * 2` on a 4-column worksheet delegates to `presenter.calculate`, which rejects non-existent `C<k>` indices with `ValueError("Choose an existing column number...")`. Additionally, `assign_formula` (`app.py:7030`) and `SET` session assignment lack `@undoable`.
   - **Fix:** Update `Presenter.calculate` so numeric/`C<k>` targets `>= len(columns)` expand columns cleanly (padding intermediate blank columns if needed, honoring `MAX_CELLS`), and decorate `Presenter.assign_formula` with `@undoable`. Route `SET` through an `@undoable` presenter helper (or `@undoable` helper call) as well.

4. **`ModernWindow.run_command_line` Erases Script on Error** ([`statcraft/modern_app.py`](../../../statcraft/modern_app.py#L3191-L3202))
   - **Root cause:** `self.command_editor.clear()` executes unconditionally even when `_call(...)` returns `None` due to a syntax or runtime error, wiping out the user's typed script.
   - **Fix:** Clear `self.command_editor` only when command execution succeeds (`entries is not None`).

5. **Cross-Model `Run Comparator` Misses Canonical Accuracy/Error Deltas** ([`statcraft/run_comparator.py`](../../../statcraft/run_comparator.py#L20-L75))
   - **Root cause:** Different model families nest identical evaluation concepts under different paths (`oob_metrics.r2`, `val_metrics.r2`, `metrics.r2`, `r_squared`, etc.), yielding zero shared scalar comparison rows across heterogeneous models (e.g., Regression vs Random Forests vs TreeNet vs MARS).
   - **Fix:** Emit canonical flattened metrics (`Canonical R2`, `Canonical Rmse`, `Canonical Mae`, `Canonical Accuracy`, `Canonical Roc Auc`, `Canonical Log Loss`) in `_flatten_scalars` and register their optimization directions in `METRIC_DIRECTIONS`.

6. **Warranty Analysis `RankWarning` & Nonsense Extrapolation on Duplicate Ages** ([`statcraft/survival_advanced.py`](../../../statcraft/survival_advanced.py#L197-L216))
   - **Root cause:** `warranty_analysis` passes unmerged duplicate age entries directly into `np.polyfit`, producing `RankWarning` and nonsensical Weibull parameters (`shape=0.1, scale=7.8e7`) when all observations share the same age.
   - **Fix:** Aggregate failure counts by unique positive age prior to Kaplan-Meier / Weibull rank regression, and raise a clear `ValueError` when fewer than 2 distinct positive ages remain.

7. **Monte Carlo Constant Output Emits `ConstantInputWarning`** ([`statcraft/monte_carlo.py`](../../../statcraft/monte_carlo.py#L204-L208))
   - **Root cause:** Constant simulation outputs or degenerate inputs pass zero-variance arrays directly to `scipy.stats.spearmanr`, triggering `ConstantInputWarning` warnings.
   - **Fix:** Check `np.std(y) > 1e-12 and np.std(draws) > 1e-12` before calling `stats.spearmanr`, defaulting correlation to `0.0` cleanly without warnings.

8. **`PrintController.snapshot` Missing Event-Loop Flush on Entry Switch** ([`statcraft/printing.py`](../../../statcraft/printing.py#L154-L159))
   - **Root cause:** Switching `w.show_result(entry)` and immediately capturing `w._active_graph_frame.capture().toImage()` skips `QApplication.processEvents()`, risking stale or unlaid-out frame captures during export/print.
   - **Fix:** Call `QApplication.processEvents()` after `w.show_result(entry)` when switching entries prior to `capture()`.

9. **AutoML Leaderboard Chart Hides Negative Validation R²** ([`statcraft/phase6_charts.py`](../../../statcraft/phase6_charts.py#L148-L160), [`statcraft/phase6_charts.py`](../../../statcraft/phase6_charts.py#L284-L329))
   - **Root cause:** `prepare` clamps negative `val_r2` via `max(0.0, ...)`, causing negative validation R² models to display `"0%"` instead of their signed score.
   - **Fix:** Preserve signed values in `prepare` for `discover_best_model`, clamp only the drawn positive bar width inside `_draw_barh` (`max(2.0, (max(0.0, val) / vmax) * plot.width())`, distinct `#dc2626` accent when negative), and keep the true signed label (`-15%`).

10. **Calculator Missing `ZSCORE` / `STANDARDIZE` & `LAG` Functions + Zero-Stdev Guard** ([`statcraft/calculator.py`](../../../statcraft/calculator.py#L123-L453))
    - **Root cause:** Column-level transforms `ZSCORE(C1)` / `STANDARDIZE(C1)` and `LAG(C1[, k])` are missing from `evaluate_advanced`, and constant-column standardization risks division by zero.
    - **Fix:** Add `ZSCORE` / `STANDARDIZE` (returning `None` per row when column stdev is 0 or row value is `None`) and `LAG(C1[, k=1])` (supporting positive lag or negative lead integer offset, returning `None` when shifted out-of-bounds or missing) cleanly to AST validation and evaluation.

---

## Execution Steps

- **Step 1 (RED):** Create `tests/test_phase9_bug_hunt_squash.py` testing all 10 bugs and run `unittest` to confirm all new tests fail on unpatched code.
- **Step 2 (GREEN):** Apply minimal, non-duplicated root-cause edits to the 9 source files and re-run `tests/test_phase9_bug_hunt_squash.py` until 100% green.
- **Step 3 (Version Bump):** Update version `116.3.0` -> `116.4.0` across `pyproject.toml`, `statcraft/__init__.py`, `statcraft/updater.py`, `statcraft/svg_html_export.py`, `StatCraft.spec`, `app_version.txt`, `installer_version.txt`, and version assertions in `tests/test_phase5_monte_carlo_and_release.py` and `tests/test_phase6_charts_r_and_sessions.py`.
- **Step 4 (Verification):** Run all Phase 1–9 suites plus core regression suites (`test_calculator.py`, `test_run_comparator.py`, `test_data_doctor.py`, `test_connect_advanced.py`, `test_app_contract.py`, `test_missing_sentinels.py`, `test_mpx_text_create.py`, `test_mpx_columns.py`, `test_mpx_create.py`).
- **Step 5 (Release):** Commit, tag `v116.4.0`, and push `main` + tag to `origin`.
