import math
import unittest
import numpy as np

from statcraft.model import Column, Worksheet
from statcraft.subgroup_control import (
    c4,
    c5,
    d2,
    d3,
    control_chart_settings,
    evaluate_nelson_tests,
    fit_subgroups,
    fit_from_worksheet,
)
from statcraft.subgroup_control_report import text_report


class TestSubgroupControl(unittest.TestCase):
    def test_unbiasing_constants(self):
        # Known theoretical c4 constants: c4(2) = sqrt(2/pi) ~ 0.79788456
        self.assertAlmostEqual(c4(2), math.sqrt(2.0 / math.pi), places=6)
        # c4(3) = sqrt(pi)/2 ~ 0.8862269
        self.assertAlmostEqual(c4(3), math.sqrt(math.pi) / 2.0, places=6)
        # c4(4) = sqrt(8 / (3*pi)) ~ 0.92131773
        self.assertAlmostEqual(c4(4), math.sqrt(8.0 / (3.0 * math.pi)), places=6)
        # c4(5) ~ 0.940032
        self.assertAlmostEqual(c4(5), 0.940032, places=4)

        # c5(n) = sqrt(1 - c4^2)
        for n in range(2, 10):
            c = c4(n)
            self.assertAlmostEqual(c5(n), math.sqrt(1.0 - c * c), places=6)

        # d2 and d3 published tables
        self.assertAlmostEqual(d2(2), 1.128)
        self.assertAlmostEqual(d2(5), 2.326)
        self.assertAlmostEqual(d2(10), 3.078)
        self.assertAlmostEqual(d3(2), 0.8525)
        self.assertAlmostEqual(d3(5), 0.8641)
        self.assertAlmostEqual(d3(10), 0.7971)

    def test_settings_validation(self):
        opts = control_chart_settings({'chart_type': 'xbar_r'})
        self.assertEqual(opts['chart_type'], 'xbar_r')
        self.assertAlmostEqual(opts['k_sigma'], 3.0)
        self.assertTrue(opts['display_upper'])
        self.assertTrue(opts['display_lower'])
        self.assertEqual(opts['estimation_method'], 'rbar')
        self.assertTrue(opts['unbiasing'])

        # Bad chart type
        with self.assertRaises(ValueError):
            control_chart_settings({'chart_type': 'invalid'})

        # Bad k_sigma
        with self.assertRaises(ValueError):
            control_chart_settings({'k_sigma': -1.0})
        with self.assertRaises(ValueError):
            control_chart_settings({'k_sigma': 15.0})

        # Historical parameters
        opts_hist = control_chart_settings({
            'chart_type': 'xbar_s',
            'historical_mean': 100.5,
            'historical_sigma': 2.5,
            'estimation_method': 'pooled_stdev',
        })
        self.assertEqual(opts_hist['historical_mean'], 100.5)
        self.assertEqual(opts_hist['historical_sigma'], 2.5)
        self.assertEqual(opts_hist['estimation_method'], 'pooled_stdev')

        # Negative historical sigma
        with self.assertRaises(ValueError):
            control_chart_settings({'historical_sigma': -2.0})

    def test_xbar_r_hand_calculation(self):
        # 3 subgroups of size 5:
        # G1: 1, 2, 3, 4, 5 (mean=3, range=4)
        # G2: 2, 3, 4, 5, 6 (mean=4, range=4)
        # G3: 3, 4, 5, 6, 7 (mean=5, range=4)
        subgroups = [
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [2.0, 3.0, 4.0, 5.0, 6.0],
            [3.0, 4.0, 5.0, 6.0, 7.0],
        ]
        res = fit_subgroups(subgroups, chart_type='xbar_r')

        self.assertEqual(res['k_subgroups'], 3)
        self.assertEqual(res['subgroup_sizes'], [5, 5, 5])
        self.assertEqual(res['means'], [3.0, 4.0, 5.0])
        self.assertEqual(res['ranges'], [4.0, 4.0, 4.0])
        self.assertEqual(res['xbar_center'], 4.0)
        self.assertEqual(res['disp_center'], 4.0)

        # Within sigma = Rbar / d2(5) = 4.0 / 2.326
        expected_sigma = 4.0 / 2.326
        self.assertAlmostEqual(res['within_stdev'], expected_sigma, places=6)

        # Xbar limits: 4.0 +/- 3 * sigma / sqrt(5)
        width = 3.0 * expected_sigma / math.sqrt(5.0)
        self.assertAlmostEqual(res['xbar_lcl'][0], 4.0 - width, places=6)
        self.assertAlmostEqual(res['xbar_ucl'][0], 4.0 + width, places=6)

        # R limits: 4.0 +/- 3 * d3(5) * sigma
        r_width = 3.0 * 0.8641 * expected_sigma
        self.assertAlmostEqual(res['disp_lcl'][0], max(0.0, 4.0 - r_width), places=6)
        self.assertAlmostEqual(res['disp_ucl'][0], 4.0 + r_width, places=6)

        # No test failures
        self.assertEqual(res['test_failures'], {})
        self.assertEqual(res['disp_signals'], [])

    def test_xbar_s_hand_calculation(self):
        # Same 3 subgroups of size 5:
        # G1: 1, 2, 3, 4, 5 (mean=3, s = sqrt(10/4) = sqrt(2.5) ~ 1.5811388)
        # G2: 2, 3, 4, 5, 6 (mean=4, s = 1.5811388)
        # G3: 3, 4, 5, 6, 7 (mean=5, s = 1.5811388)
        subgroups = [
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [2.0, 3.0, 4.0, 5.0, 6.0],
            [3.0, 4.0, 5.0, 6.0, 7.0],
        ]
        res = fit_subgroups(subgroups, chart_type='xbar_s')

        s_val = math.sqrt(2.5)
        self.assertAlmostEqual(res['disp_center'], s_val, places=6)

        # Within sigma = Sbar / c4(5)
        expected_sigma = s_val / c4(5)
        self.assertAlmostEqual(res['within_stdev'], expected_sigma, places=6)

        # Xbar limits
        width = 3.0 * expected_sigma / math.sqrt(5.0)
        self.assertAlmostEqual(res['xbar_lcl'][0], 4.0 - width, places=6)
        self.assertAlmostEqual(res['xbar_ucl'][0], 4.0 + width, places=6)

        # S limits: Sbar +/- 3 * c5(5) * sigma
        s_width = 3.0 * c5(5) * expected_sigma
        self.assertAlmostEqual(res['disp_lcl'][0], max(0.0, s_val - s_width), places=6)
        self.assertAlmostEqual(res['disp_ucl'][0], s_val + s_width, places=6)

    def test_omit_subgroups_and_historical_parameters(self):
        # Subgroups with internal variation so sigma > 0
        subgroups = [
            [9.0, 10.0, 11.0],
            [95.0, 100.0, 105.0],  # Outlier to omit
            [11.0, 12.0, 13.0],
        ]
        # Omit subgroup 2
        res = fit_subgroups(subgroups, chart_type='xbar_r', options={'omit_subgroups': [2]})
        # Center line should be computed from subgroups 1 and 3: (10 + 12)/2 = 11.0
        self.assertAlmostEqual(res['xbar_center'], 11.0)
        # Subgroup 2 still evaluated and fails Test 1
        self.assertIn(2, res['test_failures'])
        self.assertIn(1, res['test_failures'][2])

        # Historical parameters
        res_hist = fit_subgroups(subgroups, chart_type='xbar_r', options={
            'historical_mean': 50.0,
            'historical_sigma': 5.0,
        })
        self.assertEqual(res_hist['xbar_center'], 50.0)
        self.assertEqual(res_hist['within_stdev'], 5.0)

    def test_nelson_tests_all_eight(self):
        cfg = control_chart_settings({'tests': {
            'test1': {'enabled': True, 'k': 3.0},
            'test2': {'enabled': True, 'k': 9},
            'test3': {'enabled': True, 'k': 6},
            'test4': {'enabled': True, 'k': 14},
            'test5': {'enabled': True, 'k': 2},
            'test6': {'enabled': True, 'k': 4},
            'test7': {'enabled': True, 'k': 15},
            'test8': {'enabled': True, 'k': 8},
        }})['tests']

        # Test 1 failure:
        means = [0.0] * 10
        means[5] = 4.0
        sigmas = [1.0] * 10
        fails = evaluate_nelson_tests(means, center=0.0, sigmas=sigmas, tests_cfg=cfg)
        self.assertIn(6, fails)
        self.assertIn(1, fails[6])

        # Test 2: 9 points on same side of center line
        means = [0.5] * 12
        sigmas = [1.0] * 12
        fails = evaluate_nelson_tests(means, center=0.0, sigmas=sigmas, tests_cfg=cfg)
        for p in (9, 10, 11, 12):
            self.assertIn(p, fails)
            self.assertIn(2, fails[p])

        # Test 3: 6 points in a row strictly increasing
        means = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 0.0]
        sigmas = [1.0] * 7
        fails = evaluate_nelson_tests(means, center=0.0, sigmas=sigmas, tests_cfg=cfg)
        self.assertIn(6, fails)
        self.assertIn(3, fails[6])

        # Test 4: 14 points alternating up and down
        means = [1.0, -1.0] * 8  # 16 points alternating
        sigmas = [1.0] * 16
        fails = evaluate_nelson_tests(means, center=0.0, sigmas=sigmas, tests_cfg=cfg)
        self.assertIn(14, fails)
        self.assertIn(4, fails[14])

        # Test 5: 2 out of 3 points > 2 sigma
        means = [0.0, 2.2, 0.5, 2.3, 0.0]  # points 2 and 4 are > 2
        sigmas = [1.0] * 5
        fails = evaluate_nelson_tests(means, center=0.0, sigmas=sigmas, tests_cfg=cfg)
        self.assertIn(4, fails)
        self.assertIn(5, fails[4])

        # Test 6: 4 out of 5 points > 1 sigma
        means = [1.2, 1.3, 0.2, 1.4, 1.5]
        sigmas = [1.0] * 5
        fails = evaluate_nelson_tests(means, center=0.0, sigmas=sigmas, tests_cfg=cfg)
        self.assertIn(5, fails)
        self.assertIn(6, fails[5])

        # Test 7: 15 points within 1 sigma (Zone C)
        means = [0.2] * 16
        sigmas = [1.0] * 16
        fails = evaluate_nelson_tests(means, center=0.0, sigmas=sigmas, tests_cfg=cfg)
        self.assertIn(15, fails)
        self.assertIn(7, fails[15])

        # Test 8: 8 points > 1 sigma (outside Zone C)
        means = [1.5, -1.5] * 5
        sigmas = [1.0] * 10
        fails = evaluate_nelson_tests(means, center=0.0, sigmas=sigmas, tests_cfg=cfg)
        self.assertIn(8, fails)
        self.assertIn(8, fails[8])

    def test_fit_from_worksheet_and_storage(self):
        # Stacked data with constant subgroup size 4
        raw = [10.0, 11.0, 12.0, 13.0,
               20.0, 21.0, 22.0, 23.0,
               30.0, 31.0, 32.0, 33.0]
        sheet = Worksheet('QCData', [Column('Meas', 'number', raw)])

        res = fit_from_worksheet(
            sheet,
            stacked=True,
            response_index=0,
            subgroup_size=4,
            chart_type='xbar_r',
            options={'storage': {
                'points': True,
                'center_line': True,
                'control_limits': True,
                'subgroup_sizes': True,
                'test_results': True,
            }}
        )

        self.assertEqual(res['k_subgroups'], 3)
        self.assertEqual(res['subgroup_sizes'], [4, 4, 4])
        self.assertEqual(res['means'], [11.5, 21.5, 31.5])
        self.assertEqual(res['ranges'], [3.0, 3.0, 3.0])

        # Check stored columns on worksheet
        col_names = [c.name for c in sheet.columns]
        self.assertTrue(any(c.startswith('XBAR') for c in col_names))
        self.assertTrue(any(c.startswith('RANGE') for c in col_names))
        self.assertTrue(any(c.startswith('CENL') for c in col_names))
        self.assertTrue(any(c.startswith('LCON') for c in col_names))
        self.assertTrue(any(c.startswith('UCON') for c in col_names))
        self.assertTrue(any(c.startswith('SSIZ') for c in col_names))
        self.assertTrue(any(c.startswith('TEST') for c in col_names))

        # Check text report
        report = text_report(res)
        self.assertIn("Xbar-R Chart of Meas", report)
        self.assertIn("Number of subgroups: 3", report)
        self.assertIn("Process Parameters and Limit Estimates", report)
        self.assertIn("Test Results for Xbar Chart of Meas", report)


if __name__ == '__main__':
    unittest.main()
