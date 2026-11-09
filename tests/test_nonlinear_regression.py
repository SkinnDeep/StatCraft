"""Unit tests for Nonlinear Regression engine, report, dialog, and presenter integration."""
import math
import os
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.nonlinear_regression import (
    fit_nonlinear_regression,
    clean_nonlinear_data,
)
from statcraft.nonlinear_regression_report import generate_nonlinear_regression_report
from statcraft.nonlinear_regression_dialogs import NonlinearRegressionDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import columns


class TestNonlinearRegression(unittest.TestCase):
    """Test suite for Nonlinear Regression."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Asymptotic benchmark data: y = 20 - 15 * exp(-0.3 * x)
        self.x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        self.y = [
            8.89, 11.76, 13.90, 15.48, 16.65,
            17.52, 18.16, 18.64, 18.99, 19.25,
        ]

        # Michaelis-Menten benchmark data: y = (50 * x) / (5 + x)
        self.x_mm = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0]
        self.y_mm = [8.33, 14.28, 25.00, 33.33, 40.00, 45.45]

    def test_clean_data(self):
        y_raw = [10.0, None, 20.0, 30.0]
        x_raw = [1.0, 2.0, None, 4.0]
        y_c, x_c, idxs = clean_nonlinear_data(y_raw, [x_raw])
        self.assertEqual(len(y_c), 2)
        self.assertEqual(idxs, [0, 3])
        self.assertEqual(y_c.tolist(), [10.0, 30.0])

    def test_fit_asymptotic(self):
        res = fit_nonlinear_regression(
            response=self.y,
            predictors=[self.x],
            model="asymptotic",
            predictor_names=["Time"],
            response_name="Yield",
        )
        self.assertEqual(res["analysis"], "nonlinear_regression")
        self.assertTrue(res["converged"])
        self.assertEqual(len(res["parameters"]), 3)

        # Check parameter estimates: th1 ~ 20, th2 ~ -15, th3 ~ 0.3
        p_dict = {p["parameter"]: p["estimate"] for p in res["parameters"]}
        self.assertAlmostEqual(p_dict["th1"], 20.0, delta=1.0)
        self.assertAlmostEqual(p_dict["th2"], -15.0, delta=1.0)
        self.assertAlmostEqual(p_dict["th3"], 0.3, delta=0.1)

        self.assertGreater(res["r_sq"], 99.0)
        self.assertLess(res["s"], 0.5)

    def test_fit_michaelis_menten(self):
        res = fit_nonlinear_regression(
            response=self.y_mm,
            predictors=[self.x_mm],
            model="michaelis_menten",
            predictor_names=["Substrate"],
            response_name="Velocity",
        )
        self.assertTrue(res["converged"])
        p_dict = {p["parameter"]: p["estimate"] for p in res["parameters"]}
        self.assertAlmostEqual(p_dict["th1"], 50.0, delta=2.0)
        self.assertAlmostEqual(p_dict["th2"], 5.0, delta=1.0)

    def test_fit_custom_formula(self):
        res = fit_nonlinear_regression(
            response=self.y,
            predictors=[self.x],
            model="custom",
            custom_formula="a + b * exp(-c * Time)",
            parameter_names=["a", "b", "c"],
            initial_values=[20.0, -15.0, 0.3],
            predictor_names=["Time"],
            response_name="Yield",
        )
        self.assertTrue(res["converged"])
        p_dict = {p["parameter"]: p["estimate"] for p in res["parameters"]}
        self.assertAlmostEqual(p_dict["a"], 20.0, delta=1.0)
        self.assertAlmostEqual(p_dict["b"], -15.0, delta=1.0)
        self.assertAlmostEqual(p_dict["c"], 0.3, delta=0.1)

    def test_report_generation(self):
        res = fit_nonlinear_regression(
            response=self.y,
            predictors=[self.x],
            model="asymptotic",
            predictor_names=["Time"],
            response_name="Yield",
        )
        rep = generate_nonlinear_regression_report(res)
        self.assertIn("Nonlinear Regression: Yield =", rep)
        self.assertIn("Parameter Estimates", rep)
        self.assertIn("Model Summary", rep)
        self.assertIn("Analysis of Variance", rep)

    def test_dialog_instantiation(self):
        ws = Worksheet(name="NonlinearData")
        ws.columns.append(Column(name="Yield", kind="number", values=self.y))
        ws.columns.append(Column(name="Time", kind="number", values=self.x))

        pres = Presenter()
        pres.worksheet = ws

        dlg = NonlinearRegressionDialog(pres)
        self.assertEqual(dlg.windowTitle(), "Nonlinear Regression")
        self.assertEqual(dlg.spin_conf.value(), 95.0)

    def test_presenter_and_recipe(self):
        ws = Worksheet(name="NonlinearData")
        ws.columns.append(Column(name="Yield", kind="number", values=self.y))
        ws.columns.append(Column(name="Time", kind="number", values=self.x))

        pres = Presenter()
        pres.worksheet = ws

        entry = pres.nonlinear_regression({
            "response_index": 0,
            "predictor_indices": [1],
            "model": "asymptotic",
            "confidence": 0.95,
        })
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Nonlinear Regression", text)

        # Check recipe columns extraction
        recipe = entry["recipe"]
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1])


if __name__ == "__main__":
    unittest.main()
