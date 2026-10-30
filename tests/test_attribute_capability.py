"""Analytic fixtures and validation for independent attribute capability."""
import json
import math
import unittest
from scipy.stats import beta, binom, chi2, norm
from statcraft.attribute_capability import analyze
from statcraft.model import Column, Worksheet


def sheet(counts, sizes=None):
    cols = [Column('Defects', values=counts)]
    if sizes is not None:
        cols.append(Column('Units', values=sizes))
    return Worksheet(columns=cols)


class AttributeCapabilityTests(unittest.TestCase):
    def test_binomial_pooled_not_average_of_rates(self):
        r = analyze(sheet([1, 9], [10, 30]), 'binomial', 0, size_index=1)
        self.assertEqual(r['observed_rate'], .25)
        self.assertEqual(r['percent_defective'], 25)
        self.assertEqual(r['ppm_defective'], 250000)
        self.assertAlmostEqual(r['process_z'], norm.isf(.25))
        self.assertEqual(r['cumulative_rates'], [.1, .25])
        self.assertEqual(r['n_samples'], 2)
        self.assertEqual(r['total_count'], 10)
        self.assertEqual(r['total_size'], 40)

    def test_clopper_pearson_exact_tail_probabilities(self):
        r = analyze(sheet([10]), 'binomial', 0, sample_size=100)
        lo, hi = r['rate_ci']
        self.assertAlmostEqual(binom.sf(9, 100, lo), .025, places=10)
        self.assertAlmostEqual(binom.cdf(10, 100, hi), .025, places=10)
        self.assertAlmostEqual(r['percent_ci'][0], lo * 100)
        self.assertAlmostEqual(r['ppm_ci'][1], hi * 1e6)
        self.assertAlmostEqual(r['process_z_ci'][0], norm.isf(hi))
        self.assertAlmostEqual(r['process_z_ci'][1], norm.isf(lo))

    def test_zero_defectives_exact_bound_and_safe_z(self):
        r = analyze(sheet([0, 0]), 'binomial', 0, sample_size=10)
        self.assertEqual(r['rate_ci'][0], 0)
        self.assertAlmostEqual(r['rate_ci'][1], 1 - .025 ** (1 / 20))
        self.assertIsNone(r['process_z'])
        self.assertEqual(r['process_z_label'], '+Infinity')
        self.assertEqual(r['process_z_ci_labels'][1], '+Infinity')
        json.dumps(r, allow_nan=False)

    def test_all_defectives_exact_bound_and_safe_z(self):
        r = analyze(sheet([10]), 'binomial', 0, sample_size=10)
        self.assertAlmostEqual(r['rate_ci'][0], .025 ** .1)
        self.assertEqual(r['rate_ci'][1], 1)
        self.assertIsNone(r['process_z'])
        self.assertEqual(r['process_z_label'], '-Infinity')
        json.dumps(r, allow_nan=False)

    def test_one_sided_binomial_intervals(self):
        s = sheet([3])
        lower = analyze(s, 'binomial', 0, 20, options={'interval_type': 'lower'})
        upper = analyze(s, 'binomial', 0, 20, options={'interval_type': 'upper'})
        self.assertAlmostEqual(lower['rate_ci'][0], beta.ppf(.05, 3, 18))
        self.assertEqual(lower['rate_ci'][1], 1)
        self.assertEqual(upper['rate_ci'][0], 0)
        self.assertAlmostEqual(upper['rate_ci'][1], beta.isf(.05, 4, 17))

    def test_fractional_poisson_exposure(self):
        r = analyze(sheet([2, 3], [.5, 2]), 'poisson', 0, size_index=1)
        self.assertEqual(r['observed_rate'], 2)
        self.assertEqual(r['mean_defects'], 2.5)
        self.assertEqual(r['mean_dpu'], 2)
        self.assertEqual(r['min_dpu'], 1.5)
        self.assertEqual(r['max_dpu'], 4)
        self.assertEqual(r['cumulative_rates'], [4, 2])
        self.assertAlmostEqual(r['rate_ci'][0], chi2.ppf(.025, 10) / 5)
        self.assertAlmostEqual(r['rate_ci'][1], chi2.isf(.025, 12) / 5)
        self.assertIsNone(r['percent_defective'])
        json.dumps(r, allow_nan=False)

    def test_zero_poisson_and_one_sided_intervals(self):
        s = sheet([0, 0])
        r = analyze(s, 'poisson', 0, sample_size=.5)
        self.assertEqual(r['rate_ci'][0], 0)
        self.assertAlmostEqual(r['rate_ci'][1], -math.log(.025))
        lo = analyze(s, 'poisson', 0, sample_size=.5, options={'interval_type': 'lower'})
        hi = analyze(s, 'poisson', 0, sample_size=.5, options={'interval_type': 'upper'})
        self.assertEqual(lo['rate_ci'], [0, None])
        self.assertAlmostEqual(hi['rate_ci'][1], -math.log(.05))
        json.dumps(lo, allow_nan=False)

    def test_aligned_missing_preserves_rows_and_selected_extent(self):
        s = sheet([1, None, 5, 2], [10, 100, None, 20, 30])
        s.columns.append(Column('Unrelated', values=list(range(20))))
        r = analyze(s, 'binomial', 0, size_index=1)
        self.assertEqual(r['rows'], [1, 4])
        self.assertEqual(r['omitted_rows'], [2, 3, 5])
        self.assertEqual(r['total_count'], 3)
        self.assertEqual(r['total_size'], 30)
        self.assertEqual(r['counts'], [1, 2])
        self.assertEqual(r['sample_sizes'], [10, 20])

    def test_historical_controls_do_not_replace_estimates(self):
        r = analyze(sheet([1, 10]), 'binomial', 0, 10,
                    options={'historical': .1, 'target': .01})
        self.assertEqual(r['observed_rate'], .55)
        self.assertEqual(r['chart_rate'], .1)
        self.assertEqual(r['target_percent'], 1)
        self.assertEqual(r['center_line'], [.1, .1])
        self.assertAlmostEqual(r['ucl'][0], .1 + 3 * math.sqrt(.1 * .9 / 10))
        self.assertEqual(r['lcl'], [0, 0])
        self.assertEqual(r['violations'], [2])
        observed = analyze(sheet([1, 10]), 'binomial', 0, 10)
        self.assertEqual(r['rate_ci'], observed['rate_ci'])

    def test_poisson_historical_control_limits(self):
        r = analyze(sheet([0, 2]), 'poisson', 0, 2, options={'historical': 3})
        self.assertEqual(r['observed_rate'], .5)
        self.assertAlmostEqual(r['ucl'][0], 3 + 3 * math.sqrt(3 / 2))
        self.assertEqual(r['lcl'], [0, 0])

    def test_unequal_sizes_vary_limits(self):
        r = analyze(sheet([1, 2], [10, 20]), 'binomial', 0, size_index=1)
        self.assertGreater(r['ucl'][0], r['ucl'][1])
        self.assertEqual(r['center_line'], [.1, .1])

    def test_invalid_counts_and_sizes(self):
        for method in ('binomial', 'poisson'):
            for bad in (-1, 1.5, True, 2 ** 54):
                with self.subTest(method=method, bad=bad), self.assertRaises(ValueError):
                    analyze(sheet([bad]) if not isinstance(bad, bool) else sheet([0]), method, 0,
                            sample_size=True if isinstance(bad, bool) else 10)
            for size in (0, -1, True, float('inf'), float('nan'), '10'):
                with self.subTest(method=method, size=size), self.assertRaises(ValueError):
                    analyze(sheet([0]), method, 0, sample_size=size)
        with self.assertRaises(ValueError):
            analyze(sheet([2]), 'binomial', 0, 1)
        with self.assertRaises(ValueError):
            analyze(sheet([0]), 'binomial', 0, 1.5)

    def test_invalid_selection_and_no_pairs(self):
        for index in (-1, True, .5, 2):
            with self.subTest(index=index), self.assertRaises(ValueError):
                analyze(sheet([1]), 'poisson', index)
        with self.assertRaises(ValueError):
            analyze(sheet([1]), 'poisson', 0, size_index=0)
        with self.assertRaises(ValueError):
            analyze(Worksheet(columns=[Column('Text', 'text', ['1'])]), 'poisson', 0)
        for counts, sizes in (([], []), ([None], [2]), ([1], [None])):
            with self.assertRaises(ValueError):
                analyze(sheet(counts, sizes), 'poisson', 0, size_index=1)

    def test_invalid_options(self):
        for options in ({'confidence': 0}, {'confidence': 100}, {'confidence': True},
                        {'confidence': float('nan')}, {'historical': -1},
                        {'historical': 1.01}, {'target': 1.01}, {'target': -1},
                        {'interval_type': 'other'}, {'show_graphs': 1},
                        {'title': 1}, {'unknown': 10}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                analyze(sheet([0]), 'binomial', 0, 10, options=options)
        with self.assertRaises(ValueError):
            analyze(sheet([0]), 'normal', 0)
        with self.assertRaises(ValueError):
            analyze(sheet([0]), 'poisson', 0, options=[])

    def test_extreme_rate_fails_cleanly(self):
        with self.assertRaises(ValueError):
            analyze(sheet([1]), 'poisson', 0, 5e-324)
        with self.assertRaises(ValueError):
            analyze(sheet([2 ** 53, 1]), 'poisson', 0)
        with self.assertRaises(ValueError):
            analyze(sheet([0, 0]), 'binomial', 0, 2 ** 53)

    def test_options_and_worksheet_unchanged(self):
        s = sheet([1, 2])
        options = {'title': ' Custom ', 'confidence': 90}
        r = analyze(s, 'poisson', 0, options=options)
        self.assertEqual(options, {'title': ' Custom ', 'confidence': 90})
        self.assertEqual(s.columns[0].values, [1, 2])
        self.assertEqual(r['title'], 'Custom')
        json.dumps(r, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
