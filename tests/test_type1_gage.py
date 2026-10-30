"""Unit tests for Type 1 Gage Study computational engine and reporting."""
import math
import unittest
import numpy as np

from statcraft.type1_gage import compute_type1_gage
from statcraft.type1_gage_report import generate_type1_gage_report


class TestType1Gage(unittest.TestCase):
    def test_standard_gage_study(self):
        # 50 simulated measurements around 0.1002 with std ~ 0.0015
        np.random.seed(42)
        measurements = np.random.normal(loc=0.1002, scale=0.0015, size=50).tolist()
        reference = 0.1000
        tolerance = 0.05

        res = compute_type1_gage(measurements, reference, settings={'tolerance_val': tolerance, 'tolerance_type': 'tolerance'})

        self.assertEqual(res['n'], 50)
        self.assertEqual(res['reference'], 0.1000)
        self.assertEqual(res['tolerance'], 0.05)
        self.assertAlmostEqual(res['mean'], np.mean(measurements), places=7)
        self.assertAlmostEqual(res['std'], np.std(measurements, ddof=1), places=7)

        # Expected Cg = (0.20 * 0.05) / (6 * s)
        s = res['std']
        expected_cg = (0.20 * 0.05) / (6.0 * s)
        self.assertAlmostEqual(res['cg'], expected_cg, places=6)

        # Expected Cgk = (0.5 * 0.20 * 0.05 - |mean - ref|) / (3 * s)
        bias = res['mean'] - reference
        expected_cgk = (0.005 - abs(bias)) / (3.0 * s)
        self.assertAlmostEqual(res['cgk'], expected_cgk, places=6)

        # %Var relations (denominator is total tolerance)
        expected_pct_var_rep = (6.0 * s) / tolerance * 100.0
        expected_pct_var_rep_bias = (6.0 * s + 2.0 * abs(bias)) / tolerance * 100.0
        self.assertAlmostEqual(res['pct_var_repeatability'], expected_pct_var_rep, places=5)
        self.assertAlmostEqual(res['pct_var_rep_and_bias'], expected_pct_var_rep_bias, places=5)

        # Bias test
        self.assertEqual(res['df'], 49)
        self.assertAlmostEqual(res['t_stat'], bias / (s / math.sqrt(50)), places=6)
        self.assertTrue(0.0 <= res['p_value'] <= 1.0)

        # Report generation
        rpt = generate_type1_gage_report(res, "Diameter")
        self.assertIn("Type 1 Gage Study for Diameter", rpt)
        self.assertIn("Reference:  0.1", rpt)
        self.assertIn("Cg (Repeatability)", rpt)
        self.assertIn("Cgk (Repeatability and Bias)", rpt)

    def test_lower_spec_limit_only(self):
        vals = [10.02, 10.05, 9.98, 10.01, 10.03, 10.00, 9.99, 10.04, 10.02, 10.01]
        ref = 10.0
        lsl = 9.5
        res = compute_type1_gage(vals, ref, settings={'tolerance_type': 'lower', 'lsl': lsl})

        # Tol = 2 * (10.0 - 9.5) = 1.0
        self.assertEqual(res['tolerance'], 1.0)
        self.assertEqual(res['tolerance_type'], 'lower')
        self.assertEqual(res['lsl'], 9.5)
        self.assertGreater(res['cg'], 0.0)
        self.assertGreater(res['cgk'], 0.0)

    def test_upper_spec_limit_only(self):
        vals = [10.02, 10.05, 9.98, 10.01, 10.03, 10.00, 9.99, 10.04, 10.02, 10.01]
        ref = 10.0
        usl = 10.8
        res = compute_type1_gage(vals, ref, settings={'tolerance_type': 'upper', 'usl': usl})

        # Tol = 2 * (10.8 - 10.0) = 1.6
        self.assertAlmostEqual(res['tolerance'], 1.6, places=6)
        self.assertEqual(res['tolerance_type'], 'upper')
        self.assertEqual(res['usl'], 10.8)
        self.assertGreater(res['cg'], 0.0)
        self.assertGreater(res['cgk'], 0.0)

    def test_custom_options_and_resolution(self):
        vals = [5.01, 4.99, 5.00, 5.02, 4.98, 5.00]
        ref = 5.00
        res = compute_type1_gage(vals, ref, settings={
            'tolerance_type': 'tolerance',
            'tolerance_val': 0.10,
            'cg_percent': 15.0,
            'study_var': 5.15,
            'resolution': 0.001,
            'perform_bias_test': False,
            'title': 'Calibration Check'
        })
        self.assertEqual(res['cg_percent'], 15.0)
        self.assertEqual(res['study_multiplier'], 5.15)
        self.assertEqual(res['resolution'], 0.001)
        self.assertAlmostEqual(res['pct_resolution'], (0.001 / 0.10) * 100.0)
        self.assertFalse(res['perform_bias_test'])
        self.assertEqual(res['title'], 'Calibration Check')

    def test_error_handling(self):
        with self.assertRaises(ValueError):
            compute_type1_gage([1.0], 1.0, {'tolerance_val': 0.5})

        with self.assertRaises(ValueError):
            compute_type1_gage([1.0, 2.0], float('nan'), {'tolerance_val': 0.5})

        with self.assertRaises(ValueError):
            compute_type1_gage([1.0, 2.0], 1.0, {'tolerance_val': -0.5})

        with self.assertRaises(ValueError):
            # Ref <= LSL
            compute_type1_gage([1.0, 2.0], 1.0, {'tolerance_type': 'lower', 'lsl': 1.5})

        with self.assertRaises(ValueError):
            # Ref >= USL
            compute_type1_gage([1.0, 2.0], 2.0, {'tolerance_type': 'upper', 'usl': 1.5})


    def test_constant_measurements_do_not_report_perfect_capability(self):
        for value, reference in ((10.0, 10.0), (10.0, 0.0), (0.1, 0.1), (0.1, 0.0)):
            with self.subTest(value=value, reference=reference):
                with self.assertRaisesRegex(ValueError, 'nonzero, finite measurement variation'):
                    compute_type1_gage([value] * 20, reference, {'tolerance_val': 1.0})

if __name__ == '__main__':
    unittest.main()
