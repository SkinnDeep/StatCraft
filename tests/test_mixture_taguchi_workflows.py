"""Saved-source identity and UI output for mixture and static Taguchi workflows."""
import copy,math
from pathlib import Path
import unittest
from test_mpx import scratch
from statcraft.app import Presenter,format_entry
from statcraft.model import Column
from statcraft.recipes import columns
from statcraft.modern_charts import supported


def mixture():
    p=Presenter();p.create_doe_plan(kind='extreme_vertices',factors=[dict(name=n,low=.1,high=.8) for n in ('A','B','C')],replicates=3,name='Blend')
    values=[]
    for at in range(p.worksheet.row_count):
        a,b,c=[p.worksheet.columns[i].values[at] for i in (4,5,6)]
        values.append(10*a+20*b+30*c+.05*math.sin(at))
    p.worksheet.columns.append(Column('Strength',values=values));return p


class MixtureTaguchiWorkflowTests(unittest.TestCase):
    def test_mixture_prediction_and_bounds_follow_sources_through_mpx(self):
        p=mixture();entry=p.analyze_mixture(7,[4,5,6],model='linear')
        prediction=p.predict_mixture(entry['recipe'],[[.2,.3,.5]])
        expected=prediction['result']['rows'][0]['fit']
        self.assertEqual(entry['recipe']['parameters']['options']['bounds'],[dict(low=.1,high=.8)]*3)
        p.move_columns([5],'before_c1');p.rename_column(0,'Resin')
        self.assertAlmostEqual(p.rerun_result(prediction)['result']['rows'][0]['fit'],expected)
        with self.assertRaises(ValueError):p.predict_mixture(entry['recipe'],[[0,.5,.5]])
        with scratch() as tmp:
            path=Path(tmp)/'mixture.mpx';p.save(path);q=Presenter();q.load(path)
            for saved in q.history[:]:
                if saved.get('recipe',{}).get('action')=='predict_mixture':self.assertAlmostEqual(q.rerun_result(saved)['result']['rows'][0]['fit'],expected)

    def test_deleted_source_blocks_analysis_and_prediction_until_undo(self):
        p=mixture();entry=p.analyze_mixture(7,[4,5,6],model='linear');pred=p.predict_mixture(entry['recipe'],[[.2,.3,.5]])
        p.delete_columns([5])
        for e in (entry,pred):
            with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(e)
        p.undo()
        self.assertEqual(p.rerun_result(entry)['result']['count'],entry['result']['count'])
        self.assertAlmostEqual(p.rerun_result(pred)['result']['rows'][0]['fit'],pred['result']['rows'][0]['fit'])

    def test_suppressed_mixture_graphs_and_taguchi_options_retain(self):
        p=mixture();entry=p.analyze_mixture(7,[4,5,6],model='linear',options={'show_graphs':False})
        self.assertFalse(supported(entry));self.assertFalse(supported(p.rerun_result(entry)))
        self.assertIn('Coefficients',format_entry(entry))

    def test_taguchi_measurements_and_factors_remap_without_remapping_options(self):
        p=Presenter();p.worksheet.columns=[Column('A',values=[-1,-1,1,1]*2),Column('B',values=[-1,1,-1,1]*2),
            Column('Trial1',values=[10+i*.3 for i in range(8)]),Column('Trial2',values=[11+i*.4 for i in range(8)])]
        entry=p.analyze_taguchi([2,3],[0,1],options={'sn_type':'nominal','log_stdev':True,'fit_models':True,'show_graphs':False})
        expected=[r['sn'] for r in entry['result']['rows']]
        p.move_columns([2],'before_c1');p.rename_column(0,'Repeat one')
        self.assertEqual([r['sn'] for r in p.rerun_result(entry)['result']['rows']],expected)
        self.assertEqual(columns(entry['recipe']),[0,1,2,3]);self.assertFalse(supported(entry))
        self.assertTrue(entry['recipe']['parameters']['options']['log_stdev'])

    def test_forged_recipe_selectors_are_rejected(self):
        p=mixture();entry=p.analyze_mixture(7,[4,5,6],model='linear')
        for refs in ([4,4,6],[True,5,6],[-1,5,6]):
            recipe=copy.deepcopy(entry['recipe']);recipe['parameters']['component_indices']=refs
            with self.assertRaises(ValueError):columns(recipe)
