import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestFullColumnClear(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_full_column_clear_clears_all_rows_beyond_page_size(self):
        # 600 rows (spans 2 pages when PAGE_SIZE is 300)
        c1_vals = [float(i) for i in range(600)]
        c2_vals = [float(i * 10) for i in range(600)]
        ws = Worksheet("LargeSheet", [
            Column("C1", "number", c1_vals),
            Column("C2", "number", c2_vals),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        # Select column 0 via header
        win.select_worksheet_column(0)
        self.assertIn(0, win._selected_columns)

        # Clear cells
        win.clear_cells()

        # All 600 rows of C1 should be None (cleared), while C2 remains untouched!
        col1 = win.presenter.worksheet.columns[0]
        col2 = win.presenter.worksheet.columns[1]
        self.assertTrue(all(v is None for v in col1.values))
        self.assertEqual(col2.values[500], 5000.0)

        win.close()


if __name__ == "__main__":
    unittest.main()
