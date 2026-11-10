# Implementation Plan: 10 Make-or-Break App-Wide Usability Fixes (Outside Worksheet)

Date: 2026-11-09  
Target: StatCraft Desktop UI (Dialogs, Navigator, Graphs, Menus, File Management)  
Architecture: Pure offline Python 3.11+ / PySide6 / NumPy / SciPy  

---

## 1. Task 1: Delete Output Entry from Project / Session
- **Problem**: Output cards and graphs could never be deleted from a project session, cluttering projects permanently. Engine has `Presenter.delete_result(entry)`, but no UI was wired.
- **Files**: `statcraft/modern_app.py`
- **Fix**: Add `delete_output_entry(self, entry=None)` with confirmation dialog, removing entry from presenter history, refreshing Navigator, and switching active view. Add "Delete Output\tDel" to output context menu.
- **Test**: `tests/test_delete_output_entry.py`

## 2. Task 2: Navigator Keyboard Parity (`F2` to Rename, `Delete` to Delete)
- **Problem**: In Navigator tree, pressing `F2` or `Delete` does nothing.
- **Files**: `statcraft/modern_app.py`
- **Fix**: Subclass or event filter on `self.navigator`:
  - `F2`: triggers `rename_sheet_action` (if sheet) or `rename_output_dialog` (if result).
  - `Delete`: triggers `delete_output_entry` (if result).
- **Test**: `tests/test_navigator_keys.py`

## 3. Task 3: Column Range Expansion in Variable Dialogs (`C1-C5`)
- **Problem**: Typing `C1-C5` or `C1 - C5` in variable selector fields failed with `ValueError: Unknown or ambiguous column: C1-C5`.
- **Files**: `statcraft/variable_dialogs.py` (`_variable_tokens` or `resolve_variables`)
- **Fix**: Detect `C<start>-C<end>` syntax and expand to sequential column indices `range(start, end + 1)`.
- **Test**: `tests/test_column_range_expansion.py`

## 4. Task 4: Dialog "Reset" Button & `F3` Shortcut
- **Problem**: `ProcedureDialog` had no Reset button; users had to manually clear fields.
- **Files**: `statcraft/variable_dialogs.py`
- **Fix**: Add "Reset" button (`QDialogButtonBox.StandardButton.Reset`) and wire `F3` key to `reset_dialog()`, restoring selectors and fields to initial blank/default state and clearing errors.
- **Test**: `tests/test_dialog_reset.py`

## 5. Task 5: Column Filter Box in Variable Selection Dialogs
- **Problem**: Wide datasets (50+ columns) required manual scrolling through the Available variables list.
- **Files**: `statcraft/variable_dialogs.py`
- **Fix**: Add a search input `QLineEdit` ("Filter variables...") above `self.available` that dynamically shows/hides items matching typed text.
- **Test**: `tests/test_dialog_variable_filter.py`

## 6. Task 6: Recent Projects Menu (`File > Open Recent`)
- **Problem**: StatCraft lacked a Recent Projects menu, requiring manual file browsing on every launch.
- **Files**: `statcraft/modern_app.py`
- **Fix**: Maintain a persistent list of the last 10 opened project paths via `QSettings`. Add `File > Open Recent` submenu with clickable entries and "Clear Recent Projects". Add paths on `load_path` and `save_path`.
- **Test**: `tests/test_recent_projects_menu.py`

## 7. Task 7: Direct `Ctrl+C` on Graphs
- **Problem**: Pressing `Ctrl+C` while inspecting or focusing a graph widget tried to copy worksheet cells instead of copying the chart image.
- **Files**: `statcraft/modern_app.py` (`copy_cells`)
- **Fix**: In `copy_cells()`, check if an output chart or graph frame has focus or is the active view; if so, delegate to `self.copy_output_graph()`.
- **Test**: `tests/test_graph_copy_shortcut.py`

## 8. Task 8: 1-Click "Copy as SVG" on Graph Context Menu
- **Problem**: Right-clicking a graph only offered raster "Copy as Picture". Crisp vector SVG export was only on the top Edit menu.
- **Files**: `statcraft/modern_app.py` (`_show_output_context_menu`)
- **Fix**: Add "📋 Copy Lossless Vector Graphic (SVG)" directly to the graph context menu.
- **Test**: `tests/test_graph_context_svg.py`

## 9. Task 9: Dialog Validation Auto-Focus on Invalid Field
- **Problem**: When dialog validation failed, the error text was shown but focus remained unchanged, requiring manual mouse clicks.
- **Files**: `statcraft/variable_dialogs.py` (`validate`)
- **Fix**: When an exception occurs during validation, extract the offending field key, set focus to its control, and call `selectAll()`.
- **Test**: `tests/test_dialog_error_focus.py`

## 10. Task 10: Auto-Select All Text on Focus in Selector Fields
- **Problem**: Clicking or tabbing into a variable selector field left the cursor at the end, causing typed replacement characters to append to old text.
- **Files**: `statcraft/variable_dialogs.py` (`VariableEntry`)
- **Fix**: In `VariableEntry.focusInEvent`, call `self.selectAll()` so typing a new variable name cleanly replaces previous text.
- **Test**: `tests/test_variable_entry_select_all.py`
