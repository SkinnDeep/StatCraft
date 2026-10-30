"""Unit tests for One-Sample Variance (Stat > Basic Statistics > 1 Variance…)."""
import unittest
import math
from statcraft.one_variance_engine import compute_one_variance_sample
from statcraft.one_variance_report import format_one_variance_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter


class TestOneVariance(unittest.TestCase):
    def test_raw_column_two_sided(self):
        # 10 observations with known standard deviation
        vals = [10.0, 12.0, 11.0, 13.0, 9.0, 14.0, 15.0, 13.0, 16.0, 17.0]
        res = compute_one_variance_sample(
            sample_name="C1",
            values=vals,
            hypothesized_value=2.0,
            is_variance_test=False,
            perform_test=True,
            confidence_level=95.0,
            alternative="not_equal",
        )
        self.assertEqual(res["name"], "C1")
        self.assertEqual(res["n"], 10)
        self.assertAlmostEqual(res["stdev"], 2.581988897, places=5)
        self.assertAlmostEqual(res["variance"], 6.666666666, places=5)

        # Chi-square stat: df * s^2 / sigma0^2 = 9 * 6.66667 / 4 = 15.0
        self.assertAlmostEqual(res["chi2"]["statistic"], 15.0, places=5)
        self.assertEqual(res["chi2"]["df"], 9)
        self.assertIsNotNone(res["chi2"]["p_value"])

        # Chi-square CI for stdev
        low_sd, high_sd = res["chi2"]["ci_stdev"]
        self.assertLess(low_sd, res["stdev"])
        self.assertGreater(high_sd, res["stdev"])

        # Bonett method
        self.assertIsNotNone(res["bonett"])
        self.assertIsNotNone(res["bonett"]["p_value"])

        # Report format
        rep = format_one_variance_report(res)
        self.assertIn("Test and CI for One Variance: C1", rep)
        self.assertIn("Chi-Square", rep)
        self.assertIn("Bonett", rep)

    def test_summarized_stdev_directional(self):
        # Sample size 50, stdev 1.5, H0: sigma = 1.2, H1: sigma > 1.2
        res = compute_one_variance_sample(
            sample_name="Sample",
            sample_size=50,
            sample_stdev=1.5,
            hypothesized_value=1.2,
            is_variance_test=False,
            perform_test=True,
            confidence_level=99.0,
            alternative="greater",
        )
        self.assertEqual(res["n"], 50)
        self.assertEqual(res["stdev"], 1.5)
        self.assertAlmostEqual(res["variance"], 2.25)
        self.assertEqual(res["chi2"]["df"], 49)

        # Lower bound finite, upper bound inf
        low, high = res["chi2"]["ci_stdev"]
        self.assertGreater(low, 0.0)
        self.assertTrue(math.isinf(high))

        # P-value for greater
        self.assertLess(res["chi2"]["p_value"], 0.05)

    def test_summarized_variance_mode(self):
        # Sample size 25, variance 4.0, H0: sigma^2 = 5.0
        res = compute_one_variance_sample(
            sample_name="Sample",
            sample_size=25,
            sample_variance=4.0,
            hypothesized_value=5.0,
            is_variance_test=True,
            perform_test=True,
            confidence_level=90.0,
            alternative="less",
        )
        self.assertEqual(res["variance"], 4.0)
        self.assertAlmostEqual(res["stdev"], 2.0)
        low, high = res["chi2"]["ci_variance"]
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 4.0)

    def test_presenter_integration(self):
        p = Presenter()
        p.worksheet = Worksheet("TestWS", [
            Column("X", "number", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
        ])
        settings = {
            "mode": 0,
            "columns": [0],
            "perform_test": True,
            "is_variance_test": False,
            "hypothesized_value": 2.5,
            "confidence_level": 95.0,
            "alternative": "not_equal",
        }
        entry = p.one_variance(settings=settings)
        self.assertIsNotNone(entry)
        self.assertIn("Test and CI for One Variance: X", entry["title"])
        self.assertTrue(entry["result"]["one_variance_native"])

        # Re-run recipe
        rerun_entry = p.rerun_result(entry)
        self.assertIsNotNone(rerun_entry)


if __name__ == "__main__":
    unittest.main()
