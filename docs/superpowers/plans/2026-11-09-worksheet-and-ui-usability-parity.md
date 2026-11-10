# Worksheet & UI Usability Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate 10 critical usability and muscle-memory disconnects in StatCraft's worksheet, dialogs, editing, and output copy behaviors so that the desktop user experience flawlessly matches expected spreadsheet and statistical software standards (Minitab/Excel/JMP parity).

**Architecture:** Pure local desktop Python/PySide6 architecture. Enhance `statcraft/app.py`, `statcraft/variable_dialogs.py`, `statcraft/modern_worksheet.py`, `statcraft/modern_app.py`, and create `statcraft/autofill_engine.py`.

**Tech Stack:** Python 3.11+, PySide6 (Qt6), NumPy, unittest.

---

## Tasks

- [ ] **Task 1: Smart Paste with Header Detection & Auto-Typing**
  - Detect headers on clipboard paste.
  - Preserve numeric column types when pasting tabular data.
  - Test: `tests/test_smart_paste.py`

- [ ] **Task 2: Dialog Auto-Advance on Single-Variable Selection**
  - Advance focus to next selector field upon double-clicking single variable.
  - Test: `tests/test_dialog_auto_advance.py`

- [ ] **Task 3: Universal Dialog State Memory for Ctrl+E (Edit Last Dialog)**
  - Store and restore dialog parameters across all procedures in `ProcedureDialog`.
  - Test: `tests/test_dialog_state_memory.py`

- [ ] **Task 4: Full Column Selection & Entire-Column Clear Across Pages**
  - Ensure clearing a selected column clears the entire column length, not just the visible page.
  - Test: `tests/test_full_column_clear.py`

- [ ] **Task 5: Keyboard Shortcuts for Column & Row Selection (Ctrl+Space, Shift+Space)**
  - Add `Ctrl+Space` for full column selection and `Shift+Space` for full row selection.
  - Test: `tests/test_selection_shortcuts.py`

- [ ] **Task 6: Graceful Numeric Missing Sentinels (NA, N/A, NaN, None, -, .) & Type Conversion**
  - Expand `parse_cell` for numbers to accept standard missing sentinels as `None`.
  - Prompt or convert column to Text if user types non-numeric text into a populated column.
  - Test: `tests/test_missing_sentinels.py`

- [ ] **Task 7: Global Replace… (Ctrl+H) on Edit Menu**
  - Register `Replace…` with `Ctrl+H` shortcut on the main Edit menu.
  - Test: `tests/test_find_replace_menu.py`

- [ ] **Task 8: Direct Right-Click Column Sort (Top-Level Menu Parity)**
  - Promote `Sort Smallest to Largest` and `Sort Largest to Smallest` to top level of worksheet context menu.
  - Test: `tests/test_column_sort_menu.py`

- [ ] **Task 9: 1-Click "Copy Table" (Formatted TSV for Excel/Word)**
  - Add context menu and button on output cards to copy clean TSV with column headers for instant Excel paste.
  - Test: `tests/test_copy_table_tsv.py`

- [ ] **Task 10: Auto-Fill / Drag-to-Fill Sequence Engine**
  - Create `statcraft/autofill_engine.py` for linear numeric, step, factor cycle, and prefixed sequences.
  - Add **Data > Autofill / Extend Series…**.
  - Test: `tests/test_autofill_engine.py`
