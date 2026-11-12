import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow


def _app():
    return QApplication.instance() or QApplication(sys.argv)


class WorksheetErgonomicsRound1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _app()

    def test_status_summary_paginated_and_text_columns(self):
        vals_num = [float(i) for i in range(1, 351)]  # spans > PAGE_SIZE (300)
        vals_txt = ["A", "B", "C"] + [None] * 347
        ws = Worksheet(
            "PaginatedSheet",
            [
                Column("X", "number", vals_num),
                Column("Batch", "text", vals_txt),
            ],
        )
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        win.select_worksheet_column(0)
        summary = win.status_selection_summary.text()
        self.assertIn("Count: 350", summary)
        self.assertIn("Sum: 61425", summary)
        self.assertIn("Mean: 175.5", summary)
        self.assertIn("Min: 1", summary)
        self.assertIn("Max: 350", summary)

        win.select_worksheet_column(1)
        summary_txt = win.status_selection_summary.text()
        self.assertIn("Count: 3", summary_txt)
        win.close()

    def test_ctrl_arrow_block_edge_navigation_across_gaps_and_pages(self):
        col1 = [1.0, 2.0, 3.0, None, None, 6.0, 7.0] + [None] * 303 + [99.0]  # 311 rows (value at 310)
        col2 = [None] * 311
        col3 = [10.0] + [None] * 310
        ws = Worksheet(
            "BlockNav",
            [
                Column("C1", "number", col1),
                Column("C2", "number", col2),
                Column("C3", "number", col3),
            ],
        )
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()
        win.table.setCurrentCell(0, 0)

        def press(key):
            ev = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.ControlModifier)
            win.table.event(ev)

        press(Qt.Key.Key_Down)
        self.assertEqual((win.page, win.table.currentRow(), win.table.currentColumn()), (0, 2, 0))
        press(Qt.Key.Key_Down)
        self.assertEqual((win.page, win.table.currentRow(), win.table.currentColumn()), (0, 5, 0))
        press(Qt.Key.Key_Down)
        self.assertEqual((win.page, win.table.currentRow(), win.table.currentColumn()), (0, 6, 0))
        press(Qt.Key.Key_Down)
        self.assertEqual((win.page, win.table.currentRow(), win.table.currentColumn()), (1, 10, 0))

        # Horizontal block jump over empty C2
        win.page = 0
        win.refresh()
        win.table.setCurrentCell(0, 0)
        press(Qt.Key.Key_Right)
        self.assertEqual(win.table.currentColumn(), 2)
        press(Qt.Key.Key_Left)
        self.assertEqual(win.table.currentColumn(), 0)

        # Ctrl+Up at row 0 moves focus to column names
        press(Qt.Key.Key_Up)
        self.assertEqual(win.column_names.currentColumn(), 0)
        win.close()

    def test_context_menu_column_labels_rename_and_ctrl1_shortcut(self):
        ws = Worksheet(
            "CtxMenu",
            [
                Column("X", "number", [1.0, 2.0]),
                Column("Y", "number", [3.0, 4.0]),
            ],
        )
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        self.assertEqual(win.format_column_action.shortcut().toString(), "Ctrl+1")

        win.select_worksheet_column(0)
        menu = win.build_worksheet_context_menu()
        labels = [a.text() for a in menu.actions() if a.text()]
        self.assertIn("Clear Column(s)", labels)
        self.assertIn("Delete Column(s)", labels)
        self.assertTrue(any("Rename Column" in t for t in labels), f"Missing Rename Column in {labels}")
        win.close()

    def test_undo_retains_column_and_cell_selection(self):
        ws = Worksheet(
            "UndoSel",
            [
                Column("X", "number", [1.0, 2.0, 3.0]),
                Column("Y", "number", [10.0, 20.0, 30.0]),
            ],
        )
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        win.presenter.set_cell(2, 1, "99")
        win.refresh()
        win.select_worksheet_column(0)
        win.undo()
        self.assertEqual(win._selected_columns, {0})

        win.presenter.set_cell(2, 1, "88")
        win.refresh()
        win._selected_columns = set()
        win.table.setCurrentCell(2, 1)
        win.undo()
        self.assertEqual((win.table.currentRow(), win.table.currentColumn()), (2, 1))
        win.close()


if __name__ == "__main__":
    unittest.main()
