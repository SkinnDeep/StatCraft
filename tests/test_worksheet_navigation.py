import os
import sys
import unittest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.modern_worksheet import movement, WorksheetDelegate, ColumnNamesTable, WorksheetTable

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestWorksheetNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.win = ModernWindow(sandbox_mode=True)
        self.win._confirm_leave = lambda: True
        ws = Worksheet("TestNavigation", [
            Column("Strength", "number", [10.5, 12.0, 14.2, 11.8]),
            Column("Operator", "text", ["OpA", "OpB", "OpA", "OpB"]),
            Column("Batch", "number", [101.0, 102.0, 103.0, 104.0]),
        ])
        self.win.presenter.worksheet = ws
        self.win.refresh()

    def tearDown(self):
        self.win.close()

    def test_movement_function(self):
        # Normal key events
        ev_tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
        self.assertEqual(movement(ev_tab), 'right')

        ev_shift_tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(movement(ev_shift_tab), 'left')

        ev_enter_down = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        self.assertEqual(movement(ev_enter_down, enter_direction='down'), 'down')

        ev_enter_right = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        self.assertEqual(movement(ev_enter_right, enter_direction='right'), 'right')

        ev_shift_enter_down = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(movement(ev_shift_enter_down, enter_direction='down'), 'up')

        ev_shift_enter_right = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(movement(ev_shift_enter_right, enter_direction='right'), 'left')

        # In editor
        ev_down = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        self.assertIsNone(movement(ev_down, in_editor=False))
        self.assertEqual(movement(ev_down, in_editor=True), 'down')

        ev_up = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        self.assertIsNone(movement(ev_up, in_editor=False))
        self.assertEqual(movement(ev_up, in_editor=True), 'up')

    def test_toggle_entry_direction(self):
        self.assertEqual(self.win.table.enter_direction, 'down')
        self.assertEqual(self.win.column_names.enter_direction, 'down')
        self.assertEqual(self.win.entry_dir_label.text(), '↓')

        self.win.toggle_entry_direction()
        self.assertEqual(self.win.table.enter_direction, 'right')
        self.assertEqual(self.win.column_names.enter_direction, 'right')
        self.assertEqual(self.win.entry_dir_label.text(), '→')

        self.win.toggle_entry_direction()
        self.assertEqual(self.win.table.enter_direction, 'down')
        self.assertEqual(self.win.column_names.enter_direction, 'down')
        self.assertEqual(self.win.entry_dir_label.text(), '↓')

    def test_navigate_down_and_up_in_table(self):
        self.win.table.setCurrentCell(0, 0)
        self.win._navigate_cell('down')
        self.assertEqual(self.win.table.currentRow(), 1)
        self.assertEqual(self.win.table.currentColumn(), 0)

        self.win._navigate_cell('down')
        self.assertEqual(self.win.table.currentRow(), 2)

        self.win._navigate_cell('up')
        self.assertEqual(self.win.table.currentRow(), 1)

    def test_navigate_up_from_row_1_moves_to_column_names(self):
        self.win.table.setCurrentCell(0, 1)
        self.win._navigate_cell('up')
        # Should transition focus to column_names at column 1
        self.assertEqual(self.win.column_names.currentColumn(), 1)
        self.assertEqual(self.win.column_names.currentRow(), 0)

    def test_navigate_down_from_column_names_moves_to_table(self):
        self.win.column_names.setCurrentCell(0, 2)
        self.win._navigate_column_name('down')
        # Should transition focus to data table at row 0, column 2
        self.assertEqual(self.win.table.currentRow(), 0)
        self.assertEqual(self.win.table.currentColumn(), 2)

    def test_column_name_navigation_right_and_left(self):
        self.win.column_names.setCurrentCell(0, 0)
        self.win._navigate_column_name('right')
        self.assertEqual(self.win.column_names.currentColumn(), 1)

        self.win._navigate_column_name('right')
        self.assertEqual(self.win.column_names.currentColumn(), 2)

        self.win._navigate_column_name('left')
        self.assertEqual(self.win.column_names.currentColumn(), 1)

    def test_editor_commit_on_navigate(self):
        self.win.table.setCurrentCell(0, 0)
        line_edit = QLineEdit("99.99", self.win.table)
        delegate = self.win.table.itemDelegate()
        self.win._navigate_cell('down', editor=line_edit, delegate=delegate)

        # Row 0, Col 0 should now be committed to 99.99 in presenter and table
        val = self.win.presenter.worksheet.columns[0].values[0]
        self.assertEqual(val, 99.99)
        self.assertEqual(self.win.table.item(0, 0).text(), "99.99")
        # And cursor moved to Row 1
        self.assertEqual(self.win.table.currentRow(), 1)

    def test_ctrl_home_and_ctrl_end(self):
        self.win.table.setCurrentCell(2, 2)
        self.win._navigate_cell('top_left')
        self.assertEqual(self.win.table.currentRow(), 0)
        self.assertEqual(self.win.table.currentColumn(), 0)

        self.win._navigate_cell('bottom_right')
        self.assertEqual(self.win.table.currentRow(), 3)
        self.assertEqual(self.win.table.currentColumn(), 2)


if __name__ == "__main__":
    unittest.main()
