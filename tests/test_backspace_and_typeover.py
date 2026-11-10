import os
import sys
import unittest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestBackspaceAndTypeOver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_backspace_clears_and_opens_editor(self):
        ws = Worksheet("TestSheet", [
            Column("C1", "number", [100.0]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        win.table.setCurrentCell(0, 0)
        # Press Backspace on table
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier)
        handled = win.table.event(event)
        self.assertTrue(handled)

        editor = win.table.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        self.assertEqual(editor.text(), "")

        win.close()

    def test_type_over_replaces_and_opens_editor(self):
        ws = Worksheet("TestSheet", [
            Column("C1", "number", [100.0]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        win.table.setCurrentCell(0, 0)
        # Press '7' on table
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_7, Qt.KeyboardModifier.NoModifier, "7")
        handled = win.table.event(event)
        self.assertTrue(handled)

        editor = win.table.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        self.assertEqual(editor.text(), "7")

        win.close()


if __name__ == "__main__":
    unittest.main()
