"""Agreement statistics must use observed eligible samples and actual trials."""
import copy
import unittest
import numpy as np
from statcraft.msa_attribute_engine import (analyze_attribute_agreement, _compute_cohen_kappa,
    _compute_fleiss_kappa, _binomial_ci)
from statcraft.msa_reports import format_attribute_agreement_report, format_gage_linearity_report


def study(apps=('A', 'B'), samples=('1', '2'), repeats=2):
    rows = []
    for app in apps:
        for i, sample in enumerate(samples):
            truth = 'Pass' if i % 2 == 0 else 'Fail'
            for trial in range(1, repeats + 1):
                rows.append((truth, sample, app, truth, trial))
    return rows


def run(rows, **kwargs):
    values, samples, apps, standards, trials = zip(*rows)
    return analyze_attribute_agreement(list(values), list(samples), list(apps), standard=list(standards), trials=list(trials), **kwargs)


class AgreementIntegrityTests(unittest.TestCase):
    def test_conflicting_sample_standards_rejected(self):
        rows = study()
        rows[-1] = (*rows[-1][:3], 'Pass', rows[-1][4])
        with self.assertRaisesRegex(ValueError, 'Conflicting standard'):
            run(rows)

    def test_conflict_detected_even_when_rating_missing(self):
        rows = study()
        rows.append((None, '1', 'A', 'Fail', 3))
        with self.assertRaisesRegex(ValueError, 'Conflicting standard'):
            run(rows)

    def test_optional_column_lengths_must_match(self):
        for field in ('standard', 'trials'):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'same length'):
                analyze_attribute_agreement(['P'] * 4, ['1'] * 4, ['A'] * 4, **{field: [1]})

    def test_duplicate_trial_identity_rejected(self):
        rows = study()
        rows[1] = (*rows[1][:4], 1)
        with self.assertRaisesRegex(ValueError, 'Duplicate trial'):
            run(rows)

    def test_explicit_trial_order_does_not_change_results(self):
        rows = study(repeats=3, samples=('1', '2', '3', '4'))
        rows[2] = ('Fail', *rows[2][1:])
        before = run(rows)
        order = [rows[i] for i in np.random.default_rng(72).permutation(len(rows))]
        self.assertEqual(before, run(order))

    def test_all_three_trials_contribute_to_within_kappa(self):
        rows = []
        for sample, ratings in [('1', ['P', 'P', 'F']), ('2', ['F', 'F', 'P']), ('3', ['P', 'P', 'P']), ('4', ['F', 'F', 'F'])]:
            rows += [(rating, sample, 'A', None, trial) for trial, rating in enumerate(ratings, 1)]
        result = run(rows)['within_appraiser'][0]
        self.assertAlmostEqual(result['kappa'], 1 / 3)
        self.assertEqual(result['percent'], 50)
        self.assertIn('all completed trials', result['kappa_method'])
        self.assertIsNone(result['p_value'])

    def test_sparse_appraisers_have_actual_denominators(self):
        rows = study(apps=('A',), samples=('1', '2')) + study(apps=('B',), samples=('2', '3'))
        # Keep shared-sample standards consistent; the second builder starts with P.
        rows = [(rating if sample != '2' else 'Fail', sample, app, truth if sample != '2' else 'Fail', trial)
                for rating, sample, app, truth, trial in rows]
        result = run(rows)
        self.assertEqual([row['inspected'] for row in result['within_appraiser']], [2, 2])
        self.assertEqual(result['between_appraisers']['inspected'], 1)
        self.assertEqual(result['between_appraisers']['matched'], 1)

    def test_no_shared_samples_is_unestimable_between(self):
        rows = study(apps=('A',), samples=('1', '2')) + study(apps=('B',), samples=('3', '4'))
        result = run(rows)
        self.assertEqual(result['between_appraisers']['inspected'], 0)
        self.assertIsNone(result['between_appraisers']['percent'])
        self.assertIsNone(result['between_appraisers']['kappa'])
        self.assertIn('No eligible samples', format_attribute_agreement_report(result))

    def test_single_trial_cannot_prove_repeatability(self):
        result = run(study(repeats=1))
        for row in result['within_appraiser']:
            self.assertEqual(row['inspected'], 0)
            self.assertIsNone(row['percent'])
            self.assertIsNone(row['kappa'])
            self.assertIsNone(row['p_value'])
        self.assertEqual(result['between_appraisers']['percent'], 100)

    def test_constant_category_kappa_undefined_despite_perfect_percent(self):
        rows = [('Pass', sample, app, 'Pass', trial) for app in ('A', 'B') for sample in ('1', '2') for trial in (1, 2)]
        result = run(rows)
        self.assertEqual(result['within_appraiser'][0]['percent'], 100)
        self.assertIsNone(result['within_appraiser'][0]['kappa'])
        self.assertIsNone(result['between_appraisers']['kappa'])
        self.assertIsNone(_compute_cohen_kappa(['P'] * 4, ['P'] * 4, ['P'])['kappa'])

    def test_standard_only_categories_are_preserved(self):
        rows = [('Pass', sample, app, 'Pass' if sample == '1' else 'Fail', trial)
                for app in ('A', 'B') for sample in ('1', '2') for trial in (1, 2)]
        result = run(rows)
        self.assertEqual(result['categories'], ['Fail', 'Pass'])
        self.assertEqual(result['appraiser_vs_standard'][0]['percent'], 50)
        self.assertAlmostEqual(result['appraiser_vs_standard'][0]['kappa'], -1 / 3)
        cohen = _compute_cohen_kappa(['Pass', 'Pass'], ['Pass', 'Fail'], ['Pass'])
        self.assertEqual(cohen['kappa'], 0)

    def test_missing_standard_does_not_inflate_denominator(self):
        rows = [(rating, sample, app, truth if sample == '1' else None, trial) for rating, sample, app, truth, trial in study()]
        result = run(rows)
        self.assertEqual(result['appraiser_vs_standard'][0]['inspected'], 1)
        self.assertEqual(result['appraiser_vs_standard'][0]['percent'], 100)
        self.assertEqual(result['all_appraisers_vs_standard']['inspected'], 1)

    def test_missing_trial_excludes_incomplete_sample(self):
        rows = study()
        rows[1] = (*rows[1][:4], None)
        result = run(rows)
        self.assertEqual(result['within_appraiser'][0]['inspected'], 1)
        self.assertEqual(result['omitted_rows'], [1])

    def test_fleiss_rejects_unequal_counts_without_fabricated_values(self):
        result = _compute_fleiss_kappa(np.array([[2, 1], [1, 1]]))
        self.assertIsNone(result['kappa'])
        self.assertIsNone(result['p_value'])

    def test_known_standard_coefficient_averages_trials(self):
        rows = study(apps=('A',), samples=('1', '2', '3', '4'))
        rows = [('Pass' if trial == 2 else rating, sample, app, truth, trial) for rating, sample, app, truth, trial in rows]
        result = run(rows)['appraiser_vs_standard'][0]
        self.assertAlmostEqual(result['kappa'], (1 - 1 / 3) / 2)

    def test_confidence_level_validated_and_reported(self):
        result = run(study(samples=('1', '2', '3', '4')), alpha=.1)
        report = format_attribute_agreement_report(result)
        self.assertIn('90% CI', report)
        self.assertNotIn('95% CI', report)
        for alpha in (0, 1, float('nan'), True):
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                run(study(), alpha=alpha)

    def test_boundary_confidence_intervals_use_documented_tail(self):
        low, high = _binomial_ci(5, 5, .95)
        self.assertAlmostEqual(low, .05 ** (1 / 5) * 100)
        self.assertEqual(high, 100)
        low, high = _binomial_ci(0, 5, .95)
        self.assertEqual(low, 0)
        self.assertAlmostEqual(high, (1 - .05 ** (1 / 5)) * 100)
        self.assertEqual(_binomial_ci(0, 0), (None, None))

    def test_degenerate_linearity_report_accepts_none(self):
        result = {'process_variation': None, 'pct_linearity': None,
                  'regression': {'slope_t': None, 'slope_p': None, 'intercept_t': None, 'intercept_p': None, 'r_squared': None},
                  'bias_table': [{'reference': 1., 'count': 2, 'average_bias': 0., 'pct_bias': None, 'std_error': 0., 't_statistic': None, 'p_value': None}],
                  'overall_bias': {'t_statistic': None, 'p_value': None}}
        self.assertIn('T = *', format_gage_linearity_report(result))


if __name__ == '__main__':
    unittest.main()
