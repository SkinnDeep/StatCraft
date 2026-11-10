import os
import sys
import unittest
from PySide6.QtWidgets import QApplication, QTableWidgetSelectionRange
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestSelectionStatusSummary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_selection_summary_on_status_bar(self):
        ws = Worksheet("TestSheet", [
            Column("C1", "number", [10.0, 20.0, 30.0]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        # Select rows 0 to 2 in column 0 (10, 20, 30)
        win.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 2, 0), True)
        win._update_selection_summary()

        summary_text = win.status_selection_summary.text()
        self.assertIn("Count: 3", summary_text)
        self.assertIn("Sum: 60", summary_text)
        self.assertIn("Mean: 20", summary_text)
        self.assertIn("Min: 10", summary_text)
        self.assertIn("Max: 30", summary_text)

        win.close()


if __name__ == "__main__":
    unittest.main()
