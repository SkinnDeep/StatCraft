"""Comprehensive unit tests for Power and Sample Size in StatCraft."""

import unittest
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.power import (
    one_sample_z_power,
    one_sample_t_power,
    two_sample_t_power,
    paired_t_power,
    one_proportion_power,
    two_proportions_power,
    oneway_anova_power,
    factorial_power,
)
from statcraft.power_report import (
    format_one_sample_z_power_report,
    format_one_sample_t_power_report,
    format_two_sample_t_power_report,
    format_paired_t_power_report,
    format_one_proportion_power_report,
    format_two_proportions_power_report,
    format_oneway_anova_power_report,
    format_factorial_power_report,
)
from statcraft.recipes import columns as recipe_columns


class TestPowerEngine(unittest.TestCase):
    def test_one_sample_z_power_sample_size(self):
        res = one_sample_z_power(differences=[1.0], target_powers=[0.8, 0.9], sigma=1.0, alpha=0.05)
        self.assertEqual(res["analysis"], "one_sample_z_power")
        self.assertEqual(len(res["rows"]), 2)
        # For sigma=1, delta=1, alpha=0.05 two-sided: n for 0.8 is ~8, n for 0.9 is ~11
        r8 = [r for r in res["rows"] if r["target_power"] == 0.8][0]
        r9 = [r for r in res["rows"] if r["target_power"] == 0.9][0]
        self.assertTrue(7 <= r8["sample_size"] <= 9)
        self.assertTrue(10 <= r9["sample_size"] <= 12)
        self.assertGreaterEqual(r8["actual_power"], 0.8)
        self.assertGreaterEqual(r9["actual_power"], 0.9)
        self.assertTrue(len(res["curves"]) > 0)

    def test_one_sample_z_power_calc_power(self):
        res = one_sample_z_power(differences=[1.0], sample_sizes=[10, 20], sigma=1.0, alpha=0.05)
        self.assertEqual(len(res["rows"]), 2)
        r10 = [r for r in res["rows"] if r["sample_size"] == 10][0]
        r20 = [r for r in res["rows"] if r["sample_size"] == 20][0]
        self.assertGreater(r10["actual_power"], 0.8)
        self.assertGreater(r20["actual_power"], 0.95)

    def test_one_sample_t_power(self):
        res = one_sample_t_power(differences=[1.0], target_powers=[0.8, 0.9], sigma=1.0, alpha=0.05)
        self.assertEqual(res["analysis"], "one_sample_t_power")
        # t requires slightly larger n than z (e.g. n=10 for power 0.8, n=13 for 0.9)
        r8 = [r for r in res["rows"] if r["target_power"] == 0.8][0]
        r9 = [r for r in res["rows"] if r["target_power"] == 0.9][0]
        self.assertTrue(8 <= r8["sample_size"] <= 12)
        self.assertTrue(11 <= r9["sample_size"] <= 15)
        self.assertGreaterEqual(r8["actual_power"], 0.8)
        self.assertGreaterEqual(r9["actual_power"], 0.9)

    def test_two_sample_t_power(self):
        res = two_sample_t_power(differences=[1.0], target_powers=[0.8], sigma=1.0, alpha=0.05)
        self.assertEqual(res["analysis"], "two_sample_t_power")
        # 2-sample t requires roughly double the sample size per group (~17)
        r8 = res["rows"][0]
        self.assertTrue(14 <= r8["sample_size"] <= 20)
        self.assertGreaterEqual(r8["actual_power"], 0.8)

    def test_paired_t_power(self):
        res = paired_t_power(differences=[1.0], target_powers=[0.8], stdev_diff=1.0, alpha=0.05)
        self.assertEqual(res["analysis"], "paired_t_power")
        r8 = res["rows"][0]
        self.assertTrue(8 <= r8["sample_size"] <= 12)
        self.assertGreaterEqual(r8["actual_power"], 0.8)

    def test_one_proportion_power(self):
        res = one_proportion_power(comparison_proportions=[0.7], baseline_p0=0.5, target_powers=[0.8], alpha=0.05)
        self.assertEqual(res["analysis"], "one_proportion_power")
        r = res["rows"][0]
        self.assertTrue(35 <= r["sample_size"] <= 65)
        self.assertGreaterEqual(r["actual_power"], 0.8)

    def test_two_proportions_power(self):
        res = two_proportions_power(p1_values=[0.7], p2=0.5, target_powers=[0.8], alpha=0.05)
        self.assertEqual(res["analysis"], "two_proportions_power")
        r = res["rows"][0]
        self.assertTrue(70 <= r["sample_size"] <= 120)
        self.assertGreaterEqual(r["actual_power"], 0.8)

    def test_oneway_anova_power(self):
        res = oneway_anova_power(levels=4, max_differences=[1.5], target_powers=[0.8], sigma=1.0, alpha=0.05)
        self.assertEqual(res["analysis"], "oneway_anova_power")
        r = res["rows"][0]
        self.assertTrue(6 <= r["sample_size"] <= 14)
        self.assertGreaterEqual(r["actual_power"], 0.8)

    def test_factorial_power(self):
        res = factorial_power(factors=3, corner_points=8, effects=[1.5], target_powers=[0.8], sigma=1.0, alpha=0.05)
        self.assertEqual(res["analysis"], "factorial_power")
        r = res["rows"][0]
        self.assertGreaterEqual(r["replicates"], 1)
        self.assertEqual(r["total_runs"], r["replicates"] * 8)
        self.assertGreaterEqual(r["actual_power"], 0.8)


class TestPowerReports(unittest.TestCase):
    def test_reports(self):
        r_z = one_sample_z_power([1.0], target_powers=[0.8])
        rep_z = format_one_sample_z_power_report(r_z)
        self.assertIn("1-Sample Z Test", rep_z)
        self.assertIn("Results", rep_z)

        r_t = one_sample_t_power([1.0], target_powers=[0.8])
        rep_t = format_one_sample_t_power_report(r_t)
        self.assertIn("1-Sample t Test", rep_t)

        r_2t = two_sample_t_power([1.0], target_powers=[0.8])
        rep_2t = format_two_sample_t_power_report(r_2t)
        self.assertIn("2-Sample t Test", rep_2t)

        r_pt = paired_t_power([1.0], target_powers=[0.8])
        rep_pt = format_paired_t_power_report(r_pt)
        self.assertIn("Paired t Test", rep_pt)

        r_1p = one_proportion_power([0.7], baseline_p0=0.5, target_powers=[0.8])
        rep_1p = format_one_proportion_power_report(r_1p)
        self.assertIn("1 Proportion Test", rep_1p)

        r_2p = two_proportions_power([0.7], p2=0.5, target_powers=[0.8])
        rep_2p = format_two_proportions_power_report(r_2p)
        self.assertIn("2 Proportions Test", rep_2p)

        r_a = oneway_anova_power(levels=3, max_differences=[1.0], target_powers=[0.8])
        rep_a = format_oneway_anova_power_report(r_a)
        self.assertIn("One-Way ANOVA", rep_a)

        r_f = factorial_power(factors=3, corner_points=8, effects=[1.0], target_powers=[0.8])
        rep_f = format_factorial_power_report(r_f)
        self.assertIn("2-Level Factorial Design", rep_f)


class TestPowerPresenterAndRecipes(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet()
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_presenter_power_methods(self):
        e1 = self.presenter.one_sample_z_power({"differences": [1.0], "target_powers": [0.8]})
        self.assertIsNotNone(e1)
        self.assertEqual(recipe_columns(e1["recipe"]), [])

        e2 = self.presenter.one_sample_t_power({"differences": [1.0], "target_powers": [0.8]})
        self.assertIsNotNone(e2)

        e3 = self.presenter.two_sample_t_power({"differences": [1.0], "target_powers": [0.8]})
        self.assertIsNotNone(e3)

        e4 = self.presenter.paired_t_power({"differences": [1.0], "target_powers": [0.8]})
        self.assertIsNotNone(e4)

        e5 = self.presenter.one_proportion_power({"comparison_proportions": [0.7], "baseline_p0": 0.5, "target_powers": [0.8]})
        self.assertIsNotNone(e5)

        e6 = self.presenter.two_proportions_power({"p1_values": [0.7], "p2": 0.5, "target_powers": [0.8]})
        self.assertIsNotNone(e6)

        e7 = self.presenter.oneway_anova_power({"levels": 3, "max_differences": [1.0], "target_powers": [0.8]})
        self.assertIsNotNone(e7)

        e8 = self.presenter.factorial_power({"factors": 3, "corner_points": 8, "effects": [1.0], "target_powers": [0.8]})
        self.assertIsNotNone(e8)


if __name__ == "__main__":
    unittest.main()
