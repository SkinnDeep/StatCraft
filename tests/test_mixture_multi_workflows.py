"""Multi-response mixture persistence, interactive profiles and source identity."""
import copy,math,unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint,Qt
from PySide6.QtTest import QTest
from statcraft.app import Presenter,format_entry
from statcraft.model import Column
from statcraft.recipes import columns
from statcraft.mixture_multi_chart import MixtureMultiChart
from statcraft.graph_options_pane import GraphOptionsPane
from statcraft.verification_fonts import load_verification_fonts
from test_mpx import scratch


def study():
    p=Presenter();p.create_doe_plan(kind='simplex_lattice',factors=[dict(name=n,low=0,high=1) for n in ('Binder','Resin','Additive')],options={'degree':3},replicates=2)
    for label,position in [('Strength',4),('Flexibility',6)]:
        values=[]
        for row in range(p.worksheet.row_count):
            values.append(10+40*p.worksheet.columns[position].values[row]+5*p.worksheet.columns[5].values[row]+.03*math.sin(row))
        p.worksheet.columns.append(Column(label,values=values))
    models=[p.analyze_mixture(index,[4,5,6],model='linear') for index in (7,8)]
    responses=[dict(model_recipe=copy.deepcopy(e['recipe']),goal='maximize',lower=10.,target=50.,upper=None,weight=1.,importance=1.) for e in models]
    return p,responses


class MixtureMultiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def test_shared_search_and_selected_settings_follow_sources_through_mpx(self):
        p,s=study();e=p.optimize_mixture_multi(s);selected=p.evaluate_mixture_multi(s,[.3,.2,.5])
        expected=e['result']['composite_desirability'];value=selected['result']['composite_desirability']
        p.move_columns([8],'before_c1');p.rename_column(0,'Flexibility renamed');p.move_columns([6],'after_last')
        self.assertAlmostEqual(p.rerun_result(e)['result']['composite_desirability'],expected,places=8)
        self.assertAlmostEqual(p.rerun_result(selected)['result']['composite_desirability'],value,places=8)
        self.assertEqual(selected['recipe']['parameters']['components'],[.3,.2,.5])
        with scratch() as temp:
            path=Path(temp)/'multi.mpx';p.save(path);q=Presenter();q.load(path)
            for item in list(q.history):
                if item.get('recipe',{}).get('action') in ('optimize_mixture_multi','evaluate_mixture_multi'):
                    self.assertEqual(q.rerun_result(item)['result']['analysis'],item['result']['analysis'])
        self.assertIn('Composite desirability',format_entry(e))
        self.assertEqual(len(columns(e['recipe'])),5)

    def test_deleted_response_blocks_search_and_selected_recipe_until_undo(self):
        p,s=study();entries=[p.optimize_mixture_multi(s),p.evaluate_mixture_multi(s,[.3,.2,.5])]
        p.delete_columns([8])
        for item in entries:
            with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(item)
        p.undo()
        for item in entries:self.assertTrue(p.rerun_result(item)['result']['profiles'])

    def test_duplicate_responses_component_order_and_total_mismatches_rejected(self):
        p,s=study()
        with self.assertRaisesRegex(ValueError,'distinct'):p.optimize_mixture_multi([s[0],copy.deepcopy(s[0])])
        for key,value in [('component_indices',[6,5,4]),('total',100.)]:
            bad=copy.deepcopy(s);bad[1]['model_recipe']['parameters'][key]=value
            with self.assertRaisesRegex(ValueError,'same component'):p.optimize_mixture_multi(bad)

    def test_actual_profile_click_transfers_amount_and_emits_feasible_setting(self):
        p,s=study();e=p.optimize_mixture_multi(s);chart=MixtureMultiChart(e);chart.resize(1100,800)
        self.assertFalse(chart.grab().isNull());self.assertIsNone(chart.error)
        self.assertTrue(chart.profile_cells);rect,profile=chart.profile_cells[0];received=[];chart.settingSelected.connect(received.append)
        QTest.mouseClick(chart,Qt.MouseButton.LeftButton,pos=QPoint(round(rect.left()+rect.width()*.25),round(rect.center().y())))
        self.assertEqual(len(received),1);self.assertAlmostEqual(sum(received[0]),1.)
        original=e['result']['components']
        for i in range(3):
            if i not in (profile['position'],profile['balance_position']):self.assertEqual(received[0][i],original[i])
        r=p.evaluate_mixture_multi(s,received[0]);self.assertEqual(r['result']['analysis'],'mixture_multi_evaluation')
        chart.deleteLater()

    def test_profile_grid_annotation_controls_match_renderer_and_no_false_optimum(self):
        p,s=study();e=p.evaluate_mixture_multi(s,[.3,.2,.5]);chart=MixtureMultiChart(e)
        self.assertEqual(chart.panels[0]['setting_label'],'Selected Setting')
        pane=GraphOptionsPane();pane.load_entry(e)
        self.assertFalse(pane.controls['x_min'].isEnabled());self.assertFalse(pane.object_button.isEnabled())
        self.assertNotIn('Status: Converged',format_entry(e));pane.deleteLater();chart.deleteLater()

    def test_updated_response_data_is_refitted_for_selected_setting(self):
        p,s=study();before=p.evaluate_mixture_multi(s,[.3,.2,.5])
        for row,value in enumerate(p.worksheet.columns[7].values):p.set_cell(row,7,str(value+2.))
        after=p.rerun_result(before)
        self.assertAlmostEqual(after['result']['responses'][0]['prediction']['fit']-before['result']['responses'][0]['prediction']['fit'],2.,places=9)

    def test_fixed_last_component_uses_a_varying_balance_for_interactive_profiles(self):
        p,s=study();bounds=[{'low':0.,'high':1.},{'low':0.,'high':1.},{'low':.2,'high':.2}]
        e=p.evaluate_mixture_multi(s,[.3,.5,.2],bounds)
        self.assertTrue(e['result']['profiles'])
        self.assertTrue(all(profile['balance_position']==1 for profile in e['result']['profiles']))
        active=next(profile for profile in e['result']['profiles'] if profile['position']==0)
        self.assertGreater(active['high'],active['low'])
