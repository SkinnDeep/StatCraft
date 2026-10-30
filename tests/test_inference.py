"""Closed-form and independent SciPy high-level fixtures; no vendor parity."""
import math
import unittest
from scipy import stats
from statcraft.engine import MISSING_SENTINEL
from statcraft.inference import one_sample_t, paired_t, two_sample_t, one_way_anova, linear_regression


class TTestFixtures(unittest.TestCase):
    def test_one_sample_closed_form_and_frozen_scipy_interval(self):
        result = one_sample_t([1, 2, 3, 4, 5, None, MISSING_SENTINEL], mu=0)
        self.assertEqual((result["count"], result["missing"], result["df"]), (5, 2, 4))
        self.assertAlmostEqual(result["t"], 3 / math.sqrt(.5), places=13)
        self.assertAlmostEqual(result["p_value"], .01323559956368269, places=14)
        self.assertAlmostEqual(result["ci_low"], 1.0367568385224428, places=12)
        self.assertAlmostEqual(result["ci_high"], 4.963243161477557, places=12)
        null = one_sample_t([1, 2, 3, 4, 5], mu=3)
        self.assertEqual((null["t"], null["p_value"]), (0, 1))
        self.assertEqual((null["ci_low"], null["ci_high"]), (result["ci_low"], result["ci_high"]))

    def test_paired_alignment_and_closed_form_df_two_pvalue(self):
        # Complete differences are [3,4,5], not independent-column deletion.
        result = paired_t([4, None, 6, 8, 100], [1, 99, 2, 3, None])
        self.assertEqual((result["count"], result["missing"], result["row_indices"]), (3, 2, [0, 2, 3]))
        self.assertEqual(result["mean_difference"], 4)
        self.assertAlmostEqual(result["t"], math.sqrt(48), places=13)
        self.assertAlmostEqual(result["p_value"], 1 - math.sqrt(48 / 50), places=14)

    def test_welch_known_unequal_variance_fixture(self):
        result = two_sample_t([1, 2, 3, None], [2, 4, 8, 10, math.nan])
        self.assertEqual((result["count_x"], result["count_y"], result["missing_x"], result["missing_y"]), (3, 4, 1, 1))
        self.assertAlmostEqual(result["df"], 726 / 203, places=13)
        self.assertAlmostEqual(result["t"], -2.088931871468374, places=13)
        self.assertAlmostEqual(result["p_value"], .11316436629832573, places=14)
        shifted = two_sample_t([1, 2, 3], [2, 4, 8, 10], mu=-4)
        self.assertEqual(shifted["t"], 0)
        self.assertEqual((shifted["ci_low"], shifted["ci_high"]), (result["ci_low"], result["ci_high"]))

    def test_independent_high_level_scipy_fixture(self):
        x, y = [2, 4, 7, 8, 11], [1, 3, 6, 7, 9]
        one = one_sample_t(x, mu=3)
        ref = stats.ttest_1samp(x, 3)
        self.assertAlmostEqual(one["t"], float(ref.statistic), places=12)
        self.assertAlmostEqual(one["p_value"], float(ref.pvalue), places=13)
        pair, pref = paired_t(x, y), stats.ttest_rel(x, y)
        self.assertAlmostEqual(pair["t"], float(pref.statistic), places=12)
        self.assertAlmostEqual(pair["p_value"], float(pref.pvalue), places=13)
        welch, wref = two_sample_t(x, y), stats.ttest_ind(x, y, equal_var=False)
        self.assertAlmostEqual(welch["t"], float(wref.statistic), places=12)
        self.assertAlmostEqual(welch["df"], float(wref.df), places=12)

    def test_one_constant_welch_sample_is_valid_both_constant_rejected(self):
        result = two_sample_t([2, 2, 2], [1, 2, 3])
        self.assertAlmostEqual(result["df"], 2)
        self.assertEqual(result["p_value"], 1)
        for function, args in ((one_sample_t, ([7, 7, 7],)),
                               (paired_t, ([1, 2, 3], [0, 1, 2])),
                               (two_sample_t, ([1, 1], [2, 2]))):
            with self.assertRaises(ValueError):
                function(*args)

    def test_confidence_data_and_pair_length_validation(self):
        for confidence in (0, 1, -.1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                one_sample_t([1, 2, 3], confidence=confidence)
        with self.assertRaises(ValueError):
            paired_t([1, 2], [1])
        with self.assertRaises(ValueError):
            one_sample_t([None, 1])
        with self.assertRaises(TypeError):
            one_sample_t([True, 1, 2])
        with self.assertRaises(ValueError):
            one_sample_t([1, 2, 3], mu=MISSING_SENTINEL)

    def test_narrower_confidence_interval_and_location_shift(self):
        x = [1, 2, 3, 4, 5]
        narrow, wide = one_sample_t(x, confidence=.9), one_sample_t(x, confidence=.99)
        self.assertLess(narrow["ci_high"] - narrow["ci_low"], wide["ci_high"] - wide["ci_low"])
        base, translated = one_sample_t(x, mu=3), one_sample_t([value + 1000 for value in x], mu=1003)
        self.assertAlmostEqual(base["t"], translated["t"], places=12)
        self.assertAlmostEqual(base["ci_low"] + 1000, translated["ci_low"], places=12)

    def test_finite_input_statistic_overflow_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "Test statistic"):
            one_sample_t([1e-300, 2e-300, 3e-300], mu=1e300)


class AnovaFixtures(unittest.TestCase):
    def test_large_finite_sum_of_squares_is_rejected_cleanly(self):
        with self.assertRaisesRegex(ValueError, "Sum of squares"):
            one_way_anova([[-1e200, 1e200], [-2e200, 2e200]])

    def test_hand_computed_sums_and_frozen_scipy_probability(self):
        result = one_way_anova([[1, 2, 3, None], [4, 5, 6]])
        self.assertEqual((result["count"], result["missing"], result["df_between"], result["df_within"]), (6, 1, 1, 4))
        self.assertAlmostEqual(result["ss_between"], 13.5, places=12)
        self.assertAlmostEqual(result["ss_within"], 4, places=12)
        self.assertAlmostEqual(result["f"], 13.5, places=12)
        self.assertAlmostEqual(result["p_value"], .021311641128756713, places=14)

    def test_unequal_group_sizes_and_singleton_group_against_scipy(self):
        groups = [[1], [2, 4, 5], [3, 6, 7, 8]]
        result, ref = one_way_anova(groups), stats.f_oneway(*groups)
        self.assertAlmostEqual(result["f"], float(ref.statistic), places=12)
        self.assertAlmostEqual(result["p_value"], float(ref.pvalue), places=13)

    def test_equal_group_means_and_degenerate_rejections(self):
        result = one_way_anova([[1, 2, 3], [1, 2, 3]])
        self.assertEqual((result["f"], result["p_value"]), (0, 1))
        for groups in ([], [[1, 2]], [[1], [2]], [[1, 1], [2, 2]], [[1, 2], [None]]):
            with self.assertRaises(ValueError):
                one_way_anova(groups)


class RegressionFixtures(unittest.TestCase):
    def test_hand_calculated_coefficients_uncertainty_and_probability(self):
        result = linear_regression([0, 1, 2, 3, 4], [1, 2, 1, 4, 5])
        self.assertAlmostEqual(result["slope"], 1, places=14)
        self.assertAlmostEqual(result["intercept"], .6, places=14)
        self.assertAlmostEqual(result["slope_se"], math.sqrt(8 / 75), places=14)
        self.assertAlmostEqual(result["intercept_se"], .8, places=14)
        self.assertAlmostEqual(result["r_squared"], 25 / 33, places=14)
        self.assertAlmostEqual(result["slope_p_value"], .05491252385363526, places=13)
        self.assertEqual(result["df"], 3)
        self.assertLess(result["slope_ci_low"], 1)
        self.assertGreater(result["slope_ci_high"], 1)

    def test_pair_mask_and_independent_scipy_regression(self):
        result = linear_regression([0, None, 1, 2, 3, 4, 100], [1, 9, 2, 1, 4, 5, None])
        self.assertEqual((result["count"], result["missing"], result["row_indices"]), (5, 2, [0, 2, 3, 4, 5]))
        ref = stats.linregress([0, 1, 2, 3, 4], [1, 2, 1, 4, 5])
        for key, value in (("slope", ref.slope), ("intercept", ref.intercept),
                           ("slope_se", ref.stderr), ("intercept_se", ref.intercept_stderr),
                           ("slope_p_value", ref.pvalue)):
            self.assertAlmostEqual(result[key], float(value), places=13)
        self.assertAlmostEqual(sum(result["residuals"]), 0, places=12)

    def test_exact_fit_has_estimates_but_explicitly_no_inference(self):
        result = linear_regression([1, 2, 3, 4, 5], [3, 5, 7, 9, 11])
        self.assertAlmostEqual(result["slope"], 2, places=13)
        self.assertAlmostEqual(result["intercept"], 1, places=13)
        self.assertEqual((result["r_squared"], result["residual_stdev"]), (1, 0))
        self.assertEqual(result["status"], "exact_fit")
        self.assertIsNone(result["slope_p_value"])
        self.assertIsNone(result["slope_ci_low"])
        self.assertTrue(result["warnings"])

    def test_rank_data_and_constant_response_validation(self):
        for x, y in (([1, 1, 1], [1, 2, 3]), ([1, 2, 3], [2, 2, 2]),
                     ([1, 2], [1, 3]), ([1, 2, 3], [1, 2]),
                     ([1, None, 3], [1, 2, None])):
            with self.assertRaises(ValueError):
                linear_regression(x, y)


if __name__ == "__main__":
    unittest.main()
