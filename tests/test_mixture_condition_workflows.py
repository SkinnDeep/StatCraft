"""Fixed process context, saved recipes and readable diagnostic axes."""
import copy,unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter,format_entry
from statcraft.recipes import columns
from statcraft.modern_charts import ChartWidget
from statcraft.mixture_exploration_chart import MixtureExplorationChart
from statcraft.verification_fonts import load_verification_fonts
from test_mixture_process_workflows import study
from test_mpx import scratch


class MixtureConditionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def fit(self):
        p=study();return p,p.analyze_mixture_process(6,[0,1,2],[3],4,[5],model='quadratic',total=100.)

    def test_fixed_settings_follow_sources_and_survive_mpx(self):
        p,f=self.fit();c=p.mixture_process_contour(f['recipe'],[80.],[6.],'Morning',options={'resolution':12})
        o=p.optimize_mixture_process(f['recipe'],[80.],[6.],'Morning')
        expected=o['result']['predicted_response'];old=c['result']['value_range']
        p.move_columns([3],'before_c1');p.rename_column(0,'Temperature renamed');p.move_columns([6],'after_last')
        self.assertEqual(c['recipe']['parameters']['process_values'],[80.])
        self.assertEqual(p.rerun_result(c)['result']['value_range'],old)
        self.assertAlmostEqual(p.rerun_result(o)['result']['predicted_response'],expected,places=9)
        self.assertEqual(len(columns(c['recipe'])),7)
        with scratch() as temp:
            path=Path(temp)/'conditional.mpx';p.save(path);q=Presenter();q.load(path)
            for item in list(q.history):
                if item.get('recipe',{}).get('action') in ('mixture_process_contour','optimize_mixture_process'):
                    self.assertEqual(q.rerun_result(item)['result']['analysis'],item['result']['analysis'])

    def test_deleted_held_sources_block_contour_and_optimizer_until_undo(self):
        for source in (3,4,5):
            p,f=self.fit();entries=[p.mixture_process_contour(f['recipe'],[80.],[6.],'Morning',options={'resolution':8}),p.optimize_mixture_process(f['recipe'],[80.],[6.],'Morning')]
            p.delete_columns([source])
            for item in entries:
                with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(item)
            p.undo()
            for item in entries:self.assertTrue(p.rerun_result(item)['result']['conditioning'])

    def test_optimized_setting_matches_full_prediction_including_intervals(self):
        p,f=self.fit();o=p.optimize_mixture_process(f['recipe'],[80.],[6.],'Evening',options={'confidence':.9})
        q=p.predict_mixture_process(f['recipe'],[o['result']['components']],[[80.]],[[6.]],['Evening'],.9)
        for key in ('fit','standard_error','ci_low','ci_high','prediction_low','prediction_high'):
            self.assertAlmostEqual(o['result']['prediction'][key],q['result']['rows'][0][key],places=8)
        self.assertEqual(o['result']['conditioning']['process_values'],[80.])
        self.assertAlmostEqual(o['result']['conditioning']['process_coded_values'][0],.2)

    def test_actual_contour_and_optimizer_show_context_and_render(self):
        p,f=self.fit()
        for entry in (p.mixture_process_contour(f['recipe'],[80.],[6.],'Morning',options={'resolution':12}),p.optimize_mixture_process(f['recipe'],[80.],[6.],'Morning')):
            self.assertIn('Temperature',format_entry(entry));self.assertIn('Morning',format_entry(entry))
            chart=MixtureExplorationChart(entry);chart.resize(1100,750)
            self.assertFalse(chart.grab().isNull());self.assertIsNone(chart.error);chart.deleteLater()

    def test_missing_conditions_or_wrong_nested_model_do_not_record_partial_results(self):
        p,f=self.fit();count=len(p.history)
        with self.assertRaises(ValueError):p.optimize_mixture_process(f['recipe'],None,[6.],'Morning')
        self.assertEqual(len(p.history),count)
        bad=copy.deepcopy(f['recipe']);bad['action']='analyze_mixture'
        with self.assertRaises(ValueError):p.mixture_process_contour(bad,[80.],[6.],'Morning')

    def test_diagnostic_order_and_frequency_labels_are_readable_actual_render(self):
        p,f=self.fit();chart=ChartWidget(f);chart.resize(1100,850);order=[];frequency=[];original=chart._text
        def capture(painter,rect,text,*args,**kwargs):
            try:value=float(text)
            except (ValueError,TypeError):value=None
            if value is not None:
                if chart._panel_index==3 and rect.width()==84:order.append(value)
                if chart._panel_index==2 and rect.width()==62:frequency.append(value)
            return original(painter,rect,text,*args,**kwargs)
        chart._text=capture;chart._panel_index=0
        self.assertFalse(chart.grab().isNull());self.assertIsNone(chart.error)
        self.assertTrue(order);self.assertTrue(all(value>=0 and value==round(value) for value in order))
        self.assertTrue(frequency);self.assertTrue(all(value==round(value) for value in frequency));chart.deleteLater()
