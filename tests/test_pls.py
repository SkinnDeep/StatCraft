"""Unit tests for Partial Least Squares (PLS) Regression engine, report, dialog, and presenter integration."""
import math
import os
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.pls import (
    fit_pls_regression,
    clean_pls_data,
)
from statcraft.pls_report import generate_pls_report
from statcraft.pls_dialogs import PLSDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import columns


class TestPLS(unittest.TestCase):
    """Test suite for Partial Least Squares regression."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Collinear benchmark data (10 observations, 4 predictors)
        # Latent factor z explains most of X and Y
        self.y = [15.2, 17.5, 20.1, 22.4, 25.0, 27.2, 30.1, 32.5, 35.0, 37.8]
        self.x1 = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5]
        self.x2 = [2.1, 3.0, 4.1, 4.9, 6.0, 7.1, 8.0, 8.9, 10.1, 11.0]  # ~ 2 * X1
        self.x3 = [5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5]   # negatively correlated
        self.x4 = [10.2, 9.8, 11.1, 10.5, 9.9, 10.8, 10.1, 11.2, 9.7, 10.4]  # noise

    def test_clean_data(self):
        y_raw = [1.0, 2.0, None, 4.0]
        x1_raw = [10.0, 20.0, 30.0, 40.0]
        x2_raw = [100.0, None, 300.0, 400.0]
        y_c, x_c, idxs = clean_pls_data(y_raw, [x1_raw, x2_raw])
        self.assertEqual(len(y_c), 2)
        self.assertEqual(idxs, [0, 3])
        self.assertEqual(y_c.tolist(), [1.0, 4.0])

    def test_fit_pls_automatic_components(self):
        res = fit_pls_regression(
            response=self.y,
            predictors=[self.x1, self.x2, self.x3, self.x4],
            predictor_names=["X1", "X2", "X3", "X4"],
            response_name="Target",
        )
        self.assertEqual(res["analysis"], "pls_regression")
        self.assertGreaterEqual(res["optimal_components"], 1)
        self.assertGreater(res["r_sq"], 95.0)
        self.assertGreater(res["r_sq_pred"], 90.0)
        self.assertEqual(len(res["coefficients"]), 4)

        # VIP scores: X1, X2, X3 should have high VIP, X4 (noise) should have lower VIP
        vips = {c["predictor"]: c["vip"] for c in res["coefficients"]}
        self.assertGreater(vips["X1"], 0.8)
        self.assertGreater(vips["X2"], 0.8)

    def test_fit_pls_fixed_components(self):
        res = fit_pls_regression(
            response=self.y,
            predictors=[self.x1, self.x2, self.x3, self.x4],
            n_components=2,
            predictor_names=["X1", "X2", "X3", "X4"],
            response_name="Target",
        )
        self.assertEqual(res["optimal_components"], 2)
        self.assertGreater(res["cum_x_var"], 70.0)

    def test_report_generation(self):
        res = fit_pls_regression(
            response=self.y,
            predictors=[self.x1, self.x2, self.x3],
            predictor_names=["X1", "X2", "X3"],
            response_name="Target",
        )
        rep = generate_pls_report(res)
        self.assertIn("Partial Least Squares Regression: Target versus X1, X2, X3", rep)
        self.assertIn("Model Selection and Validation", rep)
        self.assertIn("X-Variance (%)", rep)
        self.assertIn("Model Summary", rep)
        self.assertIn("Regression Equation", rep)
        self.assertIn("Coefficients", rep)
        self.assertIn("VIP", rep)

    def test_dialog_instantiation(self):
        ws = Worksheet(name="PLSData")
        ws.columns.append(Column(name="Target", kind="number", values=self.y))
        ws.columns.append(Column(name="X1", kind="number", values=self.x1))
        ws.columns.append(Column(name="X2", kind="number", values=self.x2))

        pres = Presenter()
        pres.worksheet = ws

        dlg = PLSDialog(pres)
        self.assertEqual(dlg.windowTitle(), "Partial Least Squares")
        self.assertTrue(dlg.rb_auto.isChecked())

    def test_presenter_and_recipe(self):
        ws = Worksheet(name="PLSData")
        ws.columns.append(Column(name="Target", kind="number", values=self.y))
        ws.columns.append(Column(name="X1", kind="number", values=self.x1))
        ws.columns.append(Column(name="X2", kind="number", values=self.x2))

        pres = Presenter()
        pres.worksheet = ws

        entry = pres.pls_regression({
            "response_index": 0,
            "predictor_indices": [1, 2],
        })
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Partial Least Squares Regression", text)

        # Check recipe columns extraction
        recipe = entry["recipe"]
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
