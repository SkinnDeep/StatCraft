"""Unit tests for native StatCraft Paired t test."""
import unittest
import numpy as np
from statcraft.model import Column, Worksheet
from statcraft.paired_t_engine import (
    paired_t_settings,
    run_paired_t,
)
from statcraft.paired_t_report import format_paired_t_report


class TestPairedTEngine(unittest.TestCase):
    def setUp(self):
        # Sample 1 and Sample 2 paired observations
        self.s1 = [10.2, 11.5, 12.0, 11.8, 12.4, 10.9, 11.2, 12.1]
        self.s2 = [8.5, 9.2, 8.8, 9.5, 9.0, 8.7, 9.1, 8.9]
        self.ws = Worksheet("PairedDemo", [
            Column("Before", "number", self.s1),
            Column("After", "number", self.s2),
            Column("WithMissing1", "number", self.s1[:6] + [None, 12.1]),
            Column("WithMissing2", "number", [None] + self.s2[1:]),
        ])

    def test_paired_t_raw_columns(self):
        st = paired_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            confidence_level=95.0,
            hypothesized_difference=0.0,
            alternative="not_equal",
        )
        res = run_paired_t(self.ws, st)
        self.assertEqual(res["sample1"]["n"], 8)
        self.assertEqual(res["sample2"]["n"], 8)
        self.assertEqual(res["differences"]["n"], 8)
        self.assertEqual(res["df"], 7)

        # Expected differences: [1.7, 2.3, 3.2, 2.3, 3.4, 2.2, 2.1, 3.2]
        diffs = [a - b for a, b in zip(self.s1, self.s2)]
        mean_d = float(np.mean(diffs))
        sd_d = float(np.std(diffs, ddof=1))
        se_d = sd_d / np.sqrt(8)

        self.assertAlmostEqual(res["differences"]["mean"], mean_d)
        self.assertAlmostEqual(res["differences"]["sd"], sd_d)
        self.assertAlmostEqual(res["differences"]["se_mean"], se_d)

        expected_t = mean_d / se_d
        self.assertAlmostEqual(res["t_statistic"], expected_t)
        self.assertLess(res["p_value"], 0.001)
        self.assertIsNotNone(res["differences"]["ci_lower"])
        self.assertIsNotNone(res["differences"]["ci_upper"])

    def test_hypothesized_difference(self):
        st = paired_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            hypothesized_difference=2.0,
        )
        res = run_paired_t(self.ws, st)
        diffs = [a - b for a, b in zip(self.s1, self.s2)]
        mean_d = float(np.mean(diffs))
        sd_d = float(np.std(diffs, ddof=1))
        se_d = sd_d / np.sqrt(8)
        expected_t = (mean_d - 2.0) / se_d
        self.assertAlmostEqual(res["t_statistic"], expected_t)

    def test_directional_alternatives(self):
        # Greater than:
        st_gt = paired_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            hypothesized_difference=2.0,
            alternative="greater_than",
        )
        res_gt = run_paired_t(self.ws, st_gt)
        self.assertIsNotNone(res_gt["differences"]["ci_lower"])
        self.assertIsNone(res_gt["differences"]["ci_upper"])

        # Less than:
        st_lt = paired_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            hypothesized_difference=2.0,
            alternative="less_than",
        )
        res_lt = run_paired_t(self.ws, st_lt)
        self.assertIsNone(res_lt["differences"]["ci_lower"])
        self.assertIsNotNone(res_lt["differences"]["ci_upper"])

    def test_summarized_differences(self):
        st = paired_t_settings(
            data_format=2,
            summarized={"n": 15, "mean": 3.5, "sd": 1.8},
            confidence_level=95.0,
            hypothesized_difference=0.0,
        )
        res = run_paired_t(None, st)
        self.assertEqual(res["differences"]["n"], 15)
        self.assertEqual(res["df"], 14)
        self.assertAlmostEqual(res["differences"]["mean"], 3.5)
        self.assertAlmostEqual(res["differences"]["sd"], 1.8)
        se_d = 1.8 / np.sqrt(15)
        self.assertAlmostEqual(res["t_statistic"], 3.5 / se_d)
        self.assertLess(res["p_value"], 0.001)

    def test_missing_value_listwise(self):
        # WithMissing1 has missing at index 6; WithMissing2 has missing at index 0
        # Valid complete pairs: indices 1, 2, 3, 4, 5, 7 -> exactly 6 complete pairs
        st = paired_t_settings(
            data_format=1,
            sample1_col=2,
            sample2_col=3,
        )
        res = run_paired_t(self.ws, st)
        self.assertEqual(res["differences"]["n"], 6)
        self.assertEqual(res["df"], 5)

    def test_report_formatting(self):
        st = paired_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
        )
        res = run_paired_t(self.ws, st)
        entry = {"title": "Paired T-Test and CI: Before, After", "result": res}
        report = format_paired_t_report(entry)
        self.assertIn("Paired T-Test and CI: Before, After", report)
        self.assertIn("Descriptive Statistics", report)
        self.assertIn("Estimation for Paired Difference", report)
        self.assertIn("Test", report)
        self.assertIn("Null hypothesis", report)
        self.assertIn("T-Value", report)
        self.assertIn("P-Value", report)


if __name__ == "__main__":
    unittest.main()
