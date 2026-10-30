"""Numerical acceptance tests for independent balanced crossed Gage R&R."""
import copy
import json
import math
import unittest
import numpy as np
from scipy import stats
from statcraft.model import Worksheet, Column
from statcraft.gage_rr import analyze, settings


def example(interaction=0.0, noise=1.0, scale=1.0, offset=0.0):
    # 3 parts, 2 operators, 2 repeats; orthogonal effects and residuals.
    y, part, operator = [], [], []
    for a, part_effect in enumerate((-10., 0., 10.)):
        for b, operator_effect in enumerate((-2., 2.)):
            for error in (-noise, noise):
                y.append(offset + scale * (30 + part_effect + operator_effect + interaction * (a - 1) * (2*b - 1) + error))
                part.append('P' + str(a+1)); operator.append('O' + str(b+1))
    return Worksheet('Gage', [Column('Diameter', values=y), Column('Part', 'text', part), Column('Operator', 'text', operator)])


def indexed(result):
    return {c['key']: c for c in result['variance_components']}


class GageRRTests(unittest.TestCase):
    def test_hand_calculated_full_anova(self):
        r = analyze(example(), 0, 1, 2, {'remove_interaction': False})
        table = {row['source']: row for row in r['anova']}
        self.assertEqual([row['df'] for row in r['anova']], [2, 1, 2, 6, 11])
        for source, expected in [('Part', 800), ('Operator', 48), ('Part * Operator', 0), ('Repeatability', 12), ('Total', 860)]:
            self.assertAlmostEqual(table[source]['ss'], expected)
        c = indexed(r)
        for key, expected in [('repeatability', 2), ('operator', 8), ('interaction', 0), ('part_to_part', 100), ('total_grr', 10), ('total', 110)]:
            self.assertAlmostEqual(c[key]['variance'], expected)
        self.assertEqual(r['ndc'], 4)

    def test_hand_calculated_pooled_interaction(self):
        r = analyze(example(), 0, 1, 2)
        self.assertTrue(r['interaction']['pooled'])
        self.assertEqual(r['interaction']['p_value'], 1)
        self.assertEqual(len(r['anova']), 4)
        self.assertEqual(r['anova'][2]['df'], 8)
        self.assertAlmostEqual(r['anova'][2]['ms'], 1.5)
        c = indexed(r)
        self.assertNotIn('interaction', c)
        self.assertAlmostEqual(c['repeatability']['variance'], 1.5)
        self.assertAlmostEqual(c['operator']['variance'], 7.75)
        self.assertAlmostEqual(c['part_to_part']['variance'], 99.625)
        self.assertAlmostEqual(c['total_grr']['variance'], 9.25)
        self.assertAlmostEqual(r['anova'][0]['f'], 400/1.5)
        self.assertAlmostEqual(r['anova'][0]['p_value'], stats.f.sf(400/1.5, 2, 8))

    def test_significant_interaction_is_retained(self):
        r = analyze(example(interaction=4), 0, 1, 2)
        self.assertFalse(r['interaction']['pooled'])
        self.assertAlmostEqual(r['anova'][2]['ss'], 128)
        self.assertAlmostEqual(r['anova'][2]['f'], 32)
        self.assertAlmostEqual(r['interaction']['p_value'], stats.f.sf(32, 2, 6))
        c = indexed(r)
        self.assertAlmostEqual(c['interaction']['variance'], 31)
        self.assertAlmostEqual(c['operator']['variance'], 0)  # Truncate negative estimate.
        self.assertAlmostEqual(c['part_to_part']['variance'], 84)
        self.assertAlmostEqual(c['total_grr']['variance'], 33)

    def test_percentages_use_variance_or_standard_deviation_as_appropriate(self):
        c = indexed(analyze(example(), 0, 1, 2, dict(remove_interaction=False, study_multiplier=5.15, tolerance=20., process_stdev=4.)))
        self.assertAlmostEqual(c['total_grr']['percent_contribution'], 100 * 10/110)
        self.assertAlmostEqual(c['total_grr']['percent_study_variation'], 100 * math.sqrt(10/110))
        self.assertAlmostEqual(c['total_grr']['percent_tolerance'], 100 * 5.15 * math.sqrt(10)/20)
        self.assertAlmostEqual(c['total_grr']['percent_process'], 100 * math.sqrt(10)/4)
        self.assertAlmostEqual(c['repeatability']['percent_contribution'] + c['reproducibility']['percent_contribution'] + c['part_to_part']['percent_contribution'], 100)

    def test_process_sd_does_not_silently_replace_estimated_variance(self):
        a = indexed(analyze(example(), 0, 1, 2))
        b = indexed(analyze(example(), 0, 1, 2, {'process_stdev': .1}))
        self.assertEqual(a['total']['variance'], b['total']['variance'])
        self.assertGreater(b['total_grr']['percent_process'], 100)

    def test_uniform_measurement_scaling_and_offset(self):
        baseline = analyze(example(interaction=4), 0, 1, 2)
        for scale in (.01, -2., 1000.):
            r = analyze(example(interaction=4, scale=scale, offset=1e6), 0, 1, 2)
            self.assertEqual(r['ndc'], baseline['ndc'])
            for c, expected in zip(r['variance_components'], baseline['variance_components']):
                self.assertAlmostEqual(c['variance']/(scale*scale), expected['variance'], places=7)
                self.assertAlmostEqual(c['percent_study_variation'], expected['percent_study_variation'], places=7)

    def test_random_orthogonal_design_agrees_with_direct_projection(self):
        rng = np.random.default_rng(581)
        for p, q, repeat in [(2, 3, 4), (5, 2, 3), (4, 4, 2)]:
            array = rng.normal(size=(p, q, repeat))
            y = array.flatten().tolist()
            part = [i for i in range(p) for j in range(q) for k in range(repeat)]
            operator = [j for i in range(p) for j in range(q) for k in range(repeat)]
            s = Worksheet(columns=[Column('Y', values=y), Column('P', values=part), Column('O', values=operator)])
            r = analyze(s, 0, 1, 2, {'remove_interaction': False})
            # Independent least-squares projections of intercept, main effects,
            # and saturated cell means yield sequential orthogonal SS.
            intercept = np.ones((len(y), 1))
            pa = np.asarray([[float(a == level) for level in range(1, p)] for a in part])
            op = np.asarray([[float(b == level) for level in range(1, q)] for b in operator])
            cross = np.asarray([[float(a == i and b == j) for i in range(1, p) for j in range(1, q)] for a, b in zip(part, operator)])
            residual_ss = []
            for x in [intercept, np.column_stack((intercept, pa)), np.column_stack((intercept, pa, op)), np.column_stack((intercept, pa, op, cross))]:
                residual = np.asarray(y) - x @ np.linalg.lstsq(x, y, rcond=None)[0]
                residual_ss.append(float(residual @ residual))
            expected = [residual_ss[0]-residual_ss[1], residual_ss[1]-residual_ss[2], residual_ss[2]-residual_ss[3], residual_ss[3]]
            for row, ss in zip(r['anova'], expected): self.assertAlmostEqual(row['ss'], ss, places=10)

    def test_aligned_omission_keeps_original_row_indices_and_complete_cells(self):
        s = example()
        for column, value in zip(s.columns, [None, 'Extra', 'Extra']): column.values.insert(3, value)
        r = analyze(s, 0, 1, 2)
        self.assertEqual(r['missing'], 1)
        self.assertEqual(r['n'], 12)
        self.assertNotIn(3, r['row_indices'])
        self.assertNotIn('Extra', r['parts'])
        self.assertEqual(r['variance_components'], analyze(example(), 0, 1, 2)['variance_components'])

    def test_missing_measurement_cannot_silently_create_unbalanced_study(self):
        s = example(); s.columns[0].values[0] = None
        with self.assertRaisesRegex(ValueError, 'balanced'): analyze(s, 0, 1, 2)

    def test_missing_crossed_cell_is_rejected(self):
        s = example()
        for c in s.columns: del c.values[:2]
        with self.assertRaisesRegex(ValueError, 'balanced'): analyze(s, 0, 1, 2)

    def test_one_repeat_is_rejected(self):
        s = example()
        for c in s.columns: c.values = c.values[::2]
        with self.assertRaisesRegex(ValueError, 'two equal repeats'): analyze(s, 0, 1, 2)

    def test_one_factor_level_is_rejected(self):
        s = example(); s.columns[2].values = ['One'] * 12
        with self.assertRaisesRegex(ValueError, 'two observed'): analyze(s, 0, 1, 2)

    def test_role_indices_are_distinct_in_range_integers(self):
        for indices in [(0, 0, 2), (-1, 1, 2), (0, 1, 3), (True, 1, 2), (0., 1, 2)]:
            with self.subTest(indices=indices), self.assertRaises(ValueError): analyze(example(), *indices)

    def test_measurement_and_factor_types(self):
        for index, kind in [(0, 'text'), (0, 'date'), (1, 'date'), (2, 'date')]:
            s = example(); s.columns[index].kind = kind
            with self.subTest(index=index, kind=kind), self.assertRaises(ValueError): analyze(s, 0, 1, 2)

    def test_all_missing_is_rejected(self):
        s = example(); s.columns[0].values = [None] * 12
        with self.assertRaises(ValueError): analyze(s, 0, 1, 2)

    def test_options_reject_invalid_values(self):
        for o in [[], {'mystery': 1}, {'remove_interaction': 1}, {'interaction_alpha': 1}, {'interaction_alpha': 0}, {'study_multiplier': True}, {'study_multiplier': float('nan')}, {'tolerance': -1}, {'process_stdev': float('inf')}, {'study_multiplier': None}, {'study_multiplier': 10**1000}]:
            with self.subTest(options=o), self.assertRaises(ValueError): settings(o)

    def test_zero_total_variation_is_json_safe_and_explained(self):
        s = example(); s.columns[0].values = [5.] * 12
        r = analyze(s, 0, 1, 2)
        self.assertEqual(r['ndc'], 1)
        self.assertIn('all estimated variation is zero', r['ndc_note'])
        self.assertIsNone(indexed(r)['total']['percent_contribution'])
        json.dumps(r, allow_nan=False)

    def test_exact_measurements_have_unbounded_categories_without_infinity(self):
        s = example(noise=0)
        s.columns[0].values = [float(i // 4) for i in range(12)]
        r = analyze(s, 0, 1, 2)
        self.assertIsNone(r['ndc'])
        self.assertIn('Unbounded', r['ndc_note'])
        self.assertEqual(r['anova'][0]['p_value'], 0)
        json.dumps(r, allow_nan=False)

    def test_factor_order_and_raw_plot_values_preserve_associations(self):
        s = example(); s.columns[1].metadata['value_order'] = {'mode': 'custom', 'values': ['P3', 'P1', 'P2']}
        before = copy.deepcopy(s)
        r = analyze(s, 0, 1, 2)
        self.assertEqual(r['parts'], ['P3', 'P1', 'P2'])
        self.assertEqual(s, before)
        self.assertEqual(len(r['plot_data']['cells']), 6)
        for cell in r['plot_data']['cells']:
            self.assertAlmostEqual(cell['mean'], sum(cell['values'])/2)
            self.assertEqual(cell['range'], 2)
        self.assertEqual(r['plot_data']['rows'][0], {'part': 'P1', 'operator': 'O1', 'value': 17., 'row': 0})

    def test_large_values_fail_as_validation_error(self):
        s = example(); s.columns[0].values[0] = 1e308
        with self.assertRaisesRegex(ValueError, 'floating-point'): analyze(s, 0, 1, 2)

    def test_large_constant_measurements_keep_plot_means_finite(self):
        s = example(); s.columns[0].values = [1e308] * 12
        r = analyze(s, 0, 1, 2)
        self.assertEqual(r['plot_data']['cells'][0]['mean'], 1e308)
        self.assertEqual(r['plot_data']['part_means'][0]['mean'], 1e308)
        self.assertEqual(r['plot_data']['operator_means'][0]['mean'], 1e308)
        json.dumps(r, allow_nan=False)

    def test_extreme_study_percentage_is_rejected(self):
        for options in [{'study_multiplier': 1e308}, {'tolerance': 1e-308}, {'process_stdev': 1e-308}]:
            with self.subTest(options=options), self.assertRaises(ValueError): analyze(example(), 0, 1, 2, options)


if __name__ == '__main__': unittest.main()
