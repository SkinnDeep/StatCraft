import copy, tempfile, unittest
from pathlib import Path
from statcraft.app import Presenter, format_entry
from statcraft.model import Column, Worksheet
from statcraft.recipes import columns, run
from statcraft.logistic import settings
from statcraft.prediction import settings as prediction_settings


def fixture():
    return Worksheet('Logistic study', [
        Column('Outcome', 'text', ['Fail', 'Fail', 'Pass', 'Fail', 'Fail', 'Pass', 'Pass', 'Fail', 'Pass', 'Pass', 'Fail', 'Pass']),
        Column('Temperature', 'number', [10., 11., 13., 14., 15., 16., 17., 18., 19., 20., 21., 24.]),
        Column('Material', 'text', ['A', 'B', 'A', 'B', 'A', 'B', 'A', 'B', 'A', 'B', 'B', 'A']),
        Column('Events', 'number', [2, 4, 6, 9, 12, 15, 3, 5, 8, 11, 14, 17]),
        Column('Trials', 'number', [20]*12),
        Column('New temp', 'number', [13., None, 21.]),
        Column('New material', 'text', ['A', 'B', 'B']),
    ])


class BinaryLogisticIntegrationTests(unittest.TestCase):
    def presenter(self):
        p = Presenter()
        p.worksheet = fixture()
        return p

    def test_individual_fit_recipe_staleness_and_rerun(self):
        p = self.presenter()
        opts = dict(settings(), graphs='four')
        entry = p.fit_binary_logistic(0, [1], [2], event='Pass', terms=[[0], [1]], options=opts)
        self.assertEqual(columns(entry['recipe']), [0, 1, 2])
        self.assertFalse(p.result_stale(entry))
        self.assertEqual(run(p, entry['recipe'])['result'], entry['result'])
        self.assertIn('Odds Ratios', format_entry(entry))
        self.assertEqual(p.validate_brushed_rows(entry, [1, 4, 12]), [1, 4, 12])
        p.set_cell(0, 1, '11.5')
        self.assertTrue(p.result_stale(entry))
        again = p.rerun_result(entry)
        self.assertFalse(p.result_stale(again))
        self.assertNotEqual(again['result']['probabilities'], entry['result']['probabilities'])

    def test_grouped_events_trials_fit_and_column_move_undo_redo(self):
        p = self.presenter()
        entry = p.fit_binary_logistic(3, [1], [2], trials_index=4, terms=[[0], [1]])
        self.assertEqual(columns(entry['recipe']), [1, 2, 3, 4])
        p.move_columns([3, 4], destination='before_c1')
        params = entry['recipe']['parameters']
        self.assertEqual(params['response_index'], 0)
        self.assertEqual(params['trials_index'], 1)
        self.assertEqual(params['continuous_indices'], [3])
        self.assertEqual(params['categorical_indices'], [4])
        self.assertEqual(p.rerun_result(entry)['result']['probabilities'], entry['result']['probabilities'])
        p.undo()
        self.assertEqual(entry['recipe']['parameters']['response_index'], 3)
        self.assertEqual(entry['recipe']['parameters']['trials_index'], 4)
        p.redo()
        self.assertEqual(entry['recipe']['parameters']['response_index'], 0)

    def test_logistic_prediction_manual_and_columns_follow_moves_and_deletes(self):
        p = self.presenter()
        model = p.fit_binary_logistic(0, [1], [2], event='Pass', terms=[[0], [1]])
        pred_opts = dict(prediction_settings(), intervals='confidence', confidence=.9)
        manual = p.predict_model(model['recipe'], values=[['A', 15.], ['B', 22.]], options=pred_opts)
        self.assertEqual(manual['result']['analysis'], 'logistic_prediction')
        self.assertIn('Probability Predictions', format_entry(manual))
        col_pred = p.predict_model(model['recipe'], input_mode='columns', new_indices=[6, 5], options=pred_opts)
        self.assertEqual(columns(col_pred['recipe']), [0, 1, 2, 5, 6])
        self.assertEqual(col_pred['result']['missing'], 1)
        p.move_columns([0], destination='after_last')
        self.assertEqual(col_pred['recipe']['parameters']['model_recipe']['parameters']['response_index'], 6)
        self.assertEqual(col_pred['recipe']['parameters']['new_indices'], [5, 4])
        self.assertEqual(p.rerun_result(col_pred)['result']['rows'], col_pred['result']['rows'])
        p.delete_columns([4])
        self.assertTrue(col_pred.get('source_unavailable'))
        with self.assertRaises(ValueError):
            p.rerun_result(col_pred)
        p.undo()
        self.assertFalse(col_pred.get('source_unavailable'))
        self.assertEqual(p.rerun_result(col_pred)['result']['rows'], col_pred['result']['rows'])

    def test_mpx_roundtrip_logistic_fit_and_prediction(self):
        p = self.presenter()
        model = p.fit_binary_logistic(0, [1], [2], event='Pass', terms=[[0], [1]], options=dict(settings(), graphs='four'))
        pred = p.predict_model(model['recipe'], values=[['A', 15.], [None, 20.], ['B', 30.]], options=dict(prediction_settings(), intervals='confidence'))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'logistic-roundtrip.mpx'
            p.save(path)
            q = Presenter()
            q.load(path)
            loaded_fit = next(e for e in q.history if e.get('recipe', {}).get('action') == 'fit_binary_logistic')
            loaded_pred = next(e for e in q.history if e.get('recipe', {}).get('action') == 'predict_model')
            self.assertEqual(loaded_fit['result'], model['result'])
            self.assertEqual(loaded_pred['result'], pred['result'])
            self.assertFalse(q.result_stale(loaded_fit))
            self.assertFalse(q.result_stale(loaded_pred))
            self.assertEqual(q.rerun_result(loaded_fit)['result'], model['result'])
            self.assertEqual(q.rerun_result(loaded_pred)['result'], pred['result'])

    def test_invalid_logistic_and_prediction_recipes_rejected(self):
        p = self.presenter()
        model = p.fit_binary_logistic(0, [1], [2], event='Pass')
        for key, value in [
            ('continuous_indices', []),
            ('response_index', 1),
            ('trials_index', 2),
            ('event', True),
            ('event', float('nan')),
            ('terms', [[0, 1]]),
        ]:
            bad = copy.deepcopy(model['recipe'])
            if key == 'continuous_indices':
                bad['parameters']['categorical_indices'] = []
            bad['parameters'][key] = value
            with self.assertRaises(ValueError):
                columns(bad)
        pred = p.predict_model(model['recipe'], values=[['A', 15.]])
        for bad_interval in ('both', 'prediction'):
            bad_pred = copy.deepcopy(pred['recipe'])
            bad_pred['parameters']['options']['intervals'] = bad_interval
            with self.assertRaises(ValueError):
                columns(bad_pred)


if __name__ == '__main__':
    unittest.main()
