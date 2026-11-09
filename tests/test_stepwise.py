"""Tests for Stepwise Regression computational engine, report, dialog, and presenter integration."""
import os
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.stepwise import stepwise_regression, clean_stepwise_data
from statcraft.stepwise_report import generate_stepwise_report
from statcraft.stepwise_dialogs import StepwiseRegressionDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import columns


class TestStepwiseRegression(unittest.TestCase):
    """Test suite for stepwise, forward, backward regression algorithms."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Hald cement benchmark dataset
        self.y = [78.5, 74.3, 104.3, 87.6, 95.9, 109.2, 102.7, 72.5, 93.1, 115.9, 83.8, 113.3, 109.4]
        self.x1 = [7, 1, 11, 11, 7, 11, 3, 1, 2, 21, 1, 11, 10]
        self.x2 = [26, 29, 56, 31, 52, 55, 71, 31, 54, 47, 40, 66, 68]
        self.x3 = [6, 15, 8, 8, 6, 9, 17, 22, 18, 4, 23, 9, 8]
        self.x4 = [60, 52, 20, 47, 33, 22, 6, 44, 22, 26, 34, 12, 12]
        self.predictors = [self.x1, self.x2, self.x3, self.x4]
        self.names = ["X1", "X2", "X3", "X4"]

    def test_clean_data(self):
        y_messy = [1.0, None, 3.0, 4.0]
        x1_messy = [10.0, 20.0, None, 40.0]
        x2_messy = [100.0, 200.0, 300.0, 400.0]
        y_c, x_c, idxs = clean_stepwise_data(y_messy, [x1_messy, x2_messy])
        self.assertEqual(len(y_c), 2)
        self.assertEqual(idxs, [0, 3])
        self.assertEqual(y_c.tolist(), [1.0, 4.0])

    def test_stepwise_selection(self):
        res = stepwise_regression(
            response=self.y,
            predictors=self.predictors,
            predictor_names=self.names,
            response_name="Heat",
            method="stepwise",
            alpha_to_enter=0.15,
            alpha_to_remove=0.15,
        )
        self.assertEqual(res["analysis"], "stepwise_regression")
        self.assertGreater(len(res["steps"]), 0)
        # Should select significant predictors (X1, X2 or X1, X4)
        selected = res["selected_terms"]
        self.assertIn("X1", selected)
        self.assertGreater(res["r_sq"], 90.0)
        self.assertGreater(res["r_sq_adj"], 90.0)
        self.assertLess(res["s"], 3.5)

    def test_forward_selection(self):
        res = stepwise_regression(
            response=self.y,
            predictors=self.predictors,
            predictor_names=self.names,
            response_name="Heat",
            method="forward",
            alpha_to_enter=0.05,
        )
        self.assertEqual(res["method"], "forward")
        self.assertGreater(len(res["steps"]), 0)
        for s in res["steps"]:
            if s["action"] == "Add":
                self.assertIsNotNone(s["term"])

    def test_backward_elimination(self):
        res = stepwise_regression(
            response=self.y,
            predictors=self.predictors,
            predictor_names=self.names,
            response_name="Heat",
            method="backward",
            alpha_to_remove=0.10,
        )
        self.assertEqual(res["method"], "backward")
        self.assertGreater(len(res["steps"]), 0)
        self.assertLessEqual(len(res["selected_terms"]), 3)

    def test_information_criteria(self):
        res_aic = stepwise_regression(
            response=self.y,
            predictors=self.predictors,
            predictor_names=self.names,
            response_name="Heat",
            method="forward_aic",
        )
        self.assertEqual(res_aic["method"], "forward_aic")
        self.assertGreater(len(res_aic["selected_terms"]), 0)

        res_bic = stepwise_regression(
            response=self.y,
            predictors=self.predictors,
            predictor_names=self.names,
            response_name="Heat",
            method="backward_bic",
        )
        self.assertEqual(res_bic["method"], "backward_bic")

    def test_report_generation(self):
        res = stepwise_regression(
            response=self.y,
            predictors=self.predictors,
            predictor_names=self.names,
            response_name="Heat",
            method="stepwise",
        )
        rep = generate_stepwise_report(res)
        self.assertIn("Stepwise Regression: Heat versus X1, X2, X3, X4", rep)
        self.assertIn("Stepwise Details", rep)
        self.assertIn("Model Summary", rep)
        self.assertIn("Analysis of Variance", rep)
        self.assertIn("Regression Equation", rep)

    def test_dialog_instantiation(self):
        ws = Worksheet(name="HaldCement")
        ws.columns.append(Column(name="Heat", kind="number", values=self.y))
        ws.columns.append(Column(name="X1", kind="number", values=self.x1))
        ws.columns.append(Column(name="X2", kind="number", values=self.x2))

        pres = Presenter()
        pres.worksheet = ws

        dlg = StepwiseRegressionDialog(pres)
        self.assertEqual(dlg.windowTitle(), "Stepwise Regression")
        self.assertIsNotNone(dlg.combo_method)

    def test_presenter_and_recipe(self):
        ws = Worksheet(name="HaldCement")
        ws.columns.append(Column(name="Heat", kind="number", values=self.y))
        ws.columns.append(Column(name="X1", kind="number", values=self.x1))
        ws.columns.append(Column(name="X2", kind="number", values=self.x2))
        ws.columns.append(Column(name="X3", kind="number", values=self.x3))
        ws.columns.append(Column(name="X4", kind="number", values=self.x4))

        pres = Presenter()
        pres.worksheet = ws

        entry = pres.stepwise_regression({
            "response_index": 0,
            "predictor_indices": [1, 2, 3, 4],
            "method": "stepwise",
            "alpha_to_enter": 0.15,
            "alpha_to_remove": 0.15,
        })
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Stepwise Regression", text)

        # Check recipe columns extraction
        recipe = entry["recipe"]
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
