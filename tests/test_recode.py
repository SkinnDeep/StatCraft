"""Unit tests for Data Recoding engine, dialog, and presenter integration."""
import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from statcraft.recode import recode_column, recode_value
from statcraft.recode_dialogs import RecodeDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft import recipes


class TestRecode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def test_recode_text_to_numeric_exact(self):
        source = ["Low", "Medium", "High", "Low", "Unknown", None]
        rules = [
            {"type": "exact", "current": "Low", "recoded": 1},
            {"type": "exact", "current": "Medium", "recoded": 2},
            {"type": "exact", "current": "High", "recoded": 3},
            {"type": "missing", "recoded": 0},
        ]
        res = recode_column(
            source,
            rules=rules,
            target_kind="number",
            default_action="specified",
            default_value=-1,
        )
        self.assertEqual(res, [1.0, 2.0, 3.0, 1.0, -1.0, 0.0])

    def test_recode_numeric_range_to_text(self):
        scores = [45, 78, 92, 10, None, 50]
        rules = [
            {"type": "range", "low": 0, "high": 49.99, "recoded": "Fail", "inc_low": True, "inc_high": True},
            {"type": "range", "low": 50, "high": 100, "recoded": "Pass", "inc_low": True, "inc_high": True},
            {"type": "missing", "recoded": "Incomplete"},
        ]
        res = recode_column(
            scores,
            rules=rules,
            target_kind="text",
            default_action="original",
        )
        self.assertEqual(res, ["Fail", "Pass", "Pass", "Fail", "Incomplete", "Pass"])

    def test_presenter_new_column_storage(self):
        ws = Worksheet(name="TestWS")
        ws.columns.append(Column(name="Status", kind="text", values=["Open", "Closed", "Pending"]))
        pres = Presenter()
        pres.worksheet = ws

        rules = [
            {"type": "exact", "current": "Open", "recoded": 1},
            {"type": "exact", "current": "Closed", "recoded": 0},
            {"type": "exact", "current": "Pending", "recoded": 2},
        ]
        entry = pres.recode(
            source_indices=[0],
            rules=rules,
            target_kind="number",
            storage="new_columns",
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "recode")
        self.assertEqual(len(ws.columns), 2)
        rec_col = ws.columns[1]
        self.assertEqual(rec_col.name, "RECODE_Status")
        self.assertEqual(rec_col.kind, "number")
        self.assertEqual(rec_col.values, [1.0, 0.0, 2.0])

        # Test format_entry
        report = format_entry(entry)
        self.assertIn("Recode — Status", report)
        self.assertIn("Target Data Type: Number", report)

        # Test recipe columns
        cols = recipes.columns(entry["recipe"])
        self.assertEqual(cols, [0])

    def test_presenter_in_place_storage(self):
        ws = Worksheet(name="TestWS")
        ws.columns.append(Column(name="Code", kind="text", values=["A", "B", "A"]))
        pres = Presenter()
        pres.worksheet = ws

        rules = [
            {"type": "exact", "current": "A", "recoded": 10},
            {"type": "exact", "current": "B", "recoded": 20},
        ]
        pres.recode(
            source_indices=[0],
            rules=rules,
            target_kind="number",
            storage="original",
        )
        self.assertEqual(len(ws.columns), 1)
        self.assertEqual(ws.columns[0].kind, "number")
        self.assertEqual(ws.columns[0].values, [10.0, 20.0, 10.0])

    def test_dialog_distinct_values_population(self):
        ws = Worksheet(name="TestWS")
        ws.columns.append(Column(name="Category", kind="text", values=["Alpha", "Beta", "Alpha", "Gamma"]))
        dlg = RecodeDialog(ws, target_kind="number")
        self.assertEqual(dlg.windowTitle(), "Recode to Numeric")

        # Select column
        dlg.col_list.setCurrentRow(0)
        dlg._on_select_column()

        # Check mapping table has distinct values: Alpha, Beta, Gamma
        self.assertEqual(dlg.table.rowCount(), 3)
        vals_in_table = [dlg.table.item(r, 0).text() for r in range(3)]
        self.assertIn("Alpha", vals_in_table)
        self.assertIn("Beta", vals_in_table)
        self.assertIn("Gamma", vals_in_table)

        # Fill recoded values
        for r in range(3):
            dlg.table.item(r, 1).setText(str(r + 1))

        dlg._on_accept()
        self.assertIsNotNone(dlg.settings)
        self.assertEqual(dlg.settings["source_indices"], [0])
        self.assertEqual(len(dlg.settings["rules"]), 3)


if __name__ == "__main__":
    unittest.main()
