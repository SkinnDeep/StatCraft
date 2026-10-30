"""Unit tests for native StatCraft Two-Sample Proportion test."""
import unittest
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry
from statcraft.two_sample_proportion_engine import (
    two_sample_proportion_settings,
    run_two_sample_proportion,
)
from statcraft.two_sample_proportion_report import format_two_sample_proportion_report


class TestTwoSampleProportionEngine(unittest.TestCase):
    def setUp(self):
        # Sample 1: 35 events out of 50 trials (p1 = 0.70)
        self.vals1 = [1] * 35 + [0] * 15
        # Sample 2: 25 events out of 50 trials (p2 = 0.50)
        self.vals2 = [1] * 25 + [0] * 25
        self.ws = Worksheet("TwoPropData", [
            Column("Sample1", "number", self.vals1),
            Column("Sample2", "number", self.vals2),
            Column("Combined", "number", self.vals1 + self.vals2),
            Column("GroupID", "text", ["Group1"] * 50 + ["Group2"] * 50),
        ])

    def test_unstacked_mode_pooled(self):
        st = two_sample_proportion_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            confidence_level=95.0,
            hypothesized_difference=0.0,
            alternative="not_equal",
            test_method="pooled",
        )
        res = run_two_sample_proportion(self.ws, st)
        self.assertEqual(res["sample1"]["n"], 50)
        self.assertEqual(res["sample1"]["events"], 35)
        self.assertAlmostEqual(res["sample1"]["sample_p"], 0.70)
        self.assertEqual(res["sample2"]["n"], 50)
        self.assertEqual(res["sample2"]["events"], 25)
        self.assertAlmostEqual(res["sample2"]["sample_p"], 0.50)
        self.assertAlmostEqual(res["difference"], 0.20)

        # Pooled test: p_pool = 60/100 = 0.60
        # SE_pool = sqrt(0.6 * 0.4 * (1/50 + 1/50)) = sqrt(0.24 * 0.04) = sqrt(0.0096) = 0.09797959
        # Z = 0.20 / 0.09797959 = 2.04124
        self.assertAlmostEqual(res["z_statistic"], 2.04, places=2)
        # P-value = 2 * (1 - norm.cdf(2.04124)) = 0.0412
        self.assertAlmostEqual(res["p_value"], 0.041, places=3)
        self.assertIsNotNone(res["ci_lower"])
        self.assertIsNotNone(res["ci_upper"])

    def test_unstacked_mode_unpooled(self):
        st = two_sample_proportion_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            confidence_level=95.0,
            hypothesized_difference=0.0,
            alternative="not_equal",
            test_method="unpooled",
        )
        res = run_two_sample_proportion(self.ws, st)
        # SE_diff = sqrt(0.7*0.3/50 + 0.5*0.5/50) = sqrt(0.0042 + 0.005) = sqrt(0.0092) = 0.0959166
        # Z = 0.20 / 0.0959166 = 2.0851
        self.assertAlmostEqual(res["z_statistic"], 2.09, places=2)
        self.assertAlmostEqual(res["p_value"], 0.037, places=3)

    def test_stacked_mode(self):
        st = two_sample_proportion_settings(
            data_format=0,
            samples_col=2,
            sample_ids_col=3,
            test_method="pooled",
        )
        res = run_two_sample_proportion(self.ws, st)
        self.assertEqual(res["sample1"]["n"], 50)
        self.assertEqual(res["sample2"]["n"], 50)
        self.assertAlmostEqual(res["difference"], 0.20)

    def test_summarized_mode(self):
        st = two_sample_proportion_settings(
            data_format=2,
            summarized={"events1": 35, "trials1": 50, "events2": 25, "trials2": 50},
            test_method="pooled",
        )
        res = run_two_sample_proportion(None, st)
        self.assertEqual(res["sample1"]["n"], 50)
        self.assertEqual(res["sample2"]["n"], 50)
        self.assertAlmostEqual(res["difference"], 0.20)
        self.assertAlmostEqual(res["z_statistic"], 2.04, places=2)

    def test_directional_alternatives(self):
        # Greater than
        st_gt = two_sample_proportion_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            alternative="greater_than",
            test_method="pooled",
        )
        res_gt = run_two_sample_proportion(self.ws, st_gt)
        self.assertIsNotNone(res_gt["ci_lower"])
        self.assertIsNone(res_gt["ci_upper"])
        self.assertAlmostEqual(res_gt["p_value"], 0.0412 / 2.0, places=3)

        # Less than
        st_lt = two_sample_proportion_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            alternative="less_than",
            test_method="pooled",
        )
        res_lt = run_two_sample_proportion(self.ws, st_lt)
        self.assertIsNone(res_lt["ci_lower"])
        self.assertIsNotNone(res_lt["ci_upper"])
        self.assertAlmostEqual(res_lt["p_value"], 1.0 - (0.0412 / 2.0), places=3)

    def test_report_formatting(self):
        st = two_sample_proportion_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
        )
        res = run_two_sample_proportion(self.ws, st)
        entry = {"title": "Test and CI for Two Proportions: Sample1, Sample2", "result": res}
        report = format_two_sample_proportion_report(entry)
        self.assertIn("Test and CI for Two Proportions", report)
        self.assertIn("Descriptive Statistics", report)
        self.assertIn("Estimation for Difference", report)
        self.assertIn("Normal approximation", report)
        self.assertIn("Fisher's exact", report)


if __name__ == "__main__":
    unittest.main()
