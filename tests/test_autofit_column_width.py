import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestAutofitColumnWidth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_auto_fit_column_width(self):
        long_string = "VeryLongIdentifierNameExceedingNormalColumnWidth12345"
        ws = Worksheet("TestSheet", [
            Column("Short", "number", [1, 2, 3]),
            Column("LongNameColumn", "text", [long_string, "Short", "Another"]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        initial_w = win.table.columnWidth(1)
        win.auto_fit_column_width(1)
        new_w = win.table.columnWidth(1)

        # The new width should have expanded to fit the long string
        self.assertGreater(new_w, initial_w)
        self.assertEqual(win.column_names.columnWidth(1), new_w)

        win.close()


if __name__ == "__main__":
    unittest.main()
