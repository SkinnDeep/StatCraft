"""Unit tests for native StatCraft One-Sample Z test."""
import unittest
import numpy as np
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry
from statcraft.one_sample_z_engine import (
    one_sample_z_settings,
    run_one_sample_z,
)
from statcraft.one_sample_z_report import format_one_sample_z_report


class TestOneSampleZEngine(unittest.TestCase):
    def setUp(self):
        # Sample 1: 10, 12, 11, 14, 13 (n=5, mean=12.0)
        self.vals1 = [10.0, 12.0, 11.0, 14.0, 13.0]
        # Sample 2: 20, 22, 24, 26, 28 (n=5, mean=24.0)
        self.vals2 = [20.0, 22.0, 24.0, 26.0, 28.0]
        self.ws = Worksheet("OneSampleZData", [
            Column("X1", "number", self.vals1),
            Column("X2", "number", self.vals2),
        ])

    def test_single_column_default(self):
        st = one_sample_z_settings(
            data_format=0,
            sample_cols=[0],
            sigma=2.0,
            confidence_level=95.0,
            perform_test=True,
            hypothesized_mean=0.0,
        )
        res = run_one_sample_z(self.ws, st)
        self.assertEqual(len(res["samples"]), 1)
        s0 = res["samples"][0]
        self.assertEqual(s0["n"], 5)
        self.assertAlmostEqual(s0["mean"], 12.0)
        # se_mean = 2.0 / sqrt(5) = 0.894427
        self.assertAlmostEqual(s0["se_mean"], 2.0 / np.sqrt(5))
        # z = 12 / (2 / sqrt(5)) = 13.41640786
        self.assertAlmostEqual(s0["z_statistic"], 12.0 / (2.0 / np.sqrt(5)), places=4)
        self.assertLess(s0["p_value"], 0.0001)
        self.assertIsNotNone(s0["ci_lower"])
        self.assertIsNotNone(s0["ci_upper"])

    def test_hypothesized_mean(self):
        st = one_sample_z_settings(
            data_format=0,
            sample_cols=[0],
            sigma=2.5,
            confidence_level=95.0,
            perform_test=True,
            hypothesized_mean=11.0,
        )
        res = run_one_sample_z(self.ws, st)
        s0 = res["samples"][0]
        # z = (12 - 11) / (2.5 / sqrt(5)) = 1 / 1.1180339887 = 0.894427
        self.assertAlmostEqual(s0["z_statistic"], 1.0 / (2.5 / np.sqrt(5)), places=4)
        # p-value = 2 * (1 - norm.cdf(0.894427)) = 0.3711
        self.assertAlmostEqual(s0["p_value"], 0.3711, places=3)

    def test_directional_alternatives(self):
        # Greater than:
        st_gt = one_sample_z_settings(
            data_format=0,
            sample_cols=[0],
            sigma=2.5,
            hypothesized_mean=11.0,
            alternative="greater_than",
        )
        res_gt = run_one_sample_z(self.ws, st_gt)
        s_gt = res_gt["samples"][0]
        self.assertIsNotNone(s_gt["ci_lower"])
        self.assertIsNone(s_gt["ci_upper"])
        self.assertAlmostEqual(s_gt["p_value"], 0.3711 / 2.0, places=3)

        # Less than:
        st_lt = one_sample_z_settings(
            data_format=0,
            sample_cols=[0],
            sigma=2.5,
            hypothesized_mean=11.0,
            alternative="less_than",
        )
        res_lt = run_one_sample_z(self.ws, st_lt)
        s_lt = res_lt["samples"][0]
        self.assertIsNone(s_lt["ci_lower"])
        self.assertIsNotNone(s_lt["ci_upper"])
        self.assertAlmostEqual(s_lt["p_value"], 1.0 - (0.3711 / 2.0), places=3)

    def test_no_hypothesis_test(self):
        st = one_sample_z_settings(
            data_format=0,
            sample_cols=[0],
            sigma=2.0,
            perform_test=False,
        )
        res = run_one_sample_z(self.ws, st)
        s0 = res["samples"][0]
        self.assertIsNone(s0["z_statistic"])
        self.assertIsNone(s0["p_value"])
        self.assertIsNotNone(s0["ci_lower"])
        self.assertIsNotNone(s0["ci_upper"])

    def test_summarized_data(self):
        st = one_sample_z_settings(
            data_format=2,
            summarized={"n": 16, "mean": 50.0},
            sigma=4.0,
            perform_test=True,
            hypothesized_mean=48.0,
        )
        res = run_one_sample_z(None, st)
        self.assertEqual(len(res["samples"]), 1)
        s0 = res["samples"][0]
        self.assertEqual(s0["n"], 16)
        self.assertEqual(s0["mean"], 50.0)
        self.assertEqual(s0["se_mean"], 1.0)  # 4 / sqrt(16)
        # z = (50 - 48) / 1.0 = 2.0
        self.assertAlmostEqual(s0["z_statistic"], 2.0)
        # p-value = 2 * (1 - norm.cdf(2.0)) = 0.045500
        self.assertAlmostEqual(s0["p_value"], 0.0455, places=3)

    def test_multiple_columns(self):
        st = one_sample_z_settings(
            data_format=0,
            sample_cols=[0, 1],
            sigma=1.5,
            perform_test=True,
            hypothesized_mean=15.0,
        )
        res = run_one_sample_z(self.ws, st)
        self.assertEqual(len(res["samples"]), 2)
        self.assertEqual(res["samples"][0]["name"], "X1")
        self.assertEqual(res["samples"][1]["name"], "X2")
        self.assertAlmostEqual(res["samples"][0]["mean"], 12.0)
        self.assertAlmostEqual(res["samples"][1]["mean"], 24.0)

    def test_invalid_sigma(self):
        st = one_sample_z_settings(
            data_format=0,
            sample_cols=[0],
            sigma=-1.0,
        )
        with self.assertRaises(ValueError):
            run_one_sample_z(self.ws, st)

    def test_report_formatting(self):
        st = one_sample_z_settings(
            data_format=0,
            sample_cols=[0],
            sigma=2.5,
            perform_test=True,
            hypothesized_mean=10.0,
        )
        res = run_one_sample_z(self.ws, st)
        entry = {"title": "One-Sample Z: X1", "result": res}
        report = format_one_sample_z_report(entry)
        self.assertIn("One-Sample Z: X1", report)
        self.assertIn("Known standard deviation = 2.5", report)
        self.assertIn("Descriptive Statistics", report)
        self.assertIn("Test", report)
        self.assertIn("Null hypothesis", report)
        self.assertIn("H0: μ = 10", report)
        self.assertIn("Z-Value", report)
        self.assertIn("P-Value", report)


if __name__ == "__main__":
    unittest.main()
