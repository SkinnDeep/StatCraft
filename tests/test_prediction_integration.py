import copy,tempfile,unittest
from pathlib import Path
from statcraft.app import Presenter,format_entry
from statcraft.model import Column,Worksheet
from statcraft.recipes import columns,run
from statcraft.prediction import settings


def fixture():
    return Worksheet('Prediction inputs',[Column('Time',values=[1,2,3,4,5,6]),Column('Strength',values=[2.1,4.2,5.8,8.1,9.9,12.2]),Column('New time',values=[2.5,None,7.])])


class PredictionIntegrationTests(unittest.TestCase):
    def presenter(self):
        p=Presenter();p.worksheet=fixture();model=p.multiple_regression(1,[0]);return p,model

    def test_manual_recipe_does_not_mutate_inputs_and_reruns(self):
        p,model=self.presenter();values=[[2.5],[None],[7.]];before=copy.deepcopy(values)
        entry=p.predict_model(model['recipe'],values=values)
        self.assertEqual(values,before);self.assertEqual(entry['result']['missing'],1)
        self.assertEqual(run(p,entry['recipe'])['result'],entry['result'])
        self.assertEqual(columns(entry['recipe']),[0,1]);self.assertFalse(p.result_stale(entry))

    def test_column_inputs_fingerprint_and_rerun(self):
        p,model=self.presenter();entry=p.predict_model(model['recipe'],input_mode='columns',new_indices=[2])
        self.assertEqual(columns(entry['recipe']),[0,1,2]);self.assertFalse(p.result_stale(entry))
        p.set_cell(0,2,'3.5');self.assertTrue(p.result_stale(entry))
        again=p.rerun_result(entry);self.assertFalse(p.result_stale(again))
        self.assertNotEqual(again['result']['rows'][0]['fit'],entry['result']['rows'][0]['fit'])

    def test_nested_source_and_new_columns_follow_move_undo_redo(self):
        p,model=self.presenter();entry=p.predict_model(model['recipe'],input_mode='columns',new_indices=[2])
        p.move_columns([0],destination='after_last');params=entry['recipe']['parameters']
        self.assertEqual(params['model_recipe']['parameters']['predictor_indices'],[2]);self.assertEqual(params['new_indices'],[1])
        self.assertEqual(p.rerun_result(entry)['result']['rows'],entry['result']['rows'])
        p.undo();self.assertEqual(entry['recipe']['parameters']['new_indices'],[2])
        p.redo();self.assertEqual(entry['recipe']['parameters']['new_indices'],[1])

    def test_deleted_new_input_blocks_rerun_and_undo_restores(self):
        p,model=self.presenter();entry=p.predict_model(model['recipe'],input_mode='columns',new_indices=[2])
        p.delete_columns([2]);self.assertTrue(entry.get('source_unavailable'))
        with self.assertRaises(ValueError):p.rerun_result(entry)
        p.undo();self.assertFalse(entry.get('source_unavailable'));self.assertEqual(p.rerun_result(entry)['result']['rows'],entry['result']['rows'])

    def test_mpx_roundtrip_prediction_and_source_setup(self):
        p,model=self.presenter();entry=p.predict_model(model['recipe'],values=[[3],[None],[8]])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'predictions.mpx';p.save(path);q=Presenter();q.load(path)
            loaded=next(e for e in q.history if e.get('recipe',{}).get('action')=='predict_model')
            self.assertEqual(loaded['result'],entry['result']);self.assertFalse(q.result_stale(loaded))
            self.assertEqual(q.rerun_result(loaded)['result'],entry['result'])

    def test_legacy_simple_model_canonical_saved_recipe(self):
        p=Presenter();p.worksheet=fixture();model=p.inference('linear_regression',[0,1]);entry=p.predict_model(model['recipe'],values=[[3]])
        self.assertEqual(entry['recipe']['parameters']['model_recipe']['action'],'multiple_regression')
        self.assertIn('Predictions',format_entry(entry));self.assertNotIn('methodnotes:',format_entry(entry))

    def test_invalid_recipe_rejected_before_session_record(self):
        p,model=self.presenter();entry=p.predict_model(model['recipe'],values=[[2]])
        for key,value in [('input_mode','unknown'),('new_indices',[2]),('values',[[True]]),('values',[[float('inf')]]),('values',[[1,2]])]:
            bad=copy.deepcopy(entry['recipe']);bad['parameters'][key]=value
            with self.assertRaises(ValueError):columns(bad)
        bad=copy.deepcopy(entry['recipe']);bad['parameters']['model_recipe']=entry['recipe']
        with self.assertRaises(ValueError):columns(bad)

    def test_display_choices_affect_readable_report_only(self):
        p,model=self.presenter();opts=settings();opts.update(show_table=False,show_equation=False)
        entry=p.predict_model(model['recipe'],values=[[2]],options=opts);text=format_entry(entry)
        self.assertNotIn('New Predictor Values',text);self.assertNotIn('Regression Equation',text)
        self.assertIsNotNone(entry['result']['rows'][0]['fit'])
