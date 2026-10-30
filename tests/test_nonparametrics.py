"""Unit tests for Nonparametric Statistical Tests with StatCraft parity."""
from __future__ import annotations

import unittest
import numpy as np
import scipy.stats as st

from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.recipes import run as run_recipe
from statcraft.nonparametrics import (
    sign_test,
    one_sample_wilcoxon,
    mann_whitney,
    kruskal_wallis,
    moods_median,
    friedman_test,
    runs_test,
    paired_wilcoxon,
)
from statcraft.nonparametrics_report import (
    format_sign_test_report,
    format_one_sample_wilcoxon_report,
    format_mann_whitney_report,
    format_kruskal_wallis_report,
    format_moods_median_report,
    format_friedman_report,
    format_runs_test_report,
    format_paired_wilcoxon_report,
)


class TestNonparametrics(unittest.TestCase):
    def setUp(self):
        self.sample1 = [1.5, 2.3, 3.1, 4.0, 5.2, 6.1, 7.8, 8.4, 9.2, 10.5]
        self.sample2 = [2.1, 3.4, 4.5, 5.9, 6.8, 7.2, 8.0, 9.5]

    def test_sign_test_basic(self):
        res = sign_test(self.sample1, test_median=5.0, alternative="two_sided", conf_level=0.95)
        self.assertEqual(res["n"], 10)
        self.assertEqual(res["n_below"], 4)
        self.assertEqual(res["n_above"], 6)
        self.assertEqual(res["n_equal"], 0)
        self.assertAlmostEqual(res["median"], 5.65)
        # For k=4, n=10, binom cdf(4, 10, 0.5) = 0.37695, two-sided p = 0.7539
        self.assertAlmostEqual(res["p_value"], 0.75390625, places=4)
        self.assertTrue(len(res["confidence_intervals"]) > 0)
        self.assertIsNotNone(res["best_exact_ci"])

    def test_sign_test_alternatives(self):
        res_less = sign_test(self.sample1, test_median=5.0, alternative="less")
        res_greater = sign_test(self.sample1, test_median=5.0, alternative="greater")
        self.assertTrue(0.0 <= res_less["p_value"] <= 1.0)
        self.assertTrue(0.0 <= res_greater["p_value"] <= 1.0)

    def test_one_sample_wilcoxon_basic(self):
        res = one_sample_wilcoxon(self.sample1, test_median=5.0, alternative="two_sided", conf_level=0.95)
        self.assertEqual(res["n"], 10)
        self.assertEqual(res["n_test"], 10)
        # Sum of ranks for positive differences: 36.0 (or matching scipy)
        self.assertAlmostEqual(res["statistic_w"], 36.0)
        self.assertAlmostEqual(res["mean_w"], 27.5)
        self.assertAlmostEqual(res["estimated_median"], 5.75, places=2)
        self.assertTrue(res["ci"][0] < res["estimated_median"] < res["ci"][1])

    def test_one_sample_wilcoxon_ties(self):
        tied_data = [2.0, 2.0, 4.0, 4.0, 6.0, 8.0, 8.0]
        res = one_sample_wilcoxon(tied_data, test_median=3.0)
        self.assertTrue(res["sd_w"] > 0)
        self.assertTrue(0.0 <= res["p_value"] <= 1.0)

    def test_mann_whitney_basic(self):
        res = mann_whitney(self.sample1, self.sample2, alternative="two_sided", conf_level=0.95)
        self.assertEqual(res["n1"], 10)
        self.assertEqual(res["n2"], 8)
        self.assertAlmostEqual(res["median1"], 5.65)
        self.assertAlmostEqual(res["median2"], 6.35)
        self.assertAlmostEqual(res["point_estimate"], -0.25, places=2)
        self.assertTrue(res["ci"][0] < res["point_estimate"] < res["ci"][1])
        # W sum of ranks of sample 1
        self.assertTrue(res["statistic_w"] > 0)
        self.assertTrue(0.0 <= res["p_value"] <= 1.0)

    def test_kruskal_wallis_parity(self):
        resp = [1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 7, 8, 9, 10, 11]
        fact = [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3]
        res = kruskal_wallis(resp, fact)
        self.assertEqual(res["n"], 15)
        self.assertEqual(res["k"], 3)
        self.assertEqual(res["df"], 2)
        # Compare against scipy stats.kruskal
        sp_kw = st.kruskal([1, 2, 3, 4, 5], [4, 5, 6, 7, 8], [7, 8, 9, 10, 11])
        self.assertAlmostEqual(res["h_adjusted"], sp_kw.statistic, places=7)
        self.assertAlmostEqual(res["p_adjusted"], sp_kw.pvalue, places=7)
        self.assertEqual(len(res["group_stats"]), 3)

    def test_moods_median_basic(self):
        resp = [1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 7, 8, 9, 10, 11]
        fact = ["A", "A", "A", "A", "A", "B", "B", "B", "B", "B", "C", "C", "C", "C", "C"]
        res = moods_median(resp, fact)
        self.assertEqual(res["n"], 15)
        self.assertEqual(res["k"], 3)
        self.assertEqual(res["df"], 2)
        self.assertAlmostEqual(res["overall_median"], 6.0)
        self.assertTrue(res["chi_square"] > 0)
        self.assertTrue(0.0 <= res["p_value"] <= 1.0)
        self.assertEqual(len(res["group_rows"]), 3)

    def test_friedman_test_parity(self):
        resp = [1, 2, 3, 2, 3, 4, 3, 4, 5]
        treat = ["T1", "T2", "T3", "T1", "T2", "T3", "T1", "T2", "T3"]
        block = ["B1", "B1", "B1", "B2", "B2", "B2", "B3", "B3", "B3"]
        res = friedman_test(resp, treat, block)
        self.assertEqual(res["k_treatments"], 3)
        self.assertEqual(res["b_blocks"], 3)
        self.assertEqual(res["df"], 2)
        sp_fr = st.friedmanchisquare([1, 2, 3], [2, 3, 4], [3, 4, 5])
        self.assertAlmostEqual(res["s_statistic"], sp_fr.statistic, places=7)
        self.assertAlmostEqual(res["p_value"], sp_fr.pvalue, places=7)

    def test_runs_test_basic(self):
        data = [12, 13, 14, 11, 10, 15, 16, 17, 18, 9, 8, 19, 20]
        res = runs_test(data, baseline="mean")
        self.assertEqual(res["n"], 13)
        self.assertAlmostEqual(res["k_threshold"], 14.0)
        self.assertEqual(res["n_above_or_equal"], 7)
        self.assertEqual(res["n_below"], 6)
        self.assertEqual(res["runs"], 6)
        self.assertTrue(res["sd_runs"] > 0)
        self.assertTrue(0.0 <= res["p_value"] <= 1.0)

    def test_paired_wilcoxon_basic(self):
        s1 = [10, 12, 15, 18, 20, 22, 25]
        s2 = [8, 11, 14, 19, 18, 21, 23]
        res = paired_wilcoxon(s1, s2, test_diff=0.0)
        self.assertEqual(res["analysis"], "paired_wilcoxon")
        self.assertEqual(res["n_pairs"], 7)
        self.assertTrue(0.0 <= res["p_value"] <= 1.0)

    def test_reports_formatting(self):
        st_res = sign_test(self.sample1, test_median=5.0)
        rep_st = format_sign_test_report(st_res, "C1")
        self.assertIn("Sign Test for Median: C1", rep_st)
        self.assertIn("Below  Equal  Above", rep_st)

        w_res = one_sample_wilcoxon(self.sample1, test_median=5.0)
        rep_w = format_one_sample_wilcoxon_report(w_res, "C1")
        self.assertIn("Wilcoxon Signed Rank Test: C1", rep_w)

        mw_res = mann_whitney(self.sample1, self.sample2)
        rep_mw = format_mann_whitney_report(mw_res, "C1", "C2")
        self.assertIn("Mann-Whitney Test and CI: C1, C2", rep_mw)

        resp = [1, 2, 3, 4, 5, 4, 5, 6, 7, 8]
        fact = ["A", "A", "A", "A", "A", "B", "B", "B", "B", "B"]
        kw_res = kruskal_wallis(resp, fact)
        rep_kw = format_kruskal_wallis_report(kw_res, "Resp", "Fact")
        self.assertIn("Kruskal-Wallis Test: Resp versus Fact", rep_kw)

        mood_res = moods_median(resp, fact)
        rep_mood = format_moods_median_report(mood_res, "Resp", "Fact")
        self.assertIn("Mood's Median Test: Resp versus Fact", rep_mood)

        fr_res = friedman_test([1, 2, 2, 3], ["T1", "T2", "T1", "T2"], ["B1", "B1", "B2", "B2"])
        rep_fr = format_friedman_report(fr_res, "Resp", "Treat", "Block")
        self.assertIn("Friedman Test: Resp versus Treat blocked by Block", rep_fr)

        runs_res = runs_test(self.sample1)
        rep_runs = format_runs_test_report(runs_res, "C1")
        self.assertIn("Runs Test: C1", rep_runs)

    def test_presenter_and_recipe_reruns(self):
        ws = Worksheet()
        ws.columns = [
            Column(name="S1", kind="number", values=[1.5, 2.3, 3.1, 4.0, 5.2, 6.1, 7.8, 8.4]),
            Column(name="S2", kind="number", values=[2.1, 3.4, 4.5, 5.9, 6.8, 7.2, 8.0, 9.5]),
            Column(name="Group", kind="text", values=["A", "A", "A", "A", "B", "B", "B", "B"]),
            Column(name="Block", kind="text", values=["B1", "B2", "B3", "B4", "B1", "B2", "B3", "B4"]),
        ]
        p = Presenter()
        p.worksheet = ws

        # 1. Sign test
        entry_sign = p.sign_test(settings={"variable_indices": [0], "test_median": 4.0})
        self.assertIsNotNone(entry_sign)
        rec_sign = entry_sign
        rerun_sign = run_recipe(p, rec_sign["recipe"])
        self.assertEqual(rerun_sign["result"]["median"], entry_sign["result"]["median"])

        # 2. Wilcoxon
        entry_w = p.one_sample_wilcoxon(settings={"variable_indices": [0], "test_median": 4.0})
        self.assertIsNotNone(entry_w)
        rec_w = entry_w
        rerun_w = run_recipe(p, rec_w["recipe"])
        self.assertEqual(rerun_w["result"]["statistic_w"], entry_w["result"]["statistic_w"])

        # 3. Mann-Whitney
        entry_mw = p.mann_whitney(settings={"first_index": 0, "second_index": 1})
        self.assertIsNotNone(entry_mw)
        rec_mw = entry_mw
        rerun_mw = run_recipe(p, rec_mw["recipe"])
        self.assertEqual(rerun_mw["result"]["point_estimate"], entry_mw["result"]["point_estimate"])

        # 4. Kruskal-Wallis
        entry_kw = p.kruskal_wallis(settings={"response_index": 0, "factor_index": 2})
        self.assertIsNotNone(entry_kw)
        rec_kw = entry_kw
        rerun_kw = run_recipe(p, rec_kw["recipe"])
        self.assertAlmostEqual(rerun_kw["result"]["h_statistic"], entry_kw["result"]["h_statistic"])

        # 5. Mood's Median
        entry_mood = p.moods_median(settings={"response_index": 0, "factor_index": 2})
        self.assertIsNotNone(entry_mood)
        rec_mood = entry_mood
        rerun_mood = run_recipe(p, rec_mood["recipe"])
        self.assertEqual(rerun_mood["result"]["overall_median"], entry_mood["result"]["overall_median"])

        # 6. Friedman
        entry_fr = p.friedman_test(settings={"response_index": 0, "treatment_index": 2, "block_index": 3})
        self.assertIsNotNone(entry_fr)
        rec_fr = entry_fr
        rerun_fr = run_recipe(p, rec_fr["recipe"])
        self.assertAlmostEqual(rerun_fr["result"]["s_statistic"], entry_fr["result"]["s_statistic"])

        # 7. Runs test
        entry_runs = p.runs_test(settings={"variable_indices": [0]})
        self.assertIsNotNone(entry_runs)
        rec_runs = entry_runs
        rerun_runs = run_recipe(p, rec_runs["recipe"])
        self.assertEqual(rerun_runs["result"]["runs"], entry_runs["result"]["runs"])

        # 8. Paired Wilcoxon
        entry_pw = p.paired_wilcoxon(settings={"first_index": 0, "second_index": 1})
        self.assertIsNotNone(entry_pw)
        rec_pw = entry_pw
        rerun_pw = run_recipe(p, rec_pw["recipe"])
        self.assertEqual(rerun_pw["result"]["statistic_w"], entry_pw["result"]["statistic_w"])


if __name__ == "__main__":
    unittest.main()
