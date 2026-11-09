"""Unit tests for Best Subsets Regression computational engine, report, dialog, and presenter."""
import os
import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QWidget

from statcraft.best_subsets import best_subsets_regression
from statcraft.best_subsets_report import generate_best_subsets_report
from statcraft.best_subsets_dialogs import BestSubsetsDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft import recipes


class TestBestSubsets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Classic Hald Cement data (13 observations)
        # Y: heat evolved (cals/gm)
        # X1, X2, X3, X4: % composition
        self.y = [78.5, 74.3, 104.3, 87.6, 95.9, 109.2, 102.7, 72.5, 93.1, 115.9, 83.8, 113.3, 109.4]
        self.x1 = [7, 1, 11, 11, 7, 11, 3, 1, 2, 21, 1, 11, 10]
        self.x2 = [26, 29, 56, 31, 52, 55, 71, 31, 54, 47, 40, 66, 68]
        self.x3 = [6, 15, 8, 8, 6, 9, 17, 22, 18, 4, 23, 9, 8]
        self.x4 = [60, 52, 20, 47, 33, 22, 6, 44, 22, 26, 34, 12, 12]

    def test_best_subsets_hald_cement(self):
        res = best_subsets_regression(
            response=self.y,
            free_predictors=[self.x1, self.x2, self.x3, self.x4],
            free_names=["X1", "X2", "X3", "X4"],
            models_per_subset=2,
            min_free=1,
            max_free=4,
            response_name="Heat",
        )
        self.assertEqual(res["analysis"], "best_subsets_regression")
        self.assertEqual(res["response_name"], "Heat")
        self.assertEqual(res["n"], 13)
        self.assertEqual(len(res["free_names"]), 4)

        models = res["models"]
        # Subset sizes 1, 2, 3, 4:
        # Size 1: 2 models
        # Size 2: 2 models
        # Size 3: 2 models (or top 2)
        # Size 4: 1 model (only 1 combination)
        self.assertGreaterEqual(len(models), 6)

        # In Hald cement data, best 2-predictor model is X1 + X2 (R2 ~ 97.9%)
        # and best 1-predictor model is X4 (R2 ~ 67.5%)
        # Full 4-variable model has Cp = 5.0 (P = 4 + 1 = 5)
        full_model = models[-1]
        self.assertEqual(full_model["vars"], 4)
        self.assertAlmostEqual(full_model["cp"], 5.0, places=2)
        self.assertGreater(full_model["r2"], 98.0)

        # Check vars count and sorted order
        for m in models:
            self.assertTrue(0 <= m["r2"] <= 100.0)
            self.assertGreater(m["s"], 0)
            self.assertEqual(len(m["included_free"]), 4)

    def test_forced_predictors(self):
        res = best_subsets_regression(
            response=self.y,
            free_predictors=[self.x2, self.x3, self.x4],
            free_names=["X2", "X3", "X4"],
            forced_predictors=[self.x1],
            forced_names=["X1"],
            models_per_subset=1,
            min_free=1,
            max_free=3,
            response_name="Heat",
        )
        models = res["models"]
        self.assertEqual(len(models), 3)
        # Vars count is 1 forced + k free: 2, 3, 4
        self.assertEqual(models[0]["vars"], 2)
        self.assertEqual(models[1]["vars"], 3)
        self.assertEqual(models[2]["vars"], 4)

    def test_error_handling(self):
        # Insufficient rows
        with self.assertRaises(ValueError):
            best_subsets_regression(
                response=[1, 2, 3],
                free_predictors=[[1, 2, 3], [4, 5, 6]],
            )

        # Empty free predictors
        with self.assertRaises(ValueError):
            best_subsets_regression(
                response=self.y,
                free_predictors=[],
            )

        # Zero variance response
        with self.assertRaises(ValueError):
            best_subsets_regression(
                response=[5.0] * 13,
                free_predictors=[self.x1],
            )

    def test_report_generation(self):
        res = best_subsets_regression(
            response=self.y,
            free_predictors=[self.x1, self.x2, self.x3, self.x4],
            free_names=["X1", "X2", "X3", "X4"],
            models_per_subset=2,
            response_name="Heat",
        )
        report = generate_best_subsets_report(res)
        self.assertIn("Best Subsets Regression: Heat versus X1, X2, X3, X4", report)
        self.assertIn("Response is Heat", report)
        self.assertIn("Vars", report)
        self.assertIn("R-Sq", report)
        self.assertIn("R-Sq(adj)", report)
        self.assertIn("C-p", report)
        self.assertIn("X", report)

    def test_presenter_integration(self):
        ws = Worksheet(name="HaldCement")
        ws.columns.append(Column(name="Heat", kind="number", values=self.y))
        ws.columns.append(Column(name="X1", kind="number", values=self.x1))
        ws.columns.append(Column(name="X2", kind="number", values=self.x2))
        ws.columns.append(Column(name="X3", kind="number", values=self.x3))
        ws.columns.append(Column(name="X4", kind="number", values=self.x4))

        pres = Presenter()
        pres.worksheet = ws

        entry = pres.best_subsets(
            response_index=0,
            free_indices=[1, 2, 3, 4],
            models_per_subset=2,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "best_subsets")
        self.assertEqual(entry["result"]["analysis"], "best_subsets_regression")

        # Verify formatting
        text = format_entry(entry)
        self.assertIn("Best Subsets Regression: Heat versus X1, X2, X3, X4", text)

        # Verify recipe columns
        cols = recipes.columns(entry["recipe"])
        self.assertEqual(cols, [0, 1, 2, 3, 4])

    def test_dialog_validation(self):
        ws = Worksheet(name="TestWS")
        ws.columns.append(Column(name="Y", kind="number", values=self.y))
        ws.columns.append(Column(name="X1", kind="number", values=self.x1))
        ws.columns.append(Column(name="X2", kind="number", values=self.x2))

        class MockWindow(QWidget):
            def __init__(self, worksheet):
                super().__init__()
                self.presenter = Presenter()
                self.presenter.worksheet = worksheet

        win = MockWindow(ws)
        dlg = BestSubsetsDialog(win)
        self.assertEqual(dlg.windowTitle(), "Best Subsets Regression")

        # Valid input
        dlg.parameters = {
            "response_index": 0,
            "free_indices": [1, 2],
            "forced_indices": [],
        }
        dlg.validate()
        self.assertTrue(hasattr(dlg, "best_subsets_settings"))
        self.assertEqual(dlg.best_subsets_settings["response_index"], 0)
        self.assertEqual(dlg.best_subsets_settings["free_indices"], [1, 2])


if __name__ == "__main__":
    unittest.main()
