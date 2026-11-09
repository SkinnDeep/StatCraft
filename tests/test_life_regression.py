"""Unit tests for Regression with Life Data (Accelerated Failure Time model)."""
import unittest
import numpy as np

from statcraft.life_regression import clean_life_data, fit_life_regression
from statcraft.life_regression_report import generate_life_regression_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry


class TestLifeRegression(unittest.TestCase):
    def setUp(self):
        # Stress testing lifetime data: Voltage vs Lifetime (Hours)
        # Higher voltage leads to shorter lifetime (negative slope in ln(T))
        np.random.seed(42)
        self.voltage = [100.0, 100.0, 100.0, 120.0, 120.0, 120.0, 140.0, 140.0, 140.0, 160.0, 160.0, 160.0]
        self.lifetime = [450.0, 520.0, 600.0, 210.0, 250.0, 310.0, 95.0, 110.0, 140.0, 40.0, 55.0, 65.0]
        self.censor = [1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1]  # 2 censored units

    def test_clean_data(self):
        y_raw = [10.0, None, 20.0, -5.0, 30.0]
        x_raw = [[1.0, 2.0, 3.0, 4.0, 5.0]]
        c_raw = [1, 1, 0, 1, 1]
        y, x, c, names = clean_life_data(y_raw, x_raw, c_raw, ["Voltage"])
        self.assertEqual(len(y), 3)
        self.assertEqual(list(y), [10.0, 20.0, 30.0])
        self.assertEqual(list(c), [1, 0, 1])

    def test_weibull_life_regression(self):
        res = fit_life_regression(
            response=self.lifetime,
            predictors=[self.voltage],
            censor=self.censor,
            distribution="weibull",
            predictor_names=["Voltage"],
        )
        self.assertEqual(res["analysis"], "life_regression")
        self.assertEqual(res["distribution"], "Weibull")
        self.assertEqual(res["n_obs"], 12)
        self.assertEqual(res["n_failures"], 10)
        self.assertEqual(res["n_censored"], 2)

        coefs = res["coefficients"]
        self.assertEqual(len(coefs), 2)
        intercept = coefs[0]
        slope = coefs[1]

        self.assertEqual(slope["term"], "Voltage")
        self.assertLess(slope["coef"], 0.0)  # Shorter life at higher voltage
        self.assertGreater(slope["se_coef"], 0.0)
        self.assertLess(slope["p_value"], 0.01)

        # Scale and shape parameters
        params = res["parameters"]
        self.assertGreater(params["scale"], 0.0)
        self.assertGreater(params["shape"], 0.0)

        # Percentiles
        pcts = res["percentiles"]
        self.assertGreater(len(pcts), 3)
        p50 = next(p for p in pcts if abs(p["percent"] - 50.0) < 1e-4)
        self.assertGreater(p50["estimate"], 0.0)
        self.assertLessEqual(p50["ci_lower"], p50["estimate"])
        self.assertGreaterEqual(p50["ci_upper"], p50["estimate"])

    def test_alternative_distributions(self):
        for dist in ["lognormal", "exponential", "loglogistic"]:
            res = fit_life_regression(
                response=self.lifetime,
                predictors=[self.voltage],
                censor=self.censor,
                distribution=dist,
                predictor_names=["Voltage"],
            )
            self.assertEqual(res["analysis"], "life_regression")
            coefs = res["coefficients"]
            slope = coefs[1]
            self.assertLess(slope["coef"], 0.0)
            self.assertGreater(res["parameters"]["scale"], 0.0)

    def test_report_generation(self):
        res = fit_life_regression(
            response=self.lifetime,
            predictors=[self.voltage],
            censor=self.censor,
            distribution="weibull",
            predictor_names=["Voltage"],
        )
        report = generate_life_regression_report(res)
        self.assertIn("Regression with Life Data: Lifetime versus Voltage", report)
        self.assertIn("Assumed distribution: Weibull", report)
        self.assertIn("Censoring Information", report)
        self.assertIn("Regression Table", report)
        self.assertIn("Distribution Parameters", report)
        self.assertIn("Scale (sigma)", report)
        self.assertIn("Shape (Weibull)", report)
        self.assertIn("Table of Percentiles", report)

    def test_presenter_integration(self):
        ws = Worksheet("LifeStudy", [
            Column("Lifetime", values=self.lifetime),
            Column("Voltage", values=self.voltage),
            Column("Censor", values=self.censor),
        ])
        p = Presenter()
        p.worksheet = ws

        entry = p.life_regression(
            response_column=0,
            predictor_columns=[1],
            censor_column=2,
            distribution="weibull",
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "life_regression")
        text = format_entry(entry)
        self.assertIn("Regression with Life Data", text)
        self.assertIn("Voltage", text)
        self.assertIn("Distribution Parameters", text)


if __name__ == "__main__":
    unittest.main()
