# Minitab UX Parity Round 2 — Implementation Plan

1. **Task 1: Output Report `Ctrl+F` / `F3` Search, Navigator Filter & `tab_corner_widget` Chrome**
   - Files: `statcraft/modern_app.py`, `tests/test_round2_report_nav_precision.py`
   - TDD: Write failing unit tests covering Navigator filtering (matching child hides non-matching siblings while keeping parent sheet visible; clearing restores all), `Ctrl+F` / `_find_in_report_query` cycling across `QLabel` and `QTableWidget` inside `"Report"` tab, and `tab_corner_widget` fixed height/alignment.
   - Implement `self.navigator_filter`, `self._apply_navigator_filter()`, `self._find_in_report_widget` + `_find_in_report_dialog`, and `tab_corner_widget` sizing.

2. **Task 2: Result-Table Decimal Places Quick-Toggle**
   - Files: `statcraft/modern_app.py`, `tests/test_round2_report_nav_precision.py`
   - TDD: Write failing test verifying numeric cell `UserRole` metadata, `set_result_table_decimals(table, decimals)` / step delta, reset to default, and clipboard copy using formatted precision.
   - Implement numeric metadata retention in `_result_table` and the `"Decimal Places"` context submenu + helper methods.

3. **Task 3: 2D Interactive Chart Zoom/Pan & Legend Toggle**
   - Files: `statcraft/modern_charts.py`, `statcraft/graph_interaction.py`, `tests/test_round2_chart_interaction_and_fill.py`
   - TDD: Write failing tests verifying `wheelEvent` zooms `_zoom2d_limits` for a scatter chart, pan shifts bounds cleanly, `reset_2d_zoom()` clears overrides, and clicking a legend rect toggles series visibility while retaining clickable strikethrough legend hit target.
   - Implement per-panel `_zoom2d_limits` tracking + wheel zoom + drag pan + `"Reset Zoom"` badge + legend click toggle in `ChartWidget` / `GraphInteractionMixin`.

4. **Task 4: Worksheet Mouse Drag-Fill Handle**
   - Files: `statcraft/modern_worksheet.py`, `statcraft/app.py`, `statcraft/modern_app.py`, `tests/test_round2_chart_interaction_and_fill.py`
   - TDD: Write failing tests verifying fill handle rect presence on active cell/selection, drag-fill down fills `1.0, 2.0 -> 3.0, 4.0, 5.0` and `"Sample 1", "Sample 2" -> "Sample 3"`, and `undo()` restores blanks in one step.
   - Implement fill-handle paint/hit-test/drag preview in `WorksheetDelegate` / `WorksheetTable`, `fill_range_from_handle` on `ModernWindow`, and single undoable step on `Presenter`.

5. **Task 5: Version Bump (`118.0.0`), Full Suite & PyInstaller Build Verification, Release `v118.0.0`**
   - Bump version from `117.0.0` -> `118.0.0` across updater/spec/version files and verify `test_version_bump.py` + Round 1 & Round 2 suites + full test discovery pass with `EXIT=0`.
   - Build `StatCraft.spec` and `installer.spec` locally via PyInstaller with 0 errors.
   - Commit, tag `v118.0.0`, push to `origin`, and create GitHub Release `v118.0.0`.
