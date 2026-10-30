"""Unit tests for One-Sample Poisson Rate (Stat > Basic Statistics > 1-Sample Poisson Rate…)."""
import unittest
import math
from statcraft.one_sample_poisson_engine import (
    calculate_one_sample_poisson,
    one_sample_poisson_settings,
    run_one_sample_poisson,
)
from statcraft.one_sample_poisson_report import format_one_sample_poisson_report
from statcraft.model import Worksheet, Column
from statcraft.recipes import columns as recipe_columns


class TestOneSamplePoisson(unittest.TestCase):
    def test_summarized_exact_two_sided(self):
        # 50 samples, 120 total occurrences, length 1.0 -> T=50, rate=2.4
        res = calculate_one_sample_poisson(
            sample_name="Defects",
            n=50,
            total_occurrences=120,
            length_of_observation=1.0,
            confidence_level=95.0,
            alternative="not_equal",
            method="exact",
            hypothesized_rate=2.0,
        )
        self.assertEqual(res["sample_name"], "Defects")
        self.assertEqual(res["n"], 50)
        self.assertEqual(res["total_occurrences"], 120)
        self.assertEqual(res["total_exposure"], 50.0)
        self.assertAlmostEqual(res["sample_rate"], 2.4, places=6)
        self.assertAlmostEqual(res["mean_per_unit"], 2.4, places=6)

        # CI bounds should enclose sample rate
        self.assertIsNotNone(res["ci_lower"])
        self.assertIsNotNone(res["ci_upper"])
        self.assertLess(res["ci_lower"], 2.4)
        self.assertGreater(res["ci_upper"], 2.4)
        # Expected chi2 exact bounds:
        # lower = chi2.ppf(0.025, 240) / 100
        # upper = chi2.ppf(0.975, 242) / 100
        self.assertAlmostEqual(res["ci_lower"], 1.989839, places=4)
        self.assertAlmostEqual(res["ci_upper"], 2.869812, places=4)

        # Exact P-value for mu0 = 100, observed = 120
        self.assertIsNotNone(res["p_value"])
        self.assertGreater(res["p_value"], 0.04)
        self.assertLess(res["p_value"], 0.06)

    def test_summarized_normal_approx(self):
        res = calculate_one_sample_poisson(
            sample_name="Sample",
            n=50,
            total_occurrences=120,
            length_of_observation=1.0,
            confidence_level=95.0,
            alternative="not_equal",
            method="normal_approx",
            hypothesized_rate=2.0,
        )
        self.assertIsNotNone(res["ci_lower"])
        self.assertIsNotNone(res["ci_upper"])
        self.assertIsNotNone(res["z_value"])
        self.assertIsNotNone(res["p_value"])

        # SE0 = sqrt(2.0 / 50) = 0.2
        # Z = (2.4 - 2.0) / 0.2 = 2.0
        self.assertAlmostEqual(res["z_value"], 2.0, places=4)
        # P-value for Z=2.0 is 2*(1-Phi(2.0)) = 0.0455
        self.assertAlmostEqual(res["p_value"], 0.045500, places=4)

    def test_directional_alternatives(self):
        # Less than
        res_less = calculate_one_sample_poisson(
            sample_name="Sample",
            n=20,
            total_occurrences=15,
            length_of_observation=1.0,
            confidence_level=95.0,
            alternative="less",
            method="exact",
            hypothesized_rate=1.0,
        )
        self.assertIsNone(res_less["ci_lower"])
        self.assertIsNotNone(res_less["ci_upper"])
        self.assertGreater(res_less["p_value"], 0.0)

        # Greater than
        res_greater = calculate_one_sample_poisson(
            sample_name="Sample",
            n=20,
            total_occurrences=15,
            length_of_observation=1.0,
            confidence_level=95.0,
            alternative="greater",
            method="exact",
            hypothesized_rate=1.0,
        )
        self.assertIsNotNone(res_greater["ci_lower"])
        self.assertIsNone(res_greater["ci_upper"])
        self.assertGreater(res_greater["p_value"], 0.0)

    def test_zero_occurrences_boundary(self):
        res = calculate_one_sample_poisson(
            sample_name="Sample",
            n=10,
            total_occurrences=0,
            length_of_observation=1.0,
            confidence_level=95.0,
            alternative="not_equal",
            method="exact",
            hypothesized_rate=0.5,
        )
        self.assertEqual(res["sample_rate"], 0.0)
        self.assertEqual(res["ci_lower"], 0.0)
        self.assertGreater(res["ci_upper"], 0.0)
        self.assertGreater(res["p_value"], 0.0)

    def test_length_of_observation(self):
        # 10 units observed for 2.5 hours each -> T = 25.0
        res = calculate_one_sample_poisson(
            sample_name="Sample",
            n=10,
            total_occurrences=50,
            length_of_observation=2.5,
            confidence_level=95.0,
            alternative="not_equal",
            method="exact",
            hypothesized_rate=2.0,
        )
        self.assertEqual(res["total_exposure"], 25.0)
        self.assertAlmostEqual(res["sample_rate"], 2.0, places=6)
        self.assertAlmostEqual(res["mean_per_unit"], 5.0, places=6)

    def test_worksheet_columns_execution(self):
        ws = Worksheet("W1", [Column("Defects", "number", [2, 3, 0, 1, 4, 2, 1, 0, 2, 3])])
        st = one_sample_poisson_settings(
            data_format=0,
            sample_cols=["Defects"],
            confidence_level=95.0,
            alternative="not_equal",
            method="exact",
            hypothesized_rate=1.5,
        )
        res = run_one_sample_poisson(ws, st)
        self.assertTrue(res["one_sample_poisson"])
        self.assertEqual(len(res["samples"]), 1)
        s0 = res["samples"][0]
        self.assertEqual(s0["sample_name"], "Defects")
        self.assertEqual(s0["n"], 10)
        self.assertEqual(s0["total_occurrences"], 18)
        self.assertAlmostEqual(s0["sample_rate"], 1.8, places=6)

    def test_worksheet_frequency_columns(self):
        ws = Worksheet("W2", [
            Column("Count", "number", [0, 1, 2, 3]),
            Column("Freq", "number", [5, 10, 8, 2]),
        ])
        st = one_sample_poisson_settings(
            data_format=0,
            sample_cols=["Count"],
            freq_cols=["Freq"],
            hypothesized_rate=1.0,
        )
        res = run_one_sample_poisson(ws, st)
        s0 = res["samples"][0]
        # total n = 5 + 10 + 8 + 2 = 25
        # total occurrences = 0*5 + 1*10 + 2*8 + 3*2 = 32
        self.assertEqual(s0["n"], 25)
        self.assertEqual(s0["total_occurrences"], 32)
        self.assertAlmostEqual(s0["sample_rate"], 32 / 25, places=6)

    def test_report_formatting(self):
        res = calculate_one_sample_poisson(
            sample_name="Defects",
            n=50,
            total_occurrences=120,
            length_of_observation=1.0,
            confidence_level=95.0,
            alternative="not_equal",
            method="exact",
            hypothesized_rate=2.0,
        )
        report = format_one_sample_poisson_report(res)
        self.assertIn("Test and CI for One-Sample Poisson Rate: Defects", report)
        self.assertIn("Descriptive Statistics", report)
        self.assertIn("50", report)
        self.assertIn("120", report)
        self.assertIn("2.400000", report)
        self.assertIn("Null hypothesis", report)
        self.assertIn("Exact", report)

    def test_recipe_columns(self):
        recipe = {
            "action": "one_sample_poisson",
            "parameters": {
                "settings": {
                    "data_format": 0,
                    "sample_cols": [0],
                    "freq_cols": [1],
                }
            }
        }
        cols = recipe_columns(recipe)
        self.assertEqual(cols, [0, 1])


if __name__ == "__main__":
    unittest.main()
