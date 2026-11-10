import os
import sys
import unittest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestSelectionShortcuts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_ctrl_space_selects_column(self):
        ws = Worksheet("TestSheet", [
            Column("C1", "number", [10, 20, 30]),
            Column("C2", "number", [100, 200, 300]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        # Focus cell (1, 1) -> Row 2, C2
        win.table.setCurrentCell(1, 1)

        # Press Ctrl+Space on table
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        win.table.event(event)

        # Column 1 (C2) should now be selected
        self.assertIn(1, win._selected_columns)
        self.assertNotIn(0, win._selected_columns)

        win.close()

    def test_shift_space_selects_row(self):
        ws = Worksheet("TestSheet", [
            Column("C1", "number", [10, 20, 30]),
            Column("C2", "number", [100, 200, 300]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        # Focus cell (2, 0) -> Row 3, C1
        win.table.setCurrentCell(2, 0)

        # Press Shift+Space on table
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.ShiftModifier)
        win.table.event(event)

        # Row 2 should now be selected
        self.assertIn(2, win._selected_rows)
        self.assertNotIn(0, win._selected_rows)

        win.close()


if __name__ == "__main__":
    unittest.main()
