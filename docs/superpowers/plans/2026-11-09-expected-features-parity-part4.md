# Implementation Plan: 10 Expected Features Parity (Part 4)

Date: 2026-11-09  
Target: StatCraft Full Desktop Experience  
Architecture: Pure offline Python 3.11+ / PySide6 / NumPy / SciPy  

---

## 1. Task 1: Find inside Session Output / ReportPad (`Ctrl+F` Context Sensitivity)
- **Problem**: When viewing the ReportPad or Session Output pane, pressing `Ctrl+F` opened the worksheet cell finder instead of searching text in the output.
- **Files**: `statcraft/modern_app.py`
- **Fix**: In `find_dialog()`, if focus is in `self._report_pad_editor` or `self.result_tabs`, search the output text / ReportPad using `find()`.
- **Test**: `tests/test_find_in_output.py`

## 2. Task 2: Export All Graphs from Project (`File > Export All Graphs…`)
- **Problem**: Users with multiple graphs had to right-click and save each graph one by one.
- **Files**: `statcraft/modern_app.py`
- **Fix**: Add `export_all_graphs_dialog(self)` under `File > Export All Graphs…` which iterates all graph entries in `self.presenter.history`, saving them into a selected directory as PNG/SVG.
- **Test**: `tests/test_export_all_graphs.py`

## 3. Task 3: Scalable Vector Graphics (SVG) in `Save Graph As…` Dialog
- **Problem**: `save_graph_as()` only offered PNG or TXT in the file filter, omitting SVG export.
- **Files**: `statcraft/modern_app.py` (`save_graph_as`)
- **Fix**: Add SVG format filter to `QFileDialog.getSaveFileName` and save vector SVG if chosen.
- **Test**: `tests/test_save_graph_as_svg.py`

## 4. Task 4: Duplicate Column (`Data > Duplicate Column…` & Column Context Menu)
- **Problem**: No 1-click action to duplicate/clone a column for testing transformations while preserving raw data.
- **Files**: `statcraft/app.py`, `statcraft/modern_app.py`
- **Fix**: Implement `Presenter.duplicate_column(col_index)` and wire **Duplicate Column** into the column header context menu and **Data** menu.
- **Test**: `tests/test_duplicate_column.py`

## 5. Task 5: Multi-Column Sorting
- **Problem**: `sort_columns()` only supported a single sort column. Multi-level sorting (e.g. Sort by Batch then by Temp) was impossible.
- **Files**: `statcraft/app.py` (`sort_columns`), `statcraft/modern_app.py`
- **Fix**: Support passing a list/tuple of column indices to `sort_columns()`, sorting rows by multi-column tuple keys.
- **Test**: `tests/test_multi_column_sort.py`

## 6. Task 6: Clear All Session Output (`Edit > Clear Session Output`)
- **Problem**: Users could not clear/reset the session history without restarting the app.
- **Files**: `statcraft/modern_app.py`
- **Fix**: Add `clear_session_output(self)` with confirmation, resetting `presenter.history` and showing welcome screen.
- **Test**: `tests/test_clear_session_output.py`

## 7. Task 7: Duplicate Worksheet from Tab Context Menu
- **Problem**: Worksheet tab right-click menu had New, Rename, Delete, but was missing Duplicate Worksheet.
- **Files**: `statcraft/modern_app.py` (`_worksheet_menu`)
- **Fix**: Add `self.duplicate_sheet_action` to the tab right-click context menu.
- **Test**: `tests/test_tab_duplicate_menu.py`

## 8. Task 8: Column Description / Formula in Column Header Tooltip
- **Problem**: Hovering over column headers only showed generic text, hiding column formulas or user descriptions.
- **Files**: `statcraft/modern_app.py` (`refresh`)
- **Fix**: In `refresh()`, include formula and description in header tooltips for instant inspection.
- **Test**: `tests/test_column_header_tooltips.py`

## 9. Task 9: Keyboard Output Tab Navigation (`Ctrl+Tab` / `Ctrl+Shift+Tab`)
- **Problem**: Switching between output cards required mouse clicks on tabs or Navigator.
- **Files**: `statcraft/modern_app.py`
- **Fix**: Add shortcuts `Ctrl+Tab` and `Ctrl+Shift+Tab` to cycle forward and backward through output tabs.
- **Test**: `tests/test_output_tab_navigation.py`

## 10. Task 10: Clear All Cell Formats Across Selected Columns
- **Problem**: Clearing cell formats only cleared cell selections on visible rows.
- **Files**: `statcraft/modern_app.py` (`build_worksheet_context_menu`)
- **Fix**: When columns are selected (`_selected_columns`), "Clear Formats" wipes highlights and comments across all rows in those columns.
- **Test**: `tests/test_clear_formats_full_column.py`
