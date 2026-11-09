"""Unit tests for Orthogonal Regression (Deming Regression)."""
import unittest
import numpy as np

from statcraft.orthogonal_regression import clean_orthogonal_data, fit_orthogonal_regression
from statcraft.orthogonal_regression_report import generate_orthogonal_regression_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry


class TestOrthogonalRegression(unittest.TestCase):
    def setUp(self):
        # Sample calibration data from method comparison study
        # Device A (X) vs Device B (Y)
        np.random.seed(42)
        self.x = [10.2, 15.1, 19.8, 25.3, 30.1, 35.0, 40.2, 45.1, 50.4, 55.0]
        self.y = [11.1, 16.0, 20.9, 26.1, 31.2, 36.3, 41.0, 46.2, 51.5, 56.1]

    def test_clean_data(self):
        x_raw = [1.0, None, 3.0, float('nan'), 5.0]
        y_raw = [2.0, 3.0, None, 4.0, 6.0]
        y, x, idx = clean_orthogonal_data(y_raw, x_raw)
        self.assertEqual(len(x), 2)
        self.assertEqual(len(y), 2)
        self.assertEqual(idx, [0, 4])
        self.assertEqual(list(x), [1.0, 5.0])
        self.assertEqual(list(y), [2.0, 6.0])

    def test_deming_fit_basic(self):
        res = fit_orthogonal_regression(
            response=self.y,
            predictor=self.x,
            error_variance_ratio=1.0,
            response_name="Device B",
            predictor_name="Device A",
        )
        self.assertIn("coefficients", res)
        self.assertEqual(len(res["coefficients"]), 2)

        intercept = res["coefficients"][0]
        slope = res["coefficients"][1]

        self.assertEqual(intercept["term"], "Constant")
        self.assertEqual(slope["term"], "Device A")

        # Slope should be very close to 1.0 (Device B is ~ Device A + 1.0)
        self.assertAlmostEqual(slope["coef"], 1.0, delta=0.05)
        self.assertAlmostEqual(intercept["coef"], 1.0, delta=0.5)

        # Test of Slope = 1
        t_slope = res["test_slope_1"]
        self.assertIn("t_value", t_slope)
        self.assertIn("p_value", t_slope)
        self.assertAlmostEqual(t_slope["t_value"], 2.34, places=2)
        self.assertAlmostEqual(t_slope["p_value"], 0.048, places=3)

        # Error variances
        var_x = res["error_variance_x"]
        var_y = res["error_variance_y"]
        self.assertGreater(var_x, 0)
        self.assertGreater(var_y, 0)
        # Since ratio is 1.0, var_y / var_x should be 1.0
        self.assertAlmostEqual(var_y / var_x, 1.0, places=4)

    def test_delta_sensitivity(self):
        res1 = fit_orthogonal_regression(self.y, self.x, error_variance_ratio=0.5)
        res2 = fit_orthogonal_regression(self.y, self.x, error_variance_ratio=2.0)

        var_x1 = res1["error_variance_x"]
        var_y1 = res1["error_variance_y"]
        var_x2 = res2["error_variance_x"]
        var_y2 = res2["error_variance_y"]

        self.assertAlmostEqual(var_y1 / var_x1, 0.5, places=4)
        self.assertAlmostEqual(var_y2 / var_x2, 2.0, places=4)

    def test_report_generation(self):
        res = fit_orthogonal_regression(
            response=self.y,
            predictor=self.x,
            error_variance_ratio=1.0,
            response_name="Current_Method",
            predictor_name="New_Method",
        )
        report = generate_orthogonal_regression_report(res)
        self.assertIn("Orthogonal Regression: Current_Method versus New_Method", report)
        self.assertIn("Error Variance Ratio", report)
        self.assertIn("Regression Equation", report)
        self.assertIn("Coefficients", report)
        self.assertIn("Test of Slope = 1", report)
        self.assertIn("Error Variances", report)

    def test_presenter_integration(self):
        ws = Worksheet("Demo", [
            Column("X", values=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
            Column("Y", values=[1.1, 2.2, 2.9, 4.1, 5.0, 6.2]),
        ])
        p = Presenter()
        p.worksheet = ws

        entry = p.orthogonal_regression(
            response_column=1,
            predictor_column=0,
            error_variance_ratio=1.0,
        )
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Orthogonal Regression", text)
        self.assertIn("Regression Equation", text)
        self.assertIn("Y =", text)
        self.assertIn("X", text)


if __name__ == "__main__":
    unittest.main()
