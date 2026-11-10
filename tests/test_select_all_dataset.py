import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestSelectAllDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_select_all_dataset_copies_beyond_page_size(self):
        # 500 rows (exceeds PAGE_SIZE 300)
        c1_vals = [float(i) for i in range(500)]
        ws = Worksheet("LargeSheet", [
            Column("Index", "number", c1_vals),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        # Execute Select All Dataset
        win.select_all_dataset()
        self.assertEqual(len(win._selected_columns), 1)

        # Copy cells
        win.copy_cells()
        text = QApplication.clipboard().text()
        lines = [line for line in text.splitlines() if line]
        # Should contain all 500 rows, NOT truncated at 300!
        self.assertEqual(len(lines), 500)
        self.assertEqual(lines[499], "499.0")

        win.close()


if __name__ == "__main__":
    unittest.main()
