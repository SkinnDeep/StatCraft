"""Tests for Shewhart Extended Limits and Warning Bands (StatCraft.6 feature).

Verifies multi-k sigma values, warning limit bands (UWL/LWL at 2 sigma),
zone boundaries, report rendering, and UI dialog validation.
"""

from __future__ import annotations

import unittest
import numpy as np

from statcraft.subgroup_control import fit_subgroups, control_chart_settings
from statcraft.imr_engine import run_imr_chart
from statcraft.subgroup_control_report import text_report
from statcraft.imr_report import format_imr_report


class TestShewhartExtendedLimits(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        # 10 subgroups of size 5
        self.sg_data = [
            np.random.normal(10.0, 1.0, 5).tolist() for _ in range(10)
        ]
        self.ind_data = np.random.normal(25.0, 2.0, 30).tolist()

    def test_subgroup_control_warning_limits(self):
        opts = {
            'warning_limits': True,
            'warning_k': 2.0,
            'k_sigma': 3.0,
        }
        res = fit_subgroups(self.sg_data, chart_type='xbar_r', options=opts)
        
        self.assertIn('xbar_uwl', res)
        self.assertIn('xbar_lwl', res)
        self.assertIn('disp_uwl', res)
        self.assertIn('disp_lwl', res)

        mu = res['xbar_center']
        ucl = res['xbar_ucl'][0]
        lcl = res['xbar_lcl'][0]
        uwl = res['xbar_uwl'][0]
        lwl = res['xbar_lwl'][0]

        # UCL > UWL > mu > LWL > LCL
        self.assertGreater(ucl, uwl)
        self.assertGreater(uwl, mu)
        self.assertGreater(mu, lwl)
        self.assertGreater(lwl, lcl)

        # Check ratio (UWL - mu) / (UCL - mu) == 2.0 / 3.0
        ratio = (uwl - mu) / (ucl - mu)
        self.assertAlmostEqual(ratio, 2.0 / 3.0, places=4)

    def test_subgroup_control_multi_k(self):
        opts = {
            'k_sigma': '1 2 3',
        }
        res = fit_subgroups(self.sg_data, chart_type='xbar_s', options=opts)
        self.assertIn('xbar_uwl', res)
        self.assertIn('xbar_lwl', res)
        self.assertTrue(res['options']['warning_limits'])
        self.assertTrue(res['options']['display_zones'])

    def test_subgroup_report_warning_limits(self):
        opts = {
            'warning_limits': True,
            'warning_k': 2.0,
            'k_sigma': 3.0,
        }
        res = fit_subgroups(self.sg_data, chart_type='xbar_r', options=opts)
        report = text_report(res)
        self.assertIn("Lower Warning Limit (LWL)", report)
        self.assertIn("Upper Warning Limit (UWL)", report)

    def test_imr_warning_limits(self):
        opts = {
            'warning_limits': True,
            'warning_k': 2.0,
            'k_sigma': 3.0,
        }
        res = run_imr_chart(self.ind_data, options=opts)

        self.assertIn('i_uwl', res)
        self.assertIn('i_lwl', res)
        self.assertIn('mr_uwl', res)
        self.assertIn('mr_lwl', res)

        i_cl = res['i_center']
        i_ucl = res['i_ucl']
        i_lcl = res['i_lcl']
        i_uwl = res['i_uwl']
        i_lwl = res['i_lwl']

        self.assertGreater(i_ucl, i_uwl)
        self.assertGreater(i_uwl, i_cl)
        self.assertGreater(i_cl, i_lwl)
        self.assertGreater(i_lwl, i_lcl)

        ratio = (i_uwl - i_cl) / (i_ucl - i_cl)
        self.assertAlmostEqual(ratio, 2.0 / 3.0, places=4)

    def test_imr_multi_k(self):
        opts = {
            'k_sigma': '1, 2, 3',
        }
        res = run_imr_chart(self.ind_data, options=opts)
        self.assertIn('i_uwl', res)
        self.assertIn('i_lwl', res)
        self.assertTrue(res['warning_limits'])
        self.assertTrue(res['display_zones'])

    def test_imr_report_warning_limits(self):
        opts = {
            'warning_limits': True,
            'warning_k': 2.0,
            'k_sigma': 3.0,
        }
        res = run_imr_chart(self.ind_data, options=opts)
        report = format_imr_report(res)
        self.assertIn("I LWL:", report)
        self.assertIn("I UWL:", report)
        self.assertIn("MR LWL:", report)
        self.assertIn("MR UWL:", report)


if __name__ == '__main__':
    unittest.main()
