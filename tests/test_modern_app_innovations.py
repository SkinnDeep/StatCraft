import os
import sys
import unittest
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.modern_app import ModernWindow
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestModernAppInnovations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.win = ModernWindow(sandbox_mode=True)
        # Populate worksheet
        ws = Worksheet("Batch Yields", [
            Column("Yield", "number", [98.2, 99.1, 97.8, 98.6, 99.0]),
            Column("Operator", "text", ["Alice", "Bob", "Alice", "Bob", "Charlie"]),
        ])
        self.win.presenter.worksheet = ws
        self.win.refresh()

    def test_executive_brief_copy(self):
        bullets = ["Process mean is 98.54", "Yield meets baseline spec"]
        self.win.copy_executive_brief(bullets)
        cb = QApplication.clipboard()
        if cb is not None:
            self.assertIn("Process mean is 98.54", cb.text())

    def test_sync_table_selection_to_charts(self):
        class DummyChart:
            def __init__(self):
                self.brushed_rows = set()
                self.updated = False
            def update(self):
                self.updated = True

        chart = DummyChart()
        self.win._active_chart_widget = chart
        self.win.table.selectRow(1)
        self.win.sync_table_selection_to_charts()
        self.assertIn(2, chart.brushed_rows)
        self.assertTrue(chart.updated)

    def test_anonymize_worksheet_integration(self):
        from statcraft.anonymizer import anonymize_worksheet
        anon_ws = anonymize_worksheet(self.win.presenter.worksheet, mask_numeric=False)
        self.assertEqual(anon_ws.name, "Batch Yields_Anonymized")
        self.assertTrue(all(val.startswith("Operator_") for val in anon_ws.columns[1].values))

    def test_run_comparator_integration(self):
        from statcraft.run_comparator import compare_runs
        run_a = {"title": "Model 1", "analysis": "regression", "result": {"r_squared": 0.85, "aic": 120.0}}
        run_b = {"title": "Model 2", "analysis": "regression", "result": {"r_squared": 0.94, "aic": 105.0}}
        diff = compare_runs(run_a, run_b)
        self.assertIn("Model 2", diff["verdict"])
        self.assertTrue(any("r squared" in d.name.lower() and d.delta > 0 for d in diff["deltas"]))

    def tearDown(self):
        self.win.close()


if __name__ == "__main__":
    unittest.main()
