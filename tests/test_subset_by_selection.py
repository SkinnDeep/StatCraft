import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestSubsetBySelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_subset_by_cell_value(self):
        ws = Worksheet("Production", [
            Column("Machine", "text", ["M1", "M2", "M1", "M2", "M3"]),
            Column("Speed", "number", [100, 200, 110, 205, 300]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        win.refresh()

        # Subset by cell (row 1, col 0) -> Machine="M2"
        new_sheet = win.subset_by_cell_value(0, "M2")
        self.assertIsNotNone(new_sheet)
        self.assertEqual(len(new_sheet.columns[0].values), 2)
        self.assertEqual(new_sheet.columns[0].values, ["M2", "M2"])
        self.assertEqual(new_sheet.columns[1].values, [200, 205])

        win.close()


if __name__ == "__main__":
    unittest.main()
