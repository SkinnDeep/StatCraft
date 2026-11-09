"""Unit tests for Nominal Logistic Regression engine, report, dialog, and presenter integration."""
import math
import os
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.nominal_logistic import (
    fit_nominal_logistic_regression,
    clean_nominal_data,
)
from statcraft.nominal_logistic_report import generate_nominal_logistic_report
from statcraft.nominal_logistic_dialogs import NominalLogisticDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import columns


class TestNominalLogistic(unittest.TestCase):
    """Test suite for Nominal Logistic Regression."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # 3 unordered classes: Brand A, Brand B, Brand C
        # 2 continuous predictors
        self.y = [
            "BrandA", "BrandA", "BrandA", "BrandA", "BrandA",
            "BrandB", "BrandB", "BrandB", "BrandB", "BrandB",
            "BrandC", "BrandC", "BrandC", "BrandC", "BrandC",
        ]
        self.x1 = [
            1.0, 1.2, 1.5, 1.1, 1.3,
            4.0, 4.2, 4.5, 4.1, 4.3,
            8.0, 8.2, 8.5, 8.1, 8.3,
        ]
        self.x2 = [
            2.0, 2.5, 2.1, 2.3, 2.4,
            5.0, 5.5, 5.1, 5.3, 5.4,
            1.0, 1.5, 1.1, 1.3, 1.4,
        ]

    def test_clean_data(self):
        y_raw = ["A", None, "B", "C"]
        x_raw = [10.0, 20.0, 30.0, 40.0]
        y_c, cont_c, cat_c, lvls, ref, idxs = clean_nominal_data(
            response=y_raw,
            continuous_predictors=[x_raw],
            reference_level="C",
        )
        self.assertEqual(len(y_c), 3)
        self.assertEqual(idxs, [0, 2, 3])
        self.assertEqual(ref, "C")
        self.assertEqual(lvls, ["A", "B", "C"])

    def test_fit_nominal(self):
        res = fit_nominal_logistic_regression(
            response=self.y,
            continuous_predictors=[self.x1, self.x2],
            continuous_names=["Price", "Rating"],
            reference_level="BrandC",
            response_name="Brand",
        )
        self.assertEqual(res["analysis"], "nominal_logistic_regression")
        self.assertEqual(res["reference_level"], "BrandC")
        self.assertEqual(len(res["logits"]), 2)  # BrandA vs BrandC, BrandB vs BrandC

        logit1 = res["logits"][0]
        self.assertEqual(logit1["comparison"], "BrandA vs BrandC")
        self.assertEqual(len(logit1["coefficients"]), 3)  # Constant, Price, Rating

        # Odds ratios
        self.assertGreater(len(res["odds_ratios"]), 0)

        # Goodness of fit
        self.assertEqual(len(res["goodness_of_fit"]), 2)

        # Percent correctly classified
        self.assertGreater(res["percent_correct"], 80.0)

    def test_report_generation(self):
        res = fit_nominal_logistic_regression(
            response=self.y,
            continuous_predictors=[self.x1],
            continuous_names=["Price"],
            reference_level="BrandC",
            response_name="Brand",
        )
        rep = generate_nominal_logistic_report(res)
        self.assertIn("Nominal Logistic Regression: Brand versus Price", rep)
        self.assertIn("Response Information", rep)
        self.assertIn("Reference Event", rep)
        self.assertIn("Logistic Regression Table", rep)
        self.assertIn("Odds Ratios", rep)
        self.assertIn("Goodness-of-Fit Tests", rep)
        self.assertIn("Percent Correctly Classified", rep)

    def test_dialog_instantiation(self):
        ws = Worksheet(name="NominalData")
        ws.columns.append(Column(name="Brand", kind="text", values=self.y))
        ws.columns.append(Column(name="Price", kind="number", values=self.x1))

        pres = Presenter()
        pres.worksheet = ws

        dlg = NominalLogisticDialog(pres)
        self.assertEqual(dlg.windowTitle(), "Nominal Logistic Regression")
        self.assertEqual(dlg.spin_conf.value(), 95.0)

    def test_presenter_and_recipe(self):
        ws = Worksheet(name="NominalData")
        ws.columns.append(Column(name="Brand", kind="text", values=self.y))
        ws.columns.append(Column(name="Price", kind="number", values=self.x1))

        pres = Presenter()
        pres.worksheet = ws

        entry = pres.nominal_logistic_regression({
            "response_index": 0,
            "continuous_indices": [1],
            "reference_level": "BrandC",
            "confidence": 0.95,
        })
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Nominal Logistic Regression: Brand versus Price", text)

        # Check recipe columns extraction
        recipe = entry["recipe"]
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1])


if __name__ == "__main__":
    unittest.main()
