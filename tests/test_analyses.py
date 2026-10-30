import math
import unittest

from statcraft.analyses import describe
from statcraft.engine import MISSING_SENTINEL


class DescriptiveTests(unittest.TestCase):
    def test_controlled_describe_quartile_golden_cases(self):
        # outputs/statcraft-ui-reference-observations.json: normal GUI DESCRIBE.
        # These values are displayed reference results, not inferred native output.
        cases = [
            ([1, 2, 3, 4, 5], (1.5, 3, 4.5)),
            ([1, 2, 3, 4, None], (1.25, 2.5, 3.75)),
            ([7, None, None, None, None], (7, 7, 7)),
            ([10] * 5, (10, 10, 10)),
            ([1, 2, None, None, None], (1, 1.5, 2)),
        ]
        for values, expected in cases:
            with self.subTest(values=values):
                result = describe(values)
                self.assertEqual((result["q1"], result["median"], result["q3"]), expected)

    def test_controlled_describe_mean_sd_se_at_displayed_precision(self):
        # Reference displayed StDev uses five decimals in C1/C2, six in C5;
        # SE Mean uses six decimals. Missing '*' is represented internally by None.
        cases = [
            ([1, 2, 3, 4, 5], 5, 0, "3", "1.58114", "0.707107"),
            ([1, 2, 3, 4, None], 4, 1, "2.5", "1.29099", "0.645497"),
            ([7, None, None, None, None], 1, 4, "7", None, None),
            ([10] * 5, 5, 0, "10", "0", "0"),
            ([1, 2, None, None, None], 2, 3, "1.5", "0.707107", "0.5"),
        ]
        for values, count, missing, mean, sd, se in cases:
            with self.subTest(values=values):
                result = describe(values)
                self.assertEqual((result["count"], result["missing"]), (count, missing))
                for key, displayed in (("mean", mean), ("sample_stdev", sd),
                                       ("standard_error", se)):
                    actual = result[key]
                    if displayed is None:
                        self.assertIsNone(actual)
                    else:
                        places = len(displayed.split(".")[1]) if "." in displayed else 0
                        self.assertEqual(round(actual, places), float(displayed))

    def test_quartile_order_independence_and_missing_exclusion(self):
        # An analytical property check independent of the controlled golden cases.
        first = describe([1, 2, 3, 4, 5])
        second = describe([5, math.nan, 1, None, 4, MISSING_SENTINEL, 3, 2])
        for key in ("q1", "median", "q3"):
            self.assertEqual(first[key], second[key])
        self.assertEqual(second["missing"], 3)

    def test_quantile_interpolation_remains_finite_for_large_endpoints(self):
        # Analytical stability safeguard; not a native reference-product check.
        result = describe([-1e308, 1e308, 1e308, 1e308])
        self.assertEqual(result["q1"], -5e307)
        self.assertEqual(result["q3"], 1e308)
        self.assertEqual(describe([1e308, 1e308])["median"], 1e308)

    def test_hand_calculated_sample_and_missing(self):
        result = describe([1, 2, 3, 4, 5, None, math.nan, math.inf, MISSING_SENTINEL])
        self.assertEqual((result["count"], result["missing"]), (5, 4))
        self.assertEqual(result["mean"], 3)
        self.assertEqual(result["median"], 3)
        self.assertAlmostEqual(result["sample_variance"], 2.5)
        self.assertAlmostEqual(result["standard_error"], math.sqrt(0.5))
        self.assertEqual(result["sum"], 15)

    def test_constant_and_single_observation(self):
        self.assertEqual(describe([7, 7, 7])["sample_stdev"], 0)
        result = describe([7])
        self.assertIsNone(result["sample_variance"])
        self.assertIsNone(result["standard_error"])

    def test_all_missing_and_wrong_types(self):
        for values in ([], [None, math.inf], ["7"], [True]):
            with self.subTest(values=values):
                with self.assertRaises((ValueError, TypeError)):
                    describe(values)

    def test_stable_mean_and_explicit_overflow_not_infinity(self):
        result = describe([1e308, 1e308])
        self.assertEqual(result["mean"], 1e308)
        self.assertIsNone(result["sum"])
        self.assertEqual(result["sample_stdev"], 0)
        self.assertTrue(result["warnings"])
        result = describe([-1e308, 1e308])
        self.assertTrue(math.isfinite(result["sample_stdev"]))
        self.assertIsNone(result["sample_variance"])

    def test_standard_sample_translation_identity(self):
        result = describe([10**12 + x for x in [1, 2, 3, 4, 5]])
        self.assertEqual(result["mean"], 10**12 + 3)
        self.assertAlmostEqual(result["sample_variance"], 2.5)


if __name__ == "__main__":
    unittest.main()
