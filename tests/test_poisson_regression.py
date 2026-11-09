"""Unit tests for Poisson Regression engine, report, dialog, and presenter integration."""
import math
import os
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.poisson_regression import (
    fit_poisson_regression,
    clean_poisson_data,
)
from statcraft.poisson_regression_report import generate_poisson_regression_report
from statcraft.poisson_regression_dialogs import PoissonRegressionDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import columns


class TestPoissonRegression(unittest.TestCase):
    """Test suite for Poisson regression modeling."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Simulated benchmark count data:
        # Response Y: counts
        # X1: continuous covariate (e.g. temperature)
        # Factor1: categorical factor ("Low", "High")
        # Exposure: offset variable
        self.y = [2, 3, 6, 7, 8, 10, 12, 15, 16, 20]
        self.x1 = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5]
        self.cat1 = ["A", "A", "A", "A", "A", "B", "B", "B", "B", "B"]
        self.offset = [1.0, 1.0, 1.2, 1.1, 1.0, 1.3, 1.2, 1.4, 1.5, 1.6]

    def test_clean_data(self):
        y_raw = [1, 2, None, -5, 4]
        x_raw = [10.0, 20.0, 30.0, 40.0, 50.0]
        y_c, cont_c, cat_c, off_c, idxs = clean_poisson_data(
            response=y_raw,
            continuous_predictors=[x_raw],
        )
        self.assertEqual(len(y_c), 3)
        self.assertEqual(idxs, [0, 1, 4])
        self.assertEqual(y_c.tolist(), [1.0, 2.0, 4.0])

    def test_fit_continuous_predictor(self):
        res = fit_poisson_regression(
            response=self.y,
            continuous_predictors=[self.x1],
            continuous_names=["Temp"],
            response_name="Events",
        )
        self.assertEqual(res["analysis"], "poisson_regression")
        self.assertEqual(len(res["coefficients"]), 2)
        const_coef = res["coefficients"][0]
        slope_coef = res["coefficients"][1]
        self.assertEqual(const_coef["term"], "Constant")
        self.assertEqual(slope_coef["term"], "Temp")
        self.assertGreater(slope_coef["coef"], 0.0)  # Positive slope
        self.assertGreater(slope_coef["relative_risk"], 1.0)
        self.assertGreater(res["deviance_r_sq"], 70.0)
        self.assertEqual(len(res["fits"]), 10)
        self.assertEqual(len(res["deviance_residuals"]), 10)

    def test_fit_categorical_predictor(self):
        res = fit_poisson_regression(
            response=self.y,
            categorical_predictors=[self.cat1],
            categorical_names=["Group"],
            response_name="Events",
        )
        self.assertEqual(len(res["coefficients"]), 2)
        group_b_coef = res["coefficients"][1]
        self.assertEqual(group_b_coef["term"], "Group_B")
        self.assertGreater(group_b_coef["coef"], 0.0)
        self.assertGreater(group_b_coef["relative_risk"], 1.0)

    def test_fit_with_offset(self):
        # Offset is log(exposure)
        log_exp = [math.log(v) for v in self.offset]
        res = fit_poisson_regression(
            response=self.y,
            continuous_predictors=[self.x1],
            continuous_names=["Temp"],
            offset=log_exp,
            offset_name="ln_Exposure",
            response_name="Events",
        )
        self.assertEqual(res["offset_name"], "ln_Exposure")
        self.assertIn("+ ln_Exposure", res["equation"])
        self.assertIn("goodness_of_fit", res)
        self.assertEqual(len(res["goodness_of_fit"]), 2)

    def test_report_generation(self):
        res = fit_poisson_regression(
            response=self.y,
            continuous_predictors=[self.x1],
            continuous_names=["Temp"],
            response_name="Events",
        )
        rep = generate_poisson_regression_report(res)
        self.assertIn("Poisson Regression: Events versus Temp", rep)
        self.assertIn("Regression Equation", rep)
        self.assertIn("Coefficients", rep)
        self.assertIn("Relative Risk", rep)
        self.assertIn("Goodness-of-Fit Tests", rep)
        self.assertIn("Analysis of Variance", rep)

    def test_dialog_instantiation(self):
        ws = Worksheet(name="PoissonData")
        ws.columns.append(Column(name="Events", kind="number", values=self.y))
        ws.columns.append(Column(name="Temp", kind="number", values=self.x1))

        pres = Presenter()
        pres.worksheet = ws

        dlg = PoissonRegressionDialog(pres)
        self.assertEqual(dlg.windowTitle(), "Fit Poisson Model")
        self.assertEqual(dlg.spin_conf.value(), 95.0)

    def test_presenter_and_recipe(self):
        ws = Worksheet(name="PoissonData")
        ws.columns.append(Column(name="Events", kind="number", values=self.y))
        ws.columns.append(Column(name="Temp", kind="number", values=self.x1))

        pres = Presenter()
        pres.worksheet = ws

        entry = pres.poisson_regression({
            "response_index": 0,
            "continuous_indices": [1],
            "confidence": 0.95,
        })
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Poisson Regression: Events versus Temp", text)

        # Check recipe columns extraction
        recipe = entry["recipe"]
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1])


if __name__ == "__main__":
    unittest.main()
