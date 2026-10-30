import math
import unittest
from statcraft.model import Column, Worksheet
from statcraft.oneway import (
    fit,
    fit_unstacked,
    oneway_settings,
)
from statcraft.oneway_report import sections, text_report


class TestOneWayANOVA(unittest.TestCase):
    def setUp(self):
        # Classic textbook 3-level ANOVA data (e.g., Fabric tensile strength across Cotton percentages)
        # 15%: 7, 7, 15, 11, 9  (mean = 9.8, n = 5)
        # 20%: 12, 17, 12, 18, 18 (mean = 15.4, n = 5)
        # 25%: 14, 18, 18, 19, 19 (mean = 17.6, n = 5)
        self.tensile = [7.0, 7.0, 15.0, 11.0, 9.0, 12.0, 17.0, 12.0, 18.0, 18.0, 14.0, 18.0, 18.0, 19.0, 19.0]
        self.cotton = ['15%', '15%', '15%', '15%', '15%', '20%', '20%', '20%', '20%', '20%', '25%', '25%', '25%', '25%', '25%']
        self.sheet = Worksheet(
            'Fabric',
            [
                Column('Strength', 'number', self.tensile),
                Column('Cotton', 'text', self.cotton),
                Column('Cotton15', 'number', [7.0, 7.0, 15.0, 11.0, 9.0]),
                Column('Cotton20', 'number', [12.0, 17.0, 12.0, 18.0, 18.0]),
                Column('Cotton25', 'number', [14.0, 18.0, 18.0, 19.0, 19.0]),
            ],
        )

    def test_settings_validation(self):
        opts = oneway_settings()
        self.assertTrue(opts['stacked'])
        self.assertAlmostEqual(opts['confidence'], 0.95)
        self.assertTrue(opts['assume_equal_variances'])
        self.assertTrue(opts['graphs']['interval_plot'])

        # Bad confidence
        with self.assertRaises(ValueError):
            oneway_settings({'confidence': 1.5})
        with self.assertRaises(ValueError):
            oneway_settings({'confidence': -0.1})

        # Bad interval type
        with self.assertRaises(ValueError):
            oneway_settings({'interval_type': 'invalid'})

    def test_stacked_fit_equal_variances(self):
        opts = oneway_settings({
            'confidence': 0.95,
            'assume_equal_variances': True,
            'comparisons': {
                'tukey': True,
                'fisher': True,
                'dunnett': True,
                'control_level': '15%',
                'hsu_mcb': True,
                'best_mode': 'largest',
            },
        })
        res = fit(self.sheet, response_index=0, factor_index=1, options=opts)

        self.assertEqual(res['analysis'], 'oneway_anova')
        self.assertEqual(res['response_name'], 'Strength')
        self.assertEqual(res['factor_name'], 'Cotton')

        # ANOVA table checks
        anova = res['anova_table']
        self.assertEqual(anova['df_factor'], 2)
        self.assertEqual(anova['df_error'], 12)
        self.assertEqual(anova['df_total'], 14)

        # SS: Factor = 161.73, Error = 101.2, Total = 262.93
        self.assertAlmostEqual(anova['ss_factor'], 161.7333, places=2)
        self.assertAlmostEqual(anova['ss_error'], 101.2, places=1)
        self.assertAlmostEqual(anova['ss_total'], 262.9333, places=2)

        # MS
        self.assertAlmostEqual(anova['ms_factor'], 80.8667, places=2)
        self.assertAlmostEqual(anova['ms_error'], 8.4333, places=2)

        # F-value ~ 9.59, p-value < 0.01
        self.assertAlmostEqual(anova['f_value'], 9.5889, places=2)
        self.assertLess(anova['p_value'], 0.01)

        # Model summary
        summary = res['model_summary']
        self.assertAlmostEqual(summary['s'], math.sqrt(101.2 / 12), places=3)
        self.assertAlmostEqual(summary['r_sq'], (161.7333 / 262.9333) * 100.0, places=2)
        self.assertGreater(summary['r_sq_adj'], 0.5)
        self.assertGreater(summary['r_sq_pred'], 0.1)

        # Means
        means = res['means']
        self.assertEqual(len(means), 3)
        self.assertAlmostEqual(means[0]['mean'], 9.8, places=1)
        self.assertAlmostEqual(means[1]['mean'], 15.4, places=1)
        self.assertAlmostEqual(means[2]['mean'], 17.6, places=1)

        # Fits and residuals
        self.assertEqual(len(res['fits']), 15)
        self.assertEqual(len(res['residuals']), 15)
        for y, f, r in zip(self.tensile, res['fits'], res['residuals']):
            self.assertAlmostEqual(y, f + r, places=6)

    def test_unstacked_fit(self):
        opts = oneway_settings({
            'confidence': 0.95,
            'assume_equal_variances': True,
        })
        res = fit_unstacked(self.sheet, response_indices=[2, 3, 4], options=opts)
        self.assertEqual(res['analysis'], 'oneway_anova')
        self.assertEqual(res['anova_table']['df_factor'], 2)
        self.assertEqual(res['anova_table']['df_error'], 12)
        self.assertAlmostEqual(res['anova_table']['f_value'], 9.5889, places=2)

    def test_comparisons(self):
        opts = oneway_settings({
            'confidence': 0.95,
            'assume_equal_variances': True,
            'comparisons': {
                'error_rate': 0.05,
                'tukey': True,
                'fisher': True,
                'dunnett': True,
                'control_level': '15%',
                'hsu_mcb': True,
                'best_mode': 'largest',
            },
        })
        res = fit(self.sheet, response_index=0, factor_index=1, options=opts)
        comps = res['comparisons']

        # Tukey
        self.assertIn('tukey', comps)
        tukey = comps['tukey']
        self.assertEqual(len(tukey['grouping']), 3)
        # Groups: 25% and 20% share 'A', 15% is 'B'
        grp_map = {g['level']: g['grouping'] for g in tukey['grouping']}
        self.assertIn('A', grp_map['25%'])
        self.assertIn('B', grp_map['15%'])
        self.assertEqual(len(tukey['tests']), 3)

        # Fisher
        self.assertIn('fisher', comps)
        fisher = comps['fisher']
        self.assertEqual(len(fisher['grouping']), 3)
        self.assertEqual(len(fisher['tests']), 3)

        # Dunnett
        self.assertIn('dunnett', comps)
        dunnett = comps['dunnett']
        self.assertEqual(dunnett['control'], '15%')
        self.assertEqual(len(dunnett['tests']), 2)  # Compared against 15%

        # Hsu MCB
        self.assertIn('hsu_mcb', comps)
        hsu = comps['hsu_mcb']
        self.assertEqual(hsu['best_mode'], 'largest')
        self.assertEqual(len(hsu['tests']), 3)

    def test_welch_unequal_variances(self):
        opts = oneway_settings({
            'confidence': 0.95,
            'assume_equal_variances': False,
            'comparisons': {
                'games_howell': True,
            },
        })
        res = fit(self.sheet, response_index=0, factor_index=1, options=opts)
        self.assertIn('welch_anova', res)
        welch = res['welch_anova']
        self.assertGreater(welch['f'], 0.0)
        self.assertEqual(welch['df_num'], 2)
        self.assertGreater(welch['df_den'], 0.0)
        self.assertLess(welch['p_value'], 0.05)

        # Games-Howell
        self.assertIn('games_howell', res['comparisons'])
        gh = res['comparisons']['games_howell']
        self.assertEqual(len(gh['tests']), 3)

    def test_report_generation(self):
        opts = oneway_settings({
            'confidence': 0.95,
            'assume_equal_variances': True,
            'comparisons': {'tukey': True},
        })
        res = fit(self.sheet, response_index=0, factor_index=1, options=opts)
        sec = sections(res)
        self.assertIn('method', sec)
        self.assertIn('factor_info', sec)
        self.assertIn('anova', sec)
        self.assertIn('model_summary', sec)
        self.assertIn('means', sec)
        self.assertIn('comparisons', sec)

        rep = text_report(res)
        self.assertIn('One-way ANOVA: Strength versus Cotton', rep)
        self.assertIn('Null hypothesis', rep)
        self.assertIn('Analysis of Variance', rep)
        self.assertIn('Model Summary', rep)
        self.assertIn('Means', rep)
        self.assertIn('Tukey Pairwise Comparisons', rep)


if __name__ == '__main__':
    unittest.main()
