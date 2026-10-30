"""Actual contour/optimizer UI rendering and source-bound MPX workflow checks."""
import copy,unittest,math
from pathlib import Path
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter,format_entry
from statcraft.recipes import columns
from statcraft.mixture_exploration_chart import MixtureExplorationChart
from statcraft.graph_frame import GraphFrame
from statcraft.graph_options_pane import GraphOptionsPane
from statcraft.verification_fonts import load_verification_fonts
from statcraft.model import Column
from test_mpx import scratch


class MixtureExplorationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def fitted(self):
        p=Presenter();p.create_doe_plan(kind='simplex_lattice',factors=[dict(name=n,low=.1,high=.8) for n in ('Binder','Resin','Additive')],options={'degree':3},replicates=3)
        values=[]
        for row in range(p.worksheet.row_count):
            a,b,c=[p.worksheet.columns[i].values[row] for i in (4,5,6)]
            values.append(10*a+20*b+30*c+8*a*b-3*b*c+.05*math.sin(row))
        p.worksheet.columns.append(Column('Strength',values=values))
        return p,p.analyze_mixture(7,[4,5,6],model='quadratic')

    def test_contour_and_optimizer_follow_moved_renamed_columns_and_mpx(self):
        p,f=self.fitted();c=p.mixture_contour(f['recipe'],[2,0,1],options={'resolution':12});o=p.optimize_mixture(f['recipe'],goal='maximize')
        expected=o['result']['predicted_response'];old_range=c['result']['value_range']
        p.move_columns([5],'before_c1');p.rename_column(0,'Resin renamed')
        self.assertEqual(c['recipe']['parameters']['component_positions'],[2,0,1])
        self.assertAlmostEqual(p.rerun_result(o)['result']['predicted_response'],expected,places=8)
        self.assertEqual(p.rerun_result(c)['result']['value_range'],old_range)
        self.assertEqual(columns(o['recipe']),columns(f['recipe']))
        with scratch() as temp:
            target=Path(temp)/'explore.mpx';p.save(target);q=Presenter();q.load(target)
            for e in list(q.history):
                if e.get('recipe',{}).get('action') in ('mixture_contour','optimize_mixture'):
                    self.assertEqual(q.rerun_result(e)['result']['analysis'],e['result']['analysis'])
        self.assertIn('Response Optimization',format_entry(o));self.assertNotIn("'triangles'",format_entry(c))

    def test_deleted_sources_block_both_until_undo(self):
        p,f=self.fitted();entries=[p.mixture_contour(f['recipe'],options={'resolution':8}),p.optimize_mixture(f['recipe'])]
        p.delete_columns([5])
        for e in entries:
            with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(e)
        p.undo()
        for e in entries:self.assertEqual(p.rerun_result(e)['result']['analysis'],e['result']['analysis'])

    def test_renderer_has_colored_bands_real_isolines_and_effective_object_controls(self):
        p,f=self.fitted();e=p.mixture_contour(f['recipe'],options={'resolution':12})
        chart=MixtureExplorationChart(e);chart.resize(1100,800);first=chart.grab().toImage()
        self.assertIsNone(chart.error);self.assertTrue(chart.band_polygons);self.assertGreater(len(chart.band_colors),1)
        self.assertTrue(e['result']['contour_lines'][0]['segments'])
        self.assertEqual({item['target'] for item in chart.editable_objects()},{'p0:ref0','p0:axis','p0:grid'})
        chart.graph_styles={'p0:ref0':{'color':'#ff0000','line_width':5}};second=chart.grab().toImage()
        self.assertNotEqual(first,second);self.assertIsNone(chart.error);chart.deleteLater()

    def test_constant_surface_and_maximum_legend_levels_paint(self):
        p,f=self.fitted();e=p.mixture_contour(f['recipe'],options={'resolution':8,'levels':20})
        chart=MixtureExplorationChart(e);self.assertFalse(chart.grab().isNull());self.assertIsNone(chart.error);chart.deleteLater()
        r=copy.deepcopy(e);r['result']['levels']=[];r['result']['contour_lines']=[];r['result']['value_range']=[20.,20.]
        for point in r['result']['points']:point['fit']=20.
        chart=MixtureExplorationChart(r);self.assertFalse(chart.grab().isNull());self.assertIsNone(chart.error);chart.deleteLater()

    def test_optimizer_bounds_and_target_render_and_controls_do_not_offer_cartesian_axes(self):
        p,f=self.fitted();e=p.optimize_mixture(f['recipe'],goal='target',target=20.,bounds=[{'low':.2,'high':.6}]*3)
        self.assertAlmostEqual(sum(e['result']['components']),1.)
        self.assertLess(e['result']['target_error'],1e-5)
        chart=MixtureExplorationChart(e);frame=GraphFrame(chart,e);frame.resize(1100,650)
        self.assertFalse(frame.capture().isNull());self.assertIsNone(chart.error)
        pane=GraphOptionsPane();pane.load_entry(e)
        self.assertFalse(pane.controls['x_min'].isEnabled());self.assertFalse(pane.controls['x_label'].isEnabled())
        self.assertTrue(pane.controls['grid_enabled'].isEnabled());self.assertTrue(pane.object_button.isEnabled())
        self.assertTrue(any(item['target']=='p0:bars' for item in chart.editable_objects()))
        pane.deleteLater();frame.deleteLater()

    def test_forged_nested_recipe_rejected_and_bounds_are_snapshotted(self):
        p,f=self.fitted();e=p.optimize_mixture(f['recipe'],bounds=[{'low':.2,'high':.6}]*3)
        self.assertEqual(e['recipe']['parameters']['bounds'],[{'low':.2,'high':.6}]*3)
        for action in ('mixture_contour','optimize_mixture'):
            recipe=copy.deepcopy(e['recipe']);recipe['action']=action
            if action=='mixture_contour':recipe['parameters']={'model_recipe':copy.deepcopy(f['recipe']),'component_positions':[0,1,2],'hold_values':[],'options':None}
            recipe['parameters']['model_recipe']['action']='analyze_taguchi'
            with self.assertRaises(ValueError):columns(recipe)

    def test_four_component_slice_holds_and_source_identity_survive_column_moves(self):
        p=Presenter();p.create_doe_plan(kind='simplex_lattice',factors=[dict(name=n,low=0,high=1) for n in ('A','B','C','D')],options={'degree':3},replicates=2)
        values=[]
        for row in range(p.worksheet.row_count):
            a,b,c,d=[p.worksheet.columns[i].values[row] for i in (4,5,6,7)]
            values.append(10*a+20*b+30*c+40*d+8*a*b+15*c*d+.03*math.sin(row))
        p.worksheet.columns.append(Column('Yield',values=values));f=p.analyze_mixture(8,[4,5,6,7])
        e=p.mixture_contour(f['recipe'],[0,1,2],[{'position':3,'value':.2}],{'resolution':12})
        self.assertAlmostEqual(e['result']['display_total'],.8)
        for point in e['result']['points']:
            self.assertAlmostEqual(point['components'][3],.2);self.assertAlmostEqual(sum(point['components']),1.)
        old=e['result']['value_range'];p.move_columns([7],'before_c1');p.rename_column(0,'D held renamed')
        rerun=p.rerun_result(e)
        self.assertEqual(rerun['result']['value_range'],old)
        self.assertEqual(rerun['result']['hold_values'][0]['name'],'D held renamed')
        self.assertEqual(e['recipe']['parameters']['hold_values'],[{'position':3,'value':.2}])
