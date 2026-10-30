"""Boundary/identity checks; these never execute StatCraft.

Scalar expected normalization is bound to runtime numeric-edge evidence.
Other expectations are closed-form analytical identities or hand-solved systems,
not reference-product equivalence and not tests that reimplement the functions.
Run: python -m unittest discover -s tests -v (from work/statcraft).
"""
import math
import sys
import unittest
from statcraft.engine import (
    ADAPTER_LOG_BOUND, MIN_NORMAL, MISSING_SENTINEL,
    normalize_numeric, normalize_numbers, exp_adapter, power_adapter,
    weibull_pdf, weibull_cdf, weibull_mean, givens_rotation,
    packed_triangular_solve,
)


class NumericStorageContract(unittest.TestCase):
    def test_reference_missing_edge_cases(self):
        for value in (None, math.nan, math.inf, -math.inf, MISSING_SENTINEL):
            with self.subTest(value=value):
                self.assertIsNone(normalize_numeric(value))

    def test_reference_negative_zero_and_finite_values(self):
        self.assertEqual(math.copysign(1.0, normalize_numeric(-0.0)), 1.0)
        self.assertEqual(normalize_numbers([1, -2.5, None]), [1.0, -2.5, None])
        self.assertEqual(normalize_numeric(math.nextafter(MISSING_SENTINEL, 0)),
                         math.nextafter(MISSING_SENTINEL, 0))

    def test_invalid_types_are_not_silently_coerced(self):
        for value in ("3", True, 1j):
            with self.assertRaises(TypeError):
                normalize_numeric(value)
        with self.assertRaises(ValueError):
            normalize_numeric(10 ** 1000)


class AdapterContracts(unittest.TestCase):
    def test_exp_boundaries_and_underflow_clamp(self):
        self.assertGreater(exp_adapter(-ADAPTER_LOG_BOUND), 0)
        self.assertEqual(exp_adapter(math.nextafter(-ADAPTER_LOG_BOUND, -math.inf)), 0)
        self.assertTrue(math.isfinite(exp_adapter(ADAPTER_LOG_BOUND)))
        with self.assertRaises(OverflowError):
            exp_adapter(math.nextafter(ADAPTER_LOG_BOUND, math.inf))

    def test_zero_and_negative_power_domain(self):
        self.assertEqual(power_adapter(0, 3), 0)
        self.assertEqual(power_adapter(0, 0), 1)
        self.assertTrue(math.isnan(power_adapter(0, -2)))
        self.assertEqual(power_adapter(-2, 3), -8)
        self.assertEqual(power_adapter(-2, 4), 16)
        self.assertTrue(math.isnan(power_adapter(-2, 0.5)))
        self.assertEqual(power_adapter(2, -2000), 0)
        with self.assertRaises(OverflowError):
            power_adapter(2, 2000)

    def test_nonfinite_adapter_inputs_rejected(self):
        for value in (None, math.nan, math.inf, -math.inf, MISSING_SENTINEL):
            with self.assertRaises(ValueError):
                exp_adapter(value)
            with self.assertRaises(ValueError):
                power_adapter(2, value)


class WeibullAnalyticalChecks(unittest.TestCase):
    def test_exponential_special_case_and_translated_mean(self):
        self.assertAlmostEqual(weibull_pdf(4, 1, 2), math.exp(-2) / 2, places=15)
        self.assertAlmostEqual(weibull_cdf(4, 1, 2), 1 - math.exp(-2), places=15)
        self.assertAlmostEqual(weibull_mean(1, 2, 3), 5, places=14)
        # shape=2 mean is scale*sqrt(pi)/2 + location.
        self.assertAlmostEqual(weibull_mean(2, 4, -1), 2 * math.sqrt(math.pi) - 1, places=14)

    def test_kernel_boundary_is_zero_for_all_shapes(self):
        for shape in (0.5, 1, 2):
            for value in (-3, 0):
                self.assertEqual(weibull_pdf(value, shape, 2), 0)
                self.assertEqual(weibull_cdf(value, shape, 2), 0)
                self.assertEqual(weibull_cdf(value, shape, 2, upper_tail=True), 1)

    def test_small_cdf_is_nonzero_and_tail_pair_is_consistent(self):
        lower = weibull_cdf(1e-20, 1, 1)
        self.assertGreater(lower, 0)
        self.assertAlmostEqual(lower / 1e-20, 1, places=14)
        self.assertAlmostEqual(weibull_cdf(2, 2, 3) +
                               weibull_cdf(2, 2, 3, upper_tail=True), 1, places=15)
        self.assertEqual(weibull_cdf(710, 1, 1, upper_tail=True), 0)
        self.assertEqual(weibull_cdf(710, 1, 1), 1)

    def test_missing_observations_and_invalid_parameters(self):
        for value in (None, math.nan, math.inf, -math.inf, MISSING_SENTINEL):
            self.assertIsNone(weibull_pdf(value, 2, 3))
            self.assertIsNone(weibull_cdf(value, 2, 3))
        for shape, scale in ((0, 1), (-1, 1), (1, 0), (1, -2), (math.inf, 1)):
            with self.assertRaises(ValueError):
                weibull_pdf(1, shape, scale)
            with self.assertRaises(ValueError):
                weibull_cdf(1, shape, scale)
            with self.assertRaises(ValueError):
                weibull_mean(shape, scale)


class GivensAnalyticalChecks(unittest.TestCase):
    def test_hand_calculated_sign_sensitive_cases(self):
        for a, b, expected_r, expected_c, expected_s in (
            (3, 4, 5, 0.6, 0.8), (3, -4, 5, 0.6, -0.8),
            (-3, -4, -5, 0.6, 0.8), (0, -4, 4, 0, -1),
        ):
            with self.subTest(a=a, b=b):
                result = givens_rotation(a, b)
                self.assertAlmostEqual(result.r, expected_r, places=14)
                self.assertAlmostEqual(result.c, expected_c, places=14)
                self.assertAlmostEqual(result.s, expected_s, places=14)
                self.assertAlmostEqual(result.c * b - result.s * a, 0, places=14)
                self.assertAlmostEqual(result.c ** 2 + result.s ** 2, 1, places=14)

    def test_zero_subnormal_threshold_and_raw_negative_zero(self):
        self.assertEqual(givens_rotation(0, 0), (0, 1, 0, 1))
        self.assertEqual(givens_rotation(1e-310, -1e-310), (0, 1, 0, 1))
        self.assertEqual(givens_rotation(MIN_NORMAL, 0), (0, 1, 0, 0))
        self.assertGreater(givens_rotation(math.nextafter(MIN_NORMAL, math.inf), 0).r, 0)
        result = givens_rotation(-0.0, -4)
        self.assertEqual(result.r, -4)
        self.assertEqual(result.s, 1)

    def test_invalid_or_overflowing_scale_is_explicit(self):
        for value in (None, math.nan, math.inf, -math.inf, MISSING_SENTINEL):
            with self.assertRaises(ValueError):
                givens_rotation(value, 1)
        with self.assertRaises(OverflowError):
            givens_rotation(sys.float_info.max, sys.float_info.max)


class TriangularAnalyticalChecks(unittest.TestCase):
    def test_independent_hand_solved_systems(self):
        # U=[[2,1,-1],[0,3,2],[0,0,4]], expected x=[1,-2,3].
        packed = [2, 1, 3, -1, 2, 4]
        rhs = [-3, 0, 12]
        self.assertEqual(packed_triangular_solve(packed, rhs), (-1, [1, -2, 3]))
        self.assertEqual(packed_triangular_solve(packed, [2, -5, 7], True), (-1, [1, -2, 3]))
        self.assertEqual(rhs, [-3, 0, 12])
        self.assertEqual(packed, [2, 1, 3, -1, 2, 4])

    def test_first_zero_diagonal_and_unchanged_rhs(self):
        self.assertEqual(packed_triangular_solve([0, 2, 0], [7, 8]), (0, [7, 8]))
        self.assertEqual(packed_triangular_solve([1, 2, -0.0], [7, 8]), (1, [7, 8]))
        self.assertEqual(packed_triangular_solve([2], [8]), (-1, [4]))

    def test_sizes_and_nonfinite_data_rejected(self):
        for packed, rhs in (([], []), ([1], [1, 2]), ([1, 2], [1]), ([1, 2, 3, 4], [1, 2])):
            with self.assertRaises(ValueError):
                packed_triangular_solve(packed, rhs)
        for value in (None, math.nan, math.inf, -math.inf, MISSING_SENTINEL):
            with self.assertRaises(ValueError):
                packed_triangular_solve([value], [1])
            with self.assertRaises(ValueError):
                packed_triangular_solve([1], [value])
        with self.assertRaises(TypeError):
            packed_triangular_solve([1], [1], transpose=1)


if __name__ == "__main__":
    unittest.main()
