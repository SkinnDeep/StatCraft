"""Unit tests for Tolerance Intervals (Normal Distribution) computational engine and report formatting."""
import math
import unittest
import numpy as np

from statcraft.tolerance_intervals import compute_k_factor, compute_tolerance_interval
from statcraft.tolerance_intervals_report import generate_tolerance_intervals_report


class TestToleranceIntervals(unittest.TestCase):
    def test_k_factors(self):
        # Sample size 50, 95% confidence, 95% coverage
        k2 = compute_k_factor(50, conf_level=95.0, min_percent=95.0, interval_type='two_sided')
        self.assertAlmostEqual(k2, 2.3818, places=3)

        k1 = compute_k_factor(50, conf_level=95.0, min_percent=95.0, interval_type='lower')
        self.assertAlmostEqual(k1, 2.0650, places=3)

        k1_upper = compute_k_factor(50, conf_level=95.0, min_percent=95.0, interval_type='upper')
        self.assertAlmostEqual(k1_upper, k1, places=6)

        # As n increases, k factor must decrease
        k2_large = compute_k_factor(200, conf_level=95.0, min_percent=95.0, interval_type='two_sided')
        self.assertLess(k2_large, k2)

    def test_raw_data_two_sided(self):
        np.random.seed(42)
        raw = np.random.normal(loc=50.0, scale=5.0, size=60).tolist()
        res = compute_tolerance_interval(raw_data=raw, settings={'conf_level': 95.0, 'min_percent': 90.0, 'interval_type': 'two_sided'}, variable_name="Thickness")

        self.assertEqual(res['n'], 60)
        self.assertFalse(res['is_summarized'])
        self.assertAlmostEqual(res['mean'], np.mean(raw), places=6)
        self.assertAlmostEqual(res['std'], np.std(raw, ddof=1), places=6)

        # Verify normal interval
        k = res['k']
        self.assertAlmostEqual(res['normal_lower'], res['mean'] - k * res['std'], places=6)
        self.assertAlmostEqual(res['normal_upper'], res['mean'] + k * res['std'], places=6)

        # Verify nonparametric interval
        np_res = res['nonparametric']
        self.assertIsNotNone(np_res)
        self.assertEqual(np_res['lower'], min(raw))
        self.assertEqual(np_res['upper'], max(raw))
        self.assertTrue(0.0 <= np_res['achieved_confidence'] <= 100.0)

        # Verify report
        rpt = generate_tolerance_intervals_report(res)
        self.assertIn("Tolerance Intervals (Normal Distribution)", rpt)
        self.assertIn("Thickness", rpt)
        self.assertIn("Normal Method", rpt)
        self.assertIn("Nonparametric Method", rpt)

    def test_one_sided_bounds(self):
        raw = [10.2, 10.5, 9.8, 10.1, 10.3, 10.0, 9.9, 10.4, 10.2, 10.1]
        res_lower = compute_tolerance_interval(raw_data=raw, settings={'interval_type': 'lower'})
        self.assertEqual(res_lower['interval_type'], 'lower')
        self.assertEqual(res_lower['normal_upper'], float('inf'))
        self.assertLess(res_lower['normal_lower'], res_lower['mean'])

        res_upper = compute_tolerance_interval(raw_data=raw, settings={'interval_type': 'upper'})
        self.assertEqual(res_upper['interval_type'], 'upper')
        self.assertEqual(res_upper['normal_lower'], float('-inf'))
        self.assertGreater(res_upper['normal_upper'], res_upper['mean'])

    def test_summarized_data(self):
        res = compute_tolerance_interval(n=100, mean=25.0, std=2.5, settings={'conf_level': 99.0, 'min_percent': 99.0})
        self.assertEqual(res['n'], 100)
        self.assertTrue(res['is_summarized'])
        self.assertIsNone(res['nonparametric'])
        self.assertLess(res['normal_lower'], 25.0)
        self.assertGreater(res['normal_upper'], 25.0)

        rpt = generate_tolerance_intervals_report(res)
        self.assertIn("Nonparametric interval not available for summarized data", rpt)

    def test_error_handling(self):
        with self.assertRaises(ValueError):
            compute_tolerance_interval(raw_data=[1.0])

        with self.assertRaises(ValueError):
            compute_tolerance_interval(n=1, mean=10.0, std=1.0)

        with self.assertRaises(ValueError):
            compute_tolerance_interval(n=10, mean=10.0, std=-1.0)

        with self.assertRaises(ValueError):
            compute_tolerance_interval(n=10, mean=10.0, std=1.0, settings={'conf_level': 105.0})

        with self.assertRaises(ValueError):
            compute_tolerance_interval(n=10, mean=10.0, std=1.0, settings={'min_percent': 0.0})


if __name__ == '__main__':
    unittest.main()
