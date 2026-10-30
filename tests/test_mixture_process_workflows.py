"""Saved-source and real residual plot contracts for mixture/process models."""
import copy,math,unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter,format_entry
from statcraft.model import Column
from statcraft.recipes import columns
from statcraft.modern_charts import ChartWidget,supported
from statcraft.brushing import brushable_rows
from statcraft.verification_fonts import load_verification_fonts
from test_mpx import scratch


def study():
    p=Presenter();p.new();data=[[] for unused in range(7)];row=0
    for a in range(4):
        for b in range(4-a):
            c=3-a-b
            for temperature in (50.,75.,100.):
                for block in ('Morning','Evening'):
                    for moisture in (4.,6.,8.):
                        aa,bb,cc=a/3,b/3,c/3;z=(temperature-75)/25;v=(moisture-6)/2
                        y=10*aa+20*bb+30*cc+(2*aa-3*bb+4*cc)*z+5*v+(7 if block=='Evening' else 0)+.04*math.sin(row)
                        for column,value in zip(data,[aa*100,bb*100,cc*100,temperature,block,moisture,y]):column.append(value)
                        row+=1
    p.worksheet.columns=[Column(name,'text' if i==4 else 'number',data[i]) for i,name in enumerate(('Binder','Resin','Additive','Temperature','Shift','Moisture','Strength'))]
    return p


class MixtureProcessWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def fit(self):
        p=study();p.worksheet.columns[5].values[5]=None
        return p,p.analyze_mixture_process(6,[0,1,2],[3],4,[5],model='linear',total=100.)

    def test_fit_and_predictions_follow_all_roles_after_moves_and_mpx_reopen(self):
        p,e=self.fit();pred=p.predict_mixture_process(e['recipe'],[[20.,30.,50.]],[[80.]],[[6.]],['Morning'])
        expected=pred['result']['rows'][0]['fit'];fits=e['result']['fitted']
        p.move_columns([3],'before_c1');p.rename_column(0,'Temperature renamed');p.move_columns([6],'after_last')
        self.assertAlmostEqual(p.rerun_result(pred)['result']['rows'][0]['fit'],expected,places=9)
        self.assertEqual(p.rerun_result(e)['result']['fitted'],fits)
        self.assertEqual(pred['recipe']['parameters']['process_rows'],[[80.]])
        self.assertEqual(len(columns(e['recipe'])),7)
        with scratch() as temp:
            path=Path(temp)/'process.mpx';p.save(path);q=Presenter();q.load(path)
            for saved in list(q.history):
                if saved.get('recipe',{}).get('action')=='predict_mixture_process':self.assertAlmostEqual(q.rerun_result(saved)['result']['rows'][0]['fit'],expected,places=9)
        self.assertIn('Temperature',format_entry(e));self.assertIn('Morning',format_entry(pred))

    def test_deleted_process_covariate_block_and_response_sources_block_until_undo(self):
        for index in (3,4,5,6):
            p,e=self.fit();pred=p.predict_mixture_process(e['recipe'],[[20.,30.,50.]],[[80.]],[[6.]],['Morning']);p.delete_columns([index])
            for saved in (e,pred):
                with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(saved)
            p.undo();self.assertEqual(p.rerun_result(e)['result']['count'],179)

    def test_snapshot_coding_bounds_and_generated_points_are_not_column_references(self):
        p,e=self.fit();options=e['recipe']['parameters']['options']
        self.assertEqual(options['process_coding'],[{'low':50.,'high':100.}])
        self.assertEqual(options['covariate_coding'],[{'low':4.,'high':8.}])
        self.assertEqual(options['bounds'],[{'low':0.,'high':100.}]*3)
        for key,values in [('process_indices',[True]),('covariate_indices',[3]),('component_indices',[0,0,2])]:
            bad=copy.deepcopy(e['recipe']);bad['parameters'][key]=values
            with self.assertRaises(ValueError):columns(bad)
        self.assertNotIn('mixture_fit',e['result'])

    def test_actual_four_residuals_keep_joint_complete_row_identity(self):
        p,e=self.fit();self.assertTrue(supported(e));chart=ChartWidget(e);chart.resize(1000,800)
        self.assertEqual(len(chart.panels),4);self.assertFalse(chart.grab().isNull());self.assertIsNone(chart.error)
        self.assertNotIn(6,brushable_rows(e));self.assertIn(7,brushable_rows(e))
        self.assertEqual(chart.panels[1]['row_indices'],[i+1 for i in e['result']['row_indices']]);chart.deleteLater()

    def test_no_graphs_and_wrong_nested_model_are_rejected_as_appropriate(self):
        p=study();e=p.analyze_mixture_process(6,[0,1,2],[3],4,[5],model='linear',total=100.,options={'show_graphs':False})
        self.assertFalse(supported(e));self.assertFalse(supported(p.rerun_result(e)))
        fake=copy.deepcopy(e['recipe']);fake['action']='analyze_mixture'
        with self.assertRaises(ValueError):p.predict_mixture_process(fake,[[20.,30.,50.]],[[80.]],[[6.]],['Morning'])

    def test_current_response_data_is_refitted_and_unknown_blocks_cannot_be_predicted(self):
        p,e=self.fit();pred=p.predict_mixture_process(e['recipe'],[[20.,30.,50.]],[[80.]],[[6.]],['Morning'])
        for row,value in enumerate(p.worksheet.columns[6].values):p.set_cell(row,6,str(value+2.))
        self.assertAlmostEqual(p.rerun_result(pred)['result']['rows'][0]['fit']-pred['result']['rows'][0]['fit'],2.,places=9)
        with self.assertRaises(ValueError):p.predict_mixture_process(e['recipe'],[[20.,30.,50.]],[[80.]],[[6.]],['Unknown shift'])
