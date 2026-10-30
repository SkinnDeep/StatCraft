"""Unit tests for native StatCraft One-Sample Proportion test."""
import unittest
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry
from statcraft.one_sample_proportion_engine import (
    one_sample_proportion_settings,
    run_one_sample_proportion,
)
from statcraft.one_sample_proportion_report import format_one_sample_proportion_report


class TestOneSampleProportionEngine(unittest.TestCase):
    def setUp(self):
        # 32 events out of 50 trials (binary 0 and 1)
        self.vals1 = [1] * 32 + [0] * 18
        # 40 events out of 50 trials
        self.vals2 = [1] * 40 + [0] * 10
        self.ws = Worksheet("OnePropData", [
            Column("Sample1", "number", self.vals1),
            Column("Sample2", "number", self.vals2),
        ])

    def test_single_column_exact(self):
        st = one_sample_proportion_settings(
            data_format=0,
            sample_cols=[0],
            confidence_level=95.0,
            perform_test=True,
            hypothesized_proportion=0.5,
            alternative="not_equal",
            method="exact",
        )
        res = run_one_sample_proportion(self.ws, st)
        self.assertEqual(len(res["samples"]), 1)
        s0 = res["samples"][0]
        self.assertEqual(s0["n"], 50)
        self.assertEqual(s0["events"], 32)
        self.assertAlmostEqual(s0["sample_p"], 0.64)
        # Clopper-Pearson exact 95% CI: (0.491931, 0.770843)
        self.assertAlmostEqual(s0["ci_lower"], 0.491931, places=4)
        self.assertAlmostEqual(s0["ci_upper"], 0.770843, places=4)
        # Exact two-sided P-value = 0.0649
        self.assertAlmostEqual(s0["p_value"], 0.0649, places=3)

    def test_normal_approximation(self):
        st = one_sample_proportion_settings(
            data_format=0,
            sample_cols=[0],
            confidence_level=95.0,
            perform_test=True,
            hypothesized_proportion=0.5,
            alternative="not_equal",
            method="normal",
        )
        res = run_one_sample_proportion(self.ws, st)
        s0 = res["samples"][0]
        # SE_sample = sqrt(0.64 * 0.36 / 50) = 0.06788225
        # Wald CI: 0.64 +/- 1.95996 * 0.06788225 = (0.506953, 0.773047)
        self.assertAlmostEqual(s0["ci_lower"], 0.5070, places=3)
        self.assertAlmostEqual(s0["ci_upper"], 0.7730, places=3)
        # Under H0: SE_0 = sqrt(0.5 * 0.5 / 50) = 0.070710678
        # Z = (0.64 - 0.5) / 0.070710678 = 1.97989899
        self.assertAlmostEqual(s0["z_statistic"], 1.98, places=2)
        # Two-sided normal P-value = 2 * (1 - norm.cdf(1.979899)) = 0.0477
        self.assertAlmostEqual(s0["p_value"], 0.0477, places=3)

    def test_directional_alternatives(self):
        # Greater than:
        st_gt = one_sample_proportion_settings(
            data_format=0,
            sample_cols=[0],
            hypothesized_proportion=0.5,
            alternative="greater_than",
            method="exact",
        )
        res_gt = run_one_sample_proportion(self.ws, st_gt)
        s_gt = res_gt["samples"][0]
        self.assertIsNotNone(s_gt["ci_lower"])
        self.assertIsNone(s_gt["ci_upper"])
        self.assertAlmostEqual(s_gt["ci_lower"], 0.514231, places=4)
        self.assertAlmostEqual(s_gt["p_value"], 0.0325, places=3)

        # Less than:
        st_lt = one_sample_proportion_settings(
            data_format=0,
            sample_cols=[0],
            hypothesized_proportion=0.5,
            alternative="less_than",
            method="exact",
        )
        res_lt = run_one_sample_proportion(self.ws, st_lt)
        s_lt = res_lt["samples"][0]
        self.assertIsNone(s_lt["ci_lower"])
        self.assertIsNotNone(s_lt["ci_upper"])
        self.assertAlmostEqual(s_lt["ci_upper"], 0.752794, places=4)
        self.assertAlmostEqual(s_lt["p_value"], 0.9836, places=3)

    def test_no_hypothesis_test(self):
        st = one_sample_proportion_settings(
            data_format=0,
            sample_cols=[0],
            perform_test=False,
            method="exact",
        )
        res = run_one_sample_proportion(self.ws, st)
        s0 = res["samples"][0]
        self.assertIsNone(s0["z_statistic"])
        self.assertIsNone(s0["p_value"])
        self.assertIsNotNone(s0["ci_lower"])
        self.assertIsNotNone(s0["ci_upper"])

    def test_summarized_data(self):
        st = one_sample_proportion_settings(
            data_format=2,
            summarized={"events": 32, "trials": 50},
            perform_test=True,
            hypothesized_proportion=0.5,
            method="exact",
        )
        res = run_one_sample_proportion(None, st)
        self.assertEqual(len(res["samples"]), 1)
        s0 = res["samples"][0]
        self.assertEqual(s0["n"], 50)
        self.assertEqual(s0["events"], 32)
        self.assertAlmostEqual(s0["sample_p"], 0.64)
        self.assertAlmostEqual(s0["p_value"], 0.0649, places=3)

    def test_multiple_columns(self):
        st = one_sample_proportion_settings(
            data_format=0,
            sample_cols=[0, 1],
            perform_test=True,
            hypothesized_proportion=0.5,
        )
        res = run_one_sample_proportion(self.ws, st)
        self.assertEqual(len(res["samples"]), 2)
        self.assertEqual(res["samples"][0]["name"], "Sample1")
        self.assertEqual(res["samples"][1]["name"], "Sample2")
        self.assertAlmostEqual(res["samples"][0]["sample_p"], 0.64)
        self.assertAlmostEqual(res["samples"][1]["sample_p"], 0.80)

    def test_validation_errors(self):
        # Events > trials
        st1 = one_sample_proportion_settings(
            data_format=2,
            summarized={"events": 55, "trials": 50},
        )
        with self.assertRaises(ValueError):
            run_one_sample_proportion(None, st1)

        # Hypothesized proportion out of range
        st2 = one_sample_proportion_settings(
            data_format=2,
            summarized={"events": 10, "trials": 20},
            hypothesized_proportion=1.5,
        )
        with self.assertRaises(ValueError):
            run_one_sample_proportion(None, st2)

    def test_report_formatting(self):
        st = one_sample_proportion_settings(
            data_format=0,
            sample_cols=[0],
            perform_test=True,
            hypothesized_proportion=0.5,
            method="exact",
        )
        res = run_one_sample_proportion(self.ws, st)
        entry = {"title": "Test and CI for One Proportion: Sample1", "result": res}
        report = format_one_sample_proportion_report(entry)
        self.assertIn("Test and CI for One Proportion: Sample1", report)
        self.assertIn("Descriptive Statistics", report)
        self.assertIn("Test", report)
        self.assertIn("Null hypothesis", report)
        self.assertIn("H0: p = 0.5", report)
        self.assertIn("Method", report)
        self.assertIn("Exact", report)
        self.assertIn("P-Value", report)


if __name__ == "__main__":
    unittest.main()
