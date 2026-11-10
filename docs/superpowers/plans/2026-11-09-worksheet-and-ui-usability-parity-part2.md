# Implementation Plan: 10 Make-or-Break Worksheet & UI Usability Fixes (Part 2)

Date: 2026-11-09  
Target: StatCraft Desktop UI & Worksheet Engine  
Architecture: Pure offline Python 3.11+ / PySide6 / NumPy / SciPy  

---

## 1. Task 1: Missing Cell Editing Pre-Populates with Empty Text
- **Problem**: When a numeric cell is `None` (displays `*`), editing opens `QLineEdit` with `*` inside it. The user has to backspace out the asterisk.
- **File**: `statcraft/modern_worksheet.py` (`WorksheetDelegate.setEditorData`)
- **Fix**: In `setEditorData`, if `editor.text() == "*"` and index corresponds to a numeric missing value (or text is `*`), call `editor.setText("")` so the editor is cleanly empty.
- **Test**: `tests/test_missing_cell_editor.py`

## 2. Task 2: Double-Click Column Header Divider to Auto-Fit Width
- **Problem**: Universal desktop shortcut double-clicking column header divider (`sectionHandleDoubleClicked`) is not connected.
- **File**: `statcraft/modern_app.py`
- **Fix**: Connect `self.col_header_view.sectionHandleDoubleClicked.connect(self.auto_fit_column_width)`. Implement `auto_fit_column_width(col_index)` calculating max width based on header text, column name row, and cells in column, then applying `setColumnWidth()`.
- **Test**: `tests/test_autofit_column_width.py`

## 3. Task 3: Instant Status Bar Selection Summary (`Sum`, `Average`, `Count`, `Min`, `Max`)
- **Problem**: Highlighting cells in Excel/Minitab shows `Average: X | Count: Y | Sum: Z` on status bar. StatCraft has no instant selection stats.
- **File**: `statcraft/modern_app.py`
- **Fix**: Add `_update_selection_status()` called from `_sync_selection_highlights()`. If 2 or more numeric cells are selected, calculate sum, mean, count, min, and max, and display in status bar permanent/temporary label: `Sum: ... | Mean: ... | Count: ... | Min: ... | Max: ...`.
- **Test**: `tests/test_selection_status_summary.py`

## 4. Task 4: "Copy with Column Names" (`Ctrl+Shift+C`)
- **Problem**: `Ctrl+C` only copies raw data. Users pasting into Excel/Word require column headers.
- **File**: `statcraft/modern_app.py`
- **Fix**: Add `copy_with_column_names(self)` method and wire to `Ctrl+Shift+C` and the right-click worksheet context menu. Prepends tab-separated column names to the copied TSV block.
- **Test**: `tests/test_copy_with_column_names.py`

## 5. Task 5: `Backspace` Key on Cell (Clear & Immediately Enter Inline Edit Mode)
- **Problem**: `Delete` clears cells without editing; `Backspace` should clear cell and immediately enter edit mode. Currently Backspace is ignored.
- **File**: `statcraft/modern_worksheet.py` (`WorksheetTable.event`)
- **Fix**: In `WorksheetTable.event`, if `key == Qt.Key.Key_Backspace` without modifiers: clear current cell and call `self.editItem(item)`.
- **Test**: `tests/test_backspace_cell_edit.py`

## 6. Task 6: Type-Over Cell Entry
- **Problem**: In Minitab and Excel, typing a printable character on a focused cell overwrites the cell and starts editing with that key.
- **File**: `statcraft/modern_worksheet.py` (`WorksheetTable.event`)
- **Fix**: If an unhandled printable key (e.g. `event.text()` is non-empty and printable, without Ctrl/Alt) is pressed on a selected cell, start editing and pass the typed text to the editor.
- **Test**: `tests/test_type_over_cell.py`

## 7. Task 7: Full-Dataset `Ctrl+A` / Select All Across All Pages
- **Problem**: `self.table.selectAll()` only marks items on the current 300-row page.
- **File**: `statcraft/modern_app.py`
- **Fix**: Implement `select_all_dataset(self)` which sets `_selected_columns = set(range(len(columns)))` and selects all table rows, ensuring `copy`, `clear`, and `delete` operate on the full dataset across all pages.
- **Test**: `tests/test_select_all_dataset.py`

## 8. Task 8: Drag-to-Reorder Worksheet Tabs
- **Problem**: Worksheet tabs at bottom of workbook are static and cannot be dragged to reorder.
- **File**: `statcraft/worksheet_tab_strip.py`, `statcraft/modern_app.py`
- **Fix**: Set `self.tabs.setMovable(True)` and connect `tabMoved(int, int)` to reorder worksheets in `presenter.native_project` and update tabs.
- **Test**: `tests/test_tab_reordering.py`

## 9. Task 9: Transpose Columns with Mixed Types
- **Problem**: `statcraft/data_prep.py` crashes with `ValueError("Transpose columns of the same data type.")` if columns have mixed types.
- **File**: `statcraft/data_prep.py` (`transpose`)
- **Fix**: Coerce mixed types to `"text"` so transposing mixed columns completes smoothly.
- **Test**: `tests/test_transpose_mixed_types.py`

## 10. Task 10: 1-Click "Subset Worksheet by Selection"
- **Problem**: In Minitab, right clicking a cell with value `"Batch 1"` offers **Subset Worksheet by Selection ("Batch 1")** in 1 click. StatCraft required full dialog navigation.
- **File**: `statcraft/modern_app.py`
- **Fix**: Add "Subset Worksheet by '<Value>'" to worksheet cell context menu when right-clicking a cell, filtering rows matching that cell's value into a new worksheet.
- **Test**: `tests/test_subset_by_selection.py`
