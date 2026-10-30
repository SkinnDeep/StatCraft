"""Unit tests for Two-Sample Variances (Stat > Basic Statistics > 2 Variances…)."""
import unittest
import math
from statcraft.two_variances_engine import compute_two_variances
from statcraft.two_variances_report import format_two_variances_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter


class TestTwoVariances(unittest.TestCase):
    def test_unstacked_f_test_two_sided(self):
        s1 = [10.0, 12.0, 11.0, 13.0, 9.0, 14.0, 15.0, 13.0, 16.0, 17.0]
        s2 = [20.0, 24.0, 22.0, 26.0, 18.0, 28.0, 30.0, 26.0, 32.0, 34.0]  # exactly 2x s1
        res = compute_two_variances(
            sample1_name="Low",
            sample2_name="High",
            sample1_values=s1,
            sample2_values=s2,
            hypothesized_ratio=1.0,
            is_variance_ratio=False,
            confidence_level=95.0,
            alternative="not_equal",
            use_normal_distribution=True,
        )
        self.assertEqual(res["sample1"]["n"], 10)
        self.assertEqual(res["sample2"]["n"], 10)
        self.assertAlmostEqual(res["ratio_sd"], 0.5, places=5)
        self.assertAlmostEqual(res["ratio_variance"], 0.25, places=5)

        # F statistic = 0.25 / 1.0 = 0.25
        self.assertAlmostEqual(res["f_test"]["statistic"], 0.25, places=5)
        self.assertEqual(res["f_test"]["df1"], 9)
        self.assertEqual(res["f_test"]["df2"], 9)
        self.assertIsNotNone(res["f_test"]["p_value"])

        # Bonett & Levene computed
        self.assertIsNotNone(res["bonett"])
        self.assertIsNotNone(res["levene"])

        # Report format
        rep = format_two_variances_report(res)
        self.assertIn("Test and CI for Two Variances: Low, High", rep)
        self.assertIn("Ratio of Standard Deviations", rep)
        self.assertIn("F Test", rep)

    def test_summarized_variances_ratio(self):
        res = compute_two_variances(
            sample1_name="Machine 1",
            sample2_name="Machine 2",
            sample1_size=25,
            sample1_variance=8.0,
            sample2_size=30,
            sample2_variance=4.0,
            hypothesized_ratio=1.0,
            is_variance_ratio=True,
            confidence_level=95.0,
            alternative="greater",
            use_normal_distribution=True,
        )
        self.assertAlmostEqual(res["ratio_variance"], 2.0, places=5)
        self.assertAlmostEqual(res["ratio_sd"], math.sqrt(2.0), places=5)
        self.assertAlmostEqual(res["f_test"]["statistic"], 2.0, places=5)
        self.assertEqual(res["f_test"]["df1"], 24)
        self.assertEqual(res["f_test"]["df2"], 29)
        self.assertIsNotNone(res["f_test"]["p_value"])

        low_var, high_var = res["f_test"]["ci_variance"]
        self.assertGreater(low_var, 0.0)
        self.assertTrue(math.isinf(high_var))

    def test_presenter_integration_stacked_and_unstacked(self):
        p = Presenter()
        p.worksheet = Worksheet("WS", [
            Column("A", "number", [1, 2, 3, 4, 5, 6, 7, 8]),
            Column("B", "number", [2, 3, 5, 7, 11, 13, 17, 19]),
            Column("All", "number", [1, 2, 3, 4, 2, 3, 5, 7]),
            Column("Group", "text", ["G1", "G1", "G1", "G1", "G2", "G2", "G2", "G2"]),
        ])

        # 1. Unstacked
        st_unstacked = {
            "mode": 1,
            "s1_col": 0,
            "s2_col": 1,
            "confidence_level": 95.0,
            "hypothesized_ratio": 1.0,
            "alternative": "not_equal",
            "is_variance_ratio": False,
        }
        e_unstacked = p.two_variances(settings=st_unstacked)
        self.assertIsNotNone(e_unstacked)
        self.assertIn("Test and CI for Two Variances: A, B", e_unstacked["title"])

        # 2. Stacked
        st_stacked = {
            "mode": 0,
            "samples_col": 2,
            "subscripts_col": 3,
            "confidence_level": 95.0,
            "hypothesized_ratio": 1.0,
            "alternative": "not_equal",
            "is_variance_ratio": False,
        }
        e_stacked = p.two_variances(settings=st_stacked)
        self.assertIsNotNone(e_stacked)
        self.assertIn("Test and CI for Two Variances: G1, G2", e_stacked["title"])

        # Rerun
        rerun = p.rerun_result(e_stacked)
        self.assertIsNotNone(rerun)


if __name__ == "__main__":
    unittest.main()
