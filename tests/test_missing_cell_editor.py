import os
import sys
import unittest
from PySide6.QtWidgets import QApplication, QLineEdit
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestMissingCellEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_missing_numeric_cell_opens_with_empty_editor(self):
        ws = Worksheet("TestSheet", [
            Column("C1", "number", [None]),  # displays '*'
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        item = win.table.item(0, 0)
        self.assertEqual(item.text(), "*")

        # Edit item
        win.table.editItem(item)
        editor = win.table.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        # Should be empty string, NOT '*'!
        self.assertEqual(editor.text(), "")

        win.close()


if __name__ == "__main__":
    unittest.main()
