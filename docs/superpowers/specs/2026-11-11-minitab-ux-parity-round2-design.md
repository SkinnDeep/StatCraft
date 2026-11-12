# Minitab UX Parity Round 2 — Design Spec

Date: 2026-11-11
Scope: Second iterative pass of first-timer UX gaps and Minitab 22 interaction parity inside `work/statcraft`, following `brainstorming` -> `writing-plans` -> `test-driven-development` -> `verification-before-completion`.

## Goals
1. **Output Pane Navigation, Report Search & Chrome Polish (`statcraft/modern_app.py`)**
   - Add a live filter `QLineEdit` (`self.navigator_filter`) directly below the Navigator header so users with large workbooks can filter Navigator worksheets and results interactively, preserving parent worksheet visibility whenever any child result matches.
   - Extend `Ctrl+F` (`find_dialog`) and `F3` (`find_next`) so they also search `"Report"` (`OutputZoomView` / `QScrollArea`) tabs containing `QLabel` and `QTableWidget` widgets — highlighting matched items/tables, scrolling them into view, stepping next/previous across matches, and reporting match counts on the status bar.
   - Polish `self.tab_corner_widget` in `result_tabs` (`setFixedHeight(26)`, vertically centered layout, crisp compact spacing) so `"Copy R"`, dropdown, and close controls never misalign or clip against the tab bar.

2. **Result-Table Decimal Precision Quick-Toggle (`statcraft/modern_app.py`)**
   - Store numeric float values in `Qt.ItemDataRole.UserRole` on numeric `QTableWidgetItem`s created in `_result_table` along with default text (`Qt.ItemDataRole.UserRole + 1`).
   - Add a `"Decimal Places"` submenu to the `_result_table` right-click context menu (`Increase (+1)`, `Decrease (-1)`, `Reset Default`, `0`, `2`, `3`, `4`, `6` decimal places) that reformats numeric table cells dynamically while preserving TSV/HTML clipboard fidelity of the displayed precision.

3. **2D Interactive Chart Zoom/Pan & Legend Toggle (`statcraft/modern_charts.py`, `statcraft/graph_interaction.py`)**
   - Add smooth 2D mouse-wheel zoom anchored around cursor position (for continuous numeric non-box, non-categorical panels) and Alt+drag / Middle-drag / Shift+pan panning via per-panel `_zoom2d_limits`, merged inside `ChartWidget._axes` without overwriting static `annotation_limits`.
   - Render a subtle `"Reset Zoom"` clickable badge when zoomed and allow `reset_2d_zoom()` (and clicking the badge or toolbar/context reset) to restore auto bounds cleanly.
   - Allow clicking clickable legend items (`remember_rect('s'+idx, ...)`) in `multi_scatter` (and shared legend helpers) to toggle series visibility via `_hidden_legend_series`, drawing hidden legend entries dimmed/strikethrough rather than erasing the legend hit target so a second click cleanly restores the series.

4. **Worksheet Mouse Drag-Fill Handle (`statcraft/modern_worksheet.py`, `statcraft/app.py`, `statcraft/modern_app.py`)**
   - Render an Excel/Minitab-style bottom-right fill handle square on the active selection boundary in `WorksheetDelegate.paint` and expose a `fill_handle_rect()` hit test helper on `WorksheetTable`.
   - Dragging from the fill handle downwards (or rightwards/upwards) previews the target fill rectangle and on release fills the extended range in a single `@undoable` command backed by `autofill_engine.autofill_sequence` (`Presenter.fill_range` / `Presenter.autofill_column`), supporting both numeric trends (`1, 2 -> 3, 4, 5`) and patterned text (`Item 1, Item 2 -> Item 3`).
