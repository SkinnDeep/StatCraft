"""Unit tests for Ordinal Logistic Regression engine, report, dialog, and presenter integration."""
import math
import os
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.ordinal_logistic import (
    fit_ordinal_logistic_regression,
    clean_ordinal_data,
)
from statcraft.ordinal_logistic_report import generate_ordinal_logistic_report
from statcraft.ordinal_logistic_dialogs import OrdinalLogisticDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import columns


class TestOrdinalLogistic(unittest.TestCase):
    """Test suite for Ordinal Logistic Regression."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Benchmark dataset: 3 ordered levels ("Low", "Medium", "High")
        # Continuous predictor X1 strongly correlated with response level
        self.y = [
            "Low", "Low", "Low", "Low", "Low",
            "Medium", "Medium", "Medium", "Medium", "Medium",
            "High", "High", "High", "High", "High",
        ]
        self.x1 = [
            1.0, 1.2, 1.5, 1.8, 2.0,
            3.0, 3.2, 3.5, 3.8, 4.0,
            5.0, 5.2, 5.5, 5.8, 6.0,
        ]
        self.cat1 = [
            "A", "A", "B", "B", "A",
            "A", "B", "A", "B", "A",
            "B", "B", "A", "B", "B",
        ]

    def test_clean_data(self):
        y_raw = ["Low", None, "High", "Medium"]
        x_raw = [1.0, 2.0, 3.0, 4.0]
        y_c, cont_c, cat_c, lvls, idxs = clean_ordinal_data(
            response=y_raw,
            continuous_predictors=[x_raw],
            ordered_levels=["Low", "Medium", "High"],
        )
        self.assertEqual(len(y_c), 3)
        self.assertEqual(idxs, [0, 2, 3])
        self.assertEqual(lvls, ["Low", "Medium", "High"])
        self.assertEqual(y_c.tolist(), [0, 2, 1])

    def test_fit_ordinal_continuous(self):
        res = fit_ordinal_logistic_regression(
            response=self.y,
            continuous_predictors=[self.x1],
            continuous_names=["Score"],
            ordered_levels=["Low", "Medium", "High"],
            response_name="Status",
        )
        self.assertEqual(res["analysis"], "ordinal_logistic_regression")
        self.assertEqual(res["levels"], ["Low", "Medium", "High"])
        self.assertEqual(len(res["coefficients"]), 3)  # Const(1), Const(2), Score

        # Check threshold constants
        const1 = res["coefficients"][0]
        const2 = res["coefficients"][1]
        self.assertEqual(const1["term"], "Const(1)")
        self.assertEqual(const2["term"], "Const(2)")
        self.assertLess(const1["coef"], const2["coef"])  # Strict ordering theta_1 < theta_2

        # Check slope
        slope = res["coefficients"][2]
        self.assertEqual(slope["term"], "Score")
        self.assertGreater(slope["coef"], 0.0)  # Positive relationship
        self.assertGreater(slope["z_value"], 0.0)

        # Odds ratio
        self.assertEqual(len(res["odds_ratios"]), 1)
        self.assertGreater(res["odds_ratios"][0]["odds_ratio"], 1.0)

        # Goodness of fit
        self.assertEqual(len(res["goodness_of_fit"]), 2)

        # Measures of association
        assoc = res["association"]
        self.assertGreater(assoc["pct_concordant"], 80.0)
        self.assertGreater(assoc["somers_d"], 0.7)

    def test_fit_ordinal_with_categorical(self):
        res = fit_ordinal_logistic_regression(
            response=self.y,
            continuous_predictors=[self.x1],
            categorical_predictors=[self.cat1],
            continuous_names=["Score"],
            categorical_names=["Group"],
            ordered_levels=["Low", "Medium", "High"],
        )
        coef_names = [c["term"] for c in res["coefficients"]]
        self.assertIn("Const(1)", coef_names)
        self.assertIn("Const(2)", coef_names)
        self.assertIn("Score", coef_names)
        self.assertIn("Group_B", coef_names)

    def test_report_generation(self):
        res = fit_ordinal_logistic_regression(
            response=self.y,
            continuous_predictors=[self.x1],
            continuous_names=["Score"],
            ordered_levels=["Low", "Medium", "High"],
            response_name="Status",
        )
        rep = generate_ordinal_logistic_report(res)
        self.assertIn("Ordinal Logistic Regression: Status versus Score", rep)
        self.assertIn("Response Information", rep)
        self.assertIn("Logistic Regression Table", rep)
        self.assertIn("Odds Ratios", rep)
        self.assertIn("Goodness-of-Fit Tests", rep)
        self.assertIn("Measures of Association", rep)
        self.assertIn("Somers' D", rep)

    def test_dialog_instantiation(self):
        ws = Worksheet(name="OrdinalData")
        ws.columns.append(Column(name="Status", kind="text", values=self.y))
        ws.columns.append(Column(name="Score", kind="number", values=self.x1))

        pres = Presenter()
        pres.worksheet = ws

        dlg = OrdinalLogisticDialog(pres)
        self.assertEqual(dlg.windowTitle(), "Ordinal Logistic Regression")
        self.assertEqual(dlg.spin_conf.value(), 95.0)

    def test_presenter_and_recipe(self):
        ws = Worksheet(name="OrdinalData")
        ws.columns.append(Column(name="Status", kind="text", values=self.y))
        ws.columns.append(Column(name="Score", kind="number", values=self.x1))

        pres = Presenter()
        pres.worksheet = ws

        entry = pres.ordinal_logistic_regression({
            "response_index": 0,
            "continuous_indices": [1],
            "confidence": 0.95,
        })
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Ordinal Logistic Regression: Status versus Score", text)

        # Check recipe columns extraction
        recipe = entry["recipe"]
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1])


if __name__ == "__main__":
    unittest.main()
