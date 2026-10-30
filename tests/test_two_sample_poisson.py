"""Unit tests for Two-Sample Poisson Rate (Stat > Basic Statistics > 2-Sample Poisson Rate…)."""
import unittest
import math
from statcraft.two_sample_poisson_engine import (
    calculate_two_sample_poisson,
    two_sample_poisson_settings,
    run_two_sample_poisson,
)
from statcraft.two_sample_poisson_report import format_two_sample_poisson_report
from statcraft.model import Worksheet, Column
from statcraft.recipes import columns as recipe_columns


class TestTwoSamplePoisson(unittest.TestCase):
    def test_summarized_separate_rates(self):
        # Sample 1: 50 size, 120 occurrences, 1.0 length -> Rate = 2.4
        # Sample 2: 50 size, 90 occurrences, 1.0 length -> Rate = 1.8
        res = calculate_two_sample_poisson(
            sample1_name="Sample 1",
            sample2_name="Sample 2",
            n1=50,
            x1=120,
            t1=50.0,
            n2=50,
            x2=90,
            t2=50.0,
            hypothesized_difference=0.0,
            confidence_level=95.0,
            alternative="not_equal",
            test_method="separate",
        )
        self.assertEqual(res["sample1_name"], "Sample 1")
        self.assertEqual(res["sample2_name"], "Sample 2")
        self.assertEqual(res["x1"], 120)
        self.assertEqual(res["x2"], 90)
        self.assertEqual(res["t1"], 50.0)
        self.assertEqual(res["t2"], 50.0)
        self.assertAlmostEqual(res["rate1"], 2.4, places=6)
        self.assertAlmostEqual(res["rate2"], 1.8, places=6)
        self.assertAlmostEqual(res["diff"], 0.6, places=6)

        # CI bounds should enclose diff = 0.6
        self.assertIsNotNone(res["ci_lower"])
        self.assertIsNotNone(res["ci_upper"])
        self.assertLess(res["ci_lower"], 0.6)
        self.assertGreater(res["ci_upper"], 0.6)

        # Z test separate
        self.assertIsNotNone(res["z_value"])
        self.assertIsNotNone(res["p_value"])
        self.assertGreater(res["z_value"], 2.0)
        self.assertLess(res["p_value"], 0.05)

    def test_summarized_pooled_rates_exact_binomial(self):
        res = calculate_two_sample_poisson(
            sample1_name="Sample 1",
            sample2_name="Sample 2",
            n1=40,
            x1=10,
            t1=40.0,
            n2=40,
            x2=10,
            t2=40.0,
            hypothesized_difference=0.0,
            confidence_level=95.0,
            alternative="not_equal",
            test_method="pooled",
        )
        self.assertAlmostEqual(res["diff"], 0.0, places=6)
        self.assertAlmostEqual(res["z_value"], 0.0, places=6)
        self.assertAlmostEqual(res["p_value"], 1.0, places=6)
        # Exact conditional test
        self.assertIsNotNone(res["exact_p_value"])
        self.assertAlmostEqual(res["exact_p_value"], 1.0, places=6)

    def test_unstacked_columns(self):
        ws = Worksheet("Unstacked", [
            Column("Defects_A", values=[2, 4, 1, 3, 0]),
            Column("Defects_B", values=[1, 1, 0, 2, 1]),
        ])
        settings = two_sample_poisson_settings({
            "data_format": "unstacked",
            "sample1_col": 0,
            "sample2_col": 1,
            "hypothesized_difference": 0.0,
            "confidence_level": 95.0,
            "alternative": "not_equal",
            "test_method": "separate",
        })
        res = run_two_sample_poisson(ws, settings)
        self.assertEqual(res["x1"], 10)
        self.assertEqual(res["x2"], 5)
        self.assertEqual(res["n1"], 5)
        self.assertEqual(res["n2"], 5)
        self.assertAlmostEqual(res["rate1"], 2.0, places=6)
        self.assertAlmostEqual(res["rate2"], 1.0, places=6)

    def test_stacked_columns_with_lengths(self):
        ws = Worksheet("Stacked", [
            Column("Events", "number", values=[10, 15, 8, 12]),
            Column("Group", "text", values=["A", "A", "B", "B"]),
            Column("Exposure", "number", values=[2.0, 3.0, 2.0, 2.0]),
        ])
        settings = two_sample_poisson_settings({
            "data_format": "stacked",
            "sample_col": 0,
            "group_col": 1,
            "length_col": 2,
            "confidence_level": 90.0,
            "alternative": "greater",
            "test_method": "pooled",
        })
        res = run_two_sample_poisson(ws, settings)
        self.assertEqual(res["x1"], 25)
        self.assertEqual(res["t1"], 5.0)
        self.assertEqual(res["x2"], 20)
        self.assertEqual(res["t2"], 4.0)
        self.assertAlmostEqual(res["rate1"], 5.0, places=6)
        self.assertAlmostEqual(res["rate2"], 5.0, places=6)
        self.assertAlmostEqual(res["diff"], 0.0, places=6)

    def test_report_formatting(self):
        res = calculate_two_sample_poisson(
            sample1_name="Machine 1",
            sample2_name="Machine 2",
            n1=50,
            x1=120,
            t1=50.0,
            n2=50,
            x2=90,
            t2=50.0,
            hypothesized_difference=0.0,
            confidence_level=95.0,
            alternative="not_equal",
            test_method="pooled",
        )
        report = format_two_sample_poisson_report(res)
        self.assertIn("Two-Sample Poisson Rate", report)
        self.assertIn("Descriptive Statistics", report)
        self.assertIn("Machine 1", report)
        self.assertIn("Machine 2", report)
        self.assertIn("Test", report)
        self.assertIn("Null hypothesis", report)

    def test_recipe_column_tracking(self):
        settings = two_sample_poisson_settings({
            "data_format": "unstacked",
            "sample1_col": 0,
            "sample2_col": 1,
            "length1_col": 2,
            "length2_col": 3,
        })
        cols = recipe_columns({"action": "two_sample_poisson", "parameters": {"settings": settings}})
        self.assertEqual(set(cols), {0, 1, 2, 3})


if __name__ == "__main__":
    unittest.main()
