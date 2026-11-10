import os
import sys
import unittest
from PySide6.QtWidgets import QApplication, QTableWidgetSelectionRange
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestCopyWithColumnNames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_copy_with_column_names(self):
        ws = Worksheet("TestSheet", [
            Column("Temp", "number", [72.5, 75.0]),
            Column("Pressure", "number", [101.3, 102.1]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        # Select all 2 rows and 2 columns
        win.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 1), True)
        win.copy_with_column_names()

        clipboard_text = QApplication.clipboard().text()
        lines = clipboard_text.strip().split("\n")
        self.assertEqual(lines[0], "Temp\tPressure")
        self.assertIn("72.5\t101.3", lines[1])
        self.assertIn("75.0\t102.1", lines[2])

        win.close()


if __name__ == "__main__":
    unittest.main()
