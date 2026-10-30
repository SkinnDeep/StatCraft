import copy
import unittest

from statcraft.prediction_report import sections, text_report


def example():
    return dict(analysis='model_prediction', model_action='regression',
                model_title='Regression: Strength versus Time', response_name='Strength',
                predictor_names=['Time', 'Temperature'], options={}, count=1,
                used=12, missing=2, df_error=9, residual_stdev=.123456789,
                coefficients=[{'name': 'Constant', 'estimate': 1.23456789},
                              {'name': 'Time', 'estimate': 2.5}],
                rows=[dict(row=1, inputs=[4.5, 20], fit=6.789123456,
                           se_fit=.123456789, ci_low=6., ci_high=7.,
                           pi_low=5., pi_high=8., extrapolated=False, status='ok')],
                status='ok', warnings=[])


class PredictionReportTests(unittest.TestCase):
    def table(self, r, title='Predictions'):
        return next(t for t in sections(r) if t[0] == title)

    def test_named_predictors_are_scalar_cells(self):
        _, headers, rows = self.table(example(), 'New Predictor Values')
        self.assertEqual(headers, ['Row', 'Time', 'Temperature'])
        self.assertEqual(rows, [[1, 4.5, 20]])

    def test_default_two_sided_intervals(self):
        _, headers, rows = self.table(example())
        self.assertEqual(headers, ['Row', 'Fit', 'SE Fit', '95% CI Lower',
                                  '95% CI Upper', '95% PI Lower', '95% PI Upper', 'X', 'Status'])
        self.assertEqual(rows[0][3:7], [6., 7., 5., 8.])

    def test_interval_choices(self):
        for choice, included, excluded in [('confidence', 'CI', 'PI'), ('prediction', 'PI', 'CI')]:
            r = example(); r['options']['intervals'] = choice
            headers = self.table(r)[1]
            self.assertTrue(any(included in h for h in headers))
            self.assertFalse(any(excluded in h for h in headers))
        r['options']['intervals'] = 'none'
        self.assertEqual(self.table(r)[1], ['Row', 'Fit', 'SE Fit', 'X', 'Status'])

    def test_lower_only_does_not_render_open_endpoint_as_missing(self):
        r = example(); r['options'] = {'side': 'lower', 'confidence': .9}
        r['rows'][0].update(ci_high=None, pi_high=None)
        headers = self.table(r)[1]
        self.assertIn('90% CI Lower', headers)
        self.assertFalse(any('Upper' in h for h in headers))
        self.assertNotIn('Infinity', text_report(r))

    def test_upper_only(self):
        r = example(); r['options']['side'] = 'upper'
        headers = self.table(r)[1]
        self.assertIn('95% CI Upper', headers)
        self.assertFalse(any('Lower' in h for h in headers))

    def test_table_hiding_keeps_method_and_coefficients(self):
        r = example(); r['options']['show_table'] = False
        self.assertEqual([t[0] for t in sections(r)], ['Regression Equation', 'Coefficients', 'Method'])

    def test_prediction_is_first_visible_section(self):
        tables = sections(example())
        self.assertEqual([table[0] for table in tables], [
            'Predictions', 'New Predictor Values', 'Regression Equation', 'Coefficients', 'Method'])
        self.assertIn('Fit', tables[0][1])
        self.assertIn('95% CI Lower', tables[0][1])
        self.assertLess(text_report(example()).index('Predictions'),
                        text_report(example()).index('Method'))

    def test_only_method_when_both_result_choices_hidden(self):
        r = example(); r['options'].update(show_table=False, show_equation=False)
        self.assertEqual([table[0] for table in sections(r)], ['Method'])

    def test_equation_hiding(self):
        r = example(); r['options']['show_equation'] = False
        self.assertNotIn('Coefficients', [t[0] for t in sections(r)])
        self.assertNotIn('Regression Equation', [t[0] for t in sections(r)])

    def test_equation_response_signed_terms_and_coding_note(self):
        r = example()
        r['coefficients'].append(dict(name='Temperature', estimate=-.375))
        text = text_report(r)
        self.assertIn('Strength = 1.234568 + 2.5 Time - 0.375 Temperature', text)
        self.assertIn('Source model coding and standardization', text)

    def test_equation_wraps_without_losing_terms(self):
        r = example()
        r['coefficients'] = [dict(name='Constant', estimate=3)] + [
            dict(name='Predictor_' + str(i), estimate=(-1)**i * (i+.25)) for i in range(30)]
        rows = self.table(r, 'Regression Equation')[2]
        self.assertGreater(len(rows), 2)
        self.assertTrue(all(len(row[0]) <= 78 for row in rows))
        joined = ' '.join(row[0] for row in rows)
        for term in r['coefficients'][1:]:
            self.assertIn(term['name'], joined)

    def test_exact_fit_undefined_bounds(self):
        r = example(); r['rows'][0].update(status='exact_fit', ci_low=None,
                                         ci_high=None, pi_low=None, pi_high=None)
        text = text_report(r)
        self.assertIn('Exact fit; uncertainty undefined', text)
        self.assertIn('*', text)
        self.assertNotIn('Infinity', text)

    def test_missing_prediction(self):
        r = example(); r['rows'][0].update(inputs=[None], fit=None, se_fit=None,
                                         ci_low=None, ci_high=None, pi_low=None, pi_high=None,
                                         status='missing_predictors')
        self.assertEqual(self.table(r, 'New Predictor Values')[2], [[1, None, None]])
        self.assertIn('missing_predictors', text_report(r))

    def test_extrapolation_separate_from_status(self):
        r = example(); r['rows'][0]['extrapolated'] = True
        self.assertEqual(self.table(r)[2][0][-2:], ['X', ''])
        self.assertIn('outside the observed predictor ranges', text_report(r))
        r['rows'][0]['status'] = 'estimated'
        self.assertEqual(self.table(r)[2][0][-2:], ['X', ''])

    def test_text_precision_no_array_or_metadata_dump(self):
        text = text_report(example())
        self.assertIn('6.789123', text)
        self.assertIn('0.1234568', text)
        self.assertNotIn('[4.5, 20]', text)
        self.assertNotIn('model_prediction', text)
        self.assertNotIn("{'", text)

    def test_does_not_mutate_result(self):
        r = example(); before = copy.deepcopy(r)
        text_report(r)
        self.assertEqual(r, before)

    def test_count_labels_describe_prediction_rows(self):
        values = dict(self.table(example(), 'Method')[2])
        self.assertEqual(values['Usable prediction rows'], 12)
        self.assertEqual(values['Prediction rows with missing settings'], 2)
        self.assertNotIn('Model observations', values)

    def test_real_engine_result_is_readable(self):
        from statcraft.model import Column, Worksheet
        from statcraft.prediction import predict
        sheet = Worksheet('Test', [Column('Time', values=[0, 1, 2, 3, 4]),
                                   Column('Strength', values=[2, 5, 5, 8, 11])])
        recipe = dict(action='multiple_regression', parameters=dict(
            response_index=1, predictor_indices=[0], confidence=.95))
        result = predict(sheet, recipe, values=[[2], [None], [10]])
        text = text_report(result)
        self.assertIn('Strength', text)
        self.assertIn('Time', text)
        self.assertIn('Missing predictor settings', text)
        self.assertIn('stored coefficients are not reused', text)
        for _, headers, rows in sections(result):
            for row in rows:
                self.assertEqual(len(headers), len(row))
                self.assertTrue(all(not isinstance(v, (dict, list, tuple)) for v in row))


if __name__ == '__main__':
    unittest.main()
