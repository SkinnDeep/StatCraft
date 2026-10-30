"""Unit tests for native StatCraft Two-Sample t test."""
import unittest
import numpy as np
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry
from statcraft.two_sample_t_engine import (
    two_sample_t_settings,
    run_two_sample_t,
)
from statcraft.two_sample_t_report import format_two_sample_t_report


class TestTwoSampleTEngine(unittest.TestCase):
    def setUp(self):
        # Known textbook data:
        # Sample 1: 10, 12, 11, 14, 13 (n=5, mean=12.0, var=2.5, sd=1.5811388)
        # Sample 2: 7, 8, 9, 8, 8 (n=5, mean=8.0, var=0.5, sd=0.7071068)
        self.s1 = [10.0, 12.0, 11.0, 14.0, 13.0]
        self.s2 = [7.0, 8.0, 9.0, 8.0, 8.0]
        self.ws = Worksheet("TwoSampleData", [
            Column("S1", "number", self.s1),
            Column("S2", "number", self.s2),
            Column("StackedVals", "number", self.s1 + self.s2),
            Column("Group", "text", ["A"] * 5 + ["B"] * 5),
        ])

    def test_unstacked_welch(self):
        st = two_sample_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            confidence_level=95.0,
            assume_equal_variances=False,
        )
        res = run_two_sample_t(self.ws, st)
        self.assertEqual(res["sample1"]["n"], 5)
        self.assertEqual(res["sample2"]["n"], 5)
        self.assertAlmostEqual(res["sample1"]["mean"], 12.0)
        self.assertAlmostEqual(res["sample2"]["mean"], 8.0)
        self.assertAlmostEqual(res["difference"], 4.0)
        # se_diff = sqrt(2.5/5 + 0.5/5) = sqrt(0.5 + 0.1) = sqrt(0.6) = 0.774596669
        self.assertAlmostEqual(res["se_difference"], np.sqrt(0.6))
        # t = 4.0 / sqrt(0.6) = 5.16397779
        self.assertAlmostEqual(res["t_statistic"], 4.0 / np.sqrt(0.6), places=4)
        # Welch df = (0.6)^2 / [ (0.5)^2/4 + (0.1)^2/4 ] = 0.36 / [ 0.0625 + 0.0025 ] = 0.36 / 0.065 = 5.538 -> round to 6
        self.assertEqual(res["df"], 6)
        self.assertLess(res["p_value"], 0.01)
        self.assertIsNotNone(res["ci_lower"])
        self.assertIsNotNone(res["ci_upper"])

    def test_unstacked_pooled(self):
        st = two_sample_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            confidence_level=95.0,
            assume_equal_variances=True,
        )
        res = run_two_sample_t(self.ws, st)
        self.assertEqual(res["df"], 8)  # 5 + 5 - 2 = 8
        self.assertIsNotNone(res["pooled_stdev"])
        # sp^2 = (4*2.5 + 4*0.5) / 8 = 12 / 8 = 1.5
        # se_diff = sqrt(1.5 * (1/5 + 1/5)) = sqrt(1.5 * 0.4) = sqrt(0.6)
        self.assertAlmostEqual(res["pooled_stdev"], np.sqrt(1.5))
        self.assertAlmostEqual(res["se_difference"], np.sqrt(0.6))

    def test_stacked_mode(self):
        st = two_sample_t_settings(
            data_format=0,
            samples_col=2,
            sample_ids_col=3,
            assume_equal_variances=False,
        )
        res = run_two_sample_t(self.ws, st)
        self.assertEqual(res["sample1"]["name"], "A")
        self.assertEqual(res["sample2"]["name"], "B")
        self.assertAlmostEqual(res["difference"], 4.0)

    def test_summarized_mode(self):
        st = two_sample_t_settings(
            data_format=2,
            summarized={
                "n1": 15, "mean1": 25.4, "sd1": 3.2,
                "n2": 15, "mean2": 22.1, "sd2": 2.8,
            },
            assume_equal_variances=True,
        )
        res = run_two_sample_t(None, st)
        self.assertAlmostEqual(res["difference"], 3.3)
        self.assertEqual(res["df"], 28)
        self.assertGreater(res["t_statistic"], 0)

    def test_alternative_hypotheses(self):
        # One-sided greater_than
        st_gt = two_sample_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            alternative="greater_than",
        )
        res_gt = run_two_sample_t(self.ws, st_gt)
        self.assertIsNone(res_gt["ci_upper"])
        self.assertIsNotNone(res_gt["ci_lower"])
        self.assertLess(res_gt["p_value"], 0.05)

        # One-sided less_than
        st_lt = two_sample_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
            alternative="less_than",
        )
        res_lt = run_two_sample_t(self.ws, st_lt)
        self.assertIsNone(res_lt["ci_lower"])
        self.assertIsNotNone(res_lt["ci_upper"])
        self.assertGreater(res_lt["p_value"], 0.95)

    def test_report_formatting(self):
        st = two_sample_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
        )
        res = run_two_sample_t(self.ws, st)
        entry = {"title": "Two-Sample T-Test and CI: S1, S2", "result": res}
        rep = format_two_sample_t_report(entry)
        self.assertIn("Descriptive Statistics", rep)
        self.assertIn("Estimation for Difference", rep)
        self.assertIn("Null hypothesis", rep)
        self.assertIn("Alternative hypothesis", rep)
        self.assertIn("T-Value", rep)

    def test_presenter_integration_and_rerun(self):
        p = Presenter()
        p.worksheet = self.ws
        st = two_sample_t_settings(
            data_format=1,
            sample1_col=0,
            sample2_col=1,
        )
        entry = p.two_sample_t(settings=st)
        self.assertIsNotNone(entry)
        self.assertIn("two_sample_t", entry["result"])
        self.assertFalse(p.result_stale(entry))

        # Modifying data marks result stale
        p.set_cell(0, 0, "999.0")
        self.assertTrue(p.result_stale(entry))

        # Rerun recomputes fresh result
        rerun_entry = p.rerun_result(entry)
        self.assertFalse(p.result_stale(rerun_entry))
        self.assertNotEqual(rerun_entry["result"]["sample1"]["mean"], 12.0)


if __name__ == "__main__":
    unittest.main()
