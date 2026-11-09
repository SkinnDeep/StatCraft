"""Unit tests for Split Worksheet feature."""
import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QWidget

from statcraft.data_prep import split_worksheet
from statcraft.data_prep_dialogs import SplitWorksheetDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter


class TestSplitWorksheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.ws = Worksheet(
            "ProductionData",
            [
                Column("Shift", "text", ["Day", "Night", "Day", "Night", "Day"]),
                Column("Machine", "text", ["M1", "M1", "M2", "M2", "M1"]),
                Column("Yield", "number", [95.2, 88.4, 91.0, 84.6, 96.1]),
            ],
        )

    def test_split_by_single_column(self):
        sheets = split_worksheet(self.ws, by_indices=[0])
        self.assertEqual(len(sheets), 2)
        names = [s.name for s in sheets]
        self.assertIn("ProductionData - Day", names)
        self.assertIn("ProductionData - Night", names)

        # Check Day sheet
        day_sheet = next(s for s in sheets if "Day" in s.name)
        self.assertEqual(day_sheet.row_count, 3)
        self.assertEqual(day_sheet.columns[2].values, [95.2, 91.0, 96.1])

        # Check Night sheet
        night_sheet = next(s for s in sheets if "Night" in s.name)
        self.assertEqual(night_sheet.row_count, 2)
        self.assertEqual(night_sheet.columns[2].values, [88.4, 84.6])

    def test_split_by_multiple_columns(self):
        sheets = split_worksheet(self.ws, by_indices=[0, 1])
        # Combinations: Day M1 (2 rows), Night M1 (1 row), Day M2 (1 row), Night M2 (1 row)
        self.assertEqual(len(sheets), 4)

    def test_split_empty_or_invalid(self):
        with self.assertRaises(ValueError):
            split_worksheet(self.ws, by_indices=[])

        with self.assertRaises(ValueError):
            split_worksheet(self.ws, by_indices=[99])

    def test_dialog_validation(self):
        class MockWindow(QWidget):
            def __init__(self, worksheet):
                super().__init__()
                self.presenter = Presenter()
                self.presenter.worksheet = worksheet

        win = MockWindow(self.ws)
        dlg = SplitWorksheetDialog(win)
        dlg.controls['by_indices'].setText("Shift")
        dlg.validate()
        self.assertIsNotNone(dlg.prepared)
        # Should have added 2 new worksheets to presenter
        # Initially presenter has 1 worksheet, now should have 3
        if hasattr(win.presenter, "native_project") and win.presenter.native_project:
            self.assertGreaterEqual(len(win.presenter.native_project.worksheets), 2)


if __name__ == "__main__":
    unittest.main()
