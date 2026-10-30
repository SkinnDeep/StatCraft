"""Comprehensive unit tests for Equivalence Tests in StatCraft."""

import unittest
import numpy as np
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.equivalence import (
    one_sample_equivalence,
    two_sample_equivalence,
    paired_equivalence,
    crossover_equivalence,
)
from statcraft.equivalence_report import (
    format_one_sample_equivalence_report,
    format_two_sample_equivalence_report,
    format_paired_equivalence_report,
    format_crossover_equivalence_report,
)
from statcraft.recipes import columns as recipe_columns


class TestEquivalenceEngine(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        # 1-sample data around mean 10.0
        self.sample1 = [9.8, 10.2, 10.1, 9.9, 10.0, 10.1, 9.95, 10.05, 9.9, 10.1]
        # 2-sample data: reference around 100, test around 101
        self.ref = [99.5, 100.2, 100.8, 99.1, 100.4, 101.0, 99.8, 100.1, 100.5, 99.6]
        self.test = [100.2, 101.0, 100.5, 100.8, 101.2, 100.7, 101.1, 100.9, 101.4, 100.6]

    def test_one_sample_equivalence_difference(self):
        res = one_sample_equivalence(
            self.sample1,
            target=10.0,
            lower_margin=-0.5,
            upper_margin=0.5,
            alpha=0.05,
            hypothesis_type="difference",
        )
        self.assertEqual(res["analysis"], "one_sample_equivalence")
        self.assertEqual(res["n"], 10)
        self.assertEqual(res["df"], 9)
        self.assertEqual(res["conf_level"], 90.0)
        self.assertTrue(res["ci_lower"] > -0.5)
        self.assertTrue(res["ci_upper"] < 0.5)
        self.assertTrue(res["is_equivalent"])
        self.assertLess(res["p_value"], 0.05)

    def test_one_sample_equivalence_ratio(self):
        res = one_sample_equivalence(
            self.sample1,
            target=10.0,
            lower_margin=0.9,
            upper_margin=1.1,
            alpha=0.05,
            hypothesis_type="ratio",
        )
        self.assertEqual(res["hypothesis_type"], "ratio")
        self.assertTrue(0.9 < res["ci_lower"] < res["ci_upper"] < 1.1)
        self.assertTrue(res["is_equivalent"])

    def test_one_sample_validation(self):
        with self.assertRaises(ValueError):
            one_sample_equivalence([10.0], target=10.0)  # n < 2
        with self.assertRaises(ValueError):
            one_sample_equivalence([10.0, 11.0], lower_margin=1.0, upper_margin=-1.0)  # lo >= up
        with self.assertRaises(ValueError):
            one_sample_equivalence([-1.0, 2.0], hypothesis_type="ratio")  # non-positive for ratio

    def test_two_sample_equivalence_diff(self):
        res = two_sample_equivalence(
            sample1=self.test,
            sample2=self.ref,
            name1="TestDrug",
            name2="RefDrug",
            lower_margin=-2.0,
            upper_margin=2.0,
            alpha=0.05,
            equal_variances=False,
            hypothesis_type="difference",
        )
        self.assertEqual(res["analysis"], "two_sample_equivalence")
        self.assertEqual(res["name1"], "TestDrug")
        self.assertEqual(res["name2"], "RefDrug")
        self.assertEqual(res["n1"], 10)
        self.assertEqual(res["n2"], 10)
        self.assertTrue(res["ci_lower"] > -2.0)
        self.assertTrue(res["ci_upper"] < 2.0)
        self.assertTrue(res["is_equivalent"])
        self.assertLess(res["p_value"], 0.05)

    def test_two_sample_equivalence_equal_variances(self):
        res = two_sample_equivalence(
            sample1=self.test,
            sample2=self.ref,
            lower_margin=-2.0,
            upper_margin=2.0,
            equal_variances=True,
        )
        self.assertEqual(res["df"], 18)  # n1 + n2 - 2
        self.assertTrue(res["is_equivalent"])

    def test_two_sample_equivalence_ratio(self):
        res = two_sample_equivalence(
            sample1=self.test,
            sample2=self.ref,
            lower_margin=0.8,
            upper_margin=1.25,
            hypothesis_type="ratio",
        )
        self.assertEqual(res["hypothesis_type"], "ratio")
        self.assertTrue(0.8 < res["ci_lower"] < res["ci_upper"] < 1.25)
        self.assertTrue(res["is_equivalent"])

    def test_paired_equivalence(self):
        before = [15.2, 16.0, 14.8, 15.5, 16.2, 15.1, 14.9, 15.8]
        after = [15.3, 15.9, 14.9, 15.4, 16.3, 15.0, 15.0, 15.7]
        res = paired_equivalence(
            sample1=before,
            sample2=after,
            name1="Before",
            name2="After",
            lower_margin=-1.0,
            upper_margin=1.0,
            alpha=0.05,
        )
        self.assertEqual(res["analysis"], "paired_equivalence")
        self.assertEqual(res["n"], 8)
        self.assertEqual(res["df"], 7)
        self.assertTrue(res["is_equivalent"])
        self.assertLess(res["p_value"], 0.05)

    def test_paired_equivalence_ratio(self):
        before = [15.2, 16.0, 14.8, 15.5, 16.2, 15.1, 14.9, 15.8]
        after = [15.3, 15.9, 14.9, 15.4, 16.3, 15.0, 15.0, 15.7]
        res = paired_equivalence(
            sample1=before,
            sample2=after,
            lower_margin=0.9,
            upper_margin=1.1,
            hypothesis_type="ratio",
        )
        self.assertEqual(res["hypothesis_type"], "ratio")
        self.assertTrue(res["is_equivalent"])

    def test_crossover_equivalence(self):
        # 8 subjects in a 2x2 crossover (4 in RT, 4 in TR)
        # Sequence RT: Period 1 = R, Period 2 = T
        # Sequence TR: Period 1 = T, Period 2 = R
        seq = ["RT", "RT", "RT", "RT", "RT", "RT", "RT", "RT",
               "TR", "TR", "TR", "TR", "TR", "TR", "TR", "TR"]
        per = [1, 2, 1, 2, 1, 2, 1, 2,
               1, 2, 1, 2, 1, 2, 1, 2]
        sub = [1, 1, 2, 2, 3, 3, 4, 4,
               5, 5, 6, 6, 7, 7, 8, 8]
        trt = ["R", "T", "R", "T", "R", "T", "R", "T",
               "T", "R", "T", "R", "T", "R", "T", "R"]
        # Responses where T is very close to R
        resp = [20.1, 20.4, 19.8, 20.0, 21.2, 21.5, 20.5, 20.7,
                20.3, 20.0, 21.0, 20.8, 19.9, 19.7, 20.6, 20.4]

        res = crossover_equivalence(
            response=resp,
            sequence=seq,
            period=per,
            subject=sub,
            treatment=trt,
            lower_margin=-1.0,
            upper_margin=1.0,
            alpha=0.05,
            hypothesis_type="difference",
        )
        self.assertEqual(res["analysis"], "crossover_equivalence")
        self.assertEqual(res["n_obs"], 16)
        self.assertEqual(res["n_subjects"], 8)
        self.assertEqual(res["df"], 6)  # n_subjects - 2
        self.assertTrue(res["is_equivalent"])
        self.assertTrue(-1.0 < res["ci_lower"] < res["ci_upper"] < 1.0)


class TestEquivalenceReports(unittest.TestCase):
    def test_one_sample_report(self):
        res = one_sample_equivalence([10.0, 10.1, 9.9, 10.05, 9.95], target=10.0, lower_margin=-0.5, upper_margin=0.5)
        rep = format_one_sample_equivalence_report(res, var_name="TestVar")
        self.assertIn("1-Sample Equivalence Test: TestVar", rep)
        self.assertIn("Two One-Sided Tests (TOST)", rep)
        self.assertIn("Equivalence can be claimed", rep)

    def test_two_sample_report(self):
        res = two_sample_equivalence([10.0, 10.1, 9.9], [9.9, 10.0, 10.1], name1="BrandA", name2="BrandB", lower_margin=-1.0, upper_margin=1.0)
        rep = format_two_sample_equivalence_report(res)
        self.assertIn("2-Sample Equivalence Test: BrandA, BrandB", rep)
        self.assertIn("Confidence Interval", rep)
        self.assertIn("Two One-Sided Tests (TOST)", rep)

    def test_paired_report(self):
        res = paired_equivalence([10.0, 10.1, 9.9], [9.9, 10.0, 10.1], name1="MethodA", name2="MethodB", lower_margin=-1.0, upper_margin=1.0)
        rep = format_paired_equivalence_report(res)
        self.assertIn("Paired Equivalence Test: MethodA, MethodB", rep)
        self.assertIn("Descriptive Statistics", rep)

    def test_crossover_report(self):
        seq = ["RT", "RT", "RT", "RT", "TR", "TR", "TR", "TR"]
        per = [1, 2, 1, 2, 1, 2, 1, 2]
        sub = [1, 1, 2, 2, 3, 3, 4, 4]
        trt = ["R", "T", "R", "T", "T", "R", "T", "R"]
        resp = [10.0, 10.2, 10.1, 9.9, 10.3, 10.1, 9.8, 10.0]
        res = crossover_equivalence(resp, seq, per, sub, trt, test_treatment="T", ref_treatment="R", lower_margin=-1.0, upper_margin=1.0)
        rep = format_crossover_equivalence_report(res)
        self.assertIn("2x2 Crossover Equivalence Test: T vs R", rep)
        self.assertIn("Two One-Sided Tests (TOST)", rep)


class TestEquivalencePresenterAndRecipes(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet()
        self.ws.columns = [
            Column("S1", "number", [10.0, 10.2, 9.8, 10.1, 9.9, 10.05, 9.95, 10.1]),
            Column("S2", "number", [9.9, 10.1, 9.7, 10.0, 9.8, 10.0, 9.9, 10.0]),
            Column("Resp", "number", [20.1, 20.4, 19.8, 20.0, 20.3, 20.0, 21.0, 20.8]),
            Column("Seq", "text", ["RT", "RT", "RT", "RT", "TR", "TR", "TR", "TR"]),
            Column("Per", "number", [1, 2, 1, 2, 1, 2, 1, 2]),
            Column("Sub", "number", [1, 1, 2, 2, 3, 3, 4, 4]),
            Column("Trt", "text", ["R", "T", "R", "T", "T", "R", "T", "R"]),
        ]
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_one_sample_presenter(self):
        entry = self.presenter.one_sample_equivalence({
            "sample_index": 0,
            "target": 10.0,
            "lower_margin": -0.5,
            "upper_margin": 0.5,
        })
        self.assertIsNotNone(entry)
        self.assertIn("Equivalence Test: S1", entry["title"])
        self.assertEqual(recipe_columns(entry["recipe"]), [0])

    def test_two_sample_presenter(self):
        entry = self.presenter.two_sample_equivalence({
            "first_index": 0,
            "second_index": 1,
            "lower_margin": -1.0,
            "upper_margin": 1.0,
        })
        self.assertIsNotNone(entry)
        self.assertIn("2-Sample Equivalence Test: S1 vs S2", entry["title"])
        self.assertEqual(recipe_columns(entry["recipe"]), [0, 1])

    def test_paired_presenter(self):
        entry = self.presenter.paired_equivalence({
            "first_index": 0,
            "second_index": 1,
            "lower_margin": -1.0,
            "upper_margin": 1.0,
        })
        self.assertIsNotNone(entry)
        self.assertIn("Paired Equivalence Test: S1, S2", entry["title"])
        self.assertEqual(recipe_columns(entry["recipe"]), [0, 1])

    def test_crossover_presenter(self):
        entry = self.presenter.crossover_equivalence({
            "response_index": 2,
            "sequence_index": 3,
            "period_index": 4,
            "subject_index": 5,
            "treatment_index": 6,
            "lower_margin": -2.0,
            "upper_margin": 2.0,
        })
        self.assertIsNotNone(entry)
        self.assertIn("2x2 Crossover Equivalence: Resp", entry["title"])
        self.assertEqual(recipe_columns(entry["recipe"]), [2, 3, 4, 5, 6])


if __name__ == "__main__":
    unittest.main()
