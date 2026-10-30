"""Dynamic Taguchi persistence, live plots and source identity acceptance."""
import copy,math,unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter,format_entry
from statcraft.model import Column
from statcraft.recipes import columns
from statcraft.modern_charts import supported
from statcraft.dynamic_taguchi_chart import DynamicTaguchiWidget
from statcraft.verification_fonts import load_verification_fonts
from test_mpx import scratch


def dynamic_project():
    p=Presenter();a=[-1,-1,1,1]*2;b=[-1,1,-1,1]*2
    p.worksheet.columns=[Column('Material','text',['Steel' if v==1 else 'Brass' for v in a]),Column('Pressure',values=b)]
    signals=[0.,0.,1.,1.,2.,2.];noise=[-.15,.17,.08,-.11,.12,-.09]
    for j,x in enumerate(signals):
        p.worksheet.columns.append(Column('Trial '+str(j+1),values=[2+.05*r+(2+.5*a[r]+.3*b[r]+.04*math.sin(r))*x+noise[j]*(1+.1*a[r]+.05*b[r]) for r in range(8)]))
    return p,signals


class DynamicTaguchiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def test_moved_measurements_keep_signal_pairing_and_mpx_reruns(self):
        p,s=dynamic_project();entry=p.analyze_dynamic_taguchi(list(range(2,8)),s,[0,1])
        expected=[row['slope'] for row in entry['result']['rows']]
        p.move_columns([4],'before_c1');p.rename_column(0,'Low signal first trial')
        self.assertEqual(entry['recipe']['parameters']['signal_values'],s)
        rerun=p.rerun_result(entry);self.assertEqual([row['slope'] for row in rerun['result']['rows']],expected)
        with scratch() as temp:
            target=Path(temp)/'dynamic.mpx';p.save(target);q=Presenter();q.load(target)
            saved=next(e for e in q.history if e.get('recipe',{}).get('action')=='analyze_dynamic_taguchi')
            self.assertEqual([row['slope'] for row in q.rerun_result(saved)['result']['rows']],expected)
        self.assertIn('Slope',format_entry(entry));self.assertEqual(columns(entry['recipe']),list(range(8)))

    def test_delete_blocks_rerun_and_undo_restores_source(self):
        p,s=dynamic_project();e=p.analyze_dynamic_taguchi(list(range(2,8)),s,[0,1]);p.delete_columns([4])
        with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(e)
        p.undo();self.assertEqual(p.rerun_result(e)['result']['n_runs'],8)

    def test_forged_recipe_and_signal_constants_not_source_indices(self):
        p,s=dynamic_project();e=p.analyze_dynamic_taguchi(list(range(2,8)),s,[0,1])
        for refs in ([2,2],[True,3],[-1,4]):
            recipe=copy.deepcopy(e['recipe']);recipe['parameters']['response_indices']=refs
            with self.assertRaises(ValueError):columns(recipe)
        self.assertEqual(e['recipe']['parameters']['signal_values'],s)

    def test_actual_effects_and_scatter_panels_draw_editable_symbols(self):
        p,s=dynamic_project();e=p.analyze_dynamic_taguchi(list(range(2,8)),s,[0,1],options={'show_signal_plots':True})
        chart=DynamicTaguchiWidget(e);chart.resize(1100,chart.minimumHeight());self.assertEqual(chart.signal_panel_count,8)
        self.assertEqual(len(chart.panels),14);self.assertFalse(chart.grab().isNull());self.assertIsNone(chart.error)
        panel=next(panel for panel in chart.panels if panel.get('dynamic_signal'))
        self.assertEqual(panel['x'],s);self.assertEqual(panel['row_indices'],[1]*6)
        self.assertTrue(any(panel.get('metric')=='slope' for panel in chart.panels))
        chart.deleteLater()

    def test_no_graphs_preserves_report_and_native_reference_options(self):
        p,s=dynamic_project();e=p.analyze_dynamic_taguchi(list(range(2,8)),s,[0,1],options={'show_graphs':False,'reference_method':'fixed','reference_signal':0.,'reference_response':2.,'adjusted':True})
        self.assertFalse(supported(e));self.assertIn('Signal',format_entry(e))
        self.assertEqual(p.rerun_result(e)['result']['options']['reference_response'],2.)

    def test_signal_plot_bound_is_explicit_and_brushing_uses_only_drawn_rows(self):
        from statcraft.brushing import brushable_rows,validate_brushed_rows
        p,s=dynamic_project()
        for column in p.worksheet.columns:column.values*=4
        e=p.analyze_dynamic_taguchi(list(range(2,8)),s,[0,1],options={'show_signal_plots':True})
        chart=DynamicTaguchiWidget(e);self.assertEqual(chart.signal_panel_count,24)
        self.assertIn('first 24 of 32',chart.note)
        self.assertEqual(brushable_rows(e),list(range(1,25)))
        with self.assertRaises(ValueError):validate_brushed_rows(e,p.worksheet,[25])
        effects=p.analyze_dynamic_taguchi(list(range(2,8)),s,[0,1])
        self.assertEqual(brushable_rows(effects),[])
        chart.deleteLater()

    def test_signal_plots_can_be_requested_without_main_effects(self):
        p,s=dynamic_project();e=p.analyze_dynamic_taguchi(list(range(2,8)),s,[0,1],options={'show_graphs':False,'show_signal_plots':True})
        self.assertTrue(supported(e));chart=DynamicTaguchiWidget(e)
        self.assertEqual(len(chart.panels),8);self.assertTrue(all(panel.get('dynamic_signal') for panel in chart.panels))
        self.assertFalse(chart.grab().isNull());self.assertIsNone(chart.error);chart.deleteLater()
